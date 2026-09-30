// OSCYLOSKOP na OLED-zie: Arduino mierzy napięcie na A0 128 razy z rzędu i rysuje przebieg,
// a z przejść przez połowę zakresu liczy częstotliwość. Potencjometr na A1 zmienia podstawę czasu.
// Na wejściu: sinusoida 50 Hz z przesunięciem 2,5 V (bo Arduino mierzy tylko od 0 do 5 V).
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
int samples[128];

void setup() {
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  Wire.setClock(400000);
  oled.setTextColor(SSD1306_WHITE);
}

void loop() {
  int pause = map(analogRead(A1), 0, 1023, 0, 1000);  // µs między próbkami (sam pomiar trwa ok. 112 µs)
  unsigned long start = micros();
  for (int i = 0; i < 128; i++) {
    samples[i] = analogRead(A0);
    if (pause) delayMicroseconds(pause);
  }
  float us = (micros() - start) / 128.0;  // na próbkę

  // wyzwalanie i częstotliwość: przejścia w górę przez połowę zakresu
  int first = -1, last = -1, crossings = 0;
  for (int i = 1; i < 128; i++)
    if (samples[i - 1] < 512 && samples[i] >= 512) {
      if (first < 0) first = i;
      last = i;
      crossings++;
    }

  oled.clearDisplay();
  for (int y = 0; y < 64; y += 8)
    for (int x = 0; x < 128; x += 16) oled.drawPixel(x, y, SSD1306_WHITE);  // siatka
  for (int i = 1; i < 128; i++)
    oled.drawLine(i - 1, 63 - samples[i - 1] / 17, i, 63 - samples[i] / 17, SSD1306_WHITE);
  oled.setCursor(0, 0);
  if (crossings >= 2) {
    float period = (last - first) * us / (crossings - 1);  // µs
    oled.print(1e6 / period, 1);
    oled.print(" Hz");
  } else oled.print("-- Hz");
  oled.setCursor(76, 0);
  oled.print((int)(us * 16 / 1000));
  oled.print(" ms/dz");
  oled.display();
}
