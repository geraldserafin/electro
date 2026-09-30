// WĄŻ na OLED-zie 128×64: zbieraj jedzenie, rośnij, nie wjedź w siebie ani w ścianę.
// Strzałki: przyciski na D2 (góra), D3 (dół), D4 (lewo), D5 (prawo), do masy. Buzzer pasywny na D8.
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

Adafruit_SSD1306 oled(128, 64, &Wire, -1);

const byte UP = 2, DOWN = 3, LEFT = 4, RIGHT = 5, BUZZER = 8;
const byte CELL = 4;                  // kratka ma 4×4 piksele
const byte COLS = 32, ROWS = 14;      // plansza: 32×14 kratek (pod paskiem z wynikiem)
const byte TOP = 8;                   // pasek z wynikiem na górze
const int MAX_LEN = 120;

byte xs[MAX_LEN], ys[MAX_LEN];        // ciało węża: głowa pod indeksem 0
int len;
char dx, dy;                          // kierunek ruchu
byte foodX, foodY;
int score, best;
bool over;

void placeFood() {
  while (true) {
    foodX = random(COLS);
    foodY = random(ROWS);
    bool onSnake = false;
    for (int i = 0; i < len; i++)
      if (xs[i] == foodX && ys[i] == foodY) onSnake = true;
    if (!onSnake) return;
  }
}

void start() {
  len = 4;
  for (int i = 0; i < len; i++) {
    xs[i] = 10 - i;
    ys[i] = 7;
  }
  dx = 1;
  dy = 0;
  score = 0;
  over = false;
  placeFood();
}

void setup() {
  for (byte p = UP; p <= RIGHT; p++) pinMode(p, INPUT_PULLUP);
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  Wire.setClock(400000);  // szybkie I²C: więcej klatek na sekundę
  oled.setTextColor(SSD1306_WHITE);
  randomSeed(analogRead(A0));
  start();
}

void readKeys() {
  // (nie da się zawrócić w miejscu: wąż wjechałby w siebie)
  if (digitalRead(UP) == LOW && dy == 0) { dx = 0; dy = -1; }
  else if (digitalRead(DOWN) == LOW && dy == 0) { dx = 0; dy = 1; }
  else if (digitalRead(LEFT) == LOW && dx == 0) { dx = -1; dy = 0; }
  else if (digitalRead(RIGHT) == LOW && dx == 0) { dx = 1; dy = 0; }
}

void step() {
  int nx = xs[0] + dx, ny = ys[0] + dy;
  if (nx < 0 || nx >= COLS || ny < 0 || ny >= ROWS) { over = true; return; }
  for (int i = 0; i < len - 1; i++)
    if (xs[i] == nx && ys[i] == ny) { over = true; return; }
  bool eats = nx == foodX && ny == foodY;
  if (eats && len < MAX_LEN) len++;
  for (int i = len - 1; i > 0; i--) {
    xs[i] = xs[i - 1];
    ys[i] = ys[i - 1];
  }
  xs[0] = nx;
  ys[0] = ny;
  if (eats) {
    score++;
    tone(BUZZER, 1500, 40);
    placeFood();
  }
}

void draw() {
  oled.clearDisplay();
  oled.setCursor(0, 0);
  oled.print("Wynik ");
  oled.print(score);
  oled.setCursor(80, 0);
  oled.print("Max ");
  oled.print(best);
  oled.drawRect(0, TOP - 1, 128, ROWS * CELL + 2, SSD1306_WHITE);
  for (int i = 0; i < len; i++)
    oled.fillRect(xs[i] * CELL, TOP + ys[i] * CELL, CELL - (i ? 1 : 0), CELL - (i ? 1 : 0), SSD1306_WHITE);
  oled.drawRoundRect(foodX * CELL, TOP + foodY * CELL, CELL, CELL, 1, SSD1306_WHITE);
  oled.display();
}

void loop() {
  if (over) {
    if (score > best) best = score;
    tone(BUZZER, 200, 400);
    oled.fillRect(24, 24, 80, 20, SSD1306_BLACK);
    oled.drawRect(24, 24, 80, 20, SSD1306_WHITE);
    oled.setCursor(34, 30);
    oled.print("KONIEC GRY");
    oled.display();
    while (digitalRead(UP) && digitalRead(DOWN) && digitalRead(LEFT) && digitalRead(RIGHT)) delay(10);
    start();
  }
  unsigned long until = millis() + max(60, 160 - score * 4);  // coraz szybciej
  while (millis() < until) readKeys();
  step();
  draw();
}
