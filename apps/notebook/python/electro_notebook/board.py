"""A schematic cell's buttons, each given the drawing as a problem in data (``schematic/problem.ts``): solved
on paper, compiled to run in time, its frequency response, a sweep of one element, the spread over builds.
Each returns JSON: what it found, or ``{"error": …}``."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import cast

import sympy as sp
from electro import Element, I, U, step_function
from electro.values import parse

from . import plots, readings
from .drawing import Drawing, from_drawing, quantity
from .errors import NoSweepRange, error
from .issues import issue
from .methods import resistance, swept
from .names import names
from .results import amplitude, element_result, number, solved
from .text import fmt


def _answer(work: Callable[[], dict]) -> str:
    """``work``'s data, or the error it ran into, as JSON."""
    try:
        return json.dumps(work(), ensure_ascii=False)
    except Exception as err:  # noqa: BLE001 — shown under the drawing
        return json.dumps({"error": error(err)}, ensure_ascii=False)


def solve(problem_json: str) -> str:
    """The run button: the problem (its elements, its ``marks`` — each mark's id, quantity, unit and whether it
    is given — and ``sought``, each key's quantity and unit) solved on paper. Returns ``{"results": {id: {...}},
    "problems": [...], "found": {key: value | null}}``: every element's value, voltage, current and power, each
    mark's value, what each sought key came to, and what could not be found or went wrong."""
    data = json.loads(problem_json)
    units = {e["id"]: e.get("unit", "") for e in data["elements"]}
    try:
        net = from_drawing(data)
        solution, filled = solved(net.circuit, net.values, net.elements)
    except Exception as err:  # noqa: BLE001 — every error is said on the board
        return json.dumps({"results": {}, "problems": [_said("error", err, units)], "found": {}}, ensure_ascii=False)
    results = {
        id: element_result(solution, net.values, e, units.get(id, ""), filled.get(id)) for id, e in net.elements.items()
    }
    results |= _marks(solution, net, data.get("marks") or ())
    found = {key: _found(solution, net, q, unit) for key, q, unit in data.get("sought") or ()}
    problems = _lacking(solution, net, data.get("sought") or (), units)
    return json.dumps({"results": results, "problems": problems, "found": found}, ensure_ascii=False)


def _marks(solution, net: Drawing, marks) -> dict:
    """Each mark on the drawing that was found: its value, shown as a result."""
    out = {}
    for id, q, unit, given in marks:
        value = number(solution, quantity(q, net.elements, net.points))
        if value is not None:
            out[id] = {
                "value": fmt(value, unit),
                "solved": not given,
                "U": None,
                "I": None,
                "P": None,
                "reversed": False,
            }
    return out


def _lacking(solution, net: Drawing, sought, units: dict) -> list[dict]:
    """What is sought (by the drawing or by a key) and could not be found, said as a warning."""
    find = [quantity(q, net.elements, net.points) for _, q, _ in sought if q[0] != "R"]
    try:
        solution.answers(*net.find, *find)
    except Exception as err:  # noqa: BLE001 — what was not found: a warning, the rest stands
        return [_said("warning", err, units)]
    return []


def _found(solution, net: Drawing, q: list, unit: str) -> str | None:
    """A sought key's value: a quantity's, or ``["R", a, b]`` the resistance between two points."""
    if q[0] == "R":
        try:
            z = resistance(net.circuit, net.values, net.points[q[1]], net.points[q[2]], solution.frame)
        except Exception:  # noqa: BLE001 — not two points of it: none
            return None
        return fmt(z, unit) if z is not None and z.is_number else None
    value = number(solution, quantity(q, net.elements, net.points))
    return None if value is None else fmt(value, unit)


def _said(kind: str, err: BaseException, units: dict) -> dict:
    said = issue(err, units)
    return {"kind": kind, "issue": said} if said is not None else {"kind": kind, "text": str(err)}


def live(problem_json: str) -> str:
    """The play button: Φ, the step function, for the page's engine (``simulation/engine.ts``): ``{"program": {...}}``."""

    def work() -> dict:
        net = from_drawing(json.loads(problem_json))
        return {"program": program(net.circuit, net.values)}

    return _answer(work)


def program(circuit: Element, values: Mapping) -> dict:
    """Φ as the page's engine runs it, reading what ``readings`` reads and the current into each terminal; and
    where in that the page finds each point (``nodes``), each element's quantities (``parts``), its kind
    (``kinds``) and its terminals' currents (``flows``)."""
    labels = names(circuit).labels
    flowing = {f"{labels[e]}.{t}": c for e in circuit.members for t, c in e.I.items()}
    seen = {**readings.reads(circuit), **flowing}
    place = {name: k for k, name in enumerate(seen)}
    return {
        **json.loads(step_function(circuit, values).to_json(seen)),
        "nodes": {str(v)[2:]: place[str(v)] for v in names(circuit).points.values()},
        "parts": {
            label: {name: place[called] for name, (called, _) in named.items()}
            for label, named in readings.by_element(circuit).items()
        },
        "kinds": {labels[e]: e.kind for e in circuit.members},
        "flows": {labels[e]: [place[f"{labels[e]}.{t}"] for t in e.terminals] for e in circuit.members},
    }


def frequency(problem_json: str) -> str:
    """The frequency button: the outputs (``plots.outputs``) against the frequency, per the circuit's
    source: ``{"bode": {"f", "input", "outputs": {name: {"gain", "phase"}}, "cutoffs"}}`` (decibels,
    degrees, hertz)."""

    def work() -> dict:
        net = from_drawing(json.loads(problem_json))
        name, source = plots.input_of(net.elements)
        return plots.bode(net.circuit, net.values, plots.outputs(net.elements, net.points), source, name)

    return _answer(work)


def sweep_plot(problem_json: str, element: str, lo: str = "", hi: str = "") -> str:
    """The sweep in an element's inspector: the outputs as its value goes from ``lo`` to ``hi`` (by default
    a tenth of it to ten times it), 100 steps; with sines, their amplitudes: ``{"trace": …}``."""

    def work() -> dict:
        data = json.loads(problem_json)
        net = from_drawing(data)
        e = net.elements[element]
        item = next(x for x in data["elements"] if x["id"] == element)
        a, b = _range(element, item.get("value"), lo, hi)
        values = [a + (b - a) * k / 99 for k in range(100)]
        shown = plots.outputs(net.elements, net.points, named_only=True) or {f"U_{element}": U(e), f"I_{element}": I(e)}
        found = swept(net.circuit, net.values, e, values, list(shown.values()))
        series = {n: [amplitude(v) for v in found[q]] for n, q in shown.items()}
        return plots.trace({"name": element, "unit": item.get("unit", "")}, values, series)

    return _answer(work)


def _range(element: str, value: str | None, lo: str, hi: str) -> tuple[float, float]:
    if not (lo.strip() and hi.strip()):
        number = parse(value)
        if not isinstance(number, sp.Number):
            raise NoSweepRange(element=element)
        lo, hi = lo.strip() or number / 10, hi.strip() or number * 10
    return float(cast(sp.Expr, parse(lo))), float(cast(sp.Expr, parse(hi)))


def spread(problem_json: str, tol: float = 0.05) -> str:
    """The tolerance button: the outputs over many builds, every R, C and L within ``tol``:
    ``{"histogram": {"values": {name: [...]}}}``."""

    def work() -> dict:
        net = from_drawing(json.loads(problem_json))
        shown = plots.outputs(net.elements, net.points, named_only=True)
        if not shown:
            varied = [e for e in net.elements.values() if e.positive and e in net.values][:4]
            shown = {f"U_{e.name}": U(e) for e in varied}
        return plots.histogram(net.circuit, net.values, shown, tol)

    return _answer(work)
