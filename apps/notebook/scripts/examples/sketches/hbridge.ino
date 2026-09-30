// MOSTEK H: cztery tranzystory MOSFET pozwalają kręcić silnikiem w obie strony. Potencjometr na A0:
// środek — stop, w lewo — obroty w lewo, w prawo — w prawo, tym szybciej, im dalej od środka (PWM).
// Górne tranzystory (P) włącza stan niski, dolne (N) — wysoki. Nigdy nie włączamy obu z jednej strony
// naraz: zwarcie zasilania do masy!
// Lewa strona: górny D5, dolny D6; prawa: górny D9, dolny D10.
const byte TOP_L = 5, LOW_L = 6, TOP_R = 9, LOW_R = 10;

void off() {
  digitalWrite(LOW_L, LOW);
  digitalWrite(LOW_R, LOW);
  digitalWrite(TOP_L, HIGH);
  digitalWrite(TOP_R, HIGH);
}

void setup() {
  pinMode(TOP_L, OUTPUT);
  pinMode(LOW_L, OUTPUT);
  pinMode(TOP_R, OUTPUT);
  pinMode(LOW_R, OUTPUT);
  off();
  Serial.begin(9600);
}

void loop() {
  int v = analogRead(A0) - 512;  // -512 … 511
  int speed = constrain(map(abs(v), 40, 511, 0, 255), 0, 255);
  off();
  delayMicroseconds(50);  // przerwa, zanim włączy się druga para (tranzystory wyłączają się chwilę)
  if (v > 40) {           // w prawo: lewy górny + prawy dolny
    digitalWrite(TOP_L, LOW);
    analogWrite(LOW_R, speed);
  } else if (v < -40) {   // w lewo: prawy górny + lewy dolny
    digitalWrite(TOP_R, LOW);
    analogWrite(LOW_L, speed);
  }
  Serial.print(v > 40 ? "w prawo " : v < -40 ? "w lewo " : "stop ");
  Serial.println(speed);
  delay(200);
}
