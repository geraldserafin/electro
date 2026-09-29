// For lcd.test.ts: LiquidCrystal as in Arduino's examples (RS 12, E 11, D4–D7 on 5, 4, 3, 2):
// a greeting, then a custom glyph, a degree sign and a number on the second line.
#include <LiquidCrystal.h>

LiquidCrystal lcd(12, 11, 5, 4, 3, 2);
byte heart[8] = {0b00000, 0b01010, 0b11111, 0b11111, 0b01110, 0b00100, 0b00000, 0b00000};

void setup() {
  lcd.createChar(0, heart);
  lcd.begin(16, 2);
  lcd.print("Hello, world!");
  lcd.setCursor(0, 1);
  lcd.write(byte(0));
  lcd.print(" 21.5");
  lcd.print((char)223);
  lcd.print("C");
}

void loop() {}
