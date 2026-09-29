// HELL ON PICO — a first-person shooter in the spirit of the classics, on a Raspberry Pi Pico with a
// 128×64 OLED (SSD1306 on I²C: GP4 SDA, GP5 SCL), five buttons to ground and a passive buzzer.
// Walls by ray casting (DDA over a grid), shaded by distance with ordered dithering; demons drawn as
// sprites behind the walls' depth; shoot them before they reach you.
//   GP10 forward, GP11 back, GP12 turn left, GP13 turn right, GP14 fire; the buzzer on GP15.
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

const int W = 128, H = 64, VIEW = 56;  // the screen; the 3D view above the status bar
const int FORWARD = 10, BACK = 11, LEFT = 12, RIGHT = 13, FIRE = 14, BUZZER = 15;
const uint32_t FRAME_MS = 33;  // 30 frames a second: the rest of the time the chip sleeps (the real I²C allows ~40)
Adafruit_SSD1306 oled(W, H, &Wire, -1);

// the level: 1–3 walls of three kinds (their dithering), 0 floor
const int MAP = 16;
const uint8_t level[MAP][MAP] = {
  {1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1},
  {1,0,0,0,0,0,1,0,0,0,0,0,0,0,0,1},
  {1,0,2,2,0,0,1,0,0,3,3,3,0,0,0,1},
  {1,0,2,0,0,0,0,0,0,0,0,3,0,0,0,1},
  {1,0,0,0,0,1,1,1,0,0,0,3,0,2,0,1},
  {1,0,0,0,0,0,0,1,0,0,0,0,0,2,0,1},
  {1,1,1,0,0,0,0,1,1,1,0,0,0,2,0,1},
  {1,0,0,0,3,0,0,0,0,0,0,0,0,0,0,1},
  {1,0,0,0,3,0,0,0,0,0,0,1,1,0,0,1},
  {1,0,2,2,3,0,0,2,2,0,0,0,1,0,0,1},
  {1,0,0,0,0,0,0,2,0,0,0,0,1,0,0,1},
  {1,0,0,0,0,0,0,0,0,3,0,0,0,0,0,1},
  {1,0,3,3,0,1,0,0,0,3,0,0,2,2,0,1},
  {1,0,0,0,0,1,0,0,0,0,0,0,0,0,0,1},
  {1,0,0,0,0,1,0,0,0,0,0,0,0,0,0,1},
  {1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1},
};

// a demon, 16×16 (bit 15 on the left); its mask: what of the square it covers
const uint16_t DEMON[16] = {
  0x2004, 0x300C, 0x1FF8, 0x3FFC, 0x6DB6, 0x6DB6, 0x7FFE, 0x3FFC,
  0x3BDC, 0x1FF8, 0x0FF0, 0x1FF8, 0x3E7C, 0x3C3C, 0x3C3C, 0x7C3E,
};
const uint16_t DEMON_MASK[16] = {
  0x300C, 0x381C, 0x3FFC, 0x7FFE, 0xFFFF, 0xFFFF, 0xFFFF, 0x7FFE,
  0x7FFE, 0x3FFC, 0x1FF8, 0x3FFC, 0x7FFE, 0x7E7E, 0x7E7E, 0xFE7F,
};
// the shotgun, 24×12 at the bottom of the view, and its flash
const uint32_t GUN[12] = {
  0x003C00, 0x003C00, 0x007E00, 0x007E00, 0x00FF00, 0x01FF80,
  0x03E7C0, 0x07C3E0, 0x0FC3F0, 0x1FFFF8, 0x3FFFFC, 0x7FFFFE,
};
const uint32_t FLASH[6] = { 0x081810, 0x04A420, 0x02DB40, 0x07FFE0, 0x02DB40, 0x04A420 };

// ordered dithering (4×4 Bayer): a pixel is lit when its threshold is under the brightness
const uint8_t BAYER[4][4] = { {0, 8, 2, 10}, {12, 4, 14, 6}, {3, 11, 1, 9}, {15, 7, 13, 5} };
inline bool dither(int x, int y, int bright) { return BAYER[y & 3][x & 3] < bright; }

struct Demon { float x, y; int health; bool alive; uint32_t hurt; };
const int DEMONS = 6;
Demon demons[DEMONS];
float px, py, angle;  // the player
int health, ammo, kills;
float depth[W];  // each column's wall distance: sprites hide behind nearer walls
uint32_t firedAt = 0, hitAt = 0, lastFrame = 0;
int frames = 0, fps = 0;
uint32_t fpsSince = 0;
bool dead = false;

bool held(int pin) { return digitalRead(pin) == LOW; }
bool solid(float x, float y) { return level[(int)y][(int)x] != 0; }

void reset() {
  px = 1.5; py = 1.5; angle = 0.8;
  health = 100; ammo = 25; kills = 0; dead = false;
  const float spots[DEMONS][2] = { {8.5, 3.5}, {13.5, 2.5}, {3.5, 7.5}, {9.5, 7.5}, {14.5, 10.5}, {7.5, 13.5} };
  for (int i = 0; i < DEMONS; i++) demons[i] = { spots[i][0], spots[i][1], 3, true, 0 };
}

void setup() {
  for (int pin : {FORWARD, BACK, LEFT, RIGHT, FIRE}) pinMode(pin, INPUT_PULLUP);
  Serial.begin(115200);
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  oled.setTextColor(SSD1306_WHITE);
  oled.clearDisplay();
  oled.setTextSize(2);
  oled.setCursor(22, 10);
  oled.print("HELL ON");
  oled.setCursor(40, 30);
  oled.print("PICO");
  oled.setTextSize(1);
  oled.setCursor(22, 54);
  oled.print("press FIRE (GP14)");
  oled.display();
  while (!held(FIRE)) delay(10);
  tone(BUZZER, 880, 80);
  while (held(FIRE)) delay(10);  // (that press starts the game, it is not a shot)
  reset();
  lastFrame = millis();
}

// ---------------------------------------------------------------- the world

void move(float dt) {
  float speed = 2.4 * dt, turn = 2.6 * dt;
  if (held(LEFT)) angle -= turn;
  if (held(RIGHT)) angle += turn;
  float dx = cosf(angle) * speed, dy = sinf(angle) * speed;
  if (held(BACK)) { dx = -dx; dy = -dy; }
  if (held(FORWARD) || held(BACK)) {  // slide along walls: each axis on its own, a margin from them
    if (!solid(px + dx * 2, py)) px += dx;
    if (!solid(px, py + dy * 2)) py += dy;
  }
}

void demonsAct(float dt) {
  for (Demon &d : demons) {
    if (!d.alive) continue;
    float dx = px - d.x, dy = py - d.y, dist = sqrtf(dx * dx + dy * dy);
    if (dist < 0.7) {  // at you: it claws
      if (millis() - hitAt > 600) { health -= 12; hitAt = millis(); tone(BUZZER, 110, 120); }
      continue;
    }
    if (dist > 7) continue;
    float step = 0.9 * dt / dist;
    if (!solid(d.x + dx * step * 2, d.y)) d.x += dx * step;
    if (!solid(d.x, d.y + dy * step * 2)) d.y += dy * step;
  }
}

// the wall distance straight ahead of ``angle`` (for shooting: nothing hits through a wall)
float wallAt(float a) {
  float rx = cosf(a), ry = sinf(a);
  for (float t = 0; t < 16; t += 0.05) if (solid(px + rx * t, py + ry * t)) return t;
  return 16;
}

void fire() {
  if (ammo == 0) { tone(BUZZER, 60, 40); return; }
  ammo--;
  firedAt = millis();
  tone(BUZZER, 180, 90);
  float wall = wallAt(angle);
  Demon *hit = nullptr;
  float nearest = wall;
  for (Demon &d : demons) {
    if (!d.alive) continue;
    float dx = d.x - px, dy = d.y - py, dist = sqrtf(dx * dx + dy * dy);
    float off = atan2f(dy, dx) - angle;
    while (off > PI) off -= 2 * PI;
    while (off < -PI) off += 2 * PI;
    if (fabsf(off) < 0.35 / dist + 0.03 && dist < nearest) { nearest = dist; hit = &d; }
  }
  if (hit) {
    hit->hurt = millis();
    if (--hit->health <= 0) { hit->alive = false; kills++; ammo += 4; tone(BUZZER, 330, 150); }
  }
}

// ---------------------------------------------------------------- the view

void walls() {
  float dirX = cosf(angle), dirY = sinf(angle);
  float planeX = -dirY * 0.66, planeY = dirX * 0.66;  // the camera plane: a 66° field of view
  for (int x = 0; x < W; x++) {
    float camera = 2.0 * x / W - 1;
    float rx = dirX + planeX * camera, ry = dirY + planeY * camera;
    int mx = (int)px, my = (int)py;
    float ddx = fabsf(1 / rx), ddy = fabsf(1 / ry);
    int sx = rx < 0 ? -1 : 1, sy = ry < 0 ? -1 : 1;
    float sideX = (rx < 0 ? px - mx : mx + 1 - px) * ddx;
    float sideY = (ry < 0 ? py - my : my + 1 - py) * ddy;
    int side = 0, kind = 0;
    for (int i = 0; i < 64 && !kind; i++) {  // DDA: square by square to the first wall
      if (sideX < sideY) { sideX += ddx; mx += sx; side = 0; } else { sideY += ddy; my += sy; side = 1; }
      kind = level[my][mx];
    }
    float dist = side == 0 ? sideX - ddx : sideY - ddy;
    if (dist < 0.05) dist = 0.05;
    float along = side == 0 ? py + dist * ry : px + dist * rx;  // where on the block the ray hit it: 0–1
    along -= floorf(along);
    bool edge = along < 0.05 || along > 0.95;  // the blocks' edges: dark seams
    depth[x] = dist;
    int height = (int)(VIEW / dist);
    int top = max(0, VIEW / 2 - height / 2), bottom = min(VIEW - 1, VIEW / 2 + height / 2);
    // nearer is brighter; the side walls a touch darker; the kinds their own pattern
    int bright = constrain(14 - (int)(dist * 2.0) - side * 2, 1, 13);  // (never all lit: the pattern shows)
    for (int y = top; y <= bottom; y++) {
      bool lit = kind == 2 ? ((y & 3) != 0 && dither(x, y, bright))  // bricks: a gap every 4 rows
               : kind == 3 ? ((x & 1) == 0 && dither(x, y, bright))  // panels: every other column
               : dither(x, y, bright);
      if (lit && !edge) oled.drawPixel(x, y, SSD1306_WHITE);
    }
    if (bottom + 1 < VIEW && (x & 3) == 0) oled.drawPixel(x, bottom + 1, SSD1306_WHITE);  // where the floor meets it
  }
}

void sprites() {
  float dirX = cosf(angle), dirY = sinf(angle);
  float planeX = -dirY * 0.66, planeY = dirX * 0.66;
  float inv = 1.0 / (planeX * dirY - dirX * planeY);
  int order[DEMONS];
  float far[DEMONS];
  for (int i = 0; i < DEMONS; i++) { order[i] = i; far[i] = (demons[i].x - px) * (demons[i].x - px) + (demons[i].y - py) * (demons[i].y - py); }
  for (int i = 0; i < DEMONS; i++)  // farthest first
    for (int j = i + 1; j < DEMONS; j++) if (far[order[j]] > far[order[i]]) { int t = order[i]; order[i] = order[j]; order[j] = t; }
  for (int k = 0; k < DEMONS; k++) {
    Demon &d = demons[order[k]];
    if (!d.alive) continue;
    float sx = d.x - px, sy = d.y - py;
    float tx = inv * (dirY * sx - dirX * sy), tz = inv * (-planeY * sx + planeX * sy);  // into the camera's space
    if (tz < 0.2) continue;
    int cx = (int)(W / 2 * (1 + tx / tz));
    int size = (int)(VIEW / tz);
    int left = cx - size / 2, top = VIEW / 2 - size / 2 + size / 8;
    bool flashing = millis() - d.hurt < 120;
    for (int x = max(0, left); x < min(W, left + size); x++) {
      if (depth[x] < tz) continue;  // a wall in front
      int u = (x - left) * 16 / size;
      for (int y = max(0, top); y < min(VIEW, top + size); y++) {
        int v = (y - top) * 16 / size;
        uint16_t bit = 0x8000 >> u;
        if (!(DEMON_MASK[v] & bit)) continue;
        bool body = (DEMON[v] & bit) != 0;
        oled.drawPixel(x, y, body != flashing ? SSD1306_WHITE : SSD1306_BLACK);
      }
    }
  }
}

void hud(uint32_t now) {
  // the gun, bobbing as you walk, and its flash for a moment after a shot
  int bob = (held(FORWARD) || held(BACK)) ? (int)(2 * sinf(now / 90.0)) : 0;
  for (int r = 0; r < 12; r++)
    for (int c = 0; c < 24; c++)
      if (GUN[r] & (0x800000UL >> c)) oled.drawPixel(52 + c, VIEW - 12 + r + bob, SSD1306_WHITE);
  if (now - firedAt < 80)
    for (int r = 0; r < 6; r++)
      for (int c = 0; c < 24; c++)
        if (FLASH[r] & (0x800000UL >> c)) oled.drawPixel(52 + c, VIEW - 19 + r, SSD1306_WHITE);
  oled.drawPixel(W / 2, VIEW / 2, SSD1306_INVERSE);  // the crosshair
  oled.fillRect(0, VIEW, W, H - VIEW, SSD1306_BLACK);
  oled.drawFastHLine(0, VIEW, W, SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(0, VIEW + 1);
  oled.printf("HP%3d  AMMO%2d  K%d/%d", max(health, 0), ammo, kills, DEMONS);
  if (now - hitAt < 150) oled.drawRect(0, 0, W, VIEW, SSD1306_WHITE);  // hurt: the view flashes
}

void over(const char *line) {
  oled.fillRect(20, 18, 88, 22, SSD1306_BLACK);
  oled.drawRect(20, 18, 88, 22, SSD1306_WHITE);
  oled.setCursor(26, 22);
  oled.print(line);
  oled.setCursor(26, 30);
  oled.print("FIRE: again");
}

void loop() {
  uint32_t now = millis();
  float dt = min((now - lastFrame) / 1000.0, 0.1);
  lastFrame = now;
  bool won = kills == DEMONS;
  if (health <= 0 || won) {
    if (!dead) { dead = true; tone(BUZZER, won ? 660 : 90, 400); }
    over(won ? "YOU WIN!" : "YOU DIED");
    oled.display();
    if (held(FIRE)) { delay(300); reset(); }
    return;
  }
  move(dt);
  demonsAct(dt);
  static bool wasFiring = false;
  bool firing = held(FIRE);
  if (firing && !wasFiring) fire();
  wasFiring = firing;

  oled.clearDisplay();
  walls();
  sprites();
  hud(now);
  oled.display();
  frames++;
  if (now - fpsSince >= 1000) { fps = frames; frames = 0; fpsSince = now; Serial.printf("fps %d\n", fps); }
  while (millis() - now < FRAME_MS) delay(1);
}
