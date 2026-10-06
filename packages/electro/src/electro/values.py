"""Physical values read from text (SI prefixes, units, Polish decimal comma), and expressions of quantities
read without ``eval``."""

from __future__ import annotations

import ast
import re
from fractions import Fraction
from typing import cast

import sympy as sp


class BadValue(ValueError):
    """Text that is not a value (examples of ones that are: 10, 4.7, '4.7k', '4k7', '0,5 A', 'R')."""

    def __init__(self, value: str) -> None:
        super().__init__(value)
        self.value = value


class BadExpression(ValueError):
    """Text that is not an expression of quantities (examples of ones that are: 'I_R_1', 'U_C_1 / E_1')."""

    def __init__(self, expression: str) -> None:
        super().__init__(expression)
        self.expression = expression


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


_FUNCTIONS = {"sqrt": sp.sqrt, "abs": sp.Abs, "exp": sp.exp, "log": sp.log, "sin": sp.sin, "cos": sp.cos,
              "tan": sp.tan, "atan": sp.atan, "re": sp.re, "im": sp.im, "arg": sp.arg}  # fmt: skip
_OPERATORS = {ast.Add: sp.Add, ast.Sub: lambda a, b: a - b, ast.Mult: sp.Mul, ast.Div: lambda a, b: a / b}


def expression(text: str) -> sp.Expr:
    """``"U_C_1 / E_1"``, ``"sqrt(P_R_1 * R_1)"`` → a sympy expression of plain symbols, read without
    ``eval``: only names, numbers, + − · / ** and a few functions (sympify would run any Python)."""

    def walk(node):
        match node:
            case ast.Name(id="pi"):
                return sp.pi
            case ast.Name(id=name):
                return sp.Symbol(name)
            case ast.Constant(value=bool()):
                raise BadExpression(text)
            case ast.Constant(value=int() | float() | complex() as number):
                return parse(number)
            case ast.UnaryOp(op=ast.USub(), operand=x):
                return -walk(x)
            case ast.UnaryOp(op=ast.UAdd(), operand=x):
                return walk(x)
            case ast.BinOp(op=ast.Pow(), left=a, right=ast.Constant(value=int() | float() as n)) if abs(n) <= 10:
                return walk(a) ** parse(n)
            case ast.BinOp(op=op, left=a, right=b) if type(op) in _OPERATORS:
                return _OPERATORS[type(op)](walk(a), walk(b))
            case ast.Call(func=ast.Name(id=name), args=[x], keywords=[]) if name in _FUNCTIONS:
                return _FUNCTIONS[name](walk(x))
        raise BadExpression(text)

    if not isinstance(text, str) or len(text) > 500:
        raise BadExpression(str(text)[:500])
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except (SyntaxError, RecursionError, MemoryError):
        raise BadExpression(text) from None
    return cast(sp.Expr, walk(tree.body))
