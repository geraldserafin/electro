// THEREMIN: instrument, na którym gra się, nie dotykając go. HC-SR04 mierzy odległość dłoni,
// a buzzer gra tym wyższy dźwięk, im bliżej jest dłoń — nuta po nucie, w skali C-dur.
// Przesuwaj przeszkodę suwakiem czujnika. TRIG na D9, ECHO na D10, buzzer pasywny na D8.
const byte TRIG = 9, ECHO = 10, BUZZER = 8;
// skala C-dur przez dwie oktawy (Hz)
const int SCALE[] = {262, 294, 330, 349, 392, 440, 494, 523, 587, 659, 698, 784, 880, 988, 1047};
const int NOTES = sizeof SCALE / sizeof SCALE[0];

void setup() {
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  Serial.begin(9600);
}

long distanceCm() {
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  long us = pulseIn(ECHO, HIGH, 30000UL);
  return us ? us / 58 : -1;  // 58 µs na centymetr (tam i z powrotem)
}

void loop() {
  long cm = distanceCm();
  if (cm > 0 && cm < 60) {
    int note = map(cm, 5, 60, NOTES - 1, 0);  // bliżej = wyżej
    note = constrain(note, 0, NOTES - 1);
    tone(BUZZER, SCALE[note]);
    Serial.print(cm);
    Serial.print(" cm -> ");
    Serial.print(SCALE[note]);
    Serial.println(" Hz");
  } else {
    noTone(BUZZER);  // dłoń za daleko: cisza
  }
  delay(60);
}
