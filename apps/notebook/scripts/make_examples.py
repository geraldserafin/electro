"""Builds apps/notebook/examples/nieznane-i-dziury.electro.json (run from the repo root with PYTHONPATH set, e.g. in devenv shell)."""
import json, secrets
from electro import Ammeter, Hole, Resistor, VoltageSource, loop
from electro_schematic import layout

cells = []
md = lambda text: cells.append({"id": secrets.token_hex(4), "type": "markdown", "source": text.strip()})
code = lambda text: cells.append({"id": secrets.token_hex(4), "type": "code", "source": text.strip(), "outputs": []})
drawing = lambda name, circuit, data="", simulate=False: cells.append({
    "id": secrets.token_hex(4), "type": "schematic", "name": name,
    "schematic": json.loads(layout(circuit).to_json()), "data": data, "simulate": simulate})

md("""
Każdy przykład to osobna komórka — uruchom wszystko przyciskiem **▶ Uruchom wszystko** albo pojedynczo (`Shift+Enter`).
Wartość elementu, której nie znasz, zostawiasz pustą: `Resistor()`. Solver szuka jej z dodatkowych danych
(`I_R_1=…`, `U_R_2=…`, `P_R_1=…`). Każda niewiadoma potrzebuje jednej **niezależnej** danej.
""")

md("## 1. Nieznany opór z pomiaru napięcia")
code("""
dzielnik = supply(12) + Resistor(100) + Resistor() + ground
sol = dzielnik.solve(U_R_2=4, find="R_2")
steps(sol)
""")

md("""
## 2. Nieznane źródło
Napięcie źródła też może być niewiadomą. Tu wychodzi dodatnie — źródło jest skierowane tak, jak je narysowaliśmy.
""")
code("""
petla = loop(VoltageSource(), Resistor(10), Resistor(20))
petla.solve(I_R_1="0,5", find="E_1")
""")

md("""
## 3. Minus w wyniku = odwrotna polaryzacja
Dwa źródła w jednej pętli. Prąd 2 A przez 4 Ω daje 8 V, a pierwsze źródło ma 12 V — więc drugie musi
*odbierać* 4 V. Ujemny wynik znaczy: to źródło jest w rzeczywistości skierowane odwrotnie niż w zapisie.
""")
code("""
dwa_zrodla = loop(VoltageSource(12), Resistor(4), VoltageSource())
dwa_zrodla.solve(I_R_1=2, find="E_2")
""")

md("""
## 4. Kilka niewiadomych naraz
Trzy niewiadome (R₁, R₃, E₂) i trzy pomiary. Gałęzie są czytane od masy w górę, a `.transpose()` przy R₂ i R₃
sprawia, że ich napięcie i prąd liczymy „w dół” — tak, jak mierzyliśmy.
""")
code("""
uklad = (
    (VoltageSource(12) + Resistor())
    | Resistor(4).transpose()
    | ((Resistor().transpose() | CurrentSource(1)) + VoltageSource().transpose())
)
sol = uklad.solve(I_R_1=2, U_R_2=8, U_R_3=5, find=["R_1", "R_3", "E_2"])
display(schematic(uklad, sol))
sol
""")

md("""
### 4a. Uwaga na zwrot pomiaru
Ten sam układ **bez** `.transpose()` przy R₂ i R₃ liczy ich napięcia w górę. Te same liczby oznaczają wtedy
co innego — i przestają do siebie pasować. Znak danej zależy od kierunku elementu.
""")
code("""
bez_transpose = (
    (VoltageSource(12) + Resistor())
    | Resistor(4)
    | ((Resistor() | CurrentSource(1)) + VoltageSource().transpose())
)
try:
    bez_transpose.solve(I_R_1=2, U_R_2=8, U_R_3=5)
except CircuitError as e:
    print(e)

bez_transpose.solve(I_R_1=2, U_R_2=-8, U_R_3=-5, find=["R_1", "R_3", "E_2"])  # te same pomiary „w górę”
""")

md("""
## 5. Za mało danych
Bez pomiaru na R₃ solver nie zgaduje — mówi, ilu danych brakuje i które wystarczą.
""")
code("""
try:
    uklad.solve(I_R_1=2, U_R_2=8, find=["R_1", "R_3", "E_2"])
except MissingData as e:
    print(e)
    print("Udało się wyznaczyć:", e.solution.answers["R_1"], "Ω")
""")

md("""
## 6. Dane, które niczego nie wnoszą
Przy znanym R₂ = 4 Ω napięcie 4 V i prąd 1 A na R₂ to **ta sama** informacja. Dwie dane, ale jedna wiedza —
więc przy dwóch niewiadomych dalej czegoś brakuje.
""")
code("""
try:
    (supply() + Resistor() + Resistor(4) + ground).solve(U_R_2=4, I_R_2=1, find=["E_1", "R_1"])
except MissingData as e:
    print(e)
""")

md("## 7. Sprzeczne dane\nSolver wskazuje, które dane się wykluczają.")
code("""
try:
    (supply(12) + Resistor(10) + Resistor(20) + ground).solve(I_R_1=1)
except Contradiction as e:
    print(e)
""")

md("""
## 8. Dwa rozwiązania
Moc to $P = U \\cdot I$ — równanie kwadratowe. Opornik 2 Ω i 8 Ω dają w tej pętli tę samą moc 8 W.
Jedna dodatkowa równość rozstrzyga.
""")
code("""
dwa = loop(VoltageSource(12), Resistor(), Resistor(4))
try:
    dwa.solve(P_R_1=8, find="R_1")
except Ambiguous as e:
    print(e)

dwa.solve(Eq(P("R_1"), 8), Eq(U("R_1"), 2 * U("R_2")), find="R_1")  # R₁ ma dwa razy więcej napięcia niż R₂
""")

md("## 9. Wynik literowy\nZamiast liczby — litera. Wynik wychodzi jako wzór.")
code("""
(supply("E") + Resistor("R_a") + Resistor("R_b") + ground).solve(find="U_R_2")
""")

md("## 10. Mostek z niewiadomą (nie da się zapisać przez `+` i `|`)")
code("""
mostek = net(
    (VoltageSource(10), "0", "A"),
    (Resistor(100), "A", "B"), (Resistor(), "B", "0"),
    (Resistor(50), "A", "C"), (Resistor(100), "C", "0"),
    (Ammeter(), "B", "C"),
)
mostek.solve(I_A_1=0, find="R_2")
""")

md("## 11. Nieznane źródło prądu")
code("""
rownolegle = net((CurrentSource(), "0", "A"), (Resistor(10), "A", "0"), (Resistor(40), "A", "0"))
rownolegle.solve(U_R_1=8, find="J_1")
""")

md("""
# Dziury: `Hole()`
Dziura to element, o którym nie wiemy nawet, **czym** jest. Każdy liniowy dwójnik to źródło $E$ szeregowo
z oporem $Z$, ale z jednego pomiaru nie da się ich rozdzielić — więc solver bierze **najprostszy** pasujący
element: rezystor, potem przerwę, potem źródło. Przyjęte założenie widać w rozwiązaniu.
""")

md("""
## 12. Dziura → rezystor
Żarówka 12 Ω ma dostać 0,5 A z akumulatora 12 V. Co wstawić? Na schemacie wpisz pomiar w **Dane pomiarowe**
i kliknij **Symuluj** — albo policz to kodem, jak niżej.
""")
drawing("zarowka", loop(VoltageSource(12), Resistor(12), Hole()), "I_R_1 = 0,5")
code("""
zarowka = schemat("zarowka").to_circuit()
sol = zarowka.solve(I_R_1="0,5")
display(schematic(schemat("zarowka"), sol))
steps(sol)
""")

md("## 13. Dziura → źródło\nPrąd płynie „pod prąd” akumulatora (−1 A) — żaden opornik tego nie zrobi, to musi być ładowarka.")
code("""
ladowanie = loop(VoltageSource(12), Resistor(2), Hole())
sol = ladowanie.solve(I_R_1=-1)
sol["X_1"]
""")

md("## 14. Dziura → przewód\nCałe 12 V odkłada się na 10 Ω (1,2 A) — w dziurze nie ma żadnego spadku napięcia.")
code("""
loop(VoltageSource(12), Resistor(10), Hole()).solve(I_R_1="1,2")["X_1"]
""")

md("## 15. Dziura → przerwa\nPrąd nie płynie wcale, a całe napięcie jest na dziurze.")
code("""
przerwa = loop(VoltageSource(12), Resistor(10), Hole())
sol = przerwa.solve(I_R_1=0)
print(sol["X_1"])
print(code(przerwa.fill(sol)))  # po wstawieniu przerwy pętla przestaje być pętlą
""")

md("""
## 16. Dwie dziury w szeregu
Znając tylko prąd, nie da się rozdzielić, ile napięcia przypada na którą dziurę. Jedno napięcie więcej — i już.
""")
code("""
dwie = loop(VoltageSource(12), Hole(), Hole())
try:
    dwie.solve(I_E_1=1, find="U_X_1")
except MissingData as e:
    print(e)

sol = dwie.solve(I_E_1=1, U_X_1=5)
sol["X_1"], sol["X_2"]
""")

md("## 17. Dziura i zwykła niewiadoma naraz")
code("""
sol = loop(VoltageSource(12), Resistor(), Hole()).solve(I_E_1=1, U_R_1=4)
sol
""")

md("""
## 18. Pomiar na schemacie: amperomierz z odczytem
Zadanie: $I_2 = 2\\,\\mathrm{A}$, $R_1 = 3\\,Ω$, $R_2 = 18\\,Ω$, $R_3 = 3\\,Ω$, $R_4 = 6\\,Ω$ — jakie jest napięcie
zasilające i rezystancja zastępcza? Znany prąd to **amperomierz z odczytem** `Ammeter(2)`: dana pomiarowa, a nie źródło
prądu (`CurrentSource(2)` wymusza prąd, ale jego napięcie byłoby kolejną niewiadomą). Amperomierz bez odczytu
(`Ammeter()`) solver sam „odczyta”. W edytorze odczyt wpisujesz w polu **Odczyt** amperomierza.
""")
drawing("zadanie4", loop(VoltageSource(label="E"), Resistor(3),
                         (Resistor(18) + Ammeter(2)) | (Resistor(3) + Resistor(6))), simulate=True)
code("""
obciazenie = Resistor(3) + ((Resistor(18) + Ammeter(2)) | (Resistor(3) + Resistor(6)))
zadanie = loop(VoltageSource(label="E"), obciazenie)
print("Rz =", resistance(obciazenie), "Ω")  # odczyt amperomierza nie zmienia rezystancji
zadanie.solve(find="E")
""")

# run every cell (like "Uruchom wszystko") and keep the outputs, so the example opens with its results
from electro_notebook import kernel

kernel.reset()
schematics = {c["name"]: json.dumps(c["schematic"]) for c in cells if c["type"] == "schematic"}
for cell in cells:
    if cell["type"] == "code":
        cell["outputs"] = json.loads(kernel.run(cell["source"], json.dumps(schematics)))
    if cell["type"] == "schematic" and (cell.pop("simulate") or cell["data"]):  # as if "Symuluj" was clicked
        cell.update(json.loads(kernel.simulate(json.dumps(cell["schematic"]), cell["data"])), stale=False)

notebook = {"version": 1, "title": "Przykłady: niewiadome i dziury", "codeInPdf": True, "cells": cells}
path = "apps/notebook/examples/nieznane-i-dziury.electro.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(notebook, f, ensure_ascii=False, indent=2)
print(path, len(cells), "cells")
