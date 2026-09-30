// FRAKTAL MANDELBROTA na Raspberry Pi Pico i kolorowym TFT 320×240. Dla każdego piksela c liczymy
// z → z² + c od z = 0: jeśli z ucieka do nieskończoności, piksel dostaje kolor tym jaśniejszy,
// im szybciej uciekł; jeśli nie — jest czarny (należy do zbioru). Potem obraz przybliża się do
// „Doliny Konika Morskiego”, coraz głębiej. Liczymy na liczbach całkowitych (stały przecinek, 1 = 2^24):
// RP2040 nie ma sprzętowego mnożenia liczb zmiennoprzecinkowych.
// TFT: SCK GP18, MOSI GP19, CS GP17, DC GP20, RESET GP21, podświetlenie GP22. Przycisk na GP2: od nowa.
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>

Adafruit_ILI9341 tft(17, 20, 21);
const int W = 320, H = 240, MAX_ITER = 64, RESET = 2;
const int FRAC = 24;  // bitów po przecinku
typedef int64_t fixed;
const fixed ONE = (fixed)1 << FRAC;

uint16_t palette[MAX_ITER + 1];
double zoom = 3.0;                           // szerokość obrazu w jednostkach płaszczyzny
const double CX = -0.743643, CY = 0.131825;  // Dolina Konika Morskiego
uint16_t line[W];

uint16_t rgb(int r, int g, int b) { return tft.color565(r, g, b); }

void setup() {
  pinMode(RESET, INPUT_PULLUP);
  pinMode(22, OUTPUT);
  digitalWrite(22, HIGH);
  tft.begin();
  tft.setRotation(1);
  for (int i = 0; i < MAX_ITER; i++) {  // tęczowa paleta, gładko
    float t = (float)i / MAX_ITER;
    palette[i] = rgb(9 * (1 - t) * t * t * t * 255, 15 * (1 - t) * (1 - t) * t * t * 255,
                     8.5 * (1 - t) * (1 - t) * (1 - t) * t * 255);
  }
  palette[MAX_ITER] = ILI9341_BLACK;
}

void loop() {
  double left = CX - zoom / 2, top = CY + zoom * H / W / 2, step = zoom / W;
  fixed fstep = step * ONE, ci = top * ONE;
  for (int y = 0; y < H; y++, ci -= fstep) {
    fixed cr = left * ONE;
    for (int x = 0; x < W; x++, cr += fstep) {
      fixed zr = 0, zi = 0;
      int i = 0;
      while (i < MAX_ITER) {
        fixed zr2 = (zr * zr) >> FRAC, zi2 = (zi * zi) >> FRAC;
        if (zr2 + zi2 > 4 * ONE) break;  // |z| > 2: ucieka
        zi = ((zr * zi) >> (FRAC - 1)) + ci;
        zr = zr2 - zi2 + cr;
        i++;
      }
      line[x] = palette[i];
    }
    tft.drawRGBBitmap(0, y, line, W, 1);  // wiersz po wierszu: widać, jak powstaje
    if (digitalRead(RESET) == LOW) zoom = 3.0;
  }
  tft.setCursor(4, 4);
  tft.setTextColor(ILI9341_WHITE);
  tft.print("x");
  tft.print(3.0 / zoom, 0);
  zoom *= 0.5;
  if (zoom < 1e-5) zoom = 3.0;  // dalej zabrakłoby bitów po przecinku
}
