// SYNTEZATOR Z SEKWENCEREM: trzy głosy — bas (D8), melodia (D9), perkusja (D10) — i 16 kroków na OLED-zie.
// Dźwięk liczy przerwanie Timer1, 20 000 razy na sekundę: każdy głos to licznik fazy (DDS), a jego
// najwyższy bit to fala prostokątna na pinie. Sekwencer też chodzi w przerwaniu, więc rytm się nie
// rozjeżdża, gdy rysuje się ekran. Przyciski do masy: ← D2, → D3, ↑ D4, ↓ D5, nuta wł./wył. D6,
// ścieżka D7, start/stop D12. Potencjometry: A0 tempo, A1 długość nut. Dioda L (D13) miga na każdą ćwierćnutę.
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

Adafruit_SSD1306 oled(128, 64, &Wire, -1);

const byte LEFT = 2, RIGHT = 3, UP = 4, DOWN = 5, TOGGLE = 6, TRACK = 7, PLAY = 12;
const long RATE = 20000;  // próbek na sekundę
const byte STEPS = 16, TRACKS = 3, BASS = 0, LEAD = 1, DRUMS = 2;
const byte KICK = 1, SNARE = 2, HAT = 3;  // perkusja: stopa, werbel, hi-hat
const char *const TRACK_NAMES[] = {"BAS", "MELODIA", "PERKUSJA"};
const char *const DRUM_NAMES[] = {"-", "BD", "SD", "HH"};  // bass drum, snare drum, hi-hat

// nuty jako numery MIDI (60 = C4, 69 = A4 = 440 Hz), 0 = pauza: a-moll, F-dur, G-dur
byte song[TRACKS][STEPS] = {
  {45, 0, 57, 45, 0, 45, 57, 0, 41, 0, 53, 41, 43, 0, 55, 43},
  {69, 72, 76, 81, 76, 72, 69, 72, 65, 69, 72, 77, 67, 71, 74, 79},
  {KICK, 0, HAT, 0, SNARE, 0, HAT, 0, KICK, 0, HAT, KICK, SNARE, 0, HAT, HAT},
};
byte spare[TRACKS] = {45, 69, KICK};  // co wstawić w pustą kratkę: ostatnia zdjęta nuta

// o ile rośnie licznik fazy co próbkę dla nut MIDI 120–131 (f · 65536 / RATE); niższa oktawa: połowa
const uint16_t TOP_OCTAVE[12] PROGMEM = {27433, 29065, 30793, 32624, 34564, 36619,
                                         38797, 41104, 43548, 46137, 48881, 51787};
uint16_t increment(byte note) { return pgm_read_word(&TOP_OCTAVE[note % 12]) >> (10 - note / 12); }

// --- to, co dzieli przerwanie z pętlą
volatile uint16_t stepLength = 2500;  // próbek na krok (szesnastkę)
volatile uint16_t gateLength = 1800;  // ile próbek brzmi nuta
volatile byte step = STEPS - 1;       // grany krok
volatile bool playing = true;

// --- stan głosów: tylko przerwanie
uint16_t phase[2], rise[2], left[2];  // bas i melodia: faza, przyrost, ile próbek jeszcze
uint16_t drumPhase, drumRise, drumLeft, noise = 1;
byte drum, noiseBit;
uint16_t sample, beat;

void startStep() {
  step = (step + 1) % STEPS;
  for (byte v = BASS; v <= LEAD; v++) {
    byte note = song[v][step];
    rise[v] = note ? increment(note) : 0;
    left[v] = note ? gateLength : 0;
  }
  drum = song[DRUMS][step];
  drumLeft = drum == KICK ? 2400 : drum == SNARE ? 1600 : drum == HAT ? 500 : 0;
  drumRise = increment(50);  // stopa zaczyna od ~150 Hz i opada
  beat = step % 4 == 0 ? stepLength / 2 : 0;
}

ISR(TIMER1_COMPA_vect) {
  if (playing && ++sample >= stepLength) {
    sample = 0;
    startStep();
  }
  byte out = 0;
  for (byte v = BASS; v <= LEAD; v++)
    if (left[v]) {
      left[v]--;
      phase[v] += rise[v];
      if (phase[v] & 0x8000) out |= bit(v);  // D8 = PB0, D9 = PB1
    }
  if (drumLeft) {
    drumLeft--;
    if (drum == KICK) {
      if ((drumLeft & 127) == 0) drumRise -= drumRise >> 4;  // co 6,4 ms o 6 % niżej: do ~40 Hz
      drumPhase += drumRise;
      if (drumPhase & 0x8000) out |= bit(2);
    } else {  // szum: rejestr przesuwny ze sprzężeniem (LFSR), losowe bity; werbel co drugą próbkę, niżej
      if (drum == HAT || (drumLeft & 1)) {
        noiseBit = noise & 1;
        noise >>= 1;
        if (noiseBit) noise ^= 0xB400;
      }
      if (noiseBit) out |= bit(2);
    }
  }
  if (beat) {
    beat--;
    out |= bit(5);  // D13 = PB5
  }
  PORTB = (PORTB & ~(bit(0) | bit(1) | bit(2) | bit(5))) | out;
}

// --- pętla: przyciski, potencjometry, ekran
byte track = LEAD, cursor = 0;
byte held[7];  // stan przycisków z poprzedniego obiegu
bool changed = true;  // ekran do narysowania od nowa
const byte KEYS[7] = {LEFT, RIGHT, UP, DOWN, TOGGLE, TRACK, PLAY};

bool pressed(byte k) {  // właśnie wciśnięty (zbocze), nie trzymany
  bool now = digitalRead(KEYS[k]) == LOW, was = held[k];
  held[k] = now;
  if (now && !was) changed = true;
  return now && !was;
}

void edit(int by) {
  byte &cell = song[track][cursor];
  if (track == DRUMS) cell = (cell + 4 + by) % 4;
  else cell = constrain((cell ? cell : spare[track]) + by, 24, 96);
}

void printNote(byte note) {
  const char *const NAMES[] = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "H"};
  oled.print(NAMES[note % 12]);
  oled.print(note / 12 - 1);
}

void draw(int bpm) {
  oled.clearDisplay();
  oled.setCursor(0, 0);
  oled.print(bpm);
  oled.print(playing ? " BPM" : " stop");
  oled.setCursor(50, 0);
  oled.print(TRACK_NAMES[track]);
  oled.setCursor(104, 0);
  byte cell = song[track][cursor];
  if (track == DRUMS) oled.print(DRUM_NAMES[cell]);
  else if (cell) printNote(cell);
  else oled.print("-");
  oled.fillRect(step * 8, 9, 7, 2, SSD1306_WHITE);  // grany krok
  for (byte t = 0; t < TRACKS; t++) {
    int top = 12 + t * 17;
    for (byte s = 0; s < STEPS; s++) {
      byte cell = song[t][s];
      int low = t == BASS ? 33 : 57;  // słupek: półton to pół piksela, od A1 (bas) i od A3 (melodia)
      int h = t == DRUMS ? (cell == KICK ? 14 : cell == SNARE ? 9 : cell == HAT ? 4 : 0)
                         : cell ? constrain((cell - low) / 2 + 2, 1, 15) : 0;
      if (h) oled.fillRect(s * 8, top + 15 - h, 7, h, SSD1306_WHITE);
      else oled.drawPixel(s * 8 + 3, top + 15, SSD1306_WHITE);
    }
    if (t == track) oled.fillRect(cursor * 8, top, 7, 16, SSD1306_INVERSE);
  }
  oled.display();
}

void setup() {
  for (byte k = 0; k < 7; k++) pinMode(KEYS[k], INPUT_PULLUP);
  DDRB |= bit(0) | bit(1) | bit(2) | bit(5);  // D8, D9, D10, D13: wyjścia
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  Wire.setClock(400000);
  oled.setTextColor(SSD1306_WHITE);
  cli();
  TCCR1A = 0;
  TCCR1B = bit(WGM12) | bit(CS10);  // tryb CTC, bez dzielnika: 16 MHz
  OCR1A = F_CPU / RATE - 1;         // przerwanie co 800 taktów
  TIMSK1 = bit(OCIE1A);
  sei();
}

byte shown = 255;
int shownBpm;

void loop() {
  int bpm = map(analogRead(A0), 0, 1023, 60, 200);
  int gate = map(analogRead(A1), 0, 1023, 10, 100);  // % kroku
  uint16_t length = RATE * 60 / bpm / 4;
  noInterrupts();
  stepLength = length;
  gateLength = (uint32_t)length * gate / 100;
  interrupts();
  if (pressed(0)) cursor = (cursor + STEPS - 1) % STEPS;
  if (pressed(1)) cursor = (cursor + 1) % STEPS;
  if (pressed(2)) edit(+1);
  if (pressed(3)) edit(-1);
  if (pressed(4)) {
    byte &cell = song[track][cursor];
    if (cell) spare[track] = cell;
    cell = cell ? 0 : spare[track];
  }
  if (pressed(5)) track = (track + 1) % TRACKS;
  if (pressed(6)) playing = !playing;
  if (changed || step != shown || abs(bpm - shownBpm) > 1) {
    shown = step;
    shownBpm = bpm;
    changed = false;
    draw(bpm);
  }
}
