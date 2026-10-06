"""What a solution says of each element, as a drawing shows it beside it (``ElementResult`` in
``shared/model/types.ts``): its value, voltage, current and power, formatted; a source's voltage the rise
across it and its power what it gives; a meter's value its reading; a hole what it turned out to be."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import sympy as sp
from electro import Current, Element, Parameter, Power, Solution, Voltage
from electro.frame.formula import is_source
from electro.values import UNKNOWN, fmt

from .kinds import reading
from .methods import fill


def solved(circuit: Element, values: Mapping, elements: Mapping[str, Element]) -> tuple[Solution, dict[str, Element]]:
    """Solved, a hole filled with the simplest element that fits (``{id: what it is}``)."""
    holes = [(id, e) for id, e in elements.items() if e.kind == "hole"]
    if len(holes) == 1:
        id, hole = holes[0]
        filled = fill(circuit, values, hole)
        return filled.solution, {id: filled.by}
    return circuit.final(values), {}


def shown(solution: Solution, q) -> sp.Expr:
    """``q`` as the board shows it: a source's voltage the rise from its first end to its second, its power
    what it gives."""
    v = solution(q)
    return -v if isinstance(q, Voltage | Power) and is_source(q.of) else v


def number(read: Callable, q) -> sp.Expr | None:
    """``q`` found (by ``read``: a solution, or what shows it), or None."""
    try:
        v = read(q)
    except Exception:  # noqa: BLE001 — not found: none
        return None
    return v if v.is_number else None


def element_result(solution: Solution, values: Mapping, e: Element, unit: str, filled: Element | None = None) -> dict:
    """``values``: what was given."""
    two = len(e.terminals) == 2
    by = filled if filled is not None else e

    def read(q):
        return shown(solution, q)

    value = number(solution, Parameter(by)) if "" in by.parameters else None
    u = number(read, Voltage(by)) if two else None
    i = number(read, Current(by)) if two else None
    p = number(read, Power(by)) if two else None
    reads = reading(e)
    if reads is not None:
        shows = u if reads is Voltage else i
        text = fmt(shows, unit) if shows is not None else "?"
        solved = not given(values.get(reads(e)))
        return {"value": text, "solved": solved, "U": None, "I": None, "P": None, "reversed": False}
    if filled is not None:
        text = notation(filled, value)
    elif "" in e.parameters:
        text = fmt(value, unit) if value is not None else "?"
    else:
        text = ""
    sign = -1 if i is not None and i.is_real and i < 0 else 1
    return {
        "value": text,
        "solved": filled is not None or ("" in e.parameters and not given(values.get(e)) and value is not None),
        "U": fmt(sign * u, "V") if u is not None else None,
        "I": fmt(sign * i, "A") if i is not None else None,
        "P": fmt(p, "W") if p is not None and not p.has(sp.I) else None,
        "reversed": sign < 0,
    }


def given(value: object) -> bool:
    """A value given to an element: its main one (an element of several may be given others only)."""
    if isinstance(value, Mapping):
        return "" in value and value[""] is not UNKNOWN
    return value is not None and value is not UNKNOWN


def notation(by: Element, value) -> str:
    """What a hole turned out to be, in values: ``R = 2 Ω``, ``E = 12 V``, ``R = ∞`` (a break), ``R = 0 Ω``."""
    match by.kind:
        case "wire":
            return f"R = {fmt(0, 'Ω')}"
        case "open":
            return "R = ∞"
        case "resistor":
            return f"R = {fmt(value, 'Ω')}"
        case "voltage_source":
            return f"E = {fmt(value, 'V')}"
    return f"J = {fmt(value, 'A')}"


def amplitude(v) -> float:
    """A number as a plot shows it: a phasor by its amplitude."""
    z = complex(v)
    return abs(z) if abs(z.imag) > 1e-12 * max(1.0, abs(z)) else z.real
