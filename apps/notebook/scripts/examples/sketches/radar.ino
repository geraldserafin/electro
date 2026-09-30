// RADAR: serwo obraca czujnik odległości HC-SR04 od 0° do 180° i z powrotem, a OLED rysuje ekran
// radaru — półokrąg, wskazówkę i echa przeszkód, które powoli gasną. Przesuwaj przeszkodę suwakiem
// czujnika i patrz, jak zmienia się jej odległość na ekranie.
// Serwo na D9, TRIG D6, ECHO D7, OLED na I²C (A4, A5).
#include <Servo.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
Servo servo;
const byte TRIG = 6, ECHO = 7;
const int CX = 64, CY = 63, R = 60, RANGE = 100;  // środek, promień w pikselach, zasięg w cm
const int STEP = 6;                                // co ile stopni pomiar
uint8_t echo[181 / STEP + 1];                      // odległość (cm) dla każdego kierunku; 0: nic
int angle = 0, dir = 1;

long distanceCm() {
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  long us = pulseIn(ECHO, HIGH, 12000UL);  // dalej niż 2 m: brak echa
  return us ? us / 58 : 0;
}

void setup() {
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  servo.attach(9);
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  Wire.setClock(400000);
  oled.setTextColor(SSD1306_WHITE);
}

void loop() {
  servo.write(angle);
  delay(25);  // serwo potrzebuje chwili, żeby się obrócić
  long cm = distanceCm();
  echo[angle / STEP] = cm > 0 && cm <= RANGE ? cm : 0;

  oled.clearDisplay();
  oled.drawCircle(CX, CY, R, SSD1306_WHITE);
  oled.drawCircle(CX, CY, R / 2, SSD1306_WHITE);
  oled.drawFastHLine(0, CY, 128, SSD1306_WHITE);
  float a = angle * PI / 180;
  oled.drawLine(CX, CY, CX + R * cos(a), CY - R * sin(a), SSD1306_WHITE);
  for (int i = 0; i <= 180 / STEP; i++)
    if (echo[i]) {
      float b = i * STEP * PI / 180;
      int r = echo[i] * R / RANGE;
      oled.fillCircle(CX + r * cos(b), CY - r * sin(b), 2, SSD1306_WHITE);
    }
  oled.setCursor(0, 0);
  oled.print(angle);
  oled.print((char)247);
  oled.setCursor(92, 0);
  if (cm > 0 && cm <= RANGE) {
    oled.print(cm);
    oled.print("cm");
  } else oled.print("--");
  oled.display();

  angle += dir * STEP;
  if (angle >= 180 || angle <= 0) dir = -dir;
}
