# electro — projekt

Dokument żywy: każdy nowy „fakt” o dziedzinie dopisujemy tutaj, zanim trafi do kodu.

Cel: biblioteka spójna z teorią, na której stoi (obwody jako morfizmy kategorii hipergrafowej), jak
najmniejsza: jedna klasa `Element`, składanie, wzór klatki. Bez magii i bez funkcji pomocniczych.

## 1. Teoria

### 1.1 Kategoria obwodów

- **Obiekt** to liczba wolnych końców; **morfizm** — kawałek obwodu `m → n` (opornik `1 → 1`, zamknięty
  układ `0 → 0`). Na każdym końcu jest potencjał i prąd (wpływa lewym, wypływa prawym).
- `f >> g` to złożenie (prawe końce `f` sklejone z lewymi `g`), `f @ g` — iloczyn monoidalny (obok siebie).
- **Pająki** (algebra Frobeniusa: jeden potencjał, prądy się sumują — prawo Kirchhoffa) dają resztę:
  `f | g`, `~f` (pętla: `cap >> (f @ wire) >> cup`), `-f` (transpozycja), `swap`. `Node` to pająk
  z nazwą: ten sam obiekt w kilku miejscach to jeden punkt.
- Złożenie relacji to sklejenie **i eliminacja** (∃) tego, co zostało w środku. Dlatego każdy obwód
  jest elementem jak każdy inny: `R_1 >> R_2` to jedno prawo `U = I·(R_1 + R_2)` — nikt nie mówi
  o „szeregowo”. Definicje wyeliminowanych zmiennych zostają, więc o środek dalej można pytać.

Baez, Fong, *A Compositional Framework for Passive Linear Networks* (2015).

### 1.2 Relacje, nie funkcje

Prawa to równania bez kierunku: dane i szukane są symetryczne. Zadania odwrotne (dany prąd → szukany
opór) działają za darmo; dana to po prostu jeszcze jedno równanie.

### 1.3 Klatka

Obwód zamknięty (zero wolnych końców; nazwane punkty liczą się jako złączone) to same prawa, w słowach
czasu: `D(x)` (pochodna) i `Pre(x)` (wartość chwilę wcześniej: pamięć). Solver zamienia je na
**wzór klatki** — i nic poza tym nie wie o elementach, diodach ani AC:

| klatka | `D(x)` | `Pre(x)` |
|---|---|---|
| `Step(dt)` | `(x − x⁻)/dt` | `x⁻` |
| `DC() = Step(∞)` | 0 | `x⁻` |
| `AC(ω)` | `jω·x` (granica dt → 0 klatki obróconej o ω·dt) | `x` |

- `final` to jedna klatka, ta, do której obwód dochodzi (DC; z sinusami jednej częstotliwości — AC).
- `simulate` to klatki jedna po drugiej, od spoczynku. Kartka to równowaga symulacji; ich zgodność to
  darmowy test (kartka ≠ symulacja po ustaleniu = błąd w modelu).

### 1.4 Czego teoria nie załatwia

- Równowaga to nie granica: oscylator ma równowagę, do której nie dojdzie.
- Krok dyskretny jest funktorem tylko w przybliżeniu.
- Nieliniowe (`exp`) składają się dalej, ale rozwiązuje je Newton, nie algebra.
- Stan dyskretny (przerzutnik, program): równowag może być kilka albo żadna.

## 2. Eliminacja

Zmienna znika przy składaniu tylko z równania stopnia 1, gdy jej współczynnik:

- nie zawiera zmiennych,
- jest **stały w czasie**: bez funkcji (stan, przełącznik — bywają 0), bez `t`, `dt` i wartości sprzed
  klatki (C/dt jest 0 w klatce nieskończenie długiej),

i gdy zmienna nie leży na końcu (kawałek jest widziany przez końce) ani wewnątrz funkcji (`exp`: zostaje
dla Newtona). Najpierw najmniejsze równania i zmienne łączące (pająków), potem elementów.

`normal(e)`: `cancel` tylko, gdy w mianowniku jest litera (inaczej `expand`, bez rozbijania `exp`
sumy); mianownik zostaje (wyczyszczony dawałby fałszywe pierwiastki, np. R = 0). `dt` nie jest skracane:
x/dt to 0 przy dt = ∞, x·dt/dt nie.

Masa: w grupie potencjałów, których prawa (także każdego wariantu elementu „albo-albo”) nie zmieniają się
po dodaniu stałej do wszystkich, jeden wybierany jest 0.

## 3. Rozwiązywanie klatki

- **Algebra** (wielomianowe w niewiadomych): krok po kroku — równanie z jedną niewiadomą, potem razem.
  Kroki to ślad eliminacji i rozwiązywania: co znaleziono, z jakiego równania, dlaczego.
- **Przypadki**: element „albo-albo” (dioda podręcznikowa: przewodzi albo nie) — zakładamy wariant,
  rozwiązujemy, sprawdzamy warunek; jak na kartce.
- **Newton**: `exp` (dioda Shockleya, tranzystor). Złącze ograniczane jak w SPICE (`pnjlim`), skala
  z prądów w prawach; DC z homotopią po źródłach (λ od 0 do 1).
- Czego nie da się wyznaczyć: `MissingData` (ile danych brakuje, które by wystarczyły); sprzeczne:
  `Contradiction` (które się wykluczają); kilka rozwiązań: `Ambiguous`.

## 4. Czas: Φ i silnik

`step_function` to wzór klatki skompilowany raz: wejścia (przełącznik, pin) i stan to litery, reszta
liczb wstawiona. W symulacji **nazwane punkty zostają niewiadomymi** (eliminowane jeden po drugim dają
w drabince wielomian w 1/dt jej długości — liczby, których float nie utrzyma), a to, co się odczytuje
(napięcia, prądy elementów), liczy się po klatce prostym kodem, nie w Newtonie.

`engine.py` (Newton, Gauss, długość kroku, pamięć wejść) to zwykły Python bez importów poza `math`;
strona dostaje go jako JavaScript drukowany z tego samego pliku przez pscript (bez przeciążania
operatorów: `PSCRIPT_OVERLOAD = False` w każdej funkcji). Jedno źródło prawdy, bez ręcznego portu.

Pomiar (Node, ten sam wynik; październik 2026), klatek na sekundę:

| obwód | stary silnik JS | nowy (Python → JS) | ngspice |
|---|---|---|---|
| dioda + RC | 343 000 | 1 025 000 | 231 000 |
| drabinka RC × 10 | 23 000 | 368 000 | 252 000 |
| 555 | 110 000 | 611 000 | — |

## 5. Zasady kodu

- Jeden `Element`; rodzaj elementu to podklasa z `terminals` i `laws`, jedna na plik, rodziny w folderach.
- Obwody tylko z kombinatorów. Bez `Problem`, bez netlist, bez SPICE w bibliotece.
- Nazwy elementów i punktów to identyfikatory (`BadName`): nic z nich nie trafia do kodu; wyrażenia po
  nazwach czytane bez `eval`.
- Biblioteka nie mówi słowami: wyniki i błędy to dane. Metody (Bode, przemiatanie, tolerancje, dziura,
  opór między punktami), kroki jako tekst i LaTeX są w notatniku, nad `final`.

## 6. Odrzucone

- **Zadanie (`Problem`) jako osobny byt** — obwód z wartościami to `circuit.final(values)`.
- **Netlista jako postać obwodu** — obwód to relacja; to, które końce sklejono (`Relation.glued`),
  wystarcza do narysowania go.
- **Osobny silnik JS pisany ręcznie** — dwa źródła prawdy rozjeżdżały się.
- **Liczenie kartki przez symulację do końca** — tracimy zadania odwrotne, litery i dokładność.
- **Węzły nazywane napisem** — przypadkowe sklejenia; punkt to obiekt.
