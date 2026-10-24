// SYNTEZATOR WAVETABLE na Raspberry Pi Pico: dwa oscylatory z tablicami fal (po 16 kształtów, płynnie
// przechodzących jeden w drugi), unison do 5 głosów z rozstrojeniem, sub i szum, filtr rezonansowy (SVF),
// dwie obwiednie ADSR, LFO, arpeggiator, przester i echo; 6 głosów naraz. Dźwięk liczy rdzeń 1,
// 25 000 próbek na sekundę, i wysyła je po SPI1 do przetwornika MCP4822; rdzeń 0 skanuje klawiaturę
// i rysuje ekran TFT 320×240.
// Klawisze (do masy, każdy na swoim pinie): C … C2 na GP0–GP9, GP12, GP14, GP15; oktawa niżej GP16, wyżej GP22.
// Siedem przycisków nawigacji na jednym pinie analogowym (GP28): drabinka rezystorów, każdy daje inne napięcie
// (układ „drabinka”). Potencjometry: odcięcie GP26, rezonans GP27. DAC: SCK GP10, SDI GP11, CS GP13.
// TFT: SCK GP18, MOSI GP19, CS GP17, DC GP20, RESET GP21 (podświetlenie wprost z 3V3).
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
#include <hardware/irq.h>
#include <hardware/spi.h>
#include <hardware/sync.h>
#include <hardware/timer.h>

const int PIANO_PINS[13] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 14, 15};  // C, Cis, … H, C2
const int OCT_DOWN = 16, OCT_UP = 22;
const int POT_CUTOFF = 26, POT_RES = 27, LADDER_PIN = 28;
// drabinka: rezystor od 3V3 do pinu i kolejne w dół; przycisk k zwiera do masy k-ty węzeł
const float LADDER_TOP = 4700, LADDER[7] = {0, 680, 1000, 1200, 1800, 3300, 6800};

const int RATE = 25000;  // próbek na sekundę: przerwanie co 40 µs
const int BLOCK = 32;    // próbek liczonych naraz; obwiednie i LFO zmieniają się co blok (781 razy na s)
const int VOICES = 6, MAX_UNISON = 5;
const int FRAMES = 16, MIPS = 6, SIZE = 256;  // kształtów w tablicy, poziomów pasma, próbek w okresie
const int ECHO_MAX = 10000;                   // 0,4 s echa

// ============================================================ parametry

enum {
  A_TABLE, A_POS, A_UNISON, A_DETUNE, A_OCT, A_SEMI, A_LEVEL,
  B_TABLE, B_POS, B_UNISON, B_DETUNE, B_OCT, B_SEMI, B_LEVEL, SUB, NOISE,
  F_TYPE, F_CUTOFF, F_RES, F_ENV, F_KEY, F_DRIVE,
  E1_A, E1_D, E1_S, E1_R, E2_A, E2_D, E2_S, E2_R,
  L_SHAPE, L_RATE, L_POS, L_CUTOFF, L_PITCH,
  G_PRESET, G_VOLUME, G_ARP, G_TEMPO, G_OCTAVES, D_TIME, D_FEEDBACK, D_MIX,
  PARAMS
};
enum Unit { PCT, SIGNED, COUNT, TABLE, FTYPE, SHAPE, CENTS, TIME, HZ, LFOHZ, ONOFF, PRESET, BPM, ECHO };
struct Param {
  const char *name;
  int16_t lo, hi;
  uint8_t unit;
};
const Param PARAM[PARAMS] = {
  {"Tablica", 0, 4, TABLE}, {"Pozycja", 0, 100, PCT}, {"Unison", 1, MAX_UNISON, COUNT},
  {"Rozstroj", 0, 100, CENTS}, {"Oktawa", -2, 2, SIGNED}, {"Poltony", -12, 12, SIGNED}, {"Glosnosc", 0, 100, PCT},
  {"Tablica", 0, 4, TABLE}, {"Pozycja", 0, 100, PCT}, {"Unison", 1, MAX_UNISON, COUNT},
  {"Rozstroj", 0, 100, CENTS}, {"Oktawa", -2, 2, SIGNED}, {"Poltony", -12, 12, SIGNED}, {"Glosnosc", 0, 100, PCT},
  {"Sub", 0, 100, PCT}, {"Szum", 0, 100, PCT},
  {"Typ", 0, 2, FTYPE}, {"Odciecie", 0, 100, HZ}, {"Rezonans", 0, 100, PCT}, {"Obwiednia", -100, 100, PCT},
  {"Sledzenie", 0, 100, PCT}, {"Przester", 0, 100, PCT},
  {"Atak 1", 0, 100, TIME}, {"Opad 1", 0, 100, TIME}, {"Poziom 1", 0, 100, PCT}, {"Wybrzm. 1", 0, 100, TIME},
  {"Atak 2", 0, 100, TIME}, {"Opad 2", 0, 100, TIME}, {"Poziom 2", 0, 100, PCT}, {"Wybrzm. 2", 0, 100, TIME},
  {"Ksztalt", 0, 4, SHAPE}, {"Szybkosc", 0, 100, LFOHZ}, {"> Pozycja", -100, 100, PCT},
  {"> Odciecie", -100, 100, PCT}, {"> Wysokosc", 0, 100, CENTS},
  {"Preset", 0, 4, PRESET}, {"Glosnosc", 0, 100, PCT}, {"Arpeggio", 0, 1, ONOFF}, {"Tempo", 60, 200, BPM},
  {"Oktawy arp", 1, 3, COUNT}, {"Echo czas", 0, 100, ECHO}, {"Echo powt.", 0, 90, PCT}, {"Echo mix", 0, 100, PCT},
};
const char *const TABLES[] = {"Analog", "PWM", "Wokal", "Sweep", "Organy"};
const char *const FILTERS[] = {"LP", "BP", "HP"};
const char *const SHAPES[] = {"sinus", "trojkat", "pila", "prostok.", "losowy"};
const char *const PRESETS[] = {"Supersaw", "Wokal Pad", "Bas PWM", "Sweep Lead", "Organy"};
const int16_t PRESET_VALUES[5][PARAMS] = {
  // A: tablica poz uni rozstr okt pol glos | B: ... | sub szum | filtr: typ odc rez obw sled przest
  // | env1 ADSR | env2 ADSR | LFO: ksztalt szyb >poz >odc >wys | preset glos arp tempo okt | echo
  {0, 66, 5, 30, 0, 0, 80, 0, 100, 1, 0, -1, 0, 25, 0, 0, 0, 58, 25, 35, 30, 15,
   12, 50, 80, 45, 5, 55, 25, 45, 0, 40, 0, 0, 0, 0, 75, 0, 120, 2, 62, 35, 25},
  {2, 0, 3, 15, 0, 0, 80, 2, 50, 1, 0, 0, 7, 40, 0, 4, 0, 78, 15, 0, 0, 0,
   55, 60, 90, 65, 0, 50, 100, 60, 1, 30, 60, 0, 0, 1, 80, 0, 100, 1, 72, 45, 35},
  {1, 30, 2, 8, -1, 0, 90, 1, 80, 1, 0, -2, 0, 45, 60, 0, 0, 30, 55, 60, 50, 40,
   0, 45, 60, 25, 0, 42, 0, 25, 3, 55, 40, 0, 0, 2, 75, 0, 116, 1, 0, 0, 0},
  {3, 20, 3, 12, 0, 0, 85, 0, 66, 1, 0, 12, 0, 20, 0, 0, 0, 70, 40, 20, 40, 25,
   8, 50, 85, 40, 0, 50, 50, 40, 2, 45, 70, 0, 15, 3, 75, 0, 120, 2, 55, 50, 30},
  {4, 50, 1, 0, 0, 0, 90, 4, 100, 1, 0, 1, 0, 30, 20, 0, 0, 85, 0, 0, 0, 10,
   5, 0, 100, 30, 0, 0, 100, 30, 0, 62, 0, 0, 8, 4, 70, 0, 120, 1, 0, 0, 0},
};
struct Page {
  const char *name;
  int8_t params[10];
};
const Page PAGES[] = {
  {"OSC A", {A_TABLE, A_POS, A_UNISON, A_DETUNE, A_OCT, A_SEMI, A_LEVEL, -1}},
  {"OSC B", {B_TABLE, B_POS, B_UNISON, B_DETUNE, B_OCT, B_SEMI, B_LEVEL, SUB, NOISE, -1}},
  {"FILTR", {F_TYPE, F_CUTOFF, F_RES, F_ENV, F_KEY, F_DRIVE, -1}},
  {"ENV", {E1_A, E1_D, E1_S, E1_R, E2_A, E2_D, E2_S, E2_R, -1}},
  {"LFO", {L_SHAPE, L_RATE, L_POS, L_CUTOFF, L_PITCH, -1}},
  {"GLOBAL", {G_PRESET, G_VOLUME, G_ARP, G_TEMPO, G_OCTAVES, D_TIME, D_FEEDBACK, D_MIX, -1}},
};
const int PAGE_COUNT = sizeof PAGES / sizeof PAGES[0];

// głosy (rdzeń 1)
enum Stage : uint8_t { IDLE, ATTACK, DECAY, RELEASE };
struct Envelope {
  Stage stage = IDLE;
  float level = 0;
};
struct Voice {
  uint8_t note;
  bool gate;
  uint32_t age;
  Envelope amp, filter;
  uint32_t phase[2][MAX_UNISON], sub;
  int32_t ic1, ic2;  // filtr: stan jego dwóch „kondensatorów"
  int32_t gain;      // głośność w ostatniej próbce (Q14)
};
Voice voice[VOICES];

// jeden oscylator głosu na ten blok: z której tablicy, poziomu i dwóch sąsiednich kształtów czyta, przyrosty
struct Osc {
  const int16_t *a, *b;  // kształt pod pozycją i następny
  int32_t between;       // jak daleko między nimi (0–255)
  uint32_t step[MAX_UNISON];
  int count;
  int32_t gain;
};

struct Event {
  uint8_t note, on;
};

volatile int16_t P[PARAMS];        // wartości: pisze rdzeń 0, czyta rdzeń 1
volatile uint32_t paramsVersion;  // rośnie przy każdej zmianie: rdzeń 1 przelicza wtedy współczynniki

// co znaczą: czasy obwiedni (ms), odcięcie (oktawy ponad 20 Hz), LFO (Hz), echo (próbki)
float envMs(int v) { return powf(10000.0f, v / 100.0f); }            // 1 ms – 10 s
float cutoffOct(int v) { return v * 9.13f / 100; }                    // 20 Hz – 11 kHz
float cutoffHz(float oct) { return 20 * exp2f(oct); }
float lfoHz(int v) { return 0.05f * powf(400.0f, v / 100.0f); }      // 0,05 – 20 Hz
int echoSamples(int v) { return 500 + (ECHO_MAX - 501) * v / 100; }  // 20 – 400 ms

// ============================================================ tablice fal

// próbka sinusa (do składania harmonicznych, suboscylatora i LFO): 1024 w okresie
int16_t SINE[1024];
// dwa oscylatory: 16 kształtów × 6 poziomów pasma × 256 próbek. Poziom m ma najwyżej 128 >> m harmonicznych:
// wyższa nuta bierze uboższy poziom, żeby żadna harmoniczna nie przekroczyła połowy częstotliwości
// próbkowania (inaczej odbiłaby się w dół jako fałszywy ton — aliasing).
int16_t wave[2][FRAMES][MIPS][SIZE];
volatile bool loading[2];   // tablica się przelicza: oscylator milczy
uint32_t mipAbove[MIPS];  // przyrost fazy, od którego poziom m ma już za dużo harmonicznych

float gauss(float x) { return expf(-x * x); }

// amplituda h-tej harmonicznej kształtu f (0–15) tablicy
float harmonic(int table, int f, int h) {
  float t = f / 15.0f;
  switch (table) {
    case 0: {  // Analog: sinus → trójkąt → piła → prostokąt
      float tri = h % 2 ? ((h / 2) % 2 ? -1.0f : 1.0f) * 0.81f / (h * h) : 0;
      float saw = (h % 2 ? 1.0f : -1.0f) * 0.64f / h, sq = h % 2 ? 0.81f / h : 0;
      float s[4] = {h == 1 ? 1.0f : 0, tri, saw, sq};
      float x = t * 3;
      int i = min(2, (int)x);
      return s[i] + (s[i + 1] - s[i]) * (x - i);
    }
    case 1: {  // PWM: prostokąt coraz węższy, od 50 % do 5 %
      float d = 0.5f - 0.45f * t;
      return sinf(PI * h * d) / h;
    }
    case 2: {  // Wokal: piła przez dwa formanty, które wędrują a → e → i → o → u
      const float F1[5] = {6.6f, 4.8f, 2.5f, 5.2f, 2.7f}, F2[5] = {9.9f, 16.7f, 20.8f, 7.6f, 7.9f};
      float x = t * 4;
      int i = min(3, (int)x);
      float u = x - i, f1 = F1[i] + (F1[i + 1] - F1[i]) * u, f2 = F2[i] + (F2[i + 1] - F2[i]) * u;
      return (gauss((h - f1) / (0.15f * f1 + 1.2f)) + 0.6f * gauss((h - f2) / (0.12f * f2 + 1.5f)) + 0.04f) / sqrtf(h);
    }
    case 3: {  // Sweep: okno harmonicznych przesuwa się w górę
      float c = 1 + t * 40, w = 1.5f + t * 6;
      return gauss((h - c) / w) + (h == 1 ? 0.3f : 0);
    }
    default: {  // Organy: kolejne „rejestry" (8', 4', 2 2/3', 2', …) dochodzą jeden po drugim
      const int BARS[9] = {1, 2, 3, 4, 6, 8, 10, 12, 16};
      for (int j = 0; j < 9; j++)
        if (BARS[j] == h) return constrain((f + 1) * 9 / 16.0f - j, 0.0f, 1.0f) / (1 + j * 0.25f);
      return 0;
    }
  }
}

// tablica ``table`` do oscylatora ``o``: każdy kształt złożony z harmonicznych (synteza addytywna)
void buildTable(int o, int table) {
  static int32_t sum[SIZE];
  static float amp[129];
  loading[o] = true;
  delay(3);  // rdzeń 1 kończy blok, który mógł jeszcze czytać tę tablicę
  for (int f = 0; f < FRAMES; f++) {
    for (int h = 1; h <= 128; h++) amp[h] = harmonic(table, f, h);
    float scale = 0;
    for (int m = 0; m < MIPS; m++) {
      memset(sum, 0, sizeof sum);
      for (int h = 1; h < (128 >> m); h++) {
        int a = (int)(amp[h] * 4096);
        if (!a) continue;
        for (int i = 0, k = 0; i < SIZE; i++, k += 4 * h) sum[i] += a * SINE[k & 1023];
      }
      if (m == 0) {  // wszystkie poziomy tak samo głośno: skala z najbogatszego
        int peak = 1;
        for (int i = 0; i < SIZE; i++) peak = max(peak, (int)abs(sum[i]));
        scale = 30000.0f / peak;
      }
      for (int i = 0; i < SIZE; i++) wave[o][f][m][i] = (int16_t)constrain(sum[i] * scale, -32767.0f, 32767.0f);
    }
  }
  loading[o] = false;
}

// przyrost fazy (32 bity na okres) dla nuty MIDI w 1/16 półtonu: z tablicy najwyższej oktawy, przesunięty
uint32_t TOP_OCTAVE[192];  // nuty 120–132
uint32_t increment(int sixteenths) {
  int k = constrain(sixteenths, 0, 132 * 16 - 1) - 120 * 16, shift = 0;
  while (k < 0) k += 192, shift++;
  return TOP_OCTAVE[k] >> shift;
}

float TAN[300];  // filtr: tg(π·f/RATE) dla odcięcia co 1/32 oktawy ponad 20 Hz

// ============================================================ głosy (rdzeń 1)


// współczynniki, przeliczane, gdy zmieni się parametr
struct Coefs {
  float attack[2], decay[2], sustain[2], release[2];
  float lfoStep, k;
  int echo;
  int32_t feedback, mix, volume, drive;  // Q15 (32768 = 1); przester: mnożnik z sumy głosów do Q15, Q8
} co;
uint32_t seenVersion = ~0u;
float lfoPhase, lfoValue, lfoHeld;
int32_t lfoQ;  // lfoValue w Q15, dla rachunków na liczbach całkowitych
uint32_t rnd = 12345;
uint32_t random32() { return rnd = rnd * 1664525 + 1013904223; }

void prepare() {
  const float block = (float)BLOCK / RATE;
  for (int e = 0; e < 2; e++) {
    int base = e ? E2_A : E1_A;
    co.attack[e] = block * 1000 / envMs(P[base]);
    co.decay[e] = expf(-4.6f * block * 1000 / envMs(P[base + 1]));
    co.sustain[e] = P[base + 2] / 100.0f;
    co.release[e] = expf(-4.6f * block * 1000 / envMs(P[base + 3]));
  }
  co.lfoStep = lfoHz(P[L_RATE]) * block;
  co.k = 2 - 1.97f * P[F_RES] / 100.0f;
  co.echo = echoSamples(P[D_TIME]);
  co.feedback = P[D_FEEDBACK] * 32768 / 100;
  co.mix = P[D_MIX] * 32768 / 100;
  co.volume = P[G_VOLUME] * 32768 / 100;
  co.drive = (1 + P[F_DRIVE] * 0.07f) * 32768 * 256 / 60000;
}

void advance(Envelope &e, int which, bool gate) {
  switch (e.stage) {
    case ATTACK:
      e.level += co.attack[which];
      if (e.level >= 1) e.level = 1, e.stage = DECAY;
      break;
    case DECAY:
      e.level = co.sustain[which] + (e.level - co.sustain[which]) * co.decay[which];
      break;
    case RELEASE:
      e.level *= co.release[which];
      if (e.level < 0.0005f) e.level = 0, e.stage = IDLE;
      break;
    default:
      break;
  }
  if (!gate && e.stage != IDLE) e.stage = RELEASE;
}

void advanceLfo() {
  lfoPhase += co.lfoStep;
  if (lfoPhase >= 1) {
    lfoPhase -= 1;
    lfoHeld = (int32_t)random32() / 2147483648.0f;
  }
  float p = lfoPhase;
  switch (P[L_SHAPE]) {
    case 0: lfoValue = SINE[(int)(p * 1024) & 1023] / 32767.0f; break;
    case 1: lfoValue = p < 0.5f ? 4 * p - 1 : 3 - 4 * p; break;
    case 2: lfoValue = 2 * p - 1; break;
    case 3: lfoValue = p < 0.5f ? 1 : -1; break;
    default: lfoValue = lfoHeld;
  }
  lfoQ = lfoValue * 32767;
}

const int32_t UNISON_GAIN[MAX_UNISON + 1] = {0, 256, 181, 148, 128, 114};  // 256/√n: unison nie głośniejszy


bool setUp(Osc &o, Voice &v, int which, int vibrato) {  // vibrato: w 1/16 półtonu
  int base = which ? B_TABLE : A_TABLE;
  if (loading[which] || !P[base + 6]) return false;
  int32_t pos = P[base + 1] * 32768 / 100 + (which ? 0 : lfoQ * P[L_POS] / 100);  // Q15
  pos = constrain(pos, 0, 32768) * (FRAMES - 1) >> 7;                             // kształt w 1/256
  int frame = min(FRAMES - 2, (int)(pos >> 8));
  o.between = pos - frame * 256;
  int semis = (v.note + P[base + 4] * 12 + P[base + 5]) * 16 + vibrato;
  o.count = P[base + 2];
  for (int k = 0; k < o.count; k++) {  // unison: rozstrojone symetrycznie wokół nuty, w centach
    int cents = o.count > 1 ? P[base + 3] * (2 * k - (o.count - 1)) / (o.count - 1) : 0;
    o.step[k] = increment(semis + cents * 16 / 100);
  }
  int m = 0;
  while (m < MIPS - 1 && o.step[o.count / 2] > mipAbove[m]) m++;
  o.a = wave[which][frame][m];
  o.b = wave[which][frame + 1][m];
  o.gain = P[base + 6] * UNISON_GAIN[o.count] / 100;
  return true;
}

// próbka okresu w punkcie ``phase``: między dwiema próbkami i między dwoma kształtami, liniowo
inline int32_t sampleAt(const Osc &o, uint32_t phase) {
  int i = phase >> 24, j = (i + 1) & (SIZE - 1), fr = (phase >> 10) & 0x3fff;
  int32_t a = o.a[i] + (((o.a[j] - o.a[i]) * fr) >> 14);
  if (!o.between) return a;
  int32_t b = o.b[i] + (((o.b[j] - o.b[i]) * fr) >> 14);
  return a + (((b - a) * o.between) >> 8);
}

void render(Voice &v, int32_t *mix) {
  bool gate = v.gate;
  advance(v.amp, 0, gate);
  advance(v.filter, 1, gate);
  int vibrato = lfoQ * P[L_PITCH] * 16 / 100 >> 15;  // P[L_PITCH] centów, w 1/16 półtonu
  Osc osc[2];
  bool on[2] = {setUp(osc[0], v, 0, vibrato), setUp(osc[1], v, 1, vibrato)};
  uint32_t subStep = increment((v.note + P[A_OCT] * 12 - 12) * 16);
  int32_t sub = P[SUB] * 256 / 100, noise = P[NOISE] * 128 / 100;
  // filtr (SVF z całkowaniem trapezami, jak w symulatorze obwodów: stabilny dla każdego odcięcia)
  float oct = cutoffOct(P[F_CUTOFF]) + v.filter.level * P[F_ENV] * 0.06f + lfoValue * P[L_CUTOFF] * 0.03f +
              (v.note - 60) / 12.0f * P[F_KEY] / 100.0f;
  float g = TAN[constrain((int)(oct * 32), 0, 299)];
  float a1 = 1 / (1 + g * (g + co.k)), a2 = g * a1, a3 = g * a2;
  int32_t A1 = a1 * 8192, A2 = a2 * 8192, A3 = a3 * 8192, K = co.k * 8192;
  int type = P[F_TYPE];
  int32_t target = v.amp.level * 16384, gainStep = (target - v.gain) / BLOCK;
  for (int i = 0; i < BLOCK; i++) {
    int32_t x = 0;
    for (int w = 0; w < 2; w++) {
      if (!on[w]) continue;
      int32_t s = 0;
      for (int k = 0; k < osc[w].count; k++) s += sampleAt(osc[w], v.phase[w][k] += osc[w].step[k]);
      x += (s * osc[w].gain) >> 10;
    }
    if (sub) x += (SINE[(v.sub += subStep) >> 22] * sub) >> 9;
    if (noise) x += ((int32_t)random32() >> 16) * noise >> 8;
    int32_t v3 = x - v.ic2;
    int32_t v1 = ((A1 * v.ic1) >> 13) + ((A2 * v3) >> 13);
    int32_t v2 = v.ic2 + ((A2 * v.ic1) >> 13) + ((A3 * v3) >> 13);
    v.ic1 = constrain(2 * v1 - v.ic1, -65535, 65535);
    v.ic2 = constrain(2 * v2 - v.ic2, -65535, 65535);
    int32_t y = type == 0 ? v2 : type == 1 ? v1 : x - ((K * v1) >> 13) - v2;
    y = constrain(y, -65535, 65535);
    mix[i] += (y * (v.gain >> 1)) >> 13;
    v.gain += gainStep;
  }
  v.gain = target;
}

// ============================================================ nuty: klawisze, arpeggio, demo (rdzeń 1)

Event events[32];
volatile uint32_t eventsIn, eventsOut;  // pisze rdzeń 0, czyta rdzeń 1
volatile bool demo = true;              // gra samo, dopóki ktoś nie naciśnie klawisza

void sendNote(int note, bool on) {
  events[eventsIn % 32] = {(uint8_t)note, (uint8_t)on};
  __dmb();
  eventsIn++;
}

uint32_t clock_ = 0;
Voice &pick(int note) {  // głos dla nuty: ten, który ją gra, wolny, a jak nie ma — najstarszy
  for (Voice &v : voice)
    if (v.note == note && v.amp.stage != IDLE) return v;
  for (Voice &v : voice)
    if (v.amp.stage == IDLE) return v;
  Voice *oldest = &voice[0];
  for (Voice &v : voice)
    if (v.age < oldest->age) oldest = &v;
  return *oldest;
}

void noteOn(int note) {
  Voice &v = pick(note);
  if (v.amp.stage == IDLE) {
    for (auto &row : v.phase)
      for (uint32_t &p : row) p = random32();
    v.ic1 = v.ic2 = 0;
  }
  v.note = note;
  v.gate = true;
  v.age = ++clock_;
  v.amp.stage = v.filter.stage = ATTACK;
}

void noteOff(int note) {
  for (Voice &v : voice)
    if (v.note == note) v.gate = false;
}

// trzymane klawisze (do arpeggia), rosnąco
uint8_t held[16];
int heldCount;
void hold(int note, bool on) {
  int i = 0;
  while (i < heldCount && held[i] < note) i++;
  bool there = i < heldCount && held[i] == note;
  if (on && !there && heldCount < 16) {
    memmove(held + i + 1, held + i, heldCount - i);
    held[i] = note, heldCount++;
  } else if (!on && there) {
    memmove(held + i, held + i + 1, heldCount - i - 1);
    heldCount--;
  }
}

// demo: a-moll, F-dur, C-dur, G-dur, po takcie każdy, przez arpeggio
const uint8_t DEMO[4][3] = {{57, 60, 64}, {53, 57, 60}, {60, 64, 67}, {55, 59, 62}};
uint32_t arpClock, arpStep, demoChord = ~0u;
int arpNote = -1;

void sequence() {
  bool arp = P[G_ARP] || demo;
  if (demo) {
    uint32_t chord = arpStep / 16 % 4;
    if (chord != demoChord) {
      demoChord = chord;
      heldCount = 3;
      memcpy(held, DEMO[chord], 3);
    }
  }
  if (!arp) {
    if (arpNote >= 0) noteOff(arpNote), arpNote = -1;
    return;
  }
  uint32_t step = RATE * 60 / P[G_TEMPO] / 4;  // szesnastka
  arpClock += BLOCK;
  if (arpNote >= 0 && arpClock >= step / 2) noteOff(arpNote), arpNote = -1;
  if (arpClock < step) return;
  arpClock -= step;
  if (!heldCount) return;
  int span = heldCount * P[G_OCTAVES], k = arpStep++ % span;
  arpNote = held[k % heldCount] + 12 * (k / heldCount);
  noteOn(arpNote);
}

void takeEvents() {
  while (eventsOut != eventsIn) {
    Event e = events[eventsOut % 32];
    eventsOut++;
    if (demo) {  // pierwszy klawisz kończy demo
      demo = false;
      heldCount = 0;
      if (arpNote >= 0) noteOff(arpNote), arpNote = -1;
    }
    hold(e.note, e.on);
    if (!P[G_ARP]) e.on ? noteOn(e.note) : noteOff(e.note);
  }
}

// ============================================================ wyjście: przerwanie co 40 µs (rdzeń 1)

uint16_t ring[512];  // próbki gotowe do wysłania (20 ms)
volatile uint32_t ringIn, ringOut;
int alarmNum;
uint32_t nextSample;
uint16_t lastWord = 0x3000 | 2048;

void onSample() {  // następna próbka do DAC: słowo 0011 + 12 bitów = kanał A, wzmocnienie 1×, włączony
  timer_hw->intr = 1u << alarmNum;
  nextSample += 1000000 / RATE;
  timer_hw->alarm[alarmNum] = nextSample;
  if (ringOut != ringIn) lastWord = ring[ringOut++ % 512];
  spi_get_hw(spi1)->dr = lastWord;
}

int16_t echoLine[ECHO_MAX];
int echoAt;
int32_t echoLow;
volatile int16_t scope[256];  // ostatnie próbki: oscyloskop na ekranie
volatile bool scopeWanted;
volatile uint32_t busyUs;  // ile z ostatniej sekundy rdzeń 1 liczył (µs): wskaźnik CPU

void renderBlock() {
  static int32_t mix[BLOCK];
  if (seenVersion != paramsVersion) seenVersion = paramsVersion, prepare();
  takeEvents();
  sequence();
  advanceLfo();
  memset(mix, 0, sizeof mix);
  for (Voice &v : voice)
    if (v.amp.stage != IDLE) render(v, mix);
  static int scopeAt = 256;
  if (scopeWanted && scopeAt >= 256) scopeAt = 0, scopeWanted = false;
  for (int i = 0; i < BLOCK; i++) {  // (na liczbach całkowitych, Q15: 32768 = 1 — RP2040 nie ma FPU)
    int32_t x = constrain((mix[i] * co.drive) >> 8, -32768, 32768);  // przester: miękkie obcięcie
    x = (3 * x - ((((x * x) >> 15) * x) >> 15)) >> 1;               // 1,5x − 0,5x³
    int32_t echo = echoLine[(echoAt + ECHO_MAX - co.echo) % ECHO_MAX];
    echoLow += ((echo - echoLow) * 11469) >> 15;  // echo coraz ciemniejsze, jak z taśmy
    echoLine[echoAt] = constrain(x + ((echoLow * co.feedback) >> 15), -32767, 32767);
    if (++echoAt == ECHO_MAX) echoAt = 0;
    int32_t out = constrain(((x + ((echo * co.mix) >> 15)) * (co.volume >> 1)) >> 14, -32767, 32767);
    int code = 2048 + ((out * 2000) >> 15);
    ring[ringIn % 512] = 0x3000 | code;
    ringIn++;
    if (scopeAt < 256) scope[scopeAt++] = code - 2048;
  }
}

volatile bool ready;
void setup1() {
  while (!ready) delay(1);
  spi_init(spi1, 20000000);
  spi_set_format(spi1, 16, SPI_CPOL_0, SPI_CPHA_0, SPI_MSB_FIRST);
  gpio_set_function(10, GPIO_FUNC_SPI);
  gpio_set_function(11, GPIO_FUNC_SPI);
  gpio_set_function(13, GPIO_FUNC_SPI);
  alarmNum = hardware_alarm_claim_unused(true);
  irq_set_exclusive_handler(TIMER_IRQ_0 + alarmNum, onSample);
  irq_set_enabled(TIMER_IRQ_0 + alarmNum, true);
  timer_hw->inte |= 1u << alarmNum;
  nextSample = timer_hw->timerawl + 1000;
  timer_hw->alarm[alarmNum] = nextSample;
}

void loop1() {
  static uint32_t second = micros(), busy;
  while (ringIn - ringOut > 512 - BLOCK) __wfi();  // bufor pełny: śpij do następnej próbki
  uint32_t start = micros();
  renderBlock();
  busy += micros() - start;
  if (micros() - second >= 1000000) busyUs = busy, busy = 0, second += 1000000;
}

// ============================================================ ekran i klawisze (rdzeń 0)

Adafruit_ILI9341 tft(17, 20, 21);
const int W = 320, PANEL_Y = 32, PANEL_H = 116, PARAMS_Y = 152, FOOT_Y = 222;
GFXcanvas8 panel(W, PANEL_H);  // obraz strony rysowany w pamięci, wysyłany naraz (bez migania)
GFXcanvas8 wave_(150, 16);    // oscyloskop w stopce
enum : uint8_t { BG, GRID, DIM, ACCENT, WARM, WHITE, GREEN, FAINT };
uint16_t PALETTE[8];
int page, row;
bool dirtyPanel = true, dirtyParams = true, dirtyHeader = true;

void blit(GFXcanvas8 &c, int x, int y) {  // wiersz po wierszu, z palety na kolory
  static uint16_t line[W];
  int w = c.width();
  const uint8_t *px = c.getBuffer();
  for (int r = 0; r < c.height(); r++) {
    for (int i = 0; i < w; i++) line[i] = PALETTE[px[r * w + i]];
    tft.drawRGBBitmap(x, y + r, line, w, 1);
  }
}

void valueText(int p, char *s) {
  int v = P[p];
  switch (PARAM[p].unit) {
    case PCT: sprintf(s, "%d%%", v); break;
    case SIGNED: sprintf(s, "%+d", v); break;
    case COUNT: sprintf(s, "%d", v); break;
    case TABLE: strcpy(s, TABLES[v]); break;
    case FTYPE: strcpy(s, FILTERS[v]); break;
    case SHAPE: strcpy(s, SHAPES[v]); break;
    case CENTS: sprintf(s, "%d ct", v); break;
    case TIME: {
      float ms = envMs(v);
      if (ms < 1000) sprintf(s, "%d ms", (int)ms);
      else sprintf(s, "%d.%d s", (int)(ms / 1000), (int)(ms / 100) % 10);
      break;
    }
    case HZ: {
      int hz = cutoffHz(cutoffOct(v));
      if (hz < 1000) sprintf(s, "%d Hz", hz);
      else sprintf(s, "%d.%d kHz", hz / 1000, hz / 100 % 10);
      break;
    }
    case LFOHZ: {
      int c = lfoHz(v) * 100;
      sprintf(s, "%d.%02d Hz", c / 100, c % 100);
      break;
    }
    case ONOFF: strcpy(s, v ? "wl." : "wyl."); break;
    case PRESET: strcpy(s, PRESETS[v]); break;
    case BPM: sprintf(s, "%d BPM", v); break;
    case ECHO: sprintf(s, "%d ms", echoSamples(v) * 1000 / RATE); break;
  }
}

int pageSize(int pg) {
  int n = 0;
  while (n < 10 && PAGES[pg].params[n] >= 0) n++;
  return n;
}

void drawHeader() {
  tft.fillRect(0, 0, W, 30, PALETTE[GRID]);
  tft.setTextSize(2);
  tft.setTextColor(PALETTE[WHITE]);
  tft.setCursor(6, 2);
  tft.print(PRESETS[P[G_PRESET]]);
  tft.setTextSize(1);
  tft.setTextColor(PALETTE[demo ? WARM : DIM]);
  tft.setCursor(196, 6);
  tft.print(demo ? "DEMO" : P[G_ARP] ? "ARP" : "    ");
  for (int i = 0; i < PAGE_COUNT; i++) {
    int x = i * (W / PAGE_COUNT);
    bool on = i == page;
    if (on) tft.fillRect(x, 19, W / PAGE_COUNT - 2, 11, PALETTE[ACCENT]);
    tft.setTextColor(PALETTE[on ? BG : FAINT]);
    tft.setCursor(x + 6, 21);
    tft.print(PAGES[i].name);
  }
}

void drawParams() {
  int n = pageSize(page);
  char s[24];
  for (int k = 0; k < 10; k++) {
    int x = (k % 2) * 160, y = PARAMS_Y + (k / 2) * 14;
    bool on = k == row;
    tft.fillRect(x, y, 158, 13, PALETTE[on ? ACCENT : BG]);
    if (k >= n) continue;
    int p = PAGES[page].params[k];
    tft.setTextColor(PALETTE[on ? BG : FAINT]);
    tft.setCursor(x + 4, y + 3);
    tft.print(PARAM[p].name);
    valueText(p, s);
    tft.setTextColor(PALETTE[on ? BG : WHITE]);
    tft.setCursor(x + 154 - 6 * strlen(s), y + 3);
    tft.print(s);
  }
}

// --- obrazy stron

void drawWavetable(int o) {  // 16 kształtów jeden za drugim, ten pod pozycją jasny
  const int base = o ? B_TABLE : A_TABLE;
  float pos = P[base + 1] / 100.0f * (FRAMES - 1);
  // od najdalszego: każdy bliższy zasłania to, co za nim, pod swoją linią
  auto frameAt = [&](float f, uint8_t color, bool solid) {
    int f0 = min(FRAMES - 2, (int)f);
    float u = f - f0;
    int ox = 6 + (int)(f * 4), oy = PANEL_H - 26 - (int)(f * 4);
    int lastX = -1, lastY = 0;
    for (int i = 0; i <= 128; i++) {
      int s = (i * 2) & 255;
      float y = wave[o][f0][0][s] * (1 - u) + wave[o][f0 + 1][0][s] * u;
      int px = ox + i * 5 / 4, py = oy - (int)(y * 22 / 32767);
      if (solid) panel.drawFastVLine(px, py + 1, oy + 24 - py, BG);
      if (lastX >= 0) panel.drawLine(lastX, lastY, px, py, color);
      lastX = px, lastY = py;
    }
  };
  for (int f = FRAMES - 1; f >= 0; f--) frameAt(f, DIM, true);
  frameAt(pos, ACCENT, false);
  // po prawej: jeden okres, duży
  panel.drawRect(236, 8, 80, 100, GRID);
  panel.drawFastHLine(236, 58, 80, GRID);
  int f0 = min(FRAMES - 2, (int)pos);
  float u = pos - f0;
  for (int i = 1; i < 80; i++) {
    auto at = [&](int k) {
      int s = k * SIZE / 80;
      return 58 - (int)((wave[o][f0][0][s] * (1 - u) + wave[o][f0 + 1][0][s] * u) * 46 / 32767);
    };
    panel.drawLine(236 + i - 1, at(i - 1), 236 + i, at(i), ACCENT);
  }
  panel.setTextColor(FAINT);
  panel.setCursor(8, 6);
  panel.print(TABLES[P[base]]);
  panel.print("  ksztalt ");
  panel.print(pos, 1);
}

int freqX(float hz) { return 30 + (int)(log2f(hz / 20) / log2f(12500.0f / 20) * 280); }
int dbY(float db) { return 10 + (int)((18 - db) * 90 / 60); }

void drawFilter() {  // charakterystyka filtru (z jego wzoru analogowego) i filtru RC na płytce
  for (int db = 12; db >= -42; db -= 6) panel.drawFastHLine(30, dbY(db), 280, db ? GRID : DIM);
  for (float hz : {50.0f, 100.0f, 500.0f, 1000.0f, 5000.0f, 10000.0f}) panel.drawFastVLine(freqX(hz), 10, 90, GRID);
  panel.setTextColor(FAINT);
  panel.setCursor(0, dbY(0) - 3);
  panel.print("0dB");
  panel.setCursor(freqX(100) - 6, 104), panel.print("100");
  panel.setCursor(freqX(1000) - 6, 104), panel.print("1k");
  panel.setCursor(freqX(10000) - 9, 104), panel.print("10k");
  float fc = cutoffHz(cutoffOct(P[F_CUTOFF])), k = 2 - 1.97f * P[F_RES] / 100.0f;
  const float rc = 2200 * 10e-9f, load = 2200.0f / 10000;  // R_1, C_1, głośnik 10 kΩ
  int lastY = 0, lastRc = 0;
  for (int x = 30; x < 310; x++) {
    float hz = 20 * powf(12500.0f / 20, (x - 30) / 280.0f), w = hz / fc;
    float re = 1 - w * w, im = k * w, den = sqrtf(re * re + im * im);
    float mag = P[F_TYPE] == 0 ? 1 / den : P[F_TYPE] == 1 ? k * w / den : w * w / den;
    int y = constrain(dbY(20 * log10f(mag + 1e-6f)), 8, 104);
    float wr = 2 * PI * hz * rc;
    int yr = constrain(dbY(-10 * log10f((1 + load) * (1 + load) + wr * wr)), 8, 104);
    if (x > 30) panel.drawLine(x - 1, lastY, x, y, ACCENT), panel.drawLine(x - 1, lastRc, x, yr, (x / 3) % 2 ? WARM : BG);
    lastY = y, lastRc = yr;
  }
  panel.drawFastVLine(freqX(fc), 10, 90, WHITE);
  panel.setTextColor(WARM);
  panel.setCursor(200, 2);
  panel.print("- - filtr RC (R1, C1)");
}

void drawEnvelope(int e, int x0, uint8_t color) {
  int base = e ? E2_A : E1_A;
  float a = sqrtf(envMs(P[base])), d = sqrtf(envMs(P[base + 1])), r = sqrtf(envMs(P[base + 3]));
  float s = P[base + 2] / 100.0f, hold = 25, total = a + d + hold + r;
  int w = 140, h = 80, y0 = 98;
  auto X = [&](float t) { return x0 + (int)(t / total * w); };
  int ys = y0 - (int)(s * h);
  panel.drawFastHLine(x0, y0, w, GRID);
  panel.drawLine(X(0), y0, X(a), y0 - h, color);
  panel.drawLine(X(a), y0 - h, X(a + d), ys, color);
  panel.drawLine(X(a + d), ys, X(a + d + hold), ys, color);
  panel.drawLine(X(a + d + hold), ys, X(total), y0, color);
  panel.setTextColor(color);
  panel.setCursor(x0, 4);
  panel.print(e ? "ENV 2 > filtr" : "ENV 1 > glosnosc");
}

float lfoAt(float p) {
  switch (P[L_SHAPE]) {
    case 0: return sinf(2 * PI * p);
    case 1: return p < 0.5f ? 4 * p - 1 : 3 - 4 * p;
    case 2: return 2 * p - 1;
    case 3: return p < 0.5f ? 1 : -1;
    default: return ((int)(p * 7) * 37 % 11) / 5.0f - 1;
  }
}

void drawLfo() {
  panel.drawFastHLine(10, 58, 300, GRID);
  int lastY = 0;
  for (int x = 10; x < 310; x++) {
    int y = 58 - (int)(lfoAt(fmodf((x - 10) / 150.0f, 1)) * 42);
    if (x > 10) panel.drawLine(x - 1, lastY, x, y, ACCENT);
    lastY = y;
  }
  int x = 10 + (int)(lfoPhase * 150);  // gdzie jest teraz (rdzeń 1 je przesuwa)
  panel.fillCircle(x, 58 - (int)(lfoValue * 42), 4, WHITE);
  panel.setTextColor(FAINT);
  panel.setCursor(10, 2);
  panel.print("LFO: ");
  panel.print(SHAPES[P[L_SHAPE]]);
}

void drawGlobal() {  // echo: kolejne powtórzenia, coraz cichsze
  panel.drawFastHLine(10, 100, 300, GRID);
  float t = echoSamples(P[D_TIME]) / (float)RATE, level = P[D_MIX] / 100.0f;
  panel.fillRect(10, 20, 4, 80, WHITE);
  for (int k = 1; k < 20 && level > 0.01f; k++, level *= P[D_FEEDBACK] / 100.0f) {
    int x = 10 + (int)(k * t / 1.6f * 300);
    if (x > 306) break;
    panel.fillRect(x, 100 - (int)(level * 80), 4, (int)(level * 80), ACCENT);
  }
  panel.setTextColor(FAINT);
  panel.setCursor(10, 2);
  panel.print("echo  ");
  panel.print(echoSamples(P[D_TIME]) * 1000 / RATE);
  panel.print(" ms   arpeggio ");
  panel.print(P[G_ARP] ? "wl." : "wyl.");
}

void drawPanel() {
  panel.fillScreen(BG);
  switch (page) {
    case 0: drawWavetable(0); break;
    case 1: drawWavetable(1); break;
    case 2: drawFilter(); break;
    case 3: drawEnvelope(0, 10, GREEN), drawEnvelope(1, 170, WARM); break;
    case 4: drawLfo(); break;
    default: drawGlobal();
  }
  blit(panel, 0, PANEL_Y);
}

int octave = 4;
const char *const NOTE_NAMES[12] = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "H"};

void drawFooter() {
  tft.fillRect(0, FOOT_Y, 165, 18, PALETTE[BG]);
  tft.setTextColor(PALETTE[FAINT]);
  tft.setCursor(4, FOOT_Y + 5);
  tft.print("oktawa ");
  tft.print(octave);
  tft.print("   CPU ");
  tft.print(busyUs / 10000);
  tft.print("%");
}

void drawScope() {
  scopeWanted = true;
  wave_.fillScreen(BG);
  wave_.drawFastHLine(0, 8, 150, GRID);
  int start = 0;  // od przejścia przez zero w górę: przebieg stoi w miejscu
  for (int i = 1; i < 100; i++)
    if (scope[i - 1] < 0 && scope[i] >= 0) {
      start = i;
      break;
    }
  for (int i = 1; i < 150 && start + i < 256; i++)
    wave_.drawLine(i - 1, 8 - scope[start + i - 1] / 256, i, 8 - scope[start + i] / 256, GREEN);
  blit(wave_, 168, FOOT_Y + 2);
}

// --- zmiany

void changed(int p) {
  paramsVersion++;
  if (p == A_TABLE || p == B_TABLE) buildTable(p == B_TABLE, P[p]);
  if (p == G_PRESET) {
    int was[2] = {P[A_TABLE], P[B_TABLE]};
    for (int i = 0; i < PARAMS; i++)
      if (i != G_PRESET) P[i] = PRESET_VALUES[P[G_PRESET]][i];
    paramsVersion++;
    if (P[A_TABLE] != was[0]) buildTable(0, P[A_TABLE]);
    if (P[B_TABLE] != was[1]) buildTable(1, P[B_TABLE]);
    dirtyHeader = true;
  }
  if (p == G_ARP) dirtyHeader = true;
  dirtyParams = dirtyPanel = true;
}

void set(int p, int v) {
  v = constrain(v, PARAM[p].lo, PARAM[p].hi);
  if (P[p] == v) return;
  P[p] = v;
  changed(p);
}

// przyciski nawigacji: który (jeśli któryś) z napięcia na GP28 — najbliższy z oczekiwanych progów
// (dwa naraz dałyby napięcie niższego: przy nawigacji to nie przeszkadza). Wciśnięty: naciśnięcie, a −/+ trzymane
// powtarzają (coraz szybciej). 6: arpeggio.
int ladderCode[7];
bool navWas[7];
uint32_t navSince[7], navRepeat[7];

int ladderButton() {
  int v = analogRead(LADDER_PIN), best = -1, gap = 4095 - v;  // (nic: pełne 3,3 V)
  for (int k = 0; k < 7; k++)
    if (abs(v - ladderCode[k]) < gap) gap = abs(v - ladderCode[k]), best = k;
  return best;
}

void readButtons() {
  uint32_t now = millis();
  int pressedNow = ladderButton();
  for (int b = 0; b < 7; b++) {
    bool down = b == pressedNow;
    bool press = down && !navWas[b];
    if (press) navSince[b] = now, navRepeat[b] = now + 350;
    navWas[b] = down;
    bool repeat = down && b >= 4 && now >= navRepeat[b];
    if (repeat) navRepeat[b] = now + (now - navSince[b] > 1500 ? 25 : 70);
    if (!press && !repeat) continue;
    int n = pageSize(page);
    switch (b) {
      case 0: page = (page + PAGE_COUNT - 1) % PAGE_COUNT, row = min(row, pageSize(page) - 1); break;
      case 1: page = (page + 1) % PAGE_COUNT, row = min(row, pageSize(page) - 1); break;
      case 2: row = (row + n - 1) % n; break;
      case 3: row = (row + 1) % n; break;
      case 6: set(G_ARP, !P[G_ARP]); break;
      default: {
        int p = PAGES[page].params[row];
        set(p, P[p] + (b == 4 ? -1 : 1));
      }
    }
    if (b < 2) dirtyHeader = dirtyPanel = true;
    dirtyParams = true;
  }
}

// klawisze: każdy na swoim pinie, więc ile ich naraz — tyle nut (w matrycy trzy wciśnięte „w L” zapalają
// czwarty — układ „duch”)
bool keyDown[15];
int keyNote[13];

void key(int n, bool down) {
  if (n < 13) {  // C … C2: nuty
    if (down) keyNote[n] = 12 * (octave + 1) + n;
    sendNote(keyNote[n], down);
  } else if (down && n == 13) octave = max(1, octave - 1), drawFooter();
  else if (down && n == 14) octave = min(7, octave + 1), drawFooter();
  if (down && demo) dirtyHeader = true;
}

void scanKeys() {
  for (int n = 0; n < 15; n++) {
    bool down = digitalRead(n < 13 ? PIANO_PINS[n] : n == 13 ? OCT_DOWN : OCT_UP) == LOW;
    if (down != keyDown[n]) keyDown[n] = down, key(n, down);
  }
}

// potencjometry: biorą parametr dopiero, gdy się nimi poruszy (inaczej nadpisałyby preset)
const int POTS[2] = {POT_CUTOFF, POT_RES}, POT_PARAM[2] = {F_CUTOFF, F_RES};
int potWas[2];
void readPots() {
  for (int k = 0; k < 2; k++) {
    int v = analogRead(POTS[k]);
    if (abs(v - potWas[k]) < 40) continue;
    potWas[k] = v;
    set(POT_PARAM[k], v * 100 / 4095);
  }
}

void setup() {
  for (int i = 0; i < 1024; i++) SINE[i] = (int16_t)(sinf(i * 2 * PI / 1024) * 32767);
  for (int k = 0; k < 192; k++) TOP_OCTAVE[k] = (uint32_t)(440 * exp2f((120 + k / 16.0f - 69) / 12) * 4294967296.0 / RATE);
  for (int m = 0; m < MIPS; m++) mipAbove[m] = (uint32_t)(12500.0 / (128 >> m) * 4294967296.0 / RATE);
  for (int i = 0; i < 300; i++) TAN[i] = tanf(PI * min(cutoffHz(i / 32.0f), 0.45f * RATE) / RATE);
  for (int i = 0; i < PARAMS; i++) P[i] = PRESET_VALUES[0][i];
  tft.begin();
  tft.setRotation(1);
  tft.fillScreen(ILI9341_BLACK);
  PALETTE[BG] = tft.color565(10, 12, 18), PALETTE[GRID] = tft.color565(36, 40, 54);
  PALETTE[DIM] = tft.color565(60, 90, 110), PALETTE[ACCENT] = tft.color565(64, 224, 255);
  PALETTE[WARM] = tft.color565(255, 160, 60), PALETTE[WHITE] = tft.color565(240, 240, 240);
  PALETTE[GREEN] = tft.color565(110, 230, 120), PALETTE[FAINT] = tft.color565(150, 156, 170);
  tft.fillScreen(PALETTE[BG]);
  tft.setTextColor(PALETTE[WHITE]);
  tft.setCursor(100, 110);
  tft.print("liczenie tablic fal...");
  buildTable(0, P[A_TABLE]);
  buildTable(1, P[B_TABLE]);
  for (int n = 0; n < 13; n++) pinMode(PIANO_PINS[n], INPUT_PULLUP);
  pinMode(OCT_DOWN, INPUT_PULLUP);
  pinMode(OCT_UP, INPUT_PULLUP);
  float r = 0;
  for (int k = 0; k < 7; k++) r += LADDER[k], ladderCode[k] = 4095 * r / (LADDER_TOP + r);
  analogReadResolution(12);
  delay(5);  // (napięcia z potencjometrów: po pierwszym odczycie obwodu)
  for (int k = 0; k < 2; k++) potWas[k] = analogRead(POTS[k]);
  for (int n = 0; n < 15; n++) keyDown[n] = digitalRead(n < 13 ? PIANO_PINS[n] : n == 13 ? OCT_DOWN : OCT_UP) == LOW;
  panel.setTextWrap(false);
  tft.fillScreen(PALETTE[BG]);
  Serial.begin(115200);
  ready = true;
}

void loop() {
  static uint32_t lastScope, lastFooter, lastLfo;
  scanKeys();
  readButtons();
  uint32_t ms = millis();
  static uint32_t lastPots;
  if (ms - lastPots >= 30) lastPots = ms, readPots();
  if (dirtyHeader) dirtyHeader = false, drawHeader();
  if (dirtyParams) dirtyParams = false, drawParams();
  uint32_t now = millis();
  if (page == 4 && now - lastLfo > 80) lastLfo = now, dirtyPanel = true;  // LFO: kropka się rusza
  if (dirtyPanel) dirtyPanel = false, drawPanel();
  if (now - lastScope > 90) lastScope = now, drawScope();
  if (now - lastFooter > 1000) lastFooter = now, drawFooter();
  delay(1);
}
