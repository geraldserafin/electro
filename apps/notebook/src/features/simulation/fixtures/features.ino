// What arduino.test.ts checks the emulator against: PWM, tone(), an interrupt, micros(), Serial both ways.
volatile unsigned int falls = 0;

void onFall() { falls++; }

void setup() {
  Serial.begin(115200);
  pinMode(9, OUTPUT);
  analogWrite(9, 64); // 25 % on timer 1, ≈ 490 Hz
  tone(8, 1000); // 1 kHz on timer 2
  pinMode(2, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(2), onFall, FALLING);
  unsigned long before = micros();
  delay(10);
  Serial.print("us=");
  Serial.println(micros() - before);
}

void loop() {
  while (Serial.available()) Serial.write(toupper(Serial.read()));
  static unsigned long last = 0;
  if (millis() - last >= 100) {
    last = millis();
    Serial.print("falls=");
    Serial.println(falls);
  }
}
