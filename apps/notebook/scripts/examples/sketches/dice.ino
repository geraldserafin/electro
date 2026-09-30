// KOSTKA DO GRY: naciśnij przycisk (D12, spacja), a na wyświetlaczu 7-segmentowym cyfry kręcą się
// coraz wolniej, aż zatrzymają się na wyniku od 1 do 6 — jak turlająca się kostka.
// Segmenty a–g na D2–D8 (każdy przez swój opornik), wspólna katoda do masy; buzzer pasywny na D9.
const byte SEG[7] = {2, 3, 4, 5, 6, 7, 8};
const byte DIGITS[10] = {0b0111111, 0b0000110, 0b1011011, 0b1001111, 0b1100110,
                         0b1101101, 0b1111101, 0b0000111, 0b1111111, 0b1101111};
const byte KEY = 12, BUZZER = 9;

void show(int n) {
  for (int i = 0; i < 7; i++) digitalWrite(SEG[i], (DIGITS[n] >> i) & 1);
}

void setup() {
  for (byte s : SEG) pinMode(s, OUTPUT);
  pinMode(KEY, INPUT_PULLUP);
  Serial.begin(9600);
  show(0);
}

void loop() {
  if (digitalRead(KEY) == HIGH) return;
  randomSeed(micros());  // chwila naciśnięcia jest losowa: ziarno dla random()
  int n = 1;
  for (int pause = 20; pause < 300; pause = pause * 11 / 10) {  // coraz wolniej
    n = random(1, 7);
    show(n);
    tone(BUZZER, 1500, 5);
    delay(pause);
  }
  tone(BUZZER, 880, 150);
  Serial.print("Wypadlo: ");
  Serial.println(n);
  while (digitalRead(KEY) == LOW) delay(5);
}
