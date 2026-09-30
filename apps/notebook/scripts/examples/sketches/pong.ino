// PONG na OLED-zie: dwóch graczy, każdy kręci swoim potencjometrem (A0 i A1).
// Kto pierwszy zdobędzie 7 punktów, wygrywa. Odbicia słychać na buzzerze pasywnym (D8).
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
const byte BUZZER = 8;
const int PADDLE = 14, WIN = 7;

float bx, by, vx, vy;  // piłka: położenie i prędkość (piksele na klatkę)
int left, right;       // punkty

void serve(int dir) {
  bx = 64;
  by = 32;
  vx = 1.6 * dir;
  vy = random(-10, 11) / 10.0;
}

void setup() {
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  Wire.setClock(400000);
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(2);
  randomSeed(analogRead(A2));
  serve(1);
}

int paddleY(byte pin) { return map(analogRead(pin), 0, 1023, 0, 64 - PADDLE); }

void loop() {
  int ly = paddleY(A0), ry = paddleY(A1);
  bx += vx;
  by += vy;
  if (by < 0 || by > 63) {  // sufit i podłoga
    vy = -vy;
    by = constrain(by, 0, 63);
  }
  // odbicie od paletki: im dalej od środka, tym bardziej ukośnie
  if (bx < 4 && vx < 0 && by >= ly && by <= ly + PADDLE) {
    vx = -vx * 1.05;
    vy += (by - ly - PADDLE / 2) / 5.0;
    tone(BUZZER, 800, 20);
  }
  if (bx > 123 && vx > 0 && by >= ry && by <= ry + PADDLE) {
    vx = -vx * 1.05;
    vy += (by - ry - PADDLE / 2) / 5.0;
    tone(BUZZER, 800, 20);
  }
  if (bx < 0) { right++; tone(BUZZER, 300, 150); serve(1); }
  if (bx > 127) { left++; tone(BUZZER, 300, 150); serve(-1); }

  oled.clearDisplay();
  for (int y = 0; y < 64; y += 6) oled.drawFastVLine(64, y, 3, SSD1306_WHITE);
  oled.setCursor(44, 2);
  oled.print(left);
  oled.setCursor(74, 2);
  oled.print(right);
  oled.fillRect(0, ly, 3, PADDLE, SSD1306_WHITE);
  oled.fillRect(125, ry, 3, PADDLE, SSD1306_WHITE);
  oled.fillRect(bx - 1, by - 1, 3, 3, SSD1306_WHITE);
  if (left == WIN || right == WIN) {
    oled.fillRect(14, 22, 100, 22, SSD1306_BLACK);
    oled.setCursor(18, 26);
    oled.print(left == WIN ? "LEWY!" : "PRAWY!");
    oled.display();
    tone(BUZZER, 1200, 500);
    delay(3000);
    left = right = 0;
  }
  oled.display();
  delay(15);
}
