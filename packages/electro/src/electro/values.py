"""Physical values read from text (SI prefixes, units, Polish decimal comma)."""

from __future__ import annotations

import re
from collections.abc import Mapping
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
        if m := _POLAR.match(value):  # a phasor: magnitude and angle in degrees, exact for 30°, 120°, …
            angle = sp.pi * sp.Rational(m.group(2).replace(",", ".")) / 180
            return sp.nsimplify(parse(m.group(1))) * (sp.cos(angle) + sp.I * sp.sin(angle))
        if _COMPLEX.match(value):  # "3+4j", "-2j"
            number = complex(value.replace(" ", "").replace(",", ".").replace("J", "j"))
            return parse(number)
        if _IDENT.match(value):
            return sp.Symbol(value, positive=True) if positive else sp.Symbol(value)
    raise BadValue(str(value))


# A circuit's values


def given(circuit, values: Mapping) -> dict[sp.Symbol, sp.Expr]:
    """Each parameter's value: as given, else its kind's default. An element's value is its main parameter;
    several by name (``{D: {"I_S": …}}``); a real part's (``part("1N4148")``); a name shared by elements."""
    from .element import Element
    from .errors import NoSuchParameter
    from .parts import Part

    out: dict[sp.Symbol, sp.Expr] = {}
    for e in circuit.members:
        out |= {e.P[w]: sp.sympify(parse(d)) for w, d in e.defaults.items()}
    for key, value in values.items():
        value = _read(value)
        if value is UNKNOWN:
            continue
        match key:
            case Element() if isinstance(value, Part):
                out |= {key.P[w]: sp.sympify(parse(x)) for w, x in value.parameters(key.kind).items()}
            case Element() if isinstance(value, Mapping):
                out |= {key.P[w]: sp.sympify(parse(x)) for w, x in value.items() if parse(x) is not UNKNOWN}
            case Element():
                out[key.P[""]] = value
            case str():
                if not any(x.name == key for e in circuit.members for x in e.P.values()):
                    raise NoSuchParameter(key)
                out[sp.Symbol(key)] = value
    return out


def data(values: Mapping) -> list:
    """The data on quantities (``I(R): 2``, ``U(R_1): 2 * U(R_2)``), each an equation."""
    from .laws import Equation, Origin

    out = []
    for key, value in values.items():
        if not hasattr(key, "expr") or isinstance(key, sp.Basic):
            continue
        value = _read(value)
        if value is not UNKNOWN:
            rhs = value.expr if hasattr(value, "expr") and not isinstance(value, sp.Basic) else value
            out.append(Equation(key.expr - rhs, Origin("given", key)))
    return out


def _read(value: object) -> object:
    from .parts import Part

    if isinstance(value, Mapping | Part) or (hasattr(value, "expr") and not isinstance(value, sp.Basic)):
        return value
    return parse(value)
