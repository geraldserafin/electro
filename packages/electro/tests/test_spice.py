"""Against ngspice: the same circuits, the same numbers — node voltages in DC, AC and in time,
linear and not. Skipped where there is no ngspice (it is in devenv).

Also the netlists both ways: ``to_spice`` then ``from_spice`` gives the same circuit back."""

import math
import re
import shutil
import subprocess

import pytest
import sympy as sp
from electro import *
from electro.spice import from_spice, to_spice

NGSPICE = shutil.which("ngspice")
needs_ngspice = pytest.mark.skipif(NGSPICE is None, reason="no ngspice on PATH")


def ngspice(c, analysis: str, nodes: list[str], tmp_path) -> dict[str, complex]:
    """``nodes``' voltages after ``analysis`` (``op``, ``ac lin 1 f f``), as ngspice prints them."""
    deck = tmp_path / "deck.cir"
    shown = " ".join(f"v({n})" for n in nodes)
    deck.write_text(to_spice(c) + f".control\nset numdgt=12\n{analysis}\nprint {shown}\n.endc\n.end\n")
    out = subprocess.run([NGSPICE, "-b", str(deck)], capture_output=True, text=True, timeout=60).stdout
    values = {}
    for name, re_, im in re.findall(r"^v\((\w+)\) = ([-+\d.e]+)(?:,([-+\d.e]+))?$", out, re.M):
        values[name] = complex(float(re_), float(im or 0))
    assert set(values) == {n.lower() for n in nodes}, out
    return values


def ngspice_tran(c, t_end: float, node: str, at: list[float], tmp_path) -> list[float]:
    deck, data = tmp_path / "deck.cir", tmp_path / "out.txt"
    step = t_end / 2000
    deck.write_text(to_spice(c) + f".control\ntran {step} {t_end} uic\nwrdata {data} v({node})\n.endc\n.end\n")
    subprocess.run([NGSPICE, "-b", str(deck)], capture_output=True, timeout=60, check=True)
    rows = [tuple(map(float, line.split()[:2])) for line in data.read_text().splitlines() if line.strip()]
    return [min(rows, key=lambda r: abs(r[0] - t))[1] for t in at]


def grid(n):
    items = [(VoltageSource(10), "GND", "n0_0")]
    for i in range(n):
        for j in range(n):
            if i + 1 < n:
                items.append((Resistor(100 + 7 * i), f"n{i}_{j}", f"n{i + 1}_{j}"))
            if j + 1 < n:
                items.append((Resistor(220 + 13 * j), f"n{i}_{j}", f"n{i}_{j + 1}"))
    return net(*items, (Resistor(50), f"n{n - 1}_{n - 1}", "GND"))


LINEAR_DC = {
    "divider": (supply(12) + Resistor("1k") + node("A") + Resistor("2.2k") + ground, ["A"]),
    "bridge": (
        net(
            (VoltageSource(10), "GND", "T"),
            (Resistor(100), "T", "A"),
            (Resistor(220), "T", "B"),
            (Resistor(330), "A", "GND"),
            (Resistor(470), "B", "GND"),
            (Resistor(1000), "A", "B"),
        ),
        ["A", "B"],
    ),
    "grid": (grid(4), ["n3_3", "n1_2", "n2_1"]),
    "current source": (
        net((CurrentSource("10m"), "GND", "A"), (Resistor(1000), "A", "B"), (Resistor(500), "B", "GND")),
        ["A", "B"],
    ),
    "inverting amplifier": (
        net(
            (VoltageSource(1), "GND", "IN"),
            (Resistor("1k"), "IN", "X"),
            (Resistor("10k"), "X", "OUT"),
            (OpAmp(), "GND", "X", "OUT"),
            (Resistor("2k"), "OUT", "GND"),
        ),
        ["OUT"],
    ),
    "controlled sources": (
        net(
            (VoltageSource(2), "GND", "A"),
            (Resistor(100), "A", "GND"),
            (VCVS(3), "A", "GND", "GND", "B"),
            (Resistor(200), "B", "GND"),
            (VCCS("10m"), "A", "GND", "GND", "C"),
            (Resistor(300), "C", "GND"),
        ),
        ["B", "C"],
    ),
    "current-controlled sources": (
        net(
            (VoltageSource(2), "GND", "A"),
            (CCCS(3), "A", "X", "GND", "B"),
            (Resistor(10), "X", "GND"),
            (Resistor(200), "B", "GND"),
            (CCVS(50), "B", "Y", "GND", "C"),
            (Resistor(40), "Y", "GND"),
            (Resistor(300), "C", "GND"),
        ),
        ["B", "C", "X"],
    ),
}


@needs_ngspice
@pytest.mark.parametrize("name", LINEAR_DC)
def test_dc_matches_ngspice(name, tmp_path):
    c, nodes = LINEAR_DC[name]
    sol = c.solve()
    spice = ngspice(c, "op", nodes, tmp_path)
    for n in nodes:
        rel = 5e-5 if "amplifier" in name else 1e-9  # ngspice's op-amp: a gain of 10⁶, not ∞
        assert float(sol.V(n)) == pytest.approx(spice[n.lower()].real, rel=rel, abs=1e-12)


AC = {
    "rc": (supply(1) + Resistor("1k") + node("A") + Capacitor("1u") + ground, ["A"]),
    "rlc": (supply(1) + Resistor(10) + node("A") + Inductor("10m") + node("B") + Capacitor("1u") + ground, ["A", "B"]),
    "coupled": (
        net(
            (VoltageSource(1), "GND", "A"),
            (Resistor(1), "A", "B"),
            (Coupled("1m", L1="2m", L2="3m"), "B", "GND", "GND", "C"),
            (Resistor(100), "C", "GND"),
        ),
        ["B", "C"],
    ),
}


@needs_ngspice
@pytest.mark.parametrize("name", AC)
@pytest.mark.parametrize("f", [50, 1591.55, 20_000])
def test_ac_matches_ngspice(name, f, tmp_path):
    c, nodes = AC[name]
    sol = c.solve(omega=2 * math.pi * f)
    spice = ngspice(c, f"ac lin 1 {f} {f}", nodes, tmp_path)
    for n in nodes:
        assert complex(sol.V(n)) == pytest.approx(spice[n.lower()], rel=1e-6, abs=1e-12)


@needs_ngspice
def test_rc_in_time_matches_ngspice(tmp_path):
    c = supply(5) + Resistor("1k") + node("A") + Capacitor("1u") + ground
    at = [0.2e-3, 1e-3, 3e-3]
    ours = simulate(c, t=4e-3)
    spice = ngspice_tran(c, 4e-3, "A", at, tmp_path)
    for t, s in zip(at, spice):
        assert ours.at(t)["V_A"] == pytest.approx(s, rel=0.01)


NONLINEAR = {
    "1N4148 and a resistor": (supply(5) + Resistor(430) + node("A") + Diode(part="1N4148") + ground, ["A"]),
    "BC547B with a base resistor": (
        net(
            (VoltageSource(9), "GND", "VCC"),
            (Resistor("100k"), "VCC", "B"),
            (Resistor("1k"), "VCC", "C"),
            (NPN(part="BC547B"), "B", "C", "GND"),
        ),
        ["B", "C"],
    ),
}


@needs_ngspice
@pytest.mark.parametrize("name", NONLINEAR)
def test_nonlinear_operating_point_matches_ngspice(name, tmp_path):
    """Ours settle in time (no DC solve of a diode); theirs is the operating point."""
    c, nodes = NONLINEAR[name]
    trace = simulate(c, t=5e-3)
    spice = ngspice(c, "op", nodes, tmp_path)
    for n in nodes:
        assert trace[f"V_{n}"][-1] == pytest.approx(spice[n.lower()].real, rel=2e-3, abs=2e-3)


def test_netlist_round_trip():
    c = net(
        (VoltageSource(12), "GND", "IN"),
        (Resistor("4.7k"), "IN", "A"),
        (Capacitor("100n"), "A", "GND"),
        (Inductor("1m"), "A", "B"),
        (Diode(part="1N4148"), "B", "GND"),
        (NPN(part="2N3904"), "A", "B", "GND"),
        (CurrentSource("1m"), "GND", "B"),
    )
    netlist = to_spice(c)
    assert to_spice(from_spice(netlist)) == netlist  # the parts' names too


def test_reads_an_ltspice_netlist():
    text = """* C:\\\\users\\\\me\\\\rc.asc
V1 N001 0 SINE(0 1 1k) AC 1
R1 N001 out 1.5k
C1 out 0 100n
D1 out 0 1N4148
.model D D
.model 1N4148 D(Is=2.52n Rs=.568 N=1.752 Cjo=4p M=.4 tt=20n Iave=200m Vpk=75 mfg=OnSemi type=silicon)
.tran 5m
.backanno
.end
"""
    parts = {x.label: x for x, _ in from_spice(text).items}
    assert parts["R1"].value == 1500 and parts["C1"].value == sp.Rational(1, 10**7)
    assert parts["D1"].IS == pytest.approx(2.52e-9) and parts["D1"].N == pytest.approx(1.752)
    assert parts["D1"].part == "1N4148"
    assert float(parts["V1"].frequency) == 1000
