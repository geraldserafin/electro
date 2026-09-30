// SYGNALIZACJA ŚWIETLNA na przejściu dla pieszych. Samochody mają zielone, dopóki pieszy nie naciśnie
// przycisku (D2, spacja); wtedy: żółte, czerwone, zielone dla pieszych (z tykaniem buzzera dla
// niewidomych), mruganie na koniec — i z powrotem. Samochody: D8 czerwone, D9 żółte, D10 zielone;
// piesi: D11 czerwone, D12 zielone; buzzer aktywny na D7.
const byte CAR_R = 8, CAR_Y = 9, CAR_G = 10, WALK_R = 11, WALK_G = 12, KEY = 2, TICK = 7;

void cars(bool r, bool y, bool g) {
  digitalWrite(CAR_R, r);
  digitalWrite(CAR_Y, y);
  digitalWrite(CAR_G, g);
}

void walkers(bool r, bool g) {
  digitalWrite(WALK_R, r);
  digitalWrite(WALK_G, g);
}

void setup() {
  for (byte p = 7; p <= 12; p++) pinMode(p, OUTPUT);
  pinMode(KEY, INPUT_PULLUP);
  Serial.begin(9600);
}

void loop() {
  cars(0, 0, 1);
  walkers(1, 0);
  while (digitalRead(KEY) == HIGH) delay(10);
  Serial.println("Pieszy czeka...");
  delay(1000);
  cars(0, 1, 0);  // żółte
  delay(1500);
  cars(1, 0, 0);  // czerwone dla aut
  delay(1000);
  walkers(0, 1);  // zielone dla pieszych, z tykaniem
  Serial.println("Piesi ida");
  for (int i = 0; i < 8; i++) {
    digitalWrite(TICK, HIGH);
    delay(80);
    digitalWrite(TICK, LOW);
    delay(420);
  }
  for (int i = 0; i < 6; i++) {  // mruga: kończ przechodzić
    walkers(0, i % 2 == 0);
    delay(300);
  }
  walkers(1, 0);
  delay(1000);
  cars(1, 1, 0);  // czerwone z żółtym: zaraz ruszamy
  delay(1200);
}
