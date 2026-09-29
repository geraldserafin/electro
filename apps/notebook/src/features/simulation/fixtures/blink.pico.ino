// For pico.test.ts: the board's LED and GP15 blinking at 10 Hz; each time, the voltage on GP26
// (analogRead) on the USB serial port and GP14 (a pull-up) on UART0.
void setup() {
  Serial.begin(115200);
  Serial1.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(15, OUTPUT);
  pinMode(14, INPUT_PULLUP);
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  digitalWrite(15, HIGH);
  delay(50);
  digitalWrite(LED_BUILTIN, LOW);
  digitalWrite(15, LOW);
  delay(50);
  Serial.print("adc=");
  Serial.println(analogRead(26));
  Serial1.print("gp14=");
  Serial1.println(digitalRead(14));
}
