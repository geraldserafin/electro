"""Logic (74HC), powered at ``V_HIGH`` from its ``gnd`` (its supply pins not drawn, as logic diagrams have
it). Inputs take no current and read 1 above half the supply; an output is a source of its level behind
``R_OUT``. A gate follows its inputs smoothly and a little late (so gates in a loop keep a state); a
flip-flop decides on its clock's rising edge, from what its inputs were just before it."""

from __future__ import annotations

from collections.abc import Callable

import sympy as sp

from ..kind import Kind, Params, Terminals
from ..time import D, Pre, rising, when
from .physics import high

V_HIGH = 5
R_OUT = 50
DELAY = sp.Rational(1, 10**7)
SHARP = 12
"""How sharply a gate's input turns from 0 to 1 around half the supply (1/V)."""


HALF = sp.Rational(V_HIGH, 2)


def level(t: Terminals, terminal: str) -> sp.Expr:
    """Its input read as 0 or 1."""
    return high(t.across(terminal, "gnd"), HALF)


def level_before(t: Terminals, terminal: str) -> sp.Expr:
    """Its input as it was just before, read as 0 or 1."""
    return high(Pre(t.across(terminal, "gnd")), HALF)


def _soft(t: Terminals, terminal: str) -> sp.Expr:
    """An input read as a gate reads it: from 0 to 1 smoothly over a few tenths of a volt."""
    return 1 / (1 + sp.exp(-SHARP * (t.across(terminal, "gnd") - HALF)))


def _output(t: Terminals, terminal: str, level_: sp.Expr) -> sp.Expr:
    """The current into an output pin driven at ``level_`` (0 to 1)."""
    return t.I[terminal] - (t.across(terminal, "gnd") - V_HIGH * level_) / R_OUT


def _gate(inputs: tuple[str, ...], logic: Callable[..., sp.Expr]):
    def laws(t: Terminals, _: Params) -> list[sp.Expr]:
        y = t.inner("y")
        return [
            *(t.I[i] for i in inputs),
            DELAY * D(y) - (V_HIGH * logic(*(_soft(t, i) for i in inputs)) - y),
            t.I["y"] - (t.across("y", "gnd") - y) / R_OUT,
        ]

    return laws


def _rising(t: Terminals) -> sp.Basic:
    return rising(t.across("clk", "gnd"), HALF)


def _flip_flop(inputs: tuple[str, ...], following: Callable[..., sp.Expr]):
    """``following(q, *inputs)``: the state after a rising edge, from the state and the inputs' levels
    just before it."""

    def laws(t: Terminals, _: Params) -> list[sp.Expr]:
        q = t.inner("q")
        after = following(Pre(q), *(level_before(t, i) for i in inputs))
        return [
            *(t.I[i] for i in (*inputs, "clk")),
            q - when(_rising(t), after, Pre(q)),
            _output(t, "q", q),
            _output(t, "nq", 1 - q),
        ]

    return laws


def _counter(t: Terminals, _: Params) -> list[sp.Expr]:
    """Four bits (``q0`` the lowest), one up on each rising edge of ``clk``, 15 then 0; ``reset`` high
    holds it at 0. ``count``: the number it holds."""
    bits = [t.inner(f"q{k}") for k in range(4)]
    keep = 1 - level(t, "reset")
    edge = when(_rising(t), 1, 0)
    laws: list[sp.Expr] = [t.I["clk"], t.I["reset"]]
    carry: sp.Expr = edge
    for k, b in enumerate(bits):
        was = Pre(b)
        laws += [b - keep * (was + carry - 2 * was * carry), _output(t, f"q{k}", b)]
        carry = carry * was
    laws.append(t.inner("count") - sum(b * 2**k for k, b in enumerate(bits)))
    return laws


def _gate_kind(name: str, inputs: tuple[str, ...], logic: Callable[..., sp.Expr]) -> Kind:
    return Kind(name, "U", (*inputs, "y", "gnd"), _gate(inputs, logic), parameters=(), ground=True)


NOT = _gate_kind("not_gate", ("a",), lambda a: 1 - a)
AND = _gate_kind("and_gate", ("a", "b"), lambda a, b: a * b)
NAND = _gate_kind("nand_gate", ("a", "b"), lambda a, b: 1 - a * b)
OR = _gate_kind("or_gate", ("a", "b"), lambda a, b: 1 - (1 - a) * (1 - b))
NOR = _gate_kind("nor_gate", ("a", "b"), lambda a, b: (1 - a) * (1 - b))
XOR = _gate_kind("xor_gate", ("a", "b"), lambda a, b: a + b - 2 * a * b)

DFlipFlop = Kind(
    "dff", "U", ("d", "clk", "q", "nq", "gnd"), _flip_flop(("d",), lambda q, d: d), parameters=(), ground=True
)
"""On a rising edge q takes d (a half of a 74HC74)."""

JKFlipFlop = Kind(
    "jkff",
    "U",
    ("j", "clk", "k", "q", "nq", "gnd"),
    _flip_flop(("j", "k"), lambda q, j, k: j * (1 - q) + (1 - k) * q),
    parameters=(),
    ground=True,
)
"""On a rising edge j sets, k resets, both toggle, neither holds."""

Counter = Kind("counter", "U", ("clk", "reset", "q0", "q1", "q2", "q3", "gnd"), _counter, parameters=(), ground=True)
"""A 4-bit synchronous binary counter (a 74HC161 without its load and enable)."""
