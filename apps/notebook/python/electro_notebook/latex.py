"""Quantities, expressions and values pretty-printed in LaTeX: ``I_R_1`` is ``I_{R_{1}}``, 0.5 A is
``500\\,\\mathrm{mA}``."""

from __future__ import annotations

from collections.abc import Mapping

import sympy as sp
from electro.formula import Names
from electro.quantities import Current, Parameter, Potential, Power, Quantity, Scaled, Voltage
from electro.values import fmt
from sympy.printing.latex import LatexPrinter

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


def quantity(q: Quantity | Scaled, n: Names) -> str:
    """As a book names it: ``I_{R_{1}}``, ``U_{R_{1}}``, ``V_{A}``, ``R_{1}``; a sum of them written out."""
    match q:
        case Voltage(of) | Power(of):
            return name(f"{'U' if isinstance(q, Voltage) else 'P'}_{n.labels[of]}")
        case Current(of, None):
            return name(f"I_{n.labels[of]}")
    e = n.of(q)
    return name(e.name) if isinstance(e, sp.Symbol) else expr(e)


def unit(q: Quantity | Scaled, units: Mapping[str, str], n: Names) -> str:
    """Its unit: a current's A, a voltage's V, a power's W, a parameter's its element's (``units``: by
    element)."""
    match q:
        case Parameter(of, which) if not which:
            return units.get(n.labels[of], "")
        case Scaled(_, x):
            return unit(x, units, n)
    return UNITS.get(type(q), "A" if "I_" in str(n.of(q)) else "V")


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
