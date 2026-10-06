"""Code cells: run in one shared namespace, like Jupyter, with ``electro`` in it, each schematic cell's
problem as a variable named after it, and helpers that show things.

The value of a cell's last expression is shown, and whatever it gives ``display``: a circuit or a schematic
as a drawing (``schematic``), a solution as its worked steps (``steps``), plots (``plot``, ``bode``,
``spread``), a task to answer (``task``), an error caught on purpose, math, else its text. All as data: the
page draws and says them (``Output`` in ``shared/model/types.ts``)."""

from __future__ import annotations

import ast
import contextlib
import io
import json
import warnings
from collections.abc import Mapping

import sympy as sp
from electro import Element, Node, Solution, Trace
from electro.circuit.names import names
from electro.circuit.quantities import Current, Parameter, Power, Quantity, Voltage

from . import plots
from . import task as tasks
from .code_view import PRELUDE, variable
from .drawing import Drawing, from_drawing, to_drawing
from .errors import CELL, NoSuchSchematic, error, issue, warning
from .names import named
from .results import element_result
from .steps import steps as steps_data

namespace: dict = {}
units: dict[str, str] = {}
"""Each kind's value's unit (``resistor`` → ``Ω``), as the page has them."""


class Shown:
    """Something a cell shows: its output as data."""

    def __init__(self, output: dict) -> None:
        self.output = output

    def _output_(self) -> dict:
        return self.output


def _parts(circuit: Element) -> tuple[dict[str, Element], dict[str, Node]]:
    """Its elements by label, its points by name."""
    n = names(circuit)
    return {label: e for e, label in n.labels.items()}, {str(v)[2:]: p for p, v in n.points.items()}


def _units_of(circuit: Element) -> dict[str, str]:
    """Each element's value's unit, by its label."""
    elements, _ = _parts(circuit)
    return {label: units.get(e.kind, "") for label, e in elements.items()}


def _name(q: Quantity, circuit: Element) -> str:
    """A quantity as one writes it: ``I_R_1``, ``U_R_1``, ``P_R_1``, ``R_1``, ``V_A``."""
    n = names(circuit)
    match q:
        case Current(e, None) | Voltage(e) | Power(e):
            return f"{'I' if isinstance(q, Current) else 'U' if isinstance(q, Voltage) else 'P'}_{n.labels[e]}"
        case Parameter(e, ""):
            return n.labels[e]
    return str(n.of(q))


def steps(solution: Solution, *find: Quantity) -> Shown:
    """A solution's worked steps: the data, each step and why it holds, the answer to ``find``."""
    return Shown({"type": "solution", "data": steps_data(solution, find, _units_of(solution.circuit))})


def schematic(what: Element | Drawing, values: Mapping | None = None, solution: Solution | None = None) -> Shown:
    """A circuit (and its ``values``) as a drawing, laid out by the page; with ``solution``, each element's
    values on it."""
    circuit, values = (what.circuit, what.values) if isinstance(what, Drawing) else (what, values or {})
    out: dict = {"type": "schematic", "netlist": to_drawing(circuit, values)}
    if solution is not None:
        elements, _ = _parts(circuit)
        by_unit = _units_of(circuit)
        out["results"] = {id: element_result(solution, values, e, by_unit[id]) for id, e in elements.items()}
    return Shown(out)


def plot(trace: Trace, *qs: str | Quantity) -> Shown:
    """A run's quantities in time, each a quantity or a name (by default its named points' potentials, else
    its capacitors' and inductors' voltages)."""
    circuit = trace.phi.circuit
    if qs:  # by name, anything it reads: a pin's current too ("I_Q_1_c")
        series = {q if isinstance(q, str) else _name(q, circuit): trace(q) for q in qs}
    else:
        series = {n: trace(q) for n, q in plots.outputs(*_parts(circuit)).items()}
    return Shown({"type": "plot", **plots.trace({"name": "t", "unit": "s"}, trace.t, series)})


def bode(circuit: Element, values: Mapping, *qs: str | Quantity) -> Shown:
    """The frequency response of ``qs`` (by default as ``plot``'s), per the circuit's source."""
    elements, points = _parts(circuit)
    name, source = plots.input_of(elements)
    shown = _by_name(circuit, qs) if qs else plots.outputs(elements, points)
    return Shown({"type": "plot", **plots.bode(circuit, values, shown, source, name)})


def spread(circuit: Element, values: Mapping, *qs: str | Quantity, tol: float = 0.05) -> Shown:
    """``qs`` over 500 builds, every R, C and L within ``tol``."""
    return Shown({"type": "plot", **plots.histogram(circuit, values, _by_name(circuit, qs), tol)})


def _by_name(circuit: Element, qs: tuple[str | Quantity, ...]) -> dict[str, Quantity]:
    """Each by its name: ``"V_A"``, or a quantity named so."""
    n = names(circuit)
    return {q if isinstance(q, str) else _name(q, circuit): named(q, n) if isinstance(q, str) else q for q in qs}


def task(circuit: Element, values: Mapping, find: str | Quantity, prompt: str = "", *, tol: float = 0.01) -> tasks.Task:
    """A field to answer ``find`` in, the answer checked (``task.py``)."""
    return tasks.task(circuit, values, find, prompt, tol=tol, units=units)


def to_output(obj: object) -> dict:
    if isinstance(obj, Element | Drawing):
        obj = schematic(obj)
    if isinstance(obj, Solution):
        obj = steps(obj)
    if hasattr(obj, "_output_"):
        return obj._output_()  # pyright: ignore[reportAttributeAccessIssue]
    if isinstance(obj, BaseException):  # an error caught and shown on purpose: display(e)
        said = issue(obj)
        return {
            "type": "issue",
            "kind": "error",
            "data": f"{type(obj).__name__}: {obj}",
            **({"issue": said} if said else {}),
        }
    if isinstance(obj, sp.Basic):
        return {"type": "markdown", "data": f"$\\displaystyle {sp.latex(obj)}$"}
    for method, kind in (("_repr_svg_", "svg"), ("_repr_markdown_", "markdown"), ("_repr_latex_", "markdown")):
        data = getattr(obj, method, lambda: None)()
        if data is not None:
            return {"type": kind, "data": data}
    return {"type": "text", "data": repr(obj)}


HELPERS = {"steps": steps, "schematic": schematic, "plot": plot, "bode": bode, "spread": spread, "task": task}


def reset() -> None:
    """Forget everything the cells defined."""
    namespace.clear()
    exec(PRELUDE, namespace)
    namespace.update(HELPERS)


def run(code: str, problems_json: str = "{}", units_json: str = "{}") -> str:
    """Run one cell, the schematic cells' problems (``problem.ts``'s data, by name) as variables; returns a
    JSON list of outputs."""
    units.update(json.loads(units_json))
    outputs: list[dict] = []
    problems = {name: from_drawing(data) for name, data in json.loads(problems_json).items()}

    def schemat(name: str) -> Drawing:
        if name not in problems:
            raise NoSuchSchematic(name=name, available=list(problems))
        return problems[name]

    namespace["schemat"] = schemat
    for name, problem in problems.items():  # "Układ 1" is układ1 in code
        namespace[variable(name)] = problem
    namespace["display"] = lambda *objects: outputs.extend(to_output(o) for o in objects)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.simplefilter("ignore", DeprecationWarning)  # the libraries' own (sympy's), not the reader's
        try:
            tree = ast.parse(code, CELL)
            last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
            assert last is None or isinstance(last, ast.Expr)
            exec(compile(tree, CELL, "exec"), namespace)
            if last is not None:
                value = eval(compile(ast.Expression(last.value), CELL, "eval"), namespace)
                if value is not None:
                    outputs.append(to_output(value))
        except Exception as err:  # noqa: BLE001 — every error is shown to the user
            outputs.append(error(err))
    printed = stdout.getvalue()
    if printed:
        outputs.insert(0, {"type": "stream", "data": printed})
    outputs += [warning(w.message) for w in caught]
    return json.dumps(outputs, ensure_ascii=False)


reset()
