// GRA W ŻYCIE Johna Conwaya na OLED-zie: komórka rodzi się, gdy ma dokładnie 3 żywych sąsiadów,
// i przeżywa z 2 albo 3 — z tych dwóch reguł wychodzą szybowce, oscylatory i całe „ekosystemy”.
// Przycisk na D2 (klawisz R) losuje nową planszę. Plansza 64×32 komórek, każda 2×2 piksele,
// zawinięta w torus (co wyjdzie z prawej, wraca z lewej).
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
const byte RESET = 2;
const int W = 64, H = 32;
uint8_t grid[H][W / 8], next[H][W / 8];  // bit na komórkę: 256 bajtów na planszę
unsigned long generation;

bool alive(int x, int y) {
  x = (x + W) % W;
  y = (y + H) % H;
  return grid[y][x >> 3] & (1 << (x & 7));
}

void randomize() {
  for (int y = 0; y < H; y++)
    for (int b = 0; b < W / 8; b++) grid[y][b] = random(256) & random(256);  // ok. 25% żywych
  // i szybowiec, żeby było co oglądać
  const int gx = 5, gy = 5;
  const byte glider[3] = {0b010, 0b001, 0b111};
  for (int y = 0; y < 3; y++)
    for (int x = 0; x < 3; x++)
      if (glider[y] & (4 >> x)) grid[gy + y][(gx + x) >> 3] |= 1 << ((gx + x) & 7);
  generation = 0;
}

void setup() {
  pinMode(RESET, INPUT_PULLUP);
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  Wire.setClock(400000);
  randomSeed(analogRead(A0));
  randomize();
}

void loop() {
  if (digitalRead(RESET) == LOW) randomize();
  oled.clearDisplay();
  int population = 0;
  for (int y = 0; y < H; y++)
    for (int x = 0; x < W; x++) {
      int n = 0;
      for (int dy = -1; dy <= 1; dy++)
        for (int dx = -1; dx <= 1; dx++)
          if ((dx || dy) && alive(x + dx, y + dy)) n++;
      bool me = alive(x, y);
      bool lives = n == 3 || (me && n == 2);
      if (lives) {
        next[y][x >> 3] |= 1 << (x & 7);
        population++;
      } else next[y][x >> 3] &= ~(1 << (x & 7));
      if (me) oled.fillRect(x * 2, y * 2, 2, 2, SSD1306_WHITE);
    }
  memcpy(grid, next, sizeof grid);
  generation++;
  oled.display();
  if (population == 0) randomize();
}
