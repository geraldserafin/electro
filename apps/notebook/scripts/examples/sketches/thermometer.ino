// TERMOMETR: termistor NTC 10 kΩ w dzielniku z opornikiem 10 kΩ, na A0. Z napięcia liczymy opór,
// a z oporu temperaturę — równaniem Steinharta–Harta w wersji z parametrem B (3950 K).
// Wynik na LCD 16×2 (I²C) razem z minimum i maksimum. Zmieniaj temperaturę suwakiem termistora.
#include <LiquidCrystal_I2C.h>
#include <math.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);
const float R_FIXED = 10000, R0 = 10000, T0 = 298.15, B = 3950;  // T0: 25 °C w kelwinach
float lowest = 1000, highest = -1000;

// stopień: znak 0 w pamięci wyświetlacza
byte degree[8] = {0b00110, 0b01001, 0b01001, 0b00110, 0, 0, 0, 0};

void setup() {
  lcd.init();
  lcd.backlight();
  lcd.createChar(0, degree);
  Serial.begin(9600);
}

void loop() {
  int raw = analogRead(A0);                        // termistor u góry, opornik u dołu dzielnika
  float r = R_FIXED * (1023.0 / max(raw, 1) - 1);   // opór termistora
  float t = 1 / (1 / T0 + log(r / R0) / B) - 273.15;
  lowest = min(lowest, t);
  highest = max(highest, t);
  lcd.setCursor(0, 0);
  lcd.print("T = ");
  lcd.print(t, 1);
  lcd.write(byte(0));
  lcd.print("C    ");
  lcd.setCursor(0, 1);
  lcd.print("min ");
  lcd.print(lowest, 0);
  lcd.print(" max ");
  lcd.print(highest, 0);
  lcd.print("   ");
  Serial.println(t, 2);
  delay(300);
}
