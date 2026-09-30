// FLAPPY na OLED-zie: jeden przycisk (D2, spacja) podrywa ptaka do góry, grawitacja ciągnie w dół.
// Przelatuj przez szczeliny w rurach. Buzzer pasywny na D8.
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
const byte FLAP = 2, BUZZER = 8;
const int GAP = 24, PIPE_W = 10, PIPES = 3;

float y, v;              // ptak: wysokość i prędkość
int pipeX[PIPES], pipeGap[PIPES];
int score, best;
bool wasDown;

// ptak 8×6
const uint8_t BIRD[] PROGMEM = {0x3C, 0x4A, 0xFF, 0xFE, 0x7C, 0x38};

void start() {
  y = 30;
  v = 0;
  score = 0;
  for (int i = 0; i < PIPES; i++) {
    pipeX[i] = 128 + i * 48;
    pipeGap[i] = random(6, 64 - GAP - 6);
  }
}

void setup() {
  pinMode(FLAP, INPUT_PULLUP);
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  Wire.setClock(400000);
  oled.setTextColor(SSD1306_WHITE);
  randomSeed(analogRead(A0));
  start();
}

bool crashed() {
  if (y < 0 || y > 58) return true;
  for (int i = 0; i < PIPES; i++)
    if (pipeX[i] < 28 && pipeX[i] + PIPE_W > 20 && (y < pipeGap[i] || y + 6 > pipeGap[i] + GAP)) return true;
  return false;
}

void loop() {
  bool down = digitalRead(FLAP) == LOW;
  if (down && !wasDown) {  // naciśnięcie, nie trzymanie
    v = -2.6;
    tone(BUZZER, 1000, 15);
  }
  wasDown = down;
  v += 0.25;
  y += v;
  for (int i = 0; i < PIPES; i++) {
    pipeX[i] -= 2;
    if (pipeX[i] == 18) {
      score++;
      tone(BUZZER, 1800, 30);
    }
    if (pipeX[i] < -PIPE_W) {
      pipeX[i] += PIPES * 48;
      pipeGap[i] = random(6, 64 - GAP - 6);
    }
  }
  oled.clearDisplay();
  for (int i = 0; i < PIPES; i++) {
    oled.fillRect(pipeX[i], 0, PIPE_W, pipeGap[i], SSD1306_WHITE);
    oled.fillRect(pipeX[i], pipeGap[i] + GAP, PIPE_W, 64 - pipeGap[i] - GAP, SSD1306_WHITE);
  }
  oled.drawBitmap(20, (int)y, BIRD, 8, 6, SSD1306_WHITE);
  oled.setCursor(56, 0);
  oled.print(score);
  oled.display();
  if (crashed()) {
    if (score > best) best = score;
    tone(BUZZER, 150, 500);
    oled.fillRect(20, 20, 88, 26, SSD1306_BLACK);
    oled.drawRect(20, 20, 88, 26, SSD1306_WHITE);
    oled.setCursor(30, 24);
    oled.print("Wynik: ");
    oled.print(score);
    oled.setCursor(30, 35);
    oled.print("Rekord: ");
    oled.print(best);
    oled.display();
    delay(800);
    while (digitalRead(FLAP) == HIGH) delay(10);
    start();
  }
  delay(20);
}
