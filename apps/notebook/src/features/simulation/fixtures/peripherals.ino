// For peripherals.test.ts: a servo on D9 sent to 45°, a passive buzzer on D8 playing A4.
#include <Servo.h>

Servo servo;

void setup() {
  servo.attach(9);
  servo.write(45);
  tone(8, 440);
}

void loop() {}
