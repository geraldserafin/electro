// For session.test.ts: an HC-SR04 with its trigger on D9 and its echo on D10, the echo's length
// (µs) printed after each ping.
const int TRIG = 9, ECHO = 10;

void setup() {
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  Serial.begin(115200);
}

void loop() {
  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  Serial.println(pulseIn(ECHO, HIGH, 30000UL));
  delay(10);
}
