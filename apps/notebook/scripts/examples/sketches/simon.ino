// SIMON: gra pamięciowa. Arduino pokazuje coraz dłuższą sekwencję kolorów (diody i dźwięki),
// a Ty ją powtarzasz przyciskami. Pomyłka — koniec gry, a wynik to długość, do której doszedłeś.
// Diody na D8–D11 (zielona, czerwona, żółta, niebieska), przyciski na D2–D5 (klawisze 1–4), buzzer na D12.
const byte LEDS[4] = {8, 9, 10, 11};
const byte KEYS[4] = {2, 3, 4, 5};
const int NOTES[4] = {392, 330, 262, 196};  // G4, E4, C4, G3 — jak w oryginale
const byte BUZZER = 12;
const int MAX = 50;

byte sequence[MAX];
int length;

void show(byte color, int ms) {
  digitalWrite(LEDS[color], HIGH);
  tone(BUZZER, NOTES[color], ms);
  delay(ms);
  digitalWrite(LEDS[color], LOW);
  delay(ms / 3);
}

int waitForKey() {  // który przycisk (0–3), albo -1, gdy gracz za długo myśli
  unsigned long until = millis() + 3000;
  while (millis() < until)
    for (byte k = 0; k < 4; k++)
      if (digitalRead(KEYS[k]) == LOW) {
        digitalWrite(LEDS[k], HIGH);
        tone(BUZZER, NOTES[k]);
        while (digitalRead(KEYS[k]) == LOW) delay(5);  // czekaj, aż puści
        noTone(BUZZER);
        digitalWrite(LEDS[k], LOW);
        return k;
      }
  return -1;
}

void gameOver() {
  Serial.print("Koniec! Wynik: ");
  Serial.println(length - 1);
  for (int f = 400; f > 100; f -= 20) {
    tone(BUZZER, f, 20);
    delay(20);
  }
  for (int i = 0; i < 3; i++) {
    for (byte c = 0; c < 4; c++) digitalWrite(LEDS[c], HIGH);
    delay(150);
    for (byte c = 0; c < 4; c++) digitalWrite(LEDS[c], LOW);
    delay(150);
  }
  delay(1000);
  length = 0;
}

void setup() {
  for (byte c = 0; c < 4; c++) {
    pinMode(LEDS[c], OUTPUT);
    pinMode(KEYS[c], INPUT_PULLUP);
  }
  Serial.begin(9600);
  Serial.println("Simon: powtarzaj sekwencje!");
  randomSeed(analogRead(A0));
}

void loop() {
  sequence[length++] = random(4);
  delay(600);
  int speed = max(150, 450 - length * 20);
  for (int i = 0; i < length; i++) show(sequence[i], speed);
  for (int i = 0; i < length; i++)
    if (waitForKey() != sequence[i]) {
      gameOver();
      return;
    }
  Serial.print("Poziom ");
  Serial.println(length);
  if (length == MAX) length = 0;
}
