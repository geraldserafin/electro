"""The circuit category is a hypergraph category: its laws hold up to black-box equivalence."""

import sympy as sp
from electro import *

a, b, c, d = Resistor(1), Resistor(2), Resistor(3), Resistor(5)


def same(f, g):
    return blackbox(f) == blackbox(g)


def test_category_laws():
    assert same((a + b) + c, a + (b + c))
    assert same(wire + a, a) and same(a + wire, a)


def test_monoidal_laws():
    assert same((a @ b) @ c, a @ (b @ c))
    assert same((a @ b) + (c @ d), (a + c) @ (b + d))  # interchange
    assert same(swap + swap, wires(2))
    assert same((a @ b) + swap, swap + (b @ a))  # naturality of swap


def test_frobenius_laws():
    assert same(split + join, wire)  # special
    assert same((split @ wire) + (wire @ join), join + split)  # Frobenius
    assert same((wire @ split) + (join @ wire), join + split)
    assert same((spider(0, 2) @ wire) + (wire @ spider(2, 0)), wire)  # snake / yanking


def test_dagger():
    assert same(a.transpose(), a)  # resistors are symmetric
    assert same((a + VoltageSource(5)).transpose(), VoltageSource(5).transpose() + a)
    assert not same(VoltageSource(5).transpose(), VoltageSource(5))  # a source has polarity


def test_physics_as_equations():
    x, y = sp.symbols("x y", positive=True)
    assert same(Resistor(x) + Resistor(y), Resistor(x + y))
    assert same(Resistor(x) | Resistor(y), Resistor(x * y / (x + y)))
    assert same(Resistor(0), wire)
    assert same(Resistor(1) + VoltageSource(3), VoltageSource(3) + Resistor(1))  # series elements commute
    assert same(CurrentSource(2) | Resistor(5), VoltageSource(10) + Resistor(5))  # Norton = Thévenin


def test_parallel_is_frobenius():
    assert same(a | b, split + (a @ b) + join)
    assert same(shunt(a), split + (wire @ (a + ground)))
