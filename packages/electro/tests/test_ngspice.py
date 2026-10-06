"""Against ngspice: the same circuits, the same numbers — point potentials in DC, AC and in time, linear and
not. Each circuit written twice: with the combinators, and as ngspice's netlist (skipped where there is no
ngspice; it is in devenv)."""

import math
import re
import shutil
import subprocess
from functools import reduce
from operator import matmul

import pytest
from electro import (
    AC,
    BJT_PARTS,
    CCCS,
    CCVS,
    GND,
    NPN,
    VCCS,
    VCVS,
    Capacitor,
    Coupled,
    CurrentSource,
    Diode,
    Inductor,
    Node,
    OpAmp,
    Problem,
    Resistor,
    V,
    VoltageSource,
    simulate,
    solve,
)

NGSPICE = shutil.which("ngspice")
pytestmark = pytest.mark.skipif(NGSPICE is None, reason="no ngspice on PATH")


def run(deck: str, tail: str, tmp_path) -> str:
    path = tmp_path / "deck.cir"
    path.write_text(f"* test\n{deck}\n.control\nset numdgt=12\n{tail}\n.endc\n.end\n")
    return subprocess.run([NGSPICE, "-b", str(path)], capture_output=True, text=True, timeout=60).stdout


def ngspice(deck: str, analysis: str, nodes: list[str], tmp_path) -> dict[str, complex]:
    """``nodes``' potentials after ``analysis`` (``op``, ``ac lin 1 f f``), as ngspice prints them."""
    out = run(deck, f"{analysis}\nprint {' '.join(f'v({n})' for n in nodes)}", tmp_path)
    values = {
        name: complex(float(re_), float(im or 0))
        for name, re_, im in re.findall(r"^v\((\w+)\) = ([-+\d.e]+)(?:,([-+\d.e]+))?$", out, re.M)
    }
    assert set(values) == {n.lower() for n in nodes}, out
    return values


def points(*names: str) -> list[Node]:
    return [Node(n) for n in names]


def divider():
    t, a = points("T", "A")
    e, r1, r2 = VoltageSource("E"), Resistor("R_1"), Resistor("R_2")
    circuit = (GND >> e >> t) @ (t >> r1 >> a) @ (a >> r2 >> GND)
    return Problem(circuit, {e: 12, r1: "1k", r2: "2.2k"}), {"A": a}, "V1 T 0 12\nR1 T A 1k\nR2 A 0 2.2k"


def bridge():
    t, a, b = points("T", "A", "B")
    e, r = VoltageSource("E"), [Resistor(f"R_{k}") for k in range(1, 6)]
    circuit = (
        (GND >> e >> t)
        @ (t >> r[0] >> a)
        @ (t >> r[1] >> b)
        @ (a >> r[2] >> GND)
        @ (b >> r[3] >> GND)
        @ (a >> r[4] >> b)
    )
    values = dict(zip(r, (100, 220, 330, 470, 1000), strict=True))
    deck = "V1 T 0 10\nR1 T A 100\nR2 T B 220\nR3 A 0 330\nR4 B 0 470\nR5 A B 1000"
    return Problem(circuit, {e: 10, **values}), {"A": a, "B": b}, deck


def grid(n: int = 4):
    p = {(i, j): Node(f"n{i}_{j}") for i in range(n) for j in range(n)}
    e, end = VoltageSource("E"), Resistor("R_end")
    pieces, given, deck = [GND >> e >> p[0, 0], p[n - 1, n - 1] >> end >> GND], {e: 10, end: 50}, []
    deck = ["V1 n0_0 0 10", f"Rend n{n - 1}_{n - 1} 0 50"]
    for i in range(n):
        for j in range(n):
            for di, dj, base, step, name in ((1, 0, 100, 7 * i, "v"), (0, 1, 220, 13 * j, "h")):
                if i + di < n and j + dj < n:
                    r = Resistor(f"R{name}{i}{j}")
                    pieces.append(p[i, j] >> r >> p[i + di, j + dj])
                    given[r] = base + step
                    deck.append(f"R{name}{i}{j} n{i}_{j} n{i + di}_{j + dj} {base + step}")
    shown = {f"n{i}_{j}": p[i, j] for i, j in ((3, 3), (1, 2), (2, 1))}
    return Problem(reduce(matmul, pieces), given), shown, "\n".join(deck)


def current_source():
    a, b = points("A", "B")
    j, r1, r2 = CurrentSource("J"), Resistor("R_1"), Resistor("R_2")
    circuit = (GND >> j >> a) @ (a >> r1 >> b) @ (b >> r2 >> GND)
    return Problem(circuit, {j: "10m", r1: 1000, r2: 500}), {"A": a, "B": b}, "I1 0 A 10m\nR1 A B 1000\nR2 B 0 500"


def inverting_amplifier():
    inn, x, out = points("IN", "X", "OUT")
    e, r1, r2, rl, oa = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Resistor("R_L"), OpAmp("OA")
    circuit = (GND >> e >> inn) @ (inn >> r1 >> x) @ (x >> r2 >> out) @ (oa >> (GND @ x @ out)) @ (out >> rl >> GND)
    deck = "V1 IN 0 1\nR1 IN X 1k\nR2 X OUT 10k\nE1 OUT 0 0 X 1e6\nRL OUT 0 2k"
    return Problem(circuit, {e: 1, r1: "1k", r2: "10k", rl: "2k"}), {"OUT": out}, deck


def controlled_sources():
    a, b, c = points("A", "B", "C")
    e, r1, r2, r3, k1, k2 = (
        VoltageSource("E"),
        Resistor("R_1"),
        Resistor("R_2"),
        Resistor("R_3"),
        VCVS("K_1"),
        VCCS("K_2"),
    )
    circuit = (
        (GND >> e >> a)
        @ (a >> r1 >> GND)
        @ (k1 >> (a @ GND @ GND @ b))
        @ (b >> r2 >> GND)
        @ (k2 >> (a @ GND @ GND @ c))
        @ (c >> r3 >> GND)
    )
    deck = "V1 A 0 2\nR1 A 0 100\nE1 B 0 A 0 3\nR2 B 0 200\nG1 0 C A 0 10m\nR3 C 0 300"
    return Problem(circuit, {e: 2, r1: 100, k1: 3, r2: 200, k2: "10m", r3: 300}), {"B": b, "C": c}, deck


def current_controlled_sources():
    a, b, c, x, y = points("A", "B", "C", "X", "Y")
    e, f1, h1 = VoltageSource("E"), CCCS("F_1"), CCVS("H_1")
    r1, r2, r3, r4 = (Resistor(f"R_{k}") for k in range(1, 5))
    circuit = (
        (GND >> e >> a)
        @ (f1 >> (a @ x @ GND @ b))
        @ (x >> r1 >> GND)
        @ (b >> r2 >> GND)
        @ (h1 >> (b @ y @ GND @ c))
        @ (y >> r3 >> GND)
        @ (c >> r4 >> GND)
    )
    deck = "V1 A 0 2\nVsF A X 0\nF1 0 B VsF 3\nR1 X 0 10\nR2 B 0 200\nVsH B Y 0\nH1 C 0 VsH 50\nR3 Y 0 40\nR4 C 0 300"
    given = {e: 2, f1: 3, r1: 10, r2: 200, h1: 50, r3: 40, r4: 300}
    return Problem(circuit, given), {"B": b, "C": c, "X": x}, deck


LINEAR_DC = {
    "divider": divider,
    "bridge": bridge,
    "grid": grid,
    "current source": current_source,
    "inverting amplifier": inverting_amplifier,
    "controlled sources": controlled_sources,
    "current-controlled sources": current_controlled_sources,
}


@pytest.mark.parametrize("name", LINEAR_DC)
def test_dc_matches_ngspice(name, tmp_path):
    problem, nodes, deck = LINEAR_DC[name]()
    sol = solve(problem)
    spice = ngspice(deck, "op", list(nodes), tmp_path)
    rel = 5e-5 if "amplifier" in name else 1e-9  # ngspice's op-amp here: a gain of 10⁶, not ∞
    for n, p in nodes.items():
        assert float(sol(V(p))) == pytest.approx(spice[n.lower()].real, rel=rel, abs=1e-12)


def rc():
    t, a = points("T", "A")
    e, r, c = VoltageSource("E"), Resistor("R"), Capacitor("C")
    return (
        Problem((GND >> e >> t) @ (t >> r >> a) @ (a >> c >> GND), {e: 1, r: "1k", c: "1u"}),
        {"A": a},
        ("V1 T 0 DC 1 AC 1\nR1 T A 1k\nC1 A 0 1u"),
    )


def rlc():
    t, a, b = points("T", "A", "B")
    e, r, ll, c = VoltageSource("E"), Resistor("R"), Inductor("L"), Capacitor("C")
    circuit = (GND >> e >> t) @ (t >> r >> a) @ (a >> ll >> b) @ (b >> c >> GND)
    deck = "V1 T 0 DC 1 AC 1\nR1 T A 10\nL1 A B 10m\nC1 B 0 1u"
    return Problem(circuit, {e: 1, r: 10, ll: "10m", c: "1u"}), {"A": a, "B": b}, deck


def coupled():
    a, b, c = points("A", "B", "C")
    e, r1, r2, m = VoltageSource("E"), Resistor("R_1"), Resistor("R_2"), Coupled("M")
    circuit = (GND >> e >> a) @ (a >> r1 >> b) @ (m >> (b @ GND @ GND @ c)) @ (c >> r2 >> GND)
    k = 1e-3 / math.sqrt(2e-3 * 3e-3)
    deck = f"V1 A 0 DC 1 AC 1\nR1 A B 1\nLa B 0 2m\nLb C 0 3m\nK1 La Lb {k:.12g}\nR2 C 0 100"
    return Problem(circuit, {e: 1, r1: 1, r2: 100, m: {"": "1m", "L1": "2m", "L2": "3m"}}), {"B": b, "C": c}, deck


AC_CIRCUITS = {"rc": rc, "rlc": rlc, "coupled": coupled}


@pytest.mark.parametrize("name", AC_CIRCUITS)
@pytest.mark.parametrize("f", [50, 1591.55, 20_000])
def test_ac_matches_ngspice(name, f, tmp_path):
    problem, nodes, deck = AC_CIRCUITS[name]()
    sol = solve(problem, AC(2 * math.pi * f))
    spice = ngspice(deck, f"ac lin 1 {f} {f}", list(nodes), tmp_path)
    for n, p in nodes.items():
        assert complex(sol(V(p))) == pytest.approx(spice[n.lower()], rel=1e-6, abs=1e-12)


def test_rc_in_time_matches_ngspice(tmp_path):
    t, a = points("T", "A")
    e, r, c = VoltageSource("E"), Resistor("R"), Capacitor("C")
    problem = Problem((GND >> e >> t) @ (t >> r >> a) @ (a >> c >> GND), {e: 5, r: "1k", c: "1u"})
    data = tmp_path / "out.txt"
    run("V1 T 0 5\nR1 T A 1k\nC1 A 0 1u", f"tran 2u 4m uic\nwrdata {data} v(A)", tmp_path)
    rows = [tuple(map(float, line.split()[:2])) for line in data.read_text().splitlines() if line.strip()]
    ours = simulate(problem, until=4e-3)
    for at in (0.2e-3, 1e-3, 3e-3):
        theirs = min(rows, key=lambda row: abs(row[0] - at))[1]
        assert ours.at(V(a), at) == pytest.approx(theirs, rel=0.01)


def diode():
    t, a = points("T", "A")
    e, r, d = VoltageSource("E"), Resistor("R"), Diode("D")
    deck = "V1 T 0 5\nR1 T A 430\nD1 A 0 D1N4148\n.model D1N4148 D(IS=2.52e-09 N=1.752)"
    return (
        Problem((GND >> e >> t) @ (t >> r >> a) @ (a >> d >> GND), {e: 5, r: 430, d: {"I_S": 2.52e-9, "n": 1.752}}),
        {"A": a},
        deck,
    )


def transistor():
    vcc, b, c = points("VCC", "B", "C")
    e, rb, rc_, q = VoltageSource("E"), Resistor("R_B"), Resistor("R_C"), NPN("Q")
    circuit = (GND >> e >> vcc) @ (vcc >> rb >> b) @ (vcc >> rc_ >> c) @ (q >> (b @ c @ GND))
    model = " ".join(f"{k}={v}" for k, v in BJT_PARTS["BC547B"].items())
    deck = f"V1 VCC 0 9\nRB VCC B 100k\nRC VCC C 1k\nQ1 C B 0 QBC\n.model QBC NPN({model})"
    return Problem(circuit, {e: 9, rb: "100k", rc_: "1k", q: BJT_PARTS["BC547B"]}), {"B": b, "C": c}, deck


NONLINEAR = {"1N4148 and a resistor": diode, "BC547B with a base resistor": transistor}


@pytest.mark.parametrize("name", NONLINEAR)
def test_nonlinear_operating_point_matches_ngspice(name, tmp_path):
    """Ours settle in time; theirs is the operating point."""
    problem, nodes, deck = NONLINEAR[name]()
    trace = simulate(problem, until=5e-3)
    spice = ngspice(deck, "op", list(nodes), tmp_path)
    for n, p in nodes.items():
        assert trace(V(p))[-1] == pytest.approx(spice[n.lower()].real, rel=2e-3, abs=2e-3)
