# electro — projekt przebudowy

Stan: ustalenia z dyskusji (październik 2026), przed wdrożeniem. Dokument żywy: każdy nowy „fakt”
o dziedzinie dopisujemy tutaj, zanim trafi do kodu.

Cel: biblioteka spójna z teorią, na której stoi (obwody jako morfizmy kategorii hipergrafowej),
napisana jak w Haskellu — małe czyste funkcje, które się komponuje, niezmienne wartości, porządne
typy, zero ręcznego grzebania we wspólnym stanie.

---

## 1. Teoria

### 1.1 Kategoria obwodów

- **Kategoria** to „rzeczy + strzałki, które da się łączyć”: strzałkę `A → B` ze strzałką `B → C`
  łączy się w `A → C`. Monoid (`a → a`) to kategoria z jednym obiektem — czyli „monoid z typami”.
- **U nas:** obiekt = liczba wolnych końcówek; strzałka (morfizm) = kawałek obwodu `n → m`
  (rezystor `1 → 1`, masa `1 → 0`, zamknięty układ `0 → 0`). Szeregowe łączenie składa strzałki
  tylko, gdy końcówki pasują — dlatego kategoria, a nie monoid (byłby nim, gdyby wszystko było `1 → 1`).
- **Jedyna prawdziwa operacja to sklejanie węzłów.** Idealny kabel = dwa punkty o tym samym
  potencjale = jeden węzeł. Szeregowo, równolegle, zamykanie, etykiety — to tylko przepisy, co z czym
  skleić:

  | operacja | skleja |
  |---|---|
  | `a >> b` | prawe końce `a` z lewymi `b` |
  | `a \| b` | lewe z lewymi, prawe z prawymi |
  | `close(a)` | prawe końce `a` z jego własnymi lewymi (ślad, *trace*; to samo co pętla sprzężenia zwrotnego) |
  | węzeł / sieć | wszystkie miejsca z tym samym węzłem |

- **Iloczyn tensorowy** `@` (obwody obok siebie) i **pająki** (węzły jako sklejenie `n → m` w jeden
  punkt; z nich `cup`, `cap`, `close`, `transpose`) czynią z tego kategorię hipergrafową
  (Frobeniusa) — wszystko da się zgiąć, odwrócić, zamknąć.

### 1.2 Jak to jest zbudowane dziś (i zostaje)

Trzy warstwy połączone funktorami (`circuit.py`):

```
Circuit (drzewo składni, kategoria wolna) --netlist--> Netlist (kospan węzłów) --semantics--> równania (relacje)
```

- **Drzewo składni** zachowane, jak je zbudowano — renderer może je narysować.
- **`Netlist`** to postać normalna: kospan `lewe końce → węzły ← prawe końce`, udekorowany elementami
  (konstrukcja Fonga, *decorated cospans*). Złożenie = sklejenie węzłów brzegu (pushout).
- **Semantyka**: równania. Konstrukcja z Baez–Fong, *A compositional framework for passive linear
  networks*: czarna skrzynka (*black-boxing*) to funktor z obwodów do relacji.

### 1.3 Funktor = tłumaczenie, które szanuje łączenie

Każdy kawałek obwodu tłumaczy się na równania (rezystor → `U = R·I`). Własność: złożyć i
przetłumaczyć = przetłumaczyć osobno i skleić równania. Takie tłumaczenie to **funktor**.

Równania to **relacje, nie funkcje** — nie mają kierunku. Stąd:
- zadania odwrotne działają za darmo (dany prąd → szukane R),
- dane i szukane są symetryczne: jedne i drugie to zmienne, jedne ograniczone, drugie odczytywane.

### 1.4 Jeden obwód, trzy tłumaczenia („+1 wymiar”)

Składnia ta sama, zmienia się tylko to, **nad czym** są relacje (pierścień skalarów):

| tłumaczenie | wielkość to | kondensator | analiza |
|---|---|---|---|
| kartka (DC) | liczba | przerwa (d/dt = 0) | `solve` |
| częstotliwość (AC) | funkcja ω, fazor | impedancja 1/(jωC) (d/dt → jω) | `solve` z sinusem, `respond` (Bode) |
| czas | funkcja t | `i = C·du/dt` | `simulate` |

- DC = ewaluacja s → 0, AC = ewaluacja s → jω tłumaczenia „po s” (impedancje jako funkcje
  wymierne, pole ℝ(s)); czas = relacje na sygnałach (podejście behawioralne, Willems).
- Ciekawostka: dla samych rezystorów i stałych źródeł wymiar czasu jest pusty — każda klatka
  symulacji = kartka. Elementy żyjące tylko w czasie (Arduino, 555, fala prostokątna) nie mają
  sensownego „punktu” — dla nich jest tylko czas.

### 1.5 Symulacja jako rekurencja; kartka jako jej równowaga

- Symulacja to maszyna ze stanem (automat Mealy'ego): `step :: State -> State`, wywoływany na
  własnym wyniku. Wynik symulacji to **cały przebieg**, nie ostatnia klatka.
- Kartka to **równowaga** tej dynamiki: stan, w którym nic się nie zmienia. Branie stanów
  ustalonych też jest funktorem (Baez–Pollard): równowaga złożenia = złożenie równowag — więc da się
  ją liczyć wprost, kompozycyjnie, bez kręcenia filmu. Szybciej, dokładnie, w obie strony.
- Przykład (RC, E = 10 V, R = 1 kΩ, C = 100 µF): kartka U_C = 10 V; symulacja 0 → 3,9 → 6,3 →
  8,6 → 9,93 V (t = 0; 0,05; 0,1; 0,2; 0,5 s) — dąży do kartki.

### 1.6 Czego teoria sama nie załatwia (żeby jej nie przecenić)

Żadna z tych rzeczy nie jest wyjątkiem w systemie — każdy element podlega temu samemu mechanizmowi
(F16, §9.2). To są granice tego, co analiza może *odpowiedzieć*, i trzeba je mówić w wyniku.


- Funktor stanów ustalonych daje **równowagi, nie granice**: oscylator ma równowagę, do której
  symulacja nigdy nie dojdzie. Stabilność to osobna własność, nie wynika z kategorii.
- Symulacja numeryczna (krok dyskretny) jest funktorem tylko w przybliżeniu — dyskretyzacja
  złożenia ≠ złożenie dyskretyzacji.
- Elementy nieliniowe (dioda): relacje dalej się składają, ale przestają być liniowe — tracimy
  rachunek macierzowy, nie kategorię. DC dla nich to i tak iteracja (Newton) do punktu stałego.
- Arduino, 555, przerzutniki: stan dyskretny + ciągły (systemy hybrydowe). W systemie to zwykłe
  elementy — relacje z `Pre` (pamięć) zamiast albo obok `D` (§9.2). Teoria takich układów to np.
  snopy czasowe (Schultz–Spivak–Vasilakopoulou); dla nas: równowaga może być niejedna (przerzutnik)
  albo żadna (działający program), co analiza DC mówi w wyniku.
- Całość zakłada **elementy skupione** (obwód mały wobec długości fali — wtedy działają prawa
  Kirchhoffa). Co to łamie (linie, anteny), wchodzi jako element z `Delay`.

### 1.7 Co z tego wynika w praktyce

1. **Nowy element dopisuje się raz** — jego równanie w każdym tłumaczeniu; łączenie, własne
   komponenty, wszystkie analizy działają od razu. I odwrotnie: nowa analiza działa dla każdego obwodu.
2. **Własny komponent to zwykły kawałek** — zagnieżdża się bez końca; można go zastąpić czarną
   skrzynką (same równania na zaciskach, np. Thévenin) — szybciej, a na zewnątrz to samo.
3. **Równoważność obwodów da się sprawdzić** (te same równania na zaciskach) → sprawdzanie układu
   zastępczego ucznia; kroki rozwiązania („R₁, R₂ szeregowo → R₁+R₂”) jako zamiany na równoważne,
   z gwarancją, że wynik się nie zmieni.
4. **Zadania odwrotne i warianty zadań** za darmo (dane = równania).
5. **Darmowy test poprawności:** kartka i symulacja to dwa tłumaczenia tego samego obwodu — ich
   niezgodność (kartka ≠ symulacja po ustaleniu) to błąd w którymś. Test losujący obwody wyłapie
   błędy modeli elementów.

### 1.8 Odrzucone alternatywy

- **Parametry jako wejście funkcji (`Para(C)`: morfizm `P ⊗ A → B`, `obwod(R_1=5)` jako częściowe
  podstawienie).** Kierunkowe — parametry wchodzą, wynik wychodzi; nie wyrazi „dany prąd → szukane R”.
  Wybrane: parametry to zmienne relacji, a dane to dodatkowe warunki (`Given`). Funkcja to
  szczególny przypadek relacji. Istniejące `circuit(**data)` (commit 7e35e06) zastąpi `Problem`.
- **Liczenie kartki przez symulację do końca.** Odpada: tracimy zadania odwrotne i symbole,
  przybliżenie zamiast dokładności, brak wyniku dla układów, które się nie ustalają.
- **Węzły nazywane napisem.** Odpada: przypadkowe sklejenia przy składaniu (F8).

## 2. Fakty o dziedzinie

Każdy fakt to coś, co w rzeczywistości jest osobnym pojęciem — więc w kodzie też ma nim być.

| # | fakt | konsekwencja w kodzie |
|---|---|---|
| F1 | Dane to **warunki**, nie tylko wartości: `R_1 = 10` i zmierzone `I_R1 = 0.2 A` to ten sam rodzaj rzeczy (jedno równanie więcej). | `Given` = warunek; wartość elementu to najprostszy przypadek. |
| F2 | **Szukane należą do zadania** — rozwiązywalność zależy od tego, czego szukamy. | `Problem(circuit, given, find)`; `find: list[Sought]`. |
| F3 | **Zadanie to osobny typ.** Obwód + dane + szukane = coś, co można trzymać, przekazać, podać kilku analizom. | `Problem` jako wartość. |
| F4 | **Zamknięty układ ≠ kawałek.** Rozwiązuje się tylko układ bez wolnych końców (`0 → 0`). Kawałek `n → m` ma inne pytania: zachowanie na zaciskach (Thévenin, rezystancja zastępcza, transmitancja). `1 → 1` to **nie** `0 → 0` — są dwa sposoby domknięcia (połączyć końce / zatkać je) i dają różne wyniki. | `Problem` przyjmuje tylko zamknięte; `equivalent(part)` osobno. Domknięcie zawsze jawne. |
| F5 | **Mierniki to obserwacje, nie elementy.** Idealny amperomierz = kabel + pytanie „ile płynie?” (jak strzałka prądu). | Odczyt miernika to `Given` albo `Sought`; na rysunku symbol zostaje. |
| F6 | **Masa ma dwie role:** łączy (wszystkie symbole masy to jeden węzeł) i jest odniesieniem potencjałów (V_A). Napięcia i prądy od masy nie zależą. | Rozdzielone pojęcia: sieć globalna `GND` + wybór odniesienia. |
| F7 | **Element ma tożsamość; nazwa to parametr.** Dwa `Resistor("R")` to dwa różne rezystory o wspólnej wartości R (każdy ma swój prąd). Pytamy o prąd **elementu**, nie nazwy. | Element = obiekt niezmienny z tożsamością; `Sought` wskazuje element. |
| F8 | **Węzeł ma tożsamość, nie nazwę.** Napis jako tożsamość działa jak zmienna globalna — dwa niezależne kawałki z węzłem `"A"` skleją się po cichu. | `Node()` — tożsamość obiektu; napis tylko do wyświetlenia. Globalne sieci (`GND`, `VCC`, etykieta na schemacie) jawnie: `Net("VCC")`. |
| F9 | **Kierunek odniesienia.** Każdy element ma kierunek (od lewej do prawej); wyniki są względem niego. Elementy **symetryczne** (R, C, L): odwrócenie zmienia tylko znaki. **Biegunowe** (źródło, dioda, tranzystor): odwrócenie to inny układ. | `transpose` zachowuje układ dla symetrycznych (z dokładnością do znaku), zmienia dla biegunowych. |
| F10 | **Stan przełącznika, pozycja potencjometru, częstotliwość źródła to dane**, nie struktura i nie parametr analizy. | Do `Given`; `solve` nie bierze `omega` — wynika z danych źródeł. |
| F11 | **Dane mogą mieć wymiar czasu** (przełącznik zamknięty od 1 s, przebieg z pomiaru). Stała to szczególny przypadek. | Wartość danej: liczba, symbol albo funkcja czasu. |
| F12 | **Wynik ma wspólny interfejs** — rozwiązanie, przebieg i charakterystyka odpowiadają na to samo pytanie, różni się wymiar odpowiedzi. | `result(sought)` → liczba / funkcja t / funkcja ω. |
| F13 | **Własny komponent to nazwana wartość** (jak `let`). | Zwykły `Circuit` przypisany do nazwy; szablon wielokrotnego użytku = funkcja zwracająca `Circuit` (świeże węzły na każde wywołanie). |
| F14 | **Wartości mają jednostki.** `R_1 = 5 V` to błąd. | Sprawdzane przy budowie `Problem`. |
| F16 | **Minimalny i ogólny rdzeń, bez wyjątków.** Prawa obwodu (sklejanie → Kirchhoff) nie zależą od elementów. Element to relacja między sygnałami na końcówkach i swoim stanem, zapisana raz w czasie słownikiem `D`, `Pre`, `Delay`, `when` i czystymi funkcjami. Rezystor, kondensator, dioda, przerzutnik, Arduino, linia transmisyjna — ten sam mechanizm. Dodanie elementu = jedna definicja; analiza = interpretacja słownika czasu. | §9.2: `two_terminal(…)`, `element(…)`; analiza = `interpret(law, analysis)`. |
| F15 | **Składanie nie jest przemienne.** `a >> b ≠ b >> a` (inny brzeg, inny kierunek). Równoległe naprawdę jest przemienne. Uwaga: `R1 >> R2` i `R2 >> R1` to różne obwody (węzeł środkowy gdzie indziej), ale z zacisków zachowują się tak samo (R₁+R₂) — przemienność na poziomie zachowania, nie struktury. Biblioteka opisuje strukturę. | `>>` zamiast `+` (patrz §4). |

## 3. Typy

```haskell
-- składnia
Circuit n m                 -- niezmienny; n końcówek z lewej, m z prawej
Element                     -- rodzaj + nazwa parametru, bez wartości; tożsamość = obiekt
Node                        -- tożsamość = obiekt; opcjonalny podpis do wyświetlania
Net                         -- globalna sieć z nazwą (GND, VCC, etykieta)

-- zadanie
Given   = Value Element Quantity      -- R_1 = 10, E_1 = 230∠0°, S_1 = closed od 1 s
        | Equals Quantity Quantity    -- I_R1 = 0.2 A, U_AB = 5 V, I_R2 = 2·I_R1
Sought  = Of Quantity Element         -- U, I, P elementu; wartość elementu
        | Potential Node
        | Between Node Node           -- napięcie, rezystancja zastępcza między punktami
Problem = Problem (Circuit 0 0) [Given] [Sought]

-- analizy (czyste funkcje)
solve      :: Problem -> Solution            -- DC / fazory (ω z danych źródeł)
respond    :: Problem -> Response            -- po częstotliwości
simulate   :: Duration -> Problem -> Trace   -- w czasie
equivalent :: Circuit n n -> Equivalent      -- kawałek widziany z zacisków

-- wynik: to samo pytanie, różny wymiar odpowiedzi
Solution (s) :: Sought -> Quantity
Trace    (s) :: Sought -> (Time -> Quantity)
Response (s) :: Sought -> (Frequency -> Quantity)
```

Nazwy zawsze angielskie i przemyślane. Wielkości (`Quantity`) to wartości z jednostką, nie gołe
liczby ani napisy.

## 4. Składanie

**Prymitywy** (jedyne konstruktory drzewa): `Element`, `wire` (identyczność `1 → 1`), `swap`,
pająk (sklejenie węzłów: `n → m` w jeden węzeł), `Node`, `Net`.

**Operatory:**

| zapis | znaczenie | uwagi |
|---|---|---|
| `a >> b` | szeregowo: prawe końce `a` z lewymi `b` | nieprzemienne — czyta się jak przepływ (jak `>>>` w Haskellu) |
| `a \| b` | równolegle | przemienne |
| `a @ b` | obok siebie (iloczyn tensorowy) | przemienne z dokładnością do `swap` |

Kolejność w Pythonie pasuje: `@` > `>>` > `|`. `+` znika.

**Funkcje pochodne** (każda jednolinijkowa, z prymitywów, bez magii): `cup` (`2 → 0`), `cap`
(`0 → 2`), `close(f) = cap >> (f @ wire) >> cup`, `loop(*parts) = close(series(*parts))`, `|`
(pająki po obu stronach), `shunt`, `transpose`.

### Sklejanie przez węzły i zasada domknięcia

```python
a = Node()
circuit = a >> E1 >> R1 >> a             # zamknięty: oba końce na węźle a

a, b = Node(), Node()
bridge = (a >> E1 >> R1 >> b) @ (b >> R2 >> a) @ (b >> R3 >> E2 >> a)   # dwa oczka
```

- Ten sam obiekt `Node` użyty kilka razy = jeden węzeł (sklejenie przez tożsamość).
- **Zasada domknięcia:** koniec leżący na węźle (`Node`/`Net`) nie jest wolny. Składanie (`>>`)
  działa na wszystkich końcach, ale **typ zadania** liczy tylko końce wolne: wyrażenie, którego każdy
  koniec leży na węźle, jest zamknięte (`0 → 0`). `a >> E >> R >> a` jest zamknięty.
- Jeden wspólny węzeł nie łączy pętli elektrycznie — dwie pętle sklejone w jednym punkcie
  („ósemka”) płyną niezależnie (prąd nie ma którędy wrócić); wspólny węzeł daje tylko wspólny
  potencjał. Oczka wpływają na siebie dopiero przez wspólną gałąź (dwa wspólne węzły):

  ```python
  a, b = Node(), Node()
  figure_eight = (a >> E1 >> R1 >> a) >> (b >> E2 >> R2 >> b)   # sklejone w a ≡ b: niezależne
  two_meshes   = (a >> E1 >> R1 >> b) @ (b >> R2 >> a) @ (b >> R3 >> E2 >> a)   # R2 wspólny
  ```
- Dwa sposoby zrobienia `0 → 0` z kawałka `1 → 1` (F4), np. E = 10 V, R₁ = R₂ = 1 kΩ:
  `close(E >> R1 >> R2)` — końce połączone, I = 5 mA; `cap`-owanie końców (zostawione wolne) —
  I = 0, napięcie jałowe na końcach 10 V (to pytanie o kawałek: `equivalent`, E_th = 10 V,
  R_th = 2 kΩ). Dlatego domknięcie musi być jawne.
- Kawałek wielokrotnego użytku to funkcja zwracająca obwód — każde wywołanie ma świeże węzły i
  świeże elementy (jak zmienne lokalne), więc dwie kopie się nie skleją i nie podzielą elementu:

  ```python
  def divider(top: str, bottom: str) -> Circuit:
      mid = Node()
      return Resistor(top) >> mid >> Resistor(bottom)
  ```

## 5. Zasady kodu

1. **Niezmienne wartości.** Wszystko `@dataclass(frozen=True)` (albo `NamedTuple`). Żadnych `self.x = …`
   poza konstrukcją, żadnego `setattr`, żadnego kopiowania obiektów i czyszczenia im cache'u.
2. **Czyste funkcje.** Wejście → wyjście, bez efektów ubocznych. Klasy to dane (typy sum/iloczynów),
   zachowanie to funkcje na nich. Metody tylko jako cukier składniowy wywołujący funkcję.
3. **Typy sum zamiast flag.** Np. `Context(omega, dt, t)` z polami „albo-albo” → `Analysis = DC | AC(ω) | Step(dt, t)`.
4. **Wielkości typowane, nie napisy.** `"I_R_1"` parsowane w locie → `Sought`/`Quantity`. Napis tylko na
   granicy (UI, notatnik), zamieniany na typ raz.
5. **Jedna implementacja jednej rzeczy.** Np. union-find (sklejanie) jest dziś w trzech miejscach.
6. **Funkcyjny rdzeń, imperatywna skorupa.** Środek solvera (sympy, macierze) i pętla symulacji (Newton,
   krok czasu) mogą być imperatywne w środku — interfejs czysty. Symulacja jako `step :: State -> State`
   + rozwinięcie w czasie (unfold), stan jawnie przekazywany.
7. **Błędy jako dane.** Zostają typowane `Issue` (już są) — ale bez kanałów bocznych (np. `warnings.warn`
   jako sposób zwracania informacji): to, co wynik ma do powiedzenia, jest w wyniku.
8. **Pełne typowanie + sprawdzanie.** Każda funkcja z typami argumentów i wyniku; pyright/mypy w CI.
   Arność `n → m` sprawdzana przy budowie (Python nie ma typów zależnych), reszta statycznie.
9. **Efekt jest jeden i jawny: świeża tożsamość.** `Node()` i nowy element przydzielają nową tożsamość
   (w Haskellu: monada świeżych nazw). Trzymamy to tylko tam — reszta czysta.
10. **Minimalny rdzeń bez wyjątków (F16).** Nowy element = jego relacja i nic więcej; nowa analiza =
    interpretacja słownika czasu i nic więcej. Żadnych specjalnych rodzajów elementów. Jeśli dodanie
    czegoś wymaga zmian w kilku miejscach albo osobnej ścieżki, to błąd projektu.

## 6. Przegląd obecnego kodu (`src/electro`, ~5800 linii)

| problem | gdzie | kierunek |
|---|---|---|
| Elementy zmienne: wartość w konstruktorze, `Parts._use` robi `setattr`, `circuit(**data)` musi kopiować obiekt i czyścić `netlist` z cache'u | `components.py:102`, `:166`, `circuit.py` (`__call__`) | element bez wartości, frozen; dane w `Problem` |
| Prawa elementów przez dziedziczenie i metodę `build(self, label, V, param, ctx) -> Model` — każdy element sam rozpatruje DC/AC/krok; `Model` to zmienny dataclass z mutowalnymi domyślnymi słownikami | `components.py`, `devices.py` | element = jedna relacja w czasie, analizy interpretują słownik czasu (F16, §9.2) |
| Wielkie imperatywne `compile_netlist`: akumuluje listy i słowniki, w środku własny union-find | `semantics.py:122` | rozbić na małe funkcje: węzły → potencjały → prawa elementów → KCL → odniesienia |
| Union-find trzy razy | `circuit.py` (`glue`), `semantics.py` (odniesienia), `electro_schematic/model.py` (`nodes`) | jedna funkcja `components(pairs) -> partition` |
| Etykiety: automatyczne nadawanie (`_labels`) i „luźne” dopasowanie (`"R1"` znajduje `R_1`) — ukryta magia na napisach | `semantics.py:87`, `System.symbol` | tożsamość elementu (F7); nazwy parametrów jawne |
| `solve(circuit, *equations, omega, find, **given)` miesza zadanie z ustawieniami analizy; wewnętrzne ponawianie z `drop`/`assumed` | `solver.py:392`, `:466` | `solve(problem)`; ω z danych (F10) |
| `Solution` zmienny, wyszukiwanie po `str` albo obiekcie elementu | `solver.py:151` | niezmienny, zapytania typem `Sought` |
| `Context(omega, dt, t)` — pola wzajemnie wykluczające się | `components.py` | typ sum `Analysis` |
| `Simulation` trzyma i mutuje stan (`self.x`, `self.t`, `self.p`) | `sim.py:288` | `step(state) -> state`, pętla jako unfold |
| Ostrzeżenia przez `warnings.warn` jako kanał wyniku | `solver.py:440` | informacja w `Solution` |
| Typowanie: ok. połowa funkcji (~210 z ~390) bez typu wyniku, brak type-checkera | całość | §5.8 |
| Stan przełącznika itp. jako argument konstruktora (`Switch(closed=True)`) | `devices.py` | dane (F10, F11) |

## 7. Wdrożenie (etapami, każdy kończy się zielonymi testami)

1. **Rdzeń danych:** niezmienne `Element` bez wartości, `Node`, `Net`, `Given`, `Sought`, `Problem`;
   `solve`/`simulate` na `Problem`. Wartości w konstruktorach usunięte twardo; cały kod w repo
   (testy, przykłady, skrypty kursów, prompt AI, README, schemat, kernel) poprawiony. Zapisane notatki
   użytkowników ze starym kodem przestaną działać.
2. **Składanie:** `>>`, prymitywy, funkcje pochodne (`close`, `loop`, `cup`, `cap`), zasada domknięcia.
3. **Semantyka jako funkcje:** prawa elementów jako czyste funkcje, `compile_netlist` rozbity, jeden
   union-find, `Analysis` jako typ sum.
4. **Wyniki:** wspólny interfejs `Solution`/`Trace`/`Response`, symulacja jako `step` + unfold.
5. **Typy:** pełne adnotacje, pyright w CI.
6. **Generator kodu i UI:** kod ze schematu w formie `circuit = …` / `Problem(circuit, given, find)`;
   mierniki jako obserwacje (F5).

## 8. Związek z aplikacją

Notatnik już działa jak `Problem` (commit 9299796): schemat = `Circuit` (na rysunku tylko nazwy),
zakładka **Dane** = `given`, lista **Szukane** = `find` (wybrane + wszystko bez wartości), zakładka
**Wyniki** = odpowiedzi na `find`, przycisk ▶ = analiza (kartka, a gdy się da — czas). Strzałki prądu i
napięcia, punkty i prądy oczkowe na schemacie to `Sought`/`Given` przypięte do miejsca w obwodzie.
Przebudowa biblioteki ma to odzwierciedlić w kodzie, nie zmieniać zachowania.

## 9. Docelowy kod (szkic do review)

Szkic, nie implementacja — pokazuje, w co idziemy. Najpierw jak się tego używa, potem jak to jest
zbudowane w środku.

### 9.1 Użycie

```python
from electro import *

# --- obwód: sama struktura, bez liczb ---------------------------------------------------------
e  = VoltageSource("E")          # element: rodzaj + nazwa parametru; tożsamość = ten obiekt
r1 = Resistor("R_1")
r2 = Resistor("R_2")
r3 = Resistor("R_3")
b  = Node("B")                   # węzeł: tożsamość = obiekt, "B" to tylko podpis

circuit = (GND >> e >> r1 >> b) @ (b >> r2 >> GND) @ (b >> r3 >> GND)
# każdy koniec leży na węźle (GND, b) → zamknięty, typ 0 → 0

# --- zadanie: obwód + dane + szukane ------------------------------------------------------------
problem = Problem(
    circuit,
    given={e: 12, r1: 10, r2: 20, r3: 20},          # klucz = element (albo nazwa parametru: "R_1")
    find=[I(r1), U(r3), R(b, GND)],                 # szukane to typy, nie napisy
)

solution = solve(problem)
solution(I(r1))        # 600 mA
solution(U(r3))        # 6 V
solution(R(b, GND))    # 5 Ω   (widziana z B: R1 ∥ R2 ∥ R3, źródło zwarte)
solution.answers       # {I(r1): 600 mA, U(r3): 6 V, R(b, GND): 5 Ω}
solution.steps         # kroki z uzasadnieniem (jak dziś)

# --- zadanie odwrotne: dany prąd, szukany opór ---------------------------------------------------
inverse = Problem(circuit, given={e: 12, r1: 10, r2: 20, I(r1): "500 mA"}, find=[Parameter(r3)])
solve(inverse)(Parameter(r3))      # 46,67 Ω

# --- ten sam problem, inny wymiar: czas ------------------------------------------------------------
c = Capacitor("C")
rc = Problem(
    (GND >> e >> r1 >> b) @ (b >> c >> GND),
    given={e: 10, r1: "1 kΩ", c: "100 µF"},
    find=[U(c)],
)
solve(rc)(U(c))                         # 10 V      — gdzie się kończy
trace = simulate(rc, until="0.5 s")
trace(U(c))                             # Signal: funkcja czasu
trace(U(c))(0.1)                        # 6,32 V    — jak tam dochodzi

# dane z wymiarem czasu (F11): przełącznik zamknięty od 1 s, źródło sinusoidalne
s = Switch("S")
given = {s: closed_from("1 s"), e: sine(amplitude="10 V", frequency="50 Hz")}

# --- kawałek, nie zadanie (F4) ---------------------------------------------------------------------
equivalent(e >> r1)     # Thevenin(E=12 V, R=10 Ω) — widziany z końcówek

# --- wspólny parametr (F7): dwa różne rezystory, jedna wartość R ----------------------------------
ra, rb = Resistor("R"), Resistor("R")
Problem(GND >> e >> ra >> rb >> GND, given={"R": 100, e: 10}, find=[I(ra), I(rb)])

# --- kawałek wielokrotnego użytku (F13): funkcja, świeże węzły i elementy ---------------------------
def divider(top: str, bottom: str) -> Circuit:
    mid = Node()
    return Resistor(top) >> mid >> Resistor(bottom)

# --- prymitywy i funkcje pochodne -----------------------------------------------------------------
loop(e, r1, r2)          # = close(e >> r1 >> r2)
r1 | r2                  # równolegle
r1 @ r2                  # obok siebie (2 → 2)
```

### 9.2 Element: jedna relacja w czasie, analizy ją tylko interpretują

Rdzeń wie tylko o sklejaniu węzłów (KCL/KVL wynikają z niego) i o tym, że **element to relacja
między sygnałami na jego końcówkach (U, I każdej) i jego stanem wewnętrznym**, zapisana raz, w czasie.
Nic więcej. Żadnych furtek ani „specjalnych” rodzajów: rezystor, kondensator, dioda, przerzutnik,
Arduino i linia transmisyjna to ten sam mechanizm (F16).

**Słownik czasu** — całość tego, czym relacja może mówić o czasie:

| operator | znaczenie | kto go używa |
|---|---|---|
| `D(x)` | pochodna po czasie (zmiana ciągła) | kondensator, cewka |
| `Pre(x)` | wartość tuż przed chwilą obecną (pamięć) | przerzutnik, licznik, rejestr, stan procesora |
| `Delay(x, τ)` | wartość sprzed τ | linia transmisyjna, element opóźniający |
| `when(c, a, b)` | warunek | logika, zbocze (`rising(x) = x > próg ∧ Pre(x) ≤ próg`) |
| czyste funkcje | dowolne, także nieliniowe i „nieprzezroczyste” | dioda (`exp`), tranzystor, krok procesora |

**Elementy** — każdy to jedna definicja:

```python
# dwukońcówkowe: (U, I, parametr) -> wyrażenie = 0
Resistor  = two_terminal("resistor",  "R", OHM,   lambda U, I, R: U - R * I)
Capacitor = two_terminal("capacitor", "C", FARAD, lambda U, I, C: I - C * D(U))
Inductor  = two_terminal("inductor",  "L", HENRY, lambda U, I, L: U - L * D(I))
Diode     = two_terminal("diode",     "D", None,
                         lambda U, I, d: I - d.I_S * (exp(U / (d.n * V_T)) - 1), symmetric=False)
VoltageSource = two_terminal("voltage_source", "E", VOLT, lambda U, I, E: U - E, symmetric=False)

# dowolne: końcówki, stan, relacja (lista wyrażeń = 0)
DFlipFlop = element(
    "d_flip_flop", "FF", ports=("d", "clk", "q"), state=("s",),
    law=lambda p, s: [
        s.s - when(rising(p.clk.V), p.d.V > V_HIGH / 2, Pre(s.s)),   # zapamiętaj d na zboczu zegara
        p.q.V - V_HIGH * s.s,                                         # wyjście
        p.d.I, p.clk.I,                                               # wejścia nie pobierają prądu
    ],
)

Arduino = element(
    "arduino", "ARD", ports=ARDUINO_PINS, state=("cpu",),
    law=lambda p, s, firmware: [
        # stan procesora: na takcie zegara krok emulatora, poza nim bez zmian
        s.cpu - when(tick(F_CPU), mcu_step(firmware, Pre(s.cpu), read_pins(p)), Pre(s.cpu)),
        # każdy pin: to, co procesor na nim ustawia (wyjście / wejście z podciąganiem / wysoka impedancja)
        *(pin_law(p[k], drive(s.cpu, k)) for k in ARDUINO_PINS),
    ],
)

TransmissionLine = element(          # bezstratna linia: fale biegnące, opóźnienie τ, impedancja Z₀
    "line", "TL", ports=("a", "b"), state=(),
    law=lambda p, _, line: [
        p.a.V + line.Z0 * p.a.I - Delay(p.b.V - line.Z0 * p.b.I, line.tau),
        p.b.V + line.Z0 * p.b.I - Delay(p.a.V - line.Z0 * p.a.I, line.tau),
    ],
)
```

`mcu_step(firmware, state, inputs) -> state` to czysta funkcja (emulator procesora) — dla rdzenia
zwykła nieprzezroczysta funkcja w relacji. **Program to dana**, nie struktura:
`given={arduino: firmware}` — tak jak wartość rezystora (F10).

Rodzaj wywołany z nazwą daje element: `Resistor("R_1")` → `Element(kind=Resistor, name="R_1")`
(niezmienny, tożsamość = obiekt — §9.3).

**Analiza = interpretacja słownika czasu** — jedna funkcja na analizę, nie gałąź w każdym elemencie:

| analiza | `D(x)` | `Pre(x)` | `Delay(x, τ)` | wynik |
|---|---|---|---|---|
| `Step(dt)` — symulacja | (x − x⁻)/dt | wartość z poprzedniego kroku | wartość sprzed τ z historii | przebieg |
| `DC` — równowaga | 0 | x | x | relacja równowag (może mieć wiele rozwiązań albo żadnego) |
| `AC(ω)` — mały sygnał wokół równowagi | jω·x | x | e^(−jωτ)·x | charakterystyka |

```python
@dataclass(frozen=True)
class DC: ...

@dataclass(frozen=True)
class AC:
    omega: sp.Expr
    around: Solution | None = None     # punkt pracy (nieliniowe: linearyzacja wychodzi z prawa sama)

@dataclass(frozen=True)
class Step:
    dt: sp.Symbol

Analysis = DC | AC | Step

def interpret(law: Relation, analysis: Analysis) -> tuple[Relation, Memory]:
    """Relacja elementu w danej analizie: operatory czasu zastąpione; co pamiętać między krokami."""
```

Co z tego wynika:

- **Nowy element = jedna definicja** (relacja). Kartka, fazory, Bode, symulacja działają od razu.
- **Nowa analiza = jedna interpretacja słownika czasu.** Działa od razu dla każdego elementu.
- **Odpowiedzi analiz są uczciwe, a nie wyjątkami.** Przerzutnik w DC ma dwie równowagi (pamięć —
  tak jest naprawdę); działające Arduino zwykle nie ma równowagi (program się wykonuje) — `solve`
  mówi to w wyniku, a symulacja liczy przebieg. To fakty o elemencie, nie dziury w systemie.
- **Kroki rozwiązania** biorą uzasadnienie z relacji elementu („prawo R_1”, nazwa prawa z definicji).
- Jedyne założenie całości to założenie teorii obwodów: **elementy skupione** (obwód mały wobec
  długości fali, więc działają prawa Kirchhoffa). Co go łamie (linie, anteny), wchodzi jako element
  z `Delay` — dalej bez wyjątków.

### 9.3 Obwód: niezmienne drzewo, operatory jako cukier

```python
@dataclass(frozen=True)
class Circuit:
    """n → m. Podklasy to konstruktory typu sum: Element, Wire, Swap, Spider, Node, Net, Seq, Tensor."""

    def __rshift__(self, other: Circuit) -> Circuit: return series(self, other)
    def __or__(self, other: Circuit) -> Circuit:     return parallel(self, other)
    def __matmul__(self, other: Circuit) -> Circuit: return beside(self, other)


@dataclass(frozen=True)
class Seq(Circuit):
    first: Circuit
    then: Circuit

@dataclass(frozen=True)
class Tensor(Circuit):
    left: Circuit
    right: Circuit

@dataclass(frozen=True)
class Spider(Circuit):          # n końców sklejonych w jeden punkt
    dom: int
    cod: int

@dataclass(frozen=True, eq=False)
class Node(Circuit):            # punkt z tożsamością; 1 → 1, jego końce nie są wolne
    label: str | None = None

@dataclass(frozen=True)
class Net(Circuit):             # globalna sieć: wszystkie Net("VCC") to jeden węzeł (F8)
    name: str

GND = Net("GND")


# --- funkcje pochodne: z prymitywów, bez magii ---
wire = Spider(1, 1)
cup, cap = Spider(2, 0), Spider(0, 2)

def series(*parts: Circuit) -> Circuit:       return reduce(Seq, parts)
def beside(*parts: Circuit) -> Circuit:       return reduce(Tensor, parts)
def parallel(f: Circuit, g: Circuit) -> Circuit:
    return split(arity(f).dom) >> (f @ g) >> merge(arity(f).cod)
def close(f: Circuit) -> Circuit:             return cap >> (f @ wire) >> cup
def loop(*parts: Circuit) -> Circuit:         return close(series(*parts))


# --- typ: liczony, nie przechowywany ---
@dataclass(frozen=True)
class Arity:
    dom: int
    cod: int

def arity(c: Circuit) -> Arity: ...        # wszystkie końce (do składania)
def free(c: Circuit) -> Arity: ...         # końce, które nie leżą na węźle (do zasady domknięcia)
def is_closed(c: Circuit) -> bool:  return free(c) == Arity(0, 0)


# --- postać normalna: czysta funkcja przez dopasowanie wzorca ---
@cache                                      # wolno: wszystko niezmienne i hashowalne
def netlist(c: Circuit) -> Netlist:
    match c:
        case Element():        return Netlist.of_element(c)
        case Seq(f, g):        return glue_series(netlist(f), netlist(g))
        case Tensor(f, g):     return disjoint(netlist(f), netlist(g))
        case Spider(n, m):     return Netlist.point(n, m)
        case Node() | Net():   return Netlist.point(1, 1, at=c)
```

### 9.4 Zadanie

```python
# wielkości: o co można pytać i co można zadać (F2, F7) — typy, nie napisy
@dataclass(frozen=True)
class Current:   of: Element
@dataclass(frozen=True)
class Voltage:   of: Element
@dataclass(frozen=True)
class Power:     of: Element
@dataclass(frozen=True)
class Parameter: of: Element          # wartość elementu
@dataclass(frozen=True)
class Potential: at: Node | Net
@dataclass(frozen=True)
class Across:    a: Node | Net; b: Node | Net      # napięcie między punktami
@dataclass(frozen=True)
class Resistance: a: Node | Net; b: Node | Net     # rezystancja zastępcza między punktami

Quantity = Current | Voltage | Power | Parameter | Potential | Across | Resistance
Sought = Quantity

# krótkie konstruktory, jak w podręczniku
def I(e: Element) -> Current: return Current(e)
def U(x: Element | Node, y: Node | None = None) -> Voltage | Across: ...
def P(e: Element) -> Power: return Power(e)
def V(n: Node | Net) -> Potential: return Potential(n)
def R(a: Node | Net, b: Node | Net) -> Resistance: return Resistance(a, b)

# dane: wartość może być liczbą, napisem z jednostką albo funkcją czasu (F11)
Value = sp.Expr | str | int | float | Signal

@dataclass(frozen=True)
class Problem:
    circuit: Circuit
    given: Mapping[Element | str | Quantity, Value]   # element / nazwa parametru → wartość; wielkość → warunek
    find: tuple[Sought, ...] = ()

    def __post_init__(self) -> None:
        # walidacja przy budowie, nie przy rozwiązywaniu
        if not is_closed(self.circuit):
            raise NotClosed(free(self.circuit))
        check_units(self.circuit, self.given)       # F14: R_1 = 5 V → BadUnit
        check_names(self.circuit, self.given)       # nazwa, której nie ma → NoSuchParameter
```

### 9.5 Analizy i wyniki

```python
def solve(problem: Problem) -> Solution:
    analysis = steady_analysis(problem)              # DC albo AC(ω) — ω z danych źródeł (F10)
    system = equations(problem, analysis)            # czysta: obwód + dane → układ równań
    return solve_system(system, problem.find)        # w środku sympy (imperatywnie, za czystym interfejsem)


@dataclass(frozen=True)
class Solution:
    problem: Problem
    values: Mapping[sp.Symbol, sp.Expr]
    steps: tuple[Step, ...]
    undetermined: tuple[Sought, ...]                 # zamiast warnings.warn: wynik mówi sam

    def __call__(self, q: Quantity) -> Measure: ...  # liczba z jednostką
    @property
    def answers(self) -> Mapping[Sought, Measure]: ...


def simulate(problem: Problem, until: Duration) -> Trace:
    program = compile_program(problem)               # czysta: równania jednego kroku → kod
    states = unfold(partial(step, program), initial(program), until)
    return Trace(problem, tuple(states))


def step(program: Program, state: State) -> State:   # czysta: nowy stan ze starego
    ...                                              # Newton w środku: pętla lokalna, nic wspólnego


@dataclass(frozen=True)
class Trace:
    problem: Problem
    states: tuple[State, ...]

    def __call__(self, q: Quantity) -> Signal: ...   # funkcja czasu


def respond(problem: Problem) -> Response: ...       # Response(q) → funkcja ω
def equivalent(part: Circuit) -> Thevenin: ...       # kawałek 1 → 1 widziany z końcówek
```

To samo pytanie (`result(U(c))`) do każdego wyniku, różny wymiar odpowiedzi: `Measure`
(liczba), `Signal` (t ↦ wartość), funkcja ω (F12).

### 9.6 Kod generowany ze schematu

```python
# Zadanie 8 (wygenerowane z rysunku)
e_1, r_1, r_2, r_3 = VoltageSource("E_1"), Resistor("R_1"), Resistor("R_2"), Resistor("R_3")
n_1 = Node()

circuit = (GND >> e_1 >> r_1 >> n_1) @ (n_1 >> r_2 >> GND) @ (n_1 >> r_3 >> GND)
problem = Problem(
    circuit,
    given={e_1: 12, r_1: 10, r_2: 20},          # zakładka Dane
    find=[Parameter(r_3), U(r_2)],              # Szukane (r_3 bez wartości — dopisane samo)
)
solution = solve(problem)
```

## 10. Ryzyka (spisane po review — patrz też §11)

1. **Problem bez zgłoszenia.** Opóźnienie odczytu pinów Arduino (1 ms) nie psuje żadnej znanej
   notatki; warianty synchronizacji (dziennik + cofanie, leniwy obwód) czekają na konkretny przykład.
   Most `chip.ts` + `session.ts` zostaje.
2. **Zapisane notatki użytkowników.** Usunięcie wartości z konstruktorów psuje kod w notatkach na
   produkcji — potrzebna migracja (przepisanie kodu przy otwarciu), nie samo „twarde usunięcie”.
3. **Koszt bez zmiany dla użytkownika.** Przebudowa to inwestycja; trzeba ją świadomie postawić
   przed innymi pracami.
4. **Ogólny silnik a zbieżność.** Dziś dioda ma ręczne sztuczki dla Newtona; ogólny silnik musi je
   odtworzyć ogólnie, inaczej symulacje zaczną zgłaszać `NoConvergence`.
5. **Synchronizacja z emulatorem**: zostaje wykonaniem (most), nie modelem — patrz 1.

## 11. Prototyp rdzenia (`src/electro/core`, testy `tests/test_core.py`)

Obok biblioteki, nic w niej nie zmienia. ~720 linii (bez eksportów): składnia + postać normalna
(`syntax.py`), zadanie + analizy (`problem.py`), zapis do danych (`data.py`).

**Co pokazał (12 testów):**

- Zamykanie węzłem, masą i `close` (z `cup`/`cap`) daje to samo; równoległe przez wspólne węzły = `|`.
- Element = jedno prawo z `D`: RC na kartce (DC: 10 V), w czasie (6,32 V po τ) i fazorem (|U| = E/√2)
  z jednej definicji; nowy rodzaj (konduktancja) dopisany w teście jedną linijką działa w DC i AC.
- Zadanie odwrotne, wspólny parametr (dwa „R”), `NotClosed`, `NoSuchParameter`.
- **Ryzyko z review: sklejanie przez `>>`** — rozwiązane regułą: `>>` nie skleja dwóch różnych
  węzłów (`JoinsNodes`); ósemkę pisze się przez `@` i wspólny węzeł. Jeden element w dwóch miejscach:
  `ElementTwice`. Błędy przy budowie, nie przy pierwszym użyciu (każde `>>`/`@` liczy postać
  normalną od razu; zapamiętaną).
- **Ryzyko z review: tożsamość a zapis** — mniejsze, niż się zdawało: w pamięci element i węzeł są
  sobą, w danych mają pozycję na liście (element) i numer (punkt); odczytane wracają jako świeże
  obiekty, zadanie rozwiązuje się tak samo (test). Nazwy potrzebne są tylko na granicy.
- Złapany błąd: podpis węzła trafiał do nazwy symbolu — dwa `Node("B")` zlewały się w równaniach.
  Poprawione (podpis tylko, gdy jedyny) i dodany test: dokładnie ta klasa błędów, przed którą
  chroni tożsamość obiektu.
- **Typy:** pyright (tryb zwykły) bez błędów. Tryb ścisły blokuje głównie brak stubów sympy
  (zamknięte w trzech funkcjach pomocniczych w `problem.py`) i niezatypowany JSON w `data.py`
  (do zrobienia: `TypedDict`).

**Czego nie ma (żeby nie porównywać jabłek z gruszkami):** kroki z uzasadnieniem, diagnoza braków
(`MissingData`), dziury (`Hole`), mierniki, jednostki (F14), elementy nieliniowe i wielokońcówkowe,
własne komponenty, Thévenin, szybka symulacja (dziś: sympy co krok, wolne), stan dyskretny (`Pre`).
Dopiero z nimi da się uczciwie porównać rozmiar i prostotę z obecną biblioteką.

**Następne kroki prototypu, w kolejności ryzyka:** dioda (nieliniowość, Newton bez ręcznych
sztuczek) → przerzutnik (`Pre`, zdarzenia) → kroki rozwiązania (czy uzasadnienia z praw wystarczą)
→ jednostki → porównanie z obecną biblioteką na jej testach.

## 12. Otwarte

- Jak pokazać `Given` z wymiarem czasu w zakładce Dane (przełącznik od 1 s, przebieg z pliku).
- `Net` a etykiety na schemacie: czy każda etykieta to `Net`, czy tylko jawnie globalne.
- Element wielokońcówkowy (tranzystor, wzmacniacz) a `Sought`: o które prądy końcówek pytać.
