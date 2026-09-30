// TESTER REFLEKSU: po losowej chwili zapala się dioda — naciśnij przycisk jak najszybciej.
// Wynik w milisekundach na LCD 16×2 (I²C, 0x27), razem z najlepszym. Za wczesne naciśnięcie = falstart.
// Dioda na D9, przycisk na D2 (klawisz spacja), buzzer na D8.
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);
const byte LED = 9, KEY = 2, BUZZER = 8;
unsigned long best = 0;

bool pressed() { return digitalRead(KEY) == LOW; }

void setup() {
  pinMode(LED, OUTPUT);
  pinMode(KEY, INPUT_PULLUP);
  lcd.init();
  lcd.backlight();
  randomSeed(analogRead(A0));
}

void loop() {
  lcd.clear();
  lcd.print("Uwaga...");
  lcd.setCursor(0, 1);
  lcd.print("Rekord: ");
  if (best) {
    lcd.print(best);
    lcd.print(" ms");
  } else lcd.print("-");
  unsigned long go = millis() + random(1500, 4000);
  while (millis() < go)
    if (pressed()) {  // falstart
      lcd.clear();
      lcd.print("FALSTART!");
      tone(BUZZER, 150, 400);
      while (pressed()) delay(5);
      delay(1500);
      return;
    }
  digitalWrite(LED, HIGH);
  tone(BUZZER, 2000, 50);
  unsigned long start = millis();
  while (!pressed()) delay(1);
  unsigned long ms = millis() - start;
  digitalWrite(LED, LOW);
  if (!best || ms < best) best = ms;
  lcd.clear();
  lcd.print("Czas: ");
  lcd.print(ms);
  lcd.print(" ms");
  lcd.setCursor(0, 1);
  lcd.print(ms < 200 ? "Blyskawica!" : ms < 300 ? "Niezle!" : "Spiacy? :)");
  while (pressed()) delay(5);
  delay(2500);
}
