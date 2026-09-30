// The TFT through Adafruit_ILI9341 on a Pico (tft.test.ts): compiled as the notes server compiles a Pico's
// sketch (arduino-pico, prepareSketch) into tft.pico.bin.
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
// the note's wiring: SPI0 SCK GP18, MOSI GP19; CS GP17, DC GP20, RST GP21
Adafruit_ILI9341 tft(17, 20, 21);
void setup() {
  pinMode(22, OUTPUT); digitalWrite(22, HIGH);
  tft.begin();
  tft.setRotation(1);
  tft.fillScreen(ILI9341_RED);
  tft.fillRect(0, 0, 160, 120, ILI9341_BLUE);
  tft.setCursor(170, 130); tft.setTextColor(ILI9341_WHITE); tft.setTextSize(3); tft.print("Hej!");
}
void loop() {}
