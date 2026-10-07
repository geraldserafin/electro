"""Plots as data, for the page to draw (``features/plots/svg.ts``): ``{"trace": …}`` in time or against a
value, ``{"bode": …}`` a frequency response, ``{"histogram": …}`` a spread of values."""

from __future__ import annotations

import re
from collections.abc import Mapping

from electro import Element, Net, Node, U, V
from electro.quantities import Quantity

from .errors import NoInput, NoOutput
from .kinds import stores
from .methods import responses, spreads

AUTO = re.compile(r"(.+_)?n\d+")
"""The names given to points no one named."""


def outputs(
    elements: Mapping[str, Element], points: Mapping[str, Node | Net], named_only: bool = False
) -> dict[str, Quantity]:
    """What a plot shows: the potentials of the points named, else (``named_only`` not) the voltages of
    what stores energy (a capacitor, an inductor)."""
    named: dict[str, Quantity] = {
        f"V_{n}": V(p) for n, p in points.items() if n not in ("GND", "0") and not AUTO.fullmatch(n)
    }
    if named or named_only:
        return named
    return {f"U_{id}": U(e) for id, e in elements.items() if len(e.terminals) == 2 and stores(e)}


def trace(x: Mapping[str, str], t: list[float], series: Mapping[str, list[float]]) -> dict:
    """``x``: ``{"name", "unit"}`` of what is along the bottom; ``series``: each line's values at ``t``."""
    return {"trace": {"x": dict(x), "t": list(t), "series": {n: list(v) for n, v in series.items()}}}


def bode(circuit: Element, values: Mapping, shown: Mapping[str, Quantity], source: Element, input: str) -> dict:
    if not shown:
        raise NoOutput()
    found = responses(circuit, values, list(shown.values()), source)
    first = found[next(iter(shown.values()))]
    outputs = {n: {"gain": list(found[q].gain_db), "phase": list(found[q].phase_deg)} for n, q in shown.items()}
    return {"bode": {"f": list(first.f), "input": input, "outputs": outputs, "cutoffs": first.cutoffs()}}


def input_of(elements: Mapping[str, Element]) -> tuple[str, Element]:
    """A frequency response's input: the first source of a voltage."""
    for id, e in elements.items():
        if e.kind in ("voltage_source", "sine_source"):
            return id, e
    raise NoInput()


def histogram(circuit: Element, values: Mapping, shown: Mapping[str, Quantity], tol: float) -> dict:
    found = spreads(circuit, values, list(shown.values()), tol)
    return {"histogram": {"values": {n: list(found[q]) for n, q in shown.items()}}}
