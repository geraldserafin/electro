"""A solution, its quantities, expressions and values pretty-printed in LaTeX: ``I_R_1`` is ``I_{R_{1}}``,
0.5 A is ``500\\,\\mathrm{mA}``."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

import sympy as sp
from electro.problem.quantities import Current, Parameter, Potential, Power, Quantity, Scaled, Voltage
from electro.solver.errors import Undetermined
from electro.solver.symbols import Symbols
from electro.values import fmt
from sympy.printing.latex import LatexPrinter

if TYPE_CHECKING:
    from electro.solver.solution import Solution, SolutionStep

UNITS = {Current: "A", Voltage: "V", Potential: "V", Power: "W"}


def name(symbol_name: str) -> str:
    """``U_R_1`` → ``U_{R_{1}}``; words like ``GND`` upright: ``V_{\\mathrm{GND}}``."""
    base, _, sub = symbol_name.partition("_")
    if len(base) > 1 and base.isalpha():
        base = rf"\mathrm{{{base}}}"
    return f"{base}_{{{name(sub)}}}" if sub else base


def expr(e: object, values: Mapping[sp.Symbol, sp.Expr] | None = None) -> str:
    """An expression; with ``values``, the known symbols shown as numbers."""
    e = sp.sympify(e)
    names = {s: name(s.name) for s in e.free_symbols if isinstance(s, sp.Symbol)}
    for s, v in (values or {}).items():
        if s in names and v.is_number and v.is_real:
            number = f"{float(v):.6g}"
            names[s] = rf"\left({number}\right)" if float(v) < 0 else number
    return _Latex({"symbol_names": names, "mul_symbol": "dot"}).doprint(e)


def value(v: object, unit: str = "") -> str:
    """A value with its unit, in engineering notation; a phasor as its magnitude and angle."""
    v = sp.sympify(v)
    if v.free_symbols:
        return expr(v) + (_unit(unit) if unit else "")
    text = fmt(v, unit)
    if "∠" in text:
        magnitude, angle = text.split(" ∠ ")
        return _text(magnitude) + r" \angle " + angle.replace("°", r"^{\circ}")
    return _text(text)


def quantity(q: Quantity | Scaled, s: Symbols) -> str:
    """As a book names it: ``I_{R_{1}}``, ``U_{R_{1}}``, ``V_{A}``, ``R_{1}``; a sum of them written out."""
    e = s.of(q)
    if isinstance(e, sp.Symbol):
        return name(e.name)
    match q:
        case Voltage(of) | Power(of) | Current(of):
            letter = {Voltage: "U", Power: "P", Current: "I"}[type(q)]
            return name(f"{letter}_{s.labels[s.index(of)]}")
    return expr(e)


def unit(q: Quantity | Scaled, units: Mapping[str, str], s: Symbols) -> str:
    """Its unit: a current's A, a voltage's V, a power's W, a parameter's its element's (``units``: by
    element)."""
    match q:
        case Parameter(of, which) if not which:
            return units.get(s.labels[s.index(of)], "")
        case Scaled(_, x):
            return unit(x, units, s)
    return UNITS.get(type(q), "A" if "I_" in str(s.of(q)) else "V")


def solution(s: Solution) -> str:
    """Each step's values, one line each, then what is sought."""
    try:
        answers = s.answers
    except Undetermined:
        answers = {}
    lines = [step(st) for st in s.steps if st.found]
    lines += [f"{quantity(q, s.symbols)} = {value(v, UNITS.get(type(q), ''))}" for q, v in answers.items()]
    return r"\begin{aligned}" + r" \\ ".join(f"&{line}" for line in lines) + r"\end{aligned}"


def step(st: SolutionStep) -> str:
    """What it found: ``U_{R_{1}} = 5\\,\\mathrm{V}``, a current in amperes, a potential in volts."""
    return ", ".join(f"{name(x.name)} = {value(v, LETTERS.get(x.name[0], ''))}" for x, v in zip(st.found, st.values))


LETTERS = {"I": "A", "V": "V", "U": "V"}
"""A variable's unit by its letter."""


def _unit(text: str) -> str:
    text = text.replace("Ω", r"\Omega").replace("µ", r"\mu ")
    return rf"\,\mathrm{{{text}}}" if text else ""


def _text(text: str) -> str:
    number, _, u = text.partition(" ")
    return number + _unit(u)


class _Latex(LatexPrinter):
    """Positive terms first: ``V_{A} - U_{R_{1}}`` rather than ``- U_{R_{1}} + V_{A}``."""

    def _as_ordered_terms(self, expr, order=None):
        return sorted(super()._as_ordered_terms(expr, order), key=lambda t: t.could_extract_minus_sign())
