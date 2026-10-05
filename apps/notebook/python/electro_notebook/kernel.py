"""Notebook kernel: runs cells in one shared namespace and turns results into outputs.

Every cell sees what earlier cells defined, like in Jupyter. The value of the last
expression is shown; objects with ``_repr_svg_`` / ``_repr_markdown_`` show as a
picture / formatted text, a worked solution (``steps(sol)``) as data. Schematic cells are
available as ``schemat("name")``.

Nothing here is said in words: what goes wrong is an issue type (``electro.issues``), sent
as JSON — ``{"type": "MissingData", "targets": ["R_{2}"], …}``, math in LaTeX — and the
notebook says it in the reader's language. Python's own errors (NameError, …) stay as
Python says them.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import re
import traceback
import warnings
from dataclasses import fields, is_dataclass

import electro.core as core
import sympy as sp
from electro.components import Law
from electro.issues import Equals, Issue, IsZero, issue
from electro.task import Task
from electro_render import Steps, symbol_library
from electro_schematic import Schematic

CELL = "<cell>"
PRELUDE = """
from electro import *
from electro_render import schematic, steps
from electro_schematic import Schematic, layout
"""

namespace: dict = {}


@issue
class NoSweepRange(Issue, ValueError):
    """A sweep of an element with no number for its value needs its range typed."""

    element: str


@issue
class NoCircuitInCode(Issue, ValueError):
    """The code view defines no circuit: it should assign one, e.g. ``variable = loop(...)``."""

    variable: str


@issue
class NoSuchSchematic(Issue, KeyError):
    name: str
    available: list


def reset() -> None:
    """Forget everything the cells defined."""
    namespace.clear()
    exec(PRELUDE, namespace)


def symbols() -> str:
    return json.dumps(symbol_library(), ensure_ascii=False)


def variable(name: str) -> str:
    """A schematic's name as the Python variable cells see it: ``"Układ 1"`` → ``układ1``."""
    v = re.sub(r"\W", "", name.lower())
    if not v:
        return "uklad"
    return f"_{v}" if v[0].isdigit() else v


def code(problem_json: str, name: str) -> str:
    """A drawing (its problem, ``schematic/problem.ts``) as electro code, for the code view."""
    from electro.core.code.write import code as written
    from electro.core.problem.netlist import from_netlist

    return written(from_netlist(json.loads(problem_json)).problem, variable(name))


def from_code(source: str, name: str) -> str:
    """The code view edited back: ``source`` run, its problem (the variable called like the schematic,
    ``uklad``, else the last one it makes; a circuit alone is a problem with no data) as data, and the
    series and parallel it is made of, for the page to lay out. Returns JSON ``{"netlist": {...},
    "shape": {...} | null}`` or ``{"error": {...}}``."""
    from electro.core import Circuit, Problem, to_netlist
    from electro.core.code.structure import shape, to_data

    var = variable(name)
    scope: dict = {}
    exec("from electro.core import *", scope)
    prelude = set(scope)
    try:
        exec(compile(source, CELL, "exec"), scope)
        found = scope.get(var)
        if not isinstance(found, Problem | Circuit):
            made = [v for k, v in scope.items() if k not in prelude and isinstance(v, Problem | Circuit)]
            if not made:
                raise NoCircuitInCode(var)
            found = made[-1]
        problem = found if isinstance(found, Problem) else Problem(found)
        laid = shape(problem)
        return json.dumps(
            {"netlist": to_netlist(problem), "shape": to_data(laid) if laid is not None else None}, ensure_ascii=False
        )
    except Exception as err:  # noqa: BLE001 — any mistake in the code is shown to the user
        return json.dumps({"error": _error(err)}, ensure_ascii=False)


def frequency(problem_json: str) -> str:
    """The frequency button of a schematic cell: its outputs (``_outputs``) against the frequency, per
    its one source. Returns JSON ``{"bode": {"f", "input", "outputs": {name: {"gain", "phase"}},
    "cutoffs"}}`` (decibels, degrees, hertz) or ``{"error": {...}}``."""
    from electro.core import responses
    from electro.core.problem.netlist import from_netlist

    try:
        net = from_netlist(json.loads(problem_json))
        sources = [e for e in net.elements.values() if e.kind.name in ("voltage_source", "sine_source")]
        if not sources:
            raise NoInput()
        outputs = _outputs(net)
        if not outputs:
            raise NoOutput()
        found = responses(net.problem, list(outputs.values()), sources[0])
        first = found[next(iter(outputs.values()))]
        bode = {
            "f": list(first.f),
            "input": sources[0].name,
            "outputs": {
                n: {"gain": list(found[q].gain_db), "phase": list(found[q].phase_deg)} for n, q in outputs.items()
            },
            "cutoffs": first.cutoffs(),
        }
        return json.dumps({"bode": bode})
    except Exception as err:  # noqa: BLE001 — shown under the drawing
        return json.dumps({"error": _error(err)}, ensure_ascii=False)


def sweep_plot(problem_json: str, element: str, lo: str = "", hi: str = "") -> str:
    """The sweep in an element's inspector: the outputs as its value goes from ``lo`` to ``hi`` (by
    default a tenth of it to ten times it), 100 steps; with sines, their amplitudes. Returns JSON
    ``{"trace": {"x": {"name", "unit"}, "t", "series": {name: [...]}}}`` or ``{"error": {...}}``."""
    from electro.core import I, U, sweeps
    from electro.core.problem.netlist import from_netlist
    from electro.values import parse

    try:
        data = json.loads(problem_json)
        net = from_netlist(data)
        e = net.elements[element]
        unit = next((x.get("unit", "") for x in data["elements"] if x["id"] == element), "")
        if not (lo.strip() and hi.strip()):
            value = parse(next(x.get("value") for x in data["elements"] if x["id"] == element))
            if not isinstance(value, sp.Number):
                raise NoSweepRange(element)
            lo, hi = lo.strip() or value / 10, hi.strip() or value * 10
        a, b = float(parse(lo)), float(parse(hi))
        values = [a + (b - a) * k / 99 for k in range(100)]
        outputs = _outputs(net, named_only=True) or {f"U_{element}": U(e), f"I_{element}": I(e)}
        found = sweeps(net.problem, e, values, list(outputs.values()))
        series = {n: [_amplitude(v) for v in found[q].results] for n, q in outputs.items()}
        return json.dumps({"trace": {"x": {"name": element, "unit": unit}, "t": values, "series": series}})
    except Exception as err:  # noqa: BLE001 — shown under the drawing
        return json.dumps({"error": _error(err)}, ensure_ascii=False)


def spread(problem_json: str, tol: float = 0.05) -> str:
    """The tolerance button: the outputs over many builds, every R, C and L within ``tol``. Returns JSON
    ``{"histogram": {"values": {name: [...]}}}`` or ``{"error": {...}}``."""
    from electro.core import U, spreads
    from electro.core.problem.netlist import from_netlist

    try:
        net = from_netlist(json.loads(problem_json))
        outputs = _outputs(net, named_only=True)
        if not outputs:
            varied = [e for e in net.elements.values() if e.kind.positive and e in net.problem.given][:4]
            outputs = {f"U_{e.name}": U(e) for e in varied}
        found = spreads(net.problem, list(outputs.values()), tol)
        return json.dumps({"histogram": {"values": {n: list(found[q].values) for n, q in outputs.items()}}})
    except Exception as err:  # noqa: BLE001 — shown under the drawing
        return json.dumps({"error": _error(err)}, ensure_ascii=False)


def _outputs(net, named_only: bool = False) -> dict:
    """What a plot shows: the potentials of the points the drawing names, else (``named_only`` not) the
    capacitors' and inductors' voltages."""
    from electro.core import U, V

    named = {
        f"V_{n}": V(p) for n, p in net.points.items() if n not in ("GND", "0") and not re.fullmatch(r"(.+_)?n\d+", n)
    }
    if named or named_only:
        return named
    return {f"U_{id}": U(e) for id, e in net.elements.items() if e.kind.name in ("capacitor", "inductor")}


def _amplitude(v) -> float:
    z = complex(v)
    return abs(z) if abs(z.imag) > 1e-12 * max(1.0, abs(z)) else z.real


@issue
class NoOutput(Issue, ValueError):
    """A plot needs something to show: no point is named, and nothing has a capacitor's or an inductor's
    voltage."""


@issue
class NoInput(Issue, ValueError):
    """A frequency response needs a source to be the input: the circuit has none."""


def task_values(problem_json: str, steps_json: str) -> str:
    """The AI's ``solve`` tool: each step's ``value`` (a quantity's name or an expression of them,
    ``U_E_1 / I_E_1``, ``core.problem.names``) on a drawing's problem, as the board shows it. Returns JSON
    ``{"values": {step: {"value": x} | {"error": ...}}}`` (an AC one as its amplitude) or ``{"error": {...}}``
    (the circuit)."""
    from electro.core.problem.names import evaluated
    from electro.core.problem.netlist import from_netlist

    try:
        net = from_netlist(json.loads(problem_json))
        solution, _ = _solved(net.problem, net)
    except Exception as err:  # noqa: BLE001 — said to the AI
        return json.dumps({"error": _error(err)}, ensure_ascii=False)
    values: dict[str, dict] = {}
    for step in json.loads(steps_json):
        try:
            value = evaluated(step["value"], lambda q: _shown(solution, q), net.elements, net.points)
            values[step["id"]] = {"value": _amplitude(sp.N(value))}
        except Exception as err:  # noqa: BLE001 — said by the step that has it
            values[step["id"]] = {"error": _error(err)}
    return json.dumps({"values": values}, ensure_ascii=False)


def solve(problem_json: str) -> str:
    """The run button of a schematic cell: its problem (``schematic/problem.ts``: the elements, what its
    marks give, ``marks`` — each mark's id, quantity and unit — and ``sought``, each key's quantity and
    unit) solved on paper.

    Returns JSON ``{"results": {id: {...}}, "problems": [...], "found": {key: value | null}}``: every
    element's value, voltage, current and power, each mark's value, what each sought key came to, and
    what could not be found or went wrong."""
    from electro.core import Problem
    from electro.core.problem.netlist import from_netlist, quantity

    data = json.loads(problem_json)
    units = {e["id"]: e.get("unit", "") for e in data["elements"]}
    problems: list[dict] = []
    problem = None
    try:
        net = from_netlist(data)
        find = [quantity(q, net.elements, net.points) for _, q, _ in data.get("sought") or () if q[0] != "R"]
        problem = Problem(net.problem.circuit, net.problem.given, find)
        solution, filled = _solved(problem, net)
    except Exception as err:  # noqa: BLE001 — every error is said on the board
        return json.dumps(
            {"results": {}, "problems": [_said("error", err, problem, units)], "found": {}}, ensure_ascii=False
        )
    try:
        _ = solution.answers
    except Exception as err:  # noqa: BLE001 — what was not found: a warning, the rest stands
        problems.append(_said("warning", err, problem, units))
    results = {id: _element_result(solution, e, units, filled.get(id)) for id, e in net.elements.items()}
    for id, q, unit, given in data.get("marks") or ():
        value = _number(solution, quantity(q, net.elements, net.points))
        if value is not None:
            results[id] = {
                "value": _fmt(value, unit),
                "solved": not given,
                "U": None,
                "I": None,
                "P": None,
                "reversed": False,
            }
    found = {key: _found(solution, net, q, unit) for key, q, unit in data.get("sought") or ()}
    return json.dumps({"results": results, "problems": problems, "found": found}, ensure_ascii=False)


def _solved(problem, net):
    """Solved, a hole filled with the simplest element that fits (``{id: what it is}``)."""
    from electro.core import fill, solve

    holes = [(id, e) for id, e in net.elements.items() if e.kind.name == "hole"]
    if len(holes) == 1:
        id, hole = holes[0]
        filled = fill(problem, hole)
        return filled.solution, {id: filled.by}
    return solve(problem), {}


SOURCES = ("voltage_source", "current_source", "sine_source", "square_source")
METERS = {"ammeter": core.I, "voltmeter": core.U}
"""A meter's value is its reading: the current through it, the voltage across it."""
"""Shown as a source is: its voltage the rise from its first end to its second, its power what it gives."""


def _element_result(solution, e, units: dict, filled) -> dict:
    from electro.core import Current, Parameter, Power, Voltage

    id = e.name
    two = len(e.kind.terminals) == 2
    by = filled if filled is not None else e
    value = _number(solution, Parameter(by)) if "" in by.kind.parameters else None
    given = _given(solution.problem.given.get(e))

    def shown(q):
        return _shown(solution, q)

    u = _number(shown, Voltage(by)) if two else None
    i = _number(shown, Current(by)) if two else None
    p = _number(shown, Power(by)) if two else None
    sign = -1 if i is not None and i.is_real and i < 0 else 1
    if e.kind.name in METERS:
        reading = u if e.kind.name == "voltmeter" else i
        shown = _fmt(reading, units.get(id, "")) if reading is not None else "?"
        solved = not _given(solution.problem.given.get(METERS[e.kind.name](e)))
        return {"value": shown, "solved": solved, "U": None, "I": None, "P": None, "reversed": False}
    if filled is not None:
        shown = _notation(filled, value)
    elif "" in e.kind.parameters:
        shown = _fmt(value, units.get(id, "")) if value is not None else "?"
    else:
        shown = ""
    return {
        "value": shown,
        "solved": filled is not None or ("" in e.kind.parameters and not given and value is not None),
        "U": _fmt(sign * u, "V") if u is not None else None,
        "I": _fmt(sign * i, "A") if i is not None else None,
        "P": _fmt(p, "W") if p is not None and not p.has(sp.I) else None,
        "reversed": sign < 0,
    }


def _given(value) -> bool:
    """A value given to an element: its main one (an element of several may be given others only)."""
    from collections.abc import Mapping

    from electro.values import UNKNOWN

    if isinstance(value, Mapping):
        return "" in value and value[""] is not UNKNOWN
    return value is not None and value is not UNKNOWN


def _notation(by, value) -> str:
    """What a hole turned out to be, in values: ``R = 2 Ω``, ``E = 12 V``, ``R = ∞`` (a break), ``R = 0 Ω``."""
    from electro.values import fmt

    match by.kind.name:
        case "wire":
            return f"R = {fmt(0, 'Ω')}"
        case "open":
            return "R = ∞"
        case "resistor":
            return f"R = {fmt(value, 'Ω')}"
        case "voltage_source":
            return f"E = {fmt(value, 'V')}"
    return f"J = {fmt(value, 'A')}"


def _shown(solution, q):
    """``q`` as the board shows it: a source's voltage the rise across it, its power what it gives."""
    from electro.core import Power, Voltage

    v = solution(q)
    return -v if isinstance(q, Voltage | Power) and q.of.kind.name in SOURCES else v


def _number(read, q):
    """``q`` found (by ``read``: a solution, or what shows it), or None."""
    try:
        v = read(q)
    except Exception:  # noqa: BLE001 — not found: none
        return None
    return v if v.is_number else None


def _found(solution, net, q, unit: str) -> str | None:
    from electro.core import between, thevenin

    if q[0] == "R":
        try:
            t = thevenin(between(solution.problem, net.points[q[1]], net.points[q[2]], solution.analysis))
        except Exception:  # noqa: BLE001 — not two points of it: none
            return None
        return _fmt(t.Z, unit) if t is not None and t.Z.is_number else None
    from electro.core.problem.netlist import quantity

    value = _number(solution, quantity(q, net.elements, net.points))
    return None if value is None else _fmt(value, unit)


def _fmt(value, unit: str) -> str:
    from electro.values import fmt

    return fmt(value, unit)


def _said(kind: str, err, problem, units: dict) -> dict:
    from electro.core.report.issues import issue

    said = issue(err, problem, units)
    return {"kind": kind, "issue": said} if said is not None else {"kind": kind, "text": str(err)}


def live(problem_json: str) -> str:
    """The play button of a schematic cell: its problem (the drawing as data, ``schematic/problem.ts``)
    compiled for the page's engine (``simulation/engine.ts``). Returns JSON ``{"program": {...}}`` or
    ``{"error": {...}}``."""
    from electro.core import compile_program
    from electro.core.problem.netlist import from_netlist

    try:
        program = compile_program(from_netlist(json.loads(problem_json)).problem)
    except Exception as err:  # noqa: BLE001 — shown on the board
        return json.dumps({"error": _error(err)}, ensure_ascii=False)
    return json.dumps({"program": json.loads(program.to_json())}, ensure_ascii=False)


def to_json(x):
    """An issue, a reason or a solution's steps as JSON: ``{"type": "OhmsLaw", "label": "R_{1}"}``.
    Quantities and expressions become LaTeX (``R_{1}``, ``\\frac{U}{I}``), the rest stays as it is."""
    from electro_render.trace import expr, name, value

    if isinstance(x, Law):
        return {"equation": f"{expr(x.expr)} = 0", "reason": to_json(x.reason)}
    if isinstance(x, Equals):
        return f"{name(x.symbol.name)} = {value(x.value, x.unit)}"
    if isinstance(x, IsZero):
        return f"{expr(x.expr)} = 0"
    if isinstance(x, Issue) or (is_dataclass(x) and not isinstance(x, type)):
        shown = [f for f in fields(x) if f.metadata.get("shown", True)] if is_dataclass(x) else []
        return {"type": type(x).__name__, **{f.name: to_json(getattr(x, f.name)) for f in shown}}
    if isinstance(x, sp.Symbol):
        return name(x.name)
    if isinstance(x, sp.Basic):
        return expr(x)
    if isinstance(x, (list, tuple)):
        return [to_json(v) for v in x]
    return x


def _issue(err) -> dict | None:
    """An error of ours as data: the library's issues, and the core's errors by their fields (a label in
    LaTeX)."""
    if isinstance(err, Issue):
        return to_json(err)
    from electro.core.report.issues import issue

    return issue(err)


def to_output(obj) -> dict:
    if isinstance(obj, Schematic):  # a schematic cell's variable on its own: show the drawing
        from electro_render import schematic

        obj = schematic(obj)
    if isinstance(obj, Steps):
        return {"type": "solution", "data": to_json(obj)}
    if isinstance(obj, Task):  # a field to answer in: the answer only as hashes (electro.task)
        from electro_render.trace import name

        return {
            "type": "task",
            "prompt": obj.prompt,
            "quantity": obj.quantity,
            "tex": name(obj.quantity),
            "unit": obj.unit,
            "tol": obj.tol,
            "hashes": list(obj.hashes),
            "amplitude": obj.amplitude,
        }
    if isinstance(obj, Issue):  # an error caught and shown on purpose: display(e)
        kind = "warning" if isinstance(obj, Warning) else "error"
        return {"type": "issue", "kind": kind, "data": repr(obj), "issue": to_json(obj)}
    for method, kind in (("_repr_svg_", "svg"), ("_repr_markdown_", "markdown"), ("_repr_latex_", "markdown")):
        data = getattr(obj, method, lambda: None)()  # sympy defines some of these and returns None
        if data is not None:
            return {"type": kind, "data": data}
    return {"type": "text", "data": repr(obj)}


def _error(err: BaseException) -> dict:
    """An error output: our issue as data (``issue``), anything else as Python says it; ``line``:
    the line of the cell it came from (not the library internals)."""
    lines = [frame.lineno for frame in traceback.extract_tb(err.__traceback__) if frame.filename == CELL]
    issue = _issue(err)
    out: dict = {"type": "error", "data": repr(err) if isinstance(err, Issue) else f"{type(err).__name__}: {err}"}
    if issue is not None:
        out["issue"] = issue
    if lines:
        out["line"] = lines[-1]
    return out


def _warning(message) -> dict:
    if isinstance(message, Issue):
        return {"type": "warning", "data": repr(message), "issue": to_json(message)}
    return {"type": "warning", "data": str(message)}


def run(code: str, schematics_json: str = "{}", standard: str = "iec") -> str:
    """Run one cell; returns a JSON list of outputs ``{"type": ..., "data": ...}``. Schematics are
    drawn with ``standard``'s symbols (the note's: "iec" or "ieee")."""
    from electro_render.symbols import use

    use(standard)
    outputs: list[dict] = []
    drawings = {name: Schematic.from_json(text) for name, text in json.loads(schematics_json).items()}

    def schemat(name: str) -> Schematic:
        if name not in drawings:
            raise NoSuchSchematic(name, list(drawings))
        return drawings[name]

    namespace["schemat"] = schemat
    for name, drawing in drawings.items():  # "Układ 1" is układ1 in code
        namespace[variable(name)] = drawing
    namespace["display"] = lambda *objects: outputs.extend(to_output(o) for o in objects)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.simplefilter("ignore", DeprecationWarning)  # the libraries' own (sympy's), not the reader's
        try:
            tree = ast.parse(code, CELL)
            last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
            exec(compile(tree, CELL, "exec"), namespace)
            if last is not None:
                value = eval(compile(ast.Expression(last.value), CELL, "eval"), namespace)
                if value is not None:
                    outputs.append(to_output(value))
        except Exception as err:  # noqa: BLE001 — every error is shown to the user
            outputs.append(_error(err))
    printed = stdout.getvalue()
    if printed:
        outputs.insert(0, {"type": "stream", "data": printed})
    outputs += [_warning(w.message) for w in caught]
    return json.dumps(outputs, ensure_ascii=False)


reset()
