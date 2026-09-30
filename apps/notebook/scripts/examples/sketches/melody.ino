// MELODIA: „Korobeiniki” — rosyjska piosenka ludowa, którą cały świat zna z Tetrisa — na buzzerze
// pasywnym (D8), a dioda RGB (D9, D10, D11) zmienia kolor z każdą nutą. Potencjometr na A0 ustawia tempo.
const byte BUZZER = 8, RED = 9, GREEN = 10, BLUE = 11;

// częstotliwości nut (Hz)
const int NOTE_E5 = 659, NOTE_B4 = 494, NOTE_C5 = 523, NOTE_D5 = 587, NOTE_A4 = 440, NOTE_F5 = 698,
          NOTE_A5 = 880, NOTE_G5 = 784, REST = 0;
// nuta i długość (w ósemkach)
const int SONG[][2] = {
  {NOTE_E5, 2}, {NOTE_B4, 1}, {NOTE_C5, 1}, {NOTE_D5, 2}, {NOTE_C5, 1}, {NOTE_B4, 1}, {NOTE_A4, 2}, {NOTE_A4, 1}, {NOTE_C5, 1}, {NOTE_E5, 2}, {NOTE_D5, 1}, {NOTE_C5, 1},
  {NOTE_B4, 3}, {NOTE_C5, 1}, {NOTE_D5, 2}, {NOTE_E5, 2}, {NOTE_C5, 2}, {NOTE_A4, 2}, {NOTE_A4, 2}, {REST, 2},
  {REST, 1}, {NOTE_D5, 2}, {NOTE_F5, 1}, {NOTE_A5, 2}, {NOTE_G5, 1}, {NOTE_F5, 1}, {NOTE_E5, 3}, {NOTE_C5, 1}, {NOTE_E5, 2}, {NOTE_D5, 1}, {NOTE_C5, 1},
  {NOTE_B4, 2}, {NOTE_B4, 1}, {NOTE_C5, 1}, {NOTE_D5, 2}, {NOTE_E5, 2}, {NOTE_C5, 2}, {NOTE_A4, 2}, {NOTE_A4, 2}, {REST, 2},
};
const int LENGTH = sizeof SONG / sizeof SONG[0];

void color(int note) {  // kolor z wysokości nuty: niskie czerwone, wysokie niebieskie
  if (!note) {
    analogWrite(RED, 0);
    analogWrite(GREEN, 0);
    analogWrite(BLUE, 0);
    return;
  }
  int h = map(note, 440, 880, 0, 255);
  analogWrite(RED, 255 - h);
  analogWrite(GREEN, h < 128 ? h * 2 : (255 - h) * 2);
  analogWrite(BLUE, h);
}

void setup() {
  pinMode(RED, OUTPUT);
  pinMode(GREEN, OUTPUT);
  pinMode(BLUE, OUTPUT);
}

void loop() {
  for (int i = 0; i < LENGTH; i++) {
    int eighth = map(analogRead(A0), 0, 1023, 90, 250);  // ms na ósemkę
    int ms = SONG[i][1] * eighth;
    color(SONG[i][0]);
    if (SONG[i][0]) tone(BUZZER, SONG[i][0], ms * 9 / 10);
    delay(ms);
  }
  color(0);
  delay(1000);
}
