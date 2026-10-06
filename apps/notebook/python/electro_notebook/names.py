"""Quantities by the names one writes: ``I_R_1``, ``U_R_1``, ``P_R_1`` (an element's current, voltage, power),
``V_A`` (a point's potential), ``R_1`` (an element's value); expressions of them (``U_E_1 / I_E_1``), read
without ``eval``: only names, numbers, + − · / ** and a few functions (sympify would run any Python)."""

from __future__ import annotations

import ast
from typing import cast

import sympy as sp
from electro.circuit.quantities import Current, Parameter, Potential, Power, Quantity, Voltage
from electro.values import parse


class BadExpression(ValueError):
    """Text that is not an expression of quantities (examples of ones that are: 'I_R_1', 'U_C_1 / E_1')."""

    def __init__(self, expression: str) -> None:
        super().__init__(expression)
        self.expression = expression


OF_ELEMENTS = {"I": Current, "U": Voltage, "P": Power}


class NoSuchQuantity(KeyError):
    def __init__(self, name: str, available: list[str]) -> None:
        super().__init__(name)
        self.name, self.available = name, available


def named(name: str, names) -> Quantity:
    """The quantity ``name`` is, in a circuit of these ``names`` (``formula.names``)."""
    elements = {label: e for e, label in names.labels.items()}
    points = {str(v)[2:]: p for p, v in names.points.items()}
    if name in elements:
        return Parameter(elements[name])
    letter, _, rest = name.partition("_")
    if letter in OF_ELEMENTS and rest in elements:
        return OF_ELEMENTS[letter](elements[rest])
    if letter == "V" and rest in points:
        return Potential(points[rest])
    available = [*(f"{x}_{e}" for e in elements for x in OF_ELEMENTS), *elements, *(f"V_{p}" for p in points)]
    raise NoSuchQuantity(name, available)


def evaluated(text: str, solution) -> sp.Expr:
    """``text`` with each name's value in ``solution``."""
    e = expression(text)
    return e.subs({s: solution(named(s.name, solution.names)) for s in e.free_symbols if isinstance(s, sp.Symbol)})


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
