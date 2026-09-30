"""Parsing and formatting of physical values (SI prefixes, units, Polish decimal comma)."""

from __future__ import annotations

import re
from fractions import Fraction

import sympy as sp

from .issues import BadValue, NotAValue

PREFIXES = {
    "p": sp.Rational(1, 10**12),
    "n": sp.Rational(1, 10**9),
    "u": sp.Rational(1, 10**6),
    "µ": sp.Rational(1, 10**6),
    "m": sp.Rational(1, 10**3),
    "": sp.Integer(1),
    "k": sp.Integer(10**3),
    "M": sp.Integer(10**6),
    "G": sp.Integer(10**9),
}
UNITS = ("Ω", "ohm", "V", "A", "F", "H", "W", "Hz", "S")

_UNITS = "|".join(UNITS)
_NUMBER = re.compile(rf"^\s*([+-]?\d+(?:[.,]\d+)?(?:e[+-]?\d+)?)\s*([pnuµmkMG]?)\s*(?:{_UNITS})?\s*$")
_RKM = re.compile(r"^\s*(\d+)([pnuµmkMGR])(\d+)\s*$")  # "4k7" = 4.7k, "4R7" = 4.7
_IDENT = re.compile(r"^[^\W\d]\w*$")
_FRACTION = re.compile(r"^\s*([+-]?\d+)\s*/\s*(\d+)\s*$")


class Unknown:
    """Marker for a value the solver has to find."""

    def __repr__(self) -> str:
        return "?"


UNKNOWN = Unknown()


def parse(value, *, positive: bool = False):
    """Turn user input into an exact sympy value, a symbol, or UNKNOWN.

    Accepts numbers, sympy expressions and strings such as "4.7k", "4k7",
    "0,5 A", "12V" or a bare identifier like "R" (a symbolic parameter).
    """
    if value is None or value is UNKNOWN or value == "?":
        return UNKNOWN
    if isinstance(value, sp.Basic):
        return value
    if isinstance(value, bool):
        raise NotAValue(repr(value))
    if isinstance(value, int):
        return sp.Integer(value)
    if isinstance(value, float):
        return sp.Rational(repr(value))
    if isinstance(value, Fraction):
        return sp.Rational(value.numerator, value.denominator)
    if isinstance(value, complex):
        return parse(value.real) + sp.I * parse(value.imag)
    if isinstance(value, str):
        if m := _RKM.match(value):
            whole, prefix, frac = m.groups()
            scale = PREFIXES["" if prefix == "R" else prefix]
            return sp.Rational(f"{whole}.{frac}") * scale
        if m := _FRACTION.match(value):
            return sp.Rational(int(m.group(1)), int(m.group(2)))
        if m := _NUMBER.match(value):
            number, prefix = m.groups()
            return sp.Rational(number.replace(",", ".")) * PREFIXES[prefix]
        if _IDENT.match(value):
            return sp.Symbol(value, positive=True) if positive else sp.Symbol(value)
    raise BadValue(str(value))


def to_text(value) -> str | None:
    """Inverse of ``parse`` for storage (e.g. JSON): exact, and readable where possible."""
    if value is None or value is UNKNOWN:
        return None
    value = sp.sympify(value)
    if isinstance(value, sp.Symbol):
        return value.name
    if isinstance(value, sp.Rational) and not isinstance(value, sp.Integer):
        q = value.q
        while q % 2 == 0:
            q //= 2
        while q % 5 == 0:
            q //= 5
        if q == 1:  # terminating decimal
            text = f"{sp.N(value, 30)}".rstrip("0")
            return text.rstrip(".")
        return f"{value.p}/{value.q}"
    return str(value)


_ENG = [
    (10**9, "G"),
    (10**6, "M"),
    (10**3, "k"),
    (1, ""),
    (sp.Rational(1, 10**3), "m"),
    (sp.Rational(1, 10**6), "µ"),
    (sp.Rational(1, 10**9), "n"),
    (sp.Rational(1, 10**12), "p"),
]


def _eng_real(x: float, unit: str) -> str:
    if x == 0:
        return f"0 {unit}".strip()
    for scale, prefix in _ENG:  # noqa: B007 — prefix: the one the loop stops at
        if abs(x) >= float(scale) * 0.9995:
            break
    mantissa = x / float(scale)
    text = f"{mantissa:.4g}"
    return f"{text} {prefix}{unit}".strip()


def fmt(value, unit: str = "") -> str:
    """Human-friendly engineering notation: 0.5 -> '500 mA', 4700 -> '4.7 kΩ'."""
    if value is None:
        return "—"
    value = sp.nsimplify(value) if isinstance(value, (int, float)) else sp.sympify(value)
    if value.free_symbols:
        text = sp.sstr(sp.simplify(value))
        return f"{text} {unit}".strip() if unit else text
    value = complex(value)
    if abs(value.imag) < 1e-12 * max(1.0, abs(value.real)):
        return _eng_real(value.real, unit)
    import cmath

    magnitude, phase = cmath.polar(value)
    return f"{_eng_real(magnitude, unit)} ∠ {phase * 180 / cmath.pi:.4g}°"
