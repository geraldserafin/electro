// For i2c.test.ts: a 128×64 SSD1306 at 0x3C (Adafruit_SSD1306): a pixel in each corner, a filled box.
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

Adafruit_SSD1306 display(128, 64, &Wire, -1);

void setup() {
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  display.clearDisplay();
  display.drawPixel(0, 0, SSD1306_WHITE);
  display.drawPixel(127, 0, SSD1306_WHITE);
  display.drawPixel(0, 63, SSD1306_WHITE);
  display.drawPixel(127, 63, SSD1306_WHITE);
  display.fillRect(10, 20, 30, 8, SSD1306_WHITE);
  display.display();
}

void loop() {}
