// For i2c.test.ts: a DS1307 (RTClib) set to 13:45:30, read two seconds later.
#include <Wire.h>
#include <RTClib.h>

RTC_DS1307 rtc;

void setup() {
  Serial.begin(115200);
  rtc.begin();
  rtc.adjust(DateTime(2024, 5, 17, 13, 45, 30));
  delay(2000);
  DateTime now = rtc.now();
  Serial.print(now.year());
  Serial.print('-');
  Serial.print(now.month());
  Serial.print('-');
  Serial.print(now.day());
  Serial.print(' ');
  Serial.print(now.hour());
  Serial.print(':');
  Serial.print(now.minute());
  Serial.print(':');
  Serial.println(now.second());
}

void loop() {}
