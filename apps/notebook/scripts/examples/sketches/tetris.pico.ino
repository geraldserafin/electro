// TETRIS na Raspberry Pi Pico i kolorowym TFT 240×320 (ILI9341 na SPI).
// Klawisze: ← → przesuwają, ↑ obraca, ↓ przyspiesza, spacja zrzuca klocek na dół.
// Pełny rząd znika; im więcej rzędów naraz, tym więcej punktów. Co 10 rzędów — szybciej.
// TFT: SCK GP18, MOSI GP19, CS GP17, DC GP20, RESET GP21, podświetlenie GP22.
// Przyciski do masy: ← GP2, → GP3, ↑ GP4, ↓ GP5, spacja GP6.
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>

Adafruit_ILI9341 tft(17, 20, 21);
const int LEFT = 2, RIGHT = 3, ROTATE = 4, DOWN = 5, DROP = 6;
const int COLS = 10, ROWS = 20, CELL = 15, X0 = 8, Y0 = 10;  // plansza na ekranie

// siedem klocków, każdy w czterech obrotach: 16 bitów = siatka 4×4 (wiersz po wierszu)
const uint16_t SHAPES[7][4] = {
  {0x0F00, 0x2222, 0x00F0, 0x4444},  // I
  {0x8E00, 0x6440, 0x0E20, 0x44C0},  // J
  {0x2E00, 0x4460, 0x0E80, 0xC440},  // L
  {0x6600, 0x6600, 0x6600, 0x6600},  // O
  {0x6C00, 0x4620, 0x06C0, 0x8C40},  // S
  {0x4E00, 0x4640, 0x0E40, 0x4C40},  // T
  {0xC600, 0x2640, 0x0C60, 0x4C80},  // Z
};
const uint16_t COLORS[8] = {ILI9341_BLACK, ILI9341_CYAN, ILI9341_BLUE, ILI9341_ORANGE,
                            ILI9341_YELLOW, ILI9341_GREEN, ILI9341_MAGENTA, ILI9341_RED};

uint8_t board[ROWS][COLS];    // 0: pusto, 1–7: kolor klocka, który tu leży
uint8_t shown[ROWS][COLS];    // co jest narysowane (rysujemy tylko zmiany: SPI nie jest za darmo)
int piece, turn, px, py, nextPiece;
long score, lines;
bool over;

bool cell(int p, int r, int x, int y) { return SHAPES[p][r] & (0x8000 >> (y * 4 + x)); }

bool fits(int p, int r, int nx, int ny) {
  for (int y = 0; y < 4; y++)
    for (int x = 0; x < 4; x++)
      if (cell(p, r, x, y)) {
        int bx = nx + x, by = ny + y;
        if (bx < 0 || bx >= COLS || by >= ROWS) return false;
        if (by >= 0 && board[by][bx]) return false;
      }
  return true;
}

void drawCell(int x, int y, uint8_t c) {
  int sx = X0 + x * CELL, sy = Y0 + y * CELL;
  if (!c) {
    tft.fillRect(sx, sy, CELL, CELL, ILI9341_BLACK);
    return;
  }
  tft.fillRect(sx, sy, CELL - 1, CELL - 1, COLORS[c]);
  tft.drawFastHLine(sx, sy, CELL - 1, ILI9341_WHITE);  // odblask
  tft.drawFastVLine(sx, sy, CELL - 1, ILI9341_WHITE);
}

void drawBoard() {  // plansza z klockiem w locie; tylko to, co się zmieniło
  uint8_t now[ROWS][COLS];
  memcpy(now, board, sizeof now);
  if (!over)
    for (int y = 0; y < 4; y++)
      for (int x = 0; x < 4; x++)
        if (cell(piece, turn, x, y) && py + y >= 0) now[py + y][px + x] = piece + 1;
  for (int y = 0; y < ROWS; y++)
    for (int x = 0; x < COLS; x++)
      if (now[y][x] != shown[y][x]) {
        drawCell(x, y, now[y][x]);
        shown[y][x] = now[y][x];
      }
}

void drawPanel() {
  tft.fillRect(170, 10, 70, 200, ILI9341_BLACK);
  tft.setTextColor(ILI9341_WHITE);
  tft.setTextSize(1);
  tft.setCursor(172, 12);
  tft.print("NASTEPNY");
  for (int y = 0; y < 4; y++)
    for (int x = 0; x < 4; x++)
      if (cell(nextPiece, 0, x, y)) tft.fillRect(176 + x * 12, 28 + y * 12, 11, 11, COLORS[nextPiece + 1]);
  tft.setCursor(172, 90);
  tft.print("WYNIK");
  tft.setTextSize(2);
  tft.setCursor(172, 102);
  tft.print(score);
  tft.setTextSize(1);
  tft.setCursor(172, 130);
  tft.print("LINIE");
  tft.setTextSize(2);
  tft.setCursor(172, 142);
  tft.print(lines);
}

void spawn() {
  piece = nextPiece;
  nextPiece = random(7);
  turn = 0;
  px = 3;
  py = -1;
  if (!fits(piece, turn, px, py)) over = true;
  drawPanel();
}

void land() {
  for (int y = 0; y < 4; y++)
    for (int x = 0; x < 4; x++)
      if (cell(piece, turn, x, y) && py + y >= 0) board[py + y][px + x] = piece + 1;
  int cleared = 0;
  for (int y = ROWS - 1; y >= 0; y--) {
    bool full = true;
    for (int x = 0; x < COLS; x++) full = full && board[y][x];
    if (full) {
      cleared++;
      for (int k = y; k > 0; k--) memcpy(board[k], board[k - 1], COLS);
      memset(board[0], 0, COLS);
      y++;  // ten sam wiersz jeszcze raz: spadło na niego to, co było wyżej
    }
  }
  const int POINTS[5] = {0, 100, 300, 500, 800};
  score += POINTS[cleared];
  lines += cleared;
  spawn();
}

void start() {
  memset(board, 0, sizeof board);
  score = lines = 0;
  over = false;
  nextPiece = random(7);
  spawn();
}

void setup() {
  for (int p = LEFT; p <= DROP; p++) pinMode(p, INPUT_PULLUP);
  pinMode(22, OUTPUT);
  digitalWrite(22, HIGH);
  tft.begin();
  tft.fillScreen(ILI9341_BLACK);
  tft.drawRect(X0 - 2, Y0 - 2, COLS * CELL + 3, ROWS * CELL + 3, ILI9341_DARKGREY);
  memset(shown, 0, sizeof shown);
  randomSeed(micros());
  start();
}

// przycisk: raz od razu, a trzymany — powtarza co chwilę
bool key(int pin, uint32_t &next, int repeat) {
  if (digitalRead(pin) == HIGH) {
    next = 0;
    return false;
  }
  if (millis() < next) return false;
  next = millis() + (next ? repeat : 170);
  return true;
}

uint32_t nextL, nextR, nextT, nextD, nextDrop, fallAt;

void loop() {
  if (over) {
    tft.setTextColor(ILI9341_WHITE, ILI9341_RED);
    tft.setTextSize(2);
    tft.setCursor(22, 150);
    tft.print(" KONIEC GRY ");
    while (digitalRead(DROP) == HIGH) delay(10);
    while (digitalRead(DROP) == LOW) delay(10);
    tft.fillRect(X0, Y0, COLS * CELL, ROWS * CELL, ILI9341_BLACK);
    memset(shown, 0, sizeof shown);
    start();
    return;
  }
  if (key(LEFT, nextL, 70) && fits(piece, turn, px - 1, py)) px--;
  if (key(RIGHT, nextR, 70) && fits(piece, turn, px + 1, py)) px++;
  if (key(ROTATE, nextT, 250)) {
    int r = (turn + 1) % 4;
    for (int kick : {0, -1, 1, -2, 2})  // obrót przy ścianie: odsuń klocek, jeśli trzeba
      if (fits(piece, r, px + kick, py)) {
        turn = r;
        px += kick;
        break;
      }
  }
  if (key(DROP, nextDrop, 400)) {
    while (fits(piece, turn, px, py + 1)) py++;
    score += 2;
    land();
  }
  int speed = max(80, 600 - (int)(lines / 10) * 60);
  if (digitalRead(DOWN) == LOW) speed = 50;
  if (millis() >= fallAt) {
    fallAt = millis() + speed;
    if (fits(piece, turn, px, py + 1)) py++;
    else land();
  }
  drawBoard();
  delay(10);
}
