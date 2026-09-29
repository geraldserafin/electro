// For i2c.test.ts: a 16×2 LCD behind a PCF8574 at 0x27 (LiquidCrystal_I2C).
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

void setup() {
  lcd.init();
  lcd.backlight();
  lcd.print("I2C works");
  lcd.setCursor(0, 1);
  lcd.print(42);
}

void loop() {}
