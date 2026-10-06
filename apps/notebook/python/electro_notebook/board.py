"""A schematic cell's buttons, each given the drawing as a problem in data (``schematic/problem.ts``): solved
on paper, compiled to run in time, its frequency response, a sweep of one element, the spread over builds.
Each returns JSON: what it found, or ``{"error": …}``."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

import sympy as sp
from electro import I, Problem, U, step_function
from electro.values import fmt, parse

from . import plots
from .errors import NoSweepRange, error
from .issues import issue
from .methods import resistance, swept
from .netlist import Netlist, from_netlist, quantity
from .results import amplitude, element_result, number, solved


def _answer(work: Callable[[], dict]) -> str:
    """``work``'s data, or the error it ran into, as JSON."""
    try:
        return json.dumps(work(), ensure_ascii=False)
    except Exception as err:  # noqa: BLE001 — shown under the drawing
        return json.dumps({"error": error(err)}, ensure_ascii=False)


def solve(problem_json: str) -> str:
    """The run button: the problem (its elements, what its marks give, ``marks`` — each mark's id, quantity,
    unit and whether it is given — and ``sought``, each key's quantity and unit) solved on paper. Returns
    ``{"results": {id: {...}}, "problems": [...], "found": {key: value | null}}``: every element's value,
    voltage, current and power, each mark's value, what each sought key came to, and what could not be found
    or went wrong."""
    data = json.loads(problem_json)
    units = {e["id"]: e.get("unit", "") for e in data["elements"]}
    problem = None
    try:
        net = from_netlist(data)
        find = [quantity(q, net.elements, net.points) for _, q, _ in data.get("sought") or () if q[0] != "R"]
        problem = Problem(net.problem.circuit, net.problem.given, find)
        solution, filled = solved(problem, net.elements)
    except Exception as err:  # noqa: BLE001 — every error is said on the board
        said = _said("error", err, problem, units)
        return json.dumps({"results": {}, "problems": [said], "found": {}}, ensure_ascii=False)
    problems = []
    try:
        _ = solution.answers
    except Exception as err:  # noqa: BLE001 — what was not found: a warning, the rest stands
        problems.append(_said("warning", err, problem, units))
    results = {id: element_result(solution, e, units.get(id, ""), filled.get(id)) for id, e in net.elements.items()}
    for id, q, unit, given in data.get("marks") or ():
        value = number(solution, quantity(q, net.elements, net.points))
        if value is not None:
            results[id] = {
                "value": fmt(value, unit),
                "solved": not given,
                "U": None,
                "I": None,
                "P": None,
                "reversed": False,
            }
    found = {key: _found(solution, net, q, unit) for key, q, unit in data.get("sought") or ()}
    return json.dumps({"results": results, "problems": problems, "found": found}, ensure_ascii=False)


def _found(solution, net: Netlist, q: list, unit: str) -> str | None:
    """A sought key's value: a quantity's, or ``["R", a, b]`` the resistance between two points."""
    if q[0] == "R":
        try:
            z = resistance(solution.problem, net.points[q[1]], net.points[q[2]], solution.analysis)
        except Exception:  # noqa: BLE001 — not two points of it: none
            return None
        return fmt(z, unit) if z is not None and z.is_number else None
    value = number(solution, quantity(q, net.elements, net.points))
    return None if value is None else fmt(value, unit)


def _said(kind: str, err: BaseException, problem, units: dict) -> dict:
    said = issue(err, problem, units)
    return {"kind": kind, "issue": said} if said is not None else {"kind": kind, "text": str(err)}


def live(problem_json: str) -> str:
    """The play button: Φ, the step function, for the page's engine (``simulation/engine.ts``): ``{"program": {...}}``."""
    return _answer(
        lambda: {"program": json.loads(step_function(from_netlist(json.loads(problem_json)).problem).to_json())}
    )


def frequency(problem_json: str) -> str:
    """The frequency button: the outputs (``plots.outputs``) against the frequency, per the circuit's
    source: ``{"bode": {"f", "input", "outputs": {name: {"gain", "phase"}}, "cutoffs"}}`` (decibels,
    degrees, hertz)."""

    def work() -> dict:
        net = from_netlist(json.loads(problem_json))
        name, source = plots.input_of(net.elements)
        return plots.bode(net.problem, plots.outputs(net.elements, net.points), source, name)

    return _answer(work)


def sweep_plot(problem_json: str, element: str, lo: str = "", hi: str = "") -> str:
    """The sweep in an element's inspector: the outputs as its value goes from ``lo`` to ``hi`` (by default
    a tenth of it to ten times it), 100 steps; with sines, their amplitudes: ``{"trace": …}``."""

    def work() -> dict:
        data = json.loads(problem_json)
        net = from_netlist(data)
        e = net.elements[element]
        item = next(x for x in data["elements"] if x["id"] == element)
        a, b = _range(element, item.get("value"), lo, hi)
        values = [a + (b - a) * k / 99 for k in range(100)]
        shown = plots.outputs(net.elements, net.points, named_only=True) or {f"U_{element}": U(e), f"I_{element}": I(e)}
        found = swept(net.problem, e, values, list(shown.values()))
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
        net = from_netlist(json.loads(problem_json))
        shown = plots.outputs(net.elements, net.points, named_only=True)
        if not shown:
            varied = [e for e in net.elements.values() if e.kind.positive and e in net.problem.given][:4]
            shown = {f"U_{e.name}": U(e) for e in varied}
        return plots.histogram(net.problem, shown, tol)

    return _answer(work)
