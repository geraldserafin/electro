// CZUJNIK PARKOWANIA: im bliżej przeszkody, tym szybciej pika buzzer i tym więcej diod się pali
// (zielone, żółte, czerwona). Poniżej 10 cm — ciągły dźwięk. Przesuń przeszkodę suwakiem czujnika.
// HC-SR04: TRIG D9, ECHO D10; diody na D3–D7; buzzer aktywny na D8.
const byte TRIG = 9, ECHO = 10, BUZZER = 8;
const byte LEDS[5] = {3, 4, 5, 6, 7};
const int STEPS[5] = {100, 70, 45, 25, 10};  // cm: od tej odległości pali się kolejna dioda

void setup() {
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  pinMode(BUZZER, OUTPUT);
  for (byte p : LEDS) pinMode(p, OUTPUT);
  Serial.begin(9600);
}

long distanceCm() {
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  long us = pulseIn(ECHO, HIGH, 30000UL);
  return us ? us / 58 : 999;
}

void loop() {
  long cm = distanceCm();
  for (byte i = 0; i < 5; i++) digitalWrite(LEDS[i], cm <= STEPS[i]);
  Serial.println(cm);
  if (cm <= 10) {  // stop!
    digitalWrite(BUZZER, HIGH);
    delay(100);
  } else if (cm <= 100) {
    int pause = map(cm, 10, 100, 40, 500);
    digitalWrite(BUZZER, HIGH);
    delay(40);
    digitalWrite(BUZZER, LOW);
    delay(pause);
  } else {
    digitalWrite(BUZZER, LOW);
    delay(100);
  }
}
