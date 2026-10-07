"""Physical values read from text (SI prefixes, units, Polish decimal comma)."""

from __future__ import annotations

import re
from fractions import Fraction

import sympy as sp


class BadValue(ValueError):
    """Text that is not a value (examples of ones that are: 10, 4.7, '4.7k', '4k7', '0,5 A', 'R')."""

    def __init__(self, value: str) -> None:
        super().__init__(value)
        self.value = value


class NotAValue(TypeError):
    """An object of a type no value is made of."""

    def __init__(self, value: str) -> None:
        super().__init__(value)
        self.value = value


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
_POLAR = re.compile(r"^\s*(.+?)\s*[∠@]\s*([+-]?\d+(?:[.,]\d+)?)\s*°?\s*$")  # "230∠-120", "10 V @ 30°"
_COMPLEX = re.compile(r"^\s*[+-]?[\d.,]*\s*(?:[+-]\s*[\d.,]*)?[jJ]\s*$|^\s*[+-]?[\d.,]+[jJ]?\s*[+-]\s*[\d.,]+[jJ]?\s*$")
_FRACTION = re.compile(r"^\s*([+-]?\d+)\s*/\s*(\d+)\s*$")


class Unknown:
    """Marker for a value the solver has to find."""

    def __repr__(self) -> str:
        return "?"


UNKNOWN = Unknown()


def parse(value, *, positive: bool = False):
    """User input as an exact sympy value, a letter, or ``UNKNOWN``: numbers, sympy expressions, and text like
    ``"4.7k"``, ``"4k7"``, ``"0,5 A"``, ``"12V"``, ``"1/3"``, ``"230∠-120"``, ``"3+4j"`` or a letter ``"R"``."""
    if value is None or value is UNKNOWN or value == "?":
        return UNKNOWN
    if isinstance(value, str):
        return _text(value, positive)
    return _number(value)


def _number(value):
    match value:
        case sp.Basic():
            return value
        case bool():
            raise NotAValue(repr(value))
        case int():
            return sp.Integer(value)
        case float():
            return sp.Rational(repr(value))
        case Fraction():
            return sp.Rational(value.numerator, value.denominator)
        case complex():
            return _number(value.real) + sp.I * _number(value.imag)
    raise NotAValue(repr(value))


def _text(text: str, positive: bool):
    for pattern, read in _READERS:
        if m := pattern.match(text):
            return read(m)
    if _IDENT.match(text):
        return sp.Symbol(text, positive=True) if positive else sp.Symbol(text)
    raise BadValue(text)


def _decimal(text: str) -> sp.Rational:
    return sp.Rational(text.replace(",", "."))


def _polar(m: re.Match) -> sp.Expr:
    """A phasor: its magnitude and its angle in degrees (exact for 30°, 120°…)."""
    angle = sp.pi * _decimal(m[2]) / 180
    return sp.nsimplify(parse(m[1])) * (sp.cos(angle) + sp.I * sp.sin(angle))


_READERS = [
    (_RKM, lambda m: sp.Rational(f"{m[1]}.{m[3]}") * PREFIXES["" if m[2] == "R" else m[2]]),
    (_FRACTION, lambda m: sp.Rational(int(m[1]), int(m[2]))),
    (_NUMBER, lambda m: _decimal(m[1]) * PREFIXES[m[2]]),
    (_POLAR, _polar),
    (_COMPLEX, lambda m: _number(complex(m[0].replace(" ", "").replace(",", ".").replace("J", "j")))),
]
"""Each way a value may be written, and how it is read."""
