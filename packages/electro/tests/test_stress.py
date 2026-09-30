"""Big circuits: they solve, in time, and the two solvers (steps on paper, numbers) agree.

The time limits are loose (a slow machine, CI) — they catch a return to the cubic blow-up, not
a few percent; in Pyodide everything is 2–3× slower still."""

import math
import time

import pytest
import sympy as sp
from electro import *
from electro.analysis import OMEGA
from electro.components import Context
from electro.numeric import LinearSystem


def grid(n, reactive=False):
    """An n×n mesh (no series-parallel shortcut): 100 Ω down, 220 Ω (or every other one 1 µF) across."""
    items = [(VoltageSource(10), "GND", "n0_0")]
    for i in range(n):
        for j in range(n):
            if i + 1 < n:
                items.append((Resistor(100), f"n{i}_{j}", f"n{i + 1}_{j}"))
            if j + 1 < n:
                across = Capacitor("1u") if reactive and (i + j) % 2 else Resistor(220)
                items.append((across, f"n{i}_{j}", f"n{i}_{j + 1}"))
    items.append((Resistor(50), f"n{n - 1}_{n - 1}", "GND"))
    return net(*items)


def timed(f):
    start = time.perf_counter()
    result = f()
    return result, time.perf_counter() - start


def test_big_mesh_on_paper():
    sol, seconds = timed(lambda: grid(8).solve())  # 114 elements
    assert seconds < 10
    ls = LinearSystem(grid(8))
    x = ls.solve()
    for name in ("V_n7_7", "V_n3_4", "I_R_1"):
        assert complex(sol(sp.Symbol(name))) == pytest.approx(ls.value(name, x), rel=1e-12)


def test_big_mesh_bode():
    r, seconds = timed(lambda: bode(grid(8, reactive=True), "V_n7_7"))  # 112 elements, 200 frequencies
    assert seconds < 10
    assert all(math.isfinite(g) for g in r.gain_db["V_n7_7"])


def test_numbers_match_the_formula():
    c = grid(3, reactive=True)
    r = bode(c, "V_n2_2", f=(10, 1e5), points=5)
    H = r.H["V_n2_2"]
    for f, h in zip(r.f, r.values["V_n2_2"]):
        assert h == pytest.approx(complex(H.subs(OMEGA, 2 * math.pi * f)), rel=1e-9)


def test_long_ladder():
    c = supply(10)
    for _ in range(40):
        c = c + Resistor(100) + shunt(Resistor(1000))
    sol, seconds = timed(lambda: (c + Resistor(100) + ground).solve())
    assert seconds < 10 and sol["E_1"].I > 0


def test_extreme_values():
    """pF next to MΩ and mΩ next to H: the numbers stay finite and agree with the exact ones."""
    c = supply(1) + Resistor("1M") + node("A") + Capacitor("10p") + Inductor(1) + Resistor("1m") + ground
    ls = LinearSystem(c, Context(OMEGA), (OMEGA,))
    for w in (1.0, 1e3, 1e6, 1e9):
        exact = complex(c.solve(omega=w)(sp.Symbol("V_A")))
        assert ls.value("V_A", ls.solve(w), (w,)) == pytest.approx(exact, rel=1e-9)
