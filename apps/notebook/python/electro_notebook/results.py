"""What a solution says of each element, as a drawing shows it beside it (``ElementResult`` in
``shared/model/types.ts``): its value, voltage, current and power, formatted; a source's voltage the rise
across it and its power what it gives; a meter's value its reading; a hole what it turned out to be."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import sympy as sp
from electro import Current, Element, Parameter, Power, Solution, Voltage
from electro.values import UNKNOWN

from .kinds import is_source, reading
from .methods import fill
from .text import fmt


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
    """What the drawing shows beside ``e``. ``values``: what was given; ``filled``: what a hole turned out to
    be."""
    by = filled if filled is not None else e
    flows = _flows(solution, by) if len(e.terminals) == 2 else {"U": None, "I": None, "P": None}
    if (reads := reading(e)) is not None:
        return _meter(flows, reads, values, e, unit)
    value = number(solution, Parameter(by)) if "" in by.parameters else None
    found = filled is not None or ("" in e.parameters and not given(values.get(e)) and value is not None)
    return {"value": _value_text(e, filled, value, unit), "solved": found, **_shown_flows(flows)}


def _flows(solution: Solution, e: Element) -> dict:
    """Its voltage, current and power, as the board shows them (``shown``), or None where not found."""
    return {
        name: number(lambda q: shown(solution, q), q(e)) for name, q in (("U", Voltage), ("I", Current), ("P", Power))
    }


def _meter(flows: dict, reads, values: Mapping, e: Element, unit: str) -> dict:
    """A meter shows its reading, and nothing else."""
    shows = flows["U" if reads is Voltage else "I"]
    text = fmt(shows, unit) if shows is not None else "?"
    return {
        "value": text,
        "solved": not given(values.get(reads(e))),
        "U": None,
        "I": None,
        "P": None,
        "reversed": False,
    }


def _value_text(e: Element, filled: Element | None, value, unit: str) -> str:
    if filled is not None:
        return notation(filled, value)
    if "" in e.parameters:
        return fmt(value, unit) if value is not None else "?"
    return ""


def _shown_flows(flows: dict) -> dict:
    """Voltage, current and power formatted; a negative current turned round (``reversed``)."""
    u, i, p = flows["U"], flows["I"], flows["P"]
    sign = -1 if i is not None and i.is_real and i < 0 else 1
    return {
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
