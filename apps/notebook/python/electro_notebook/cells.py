"""Code cells: run in one shared namespace, like Jupyter, with ``electro`` in it, each schematic cell's
problem as a variable named after it, and helpers that show things.

The value of a cell's last expression is shown, and whatever it gives ``display``: a problem or a circuit as
a drawing (``schematic``), a solution as its worked steps (``steps``), plots (``plot``, ``bode``,
``spread``), a task to answer (``task``), an error caught on purpose, math, else its text. All as data: the
page draws and says them (``Output`` in ``shared/model/types.ts``)."""

from __future__ import annotations

import ast
import contextlib
import io
import json
import warnings

import sympy as sp
from electro import Circuit, Problem, Solution, Trace, from_netlist, to_netlist
from electro.problem.names import name_of, named, naming
from electro.problem.quantities import Quantity

from . import plots
from . import task as tasks
from .code_view import PRELUDE, variable
from .errors import CELL, NoSuchSchematic, error, issue, warning
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


def _units_of(problem: Problem) -> dict[str, str]:
    """Each element's value's unit, by its label."""
    elements, _ = naming(problem.circuit)
    return {label: units.get(e.kind.name, "") for label, e in elements.items()}


def steps(solution: Solution) -> Shown:
    """A solution's worked steps: the data, each step and why it holds, the answer."""
    return Shown({"type": "solution", "data": steps_data(solution, _units_of(solution.problem))})


def schematic(what: Problem | Circuit, solution: Solution | None = None) -> Shown:
    """A circuit as a drawing (laid out by the page); with ``solution``, each element's values on it."""
    problem = what if isinstance(what, Problem) else Problem(what)
    out: dict = {"type": "schematic", "netlist": to_netlist(problem)}
    if solution is not None:
        elements, _ = naming(problem.circuit)
        by_unit = _units_of(problem)
        out["results"] = {id: element_result(solution, e, by_unit[id]) for id, e in elements.items()}
    return Shown(out)


def _quantities(problem: Problem, qs: tuple[str | Quantity, ...]) -> dict[str, Quantity]:
    """Each by its name: ``"V_A"``, or a quantity named so."""
    elements, points = naming(problem.circuit)
    by_element, by_point = {e: k for k, e in elements.items()}, {p: k for k, p in points.items()}
    out = {}
    for q in qs:
        if isinstance(q, str):
            out[q] = named(q, elements, points)
        else:
            out[name_of(q, by_element, by_point)] = q
    return out


def plot(trace: Trace, *qs: str | Quantity) -> Shown:
    """A run's quantities in time, each a quantity or a name (by default its named points' potentials, else
    its capacitors' and inductors' voltages)."""
    elements, points = naming(trace.problem.circuit)
    if qs:  # by name, any of its unknowns: a pin's current too ("I_Q_1_c")
        by_element, by_point = {e: k for k, e in elements.items()}, {p: k for k, p in points.items()}
        series = {q if isinstance(q, str) else name_of(q, by_element, by_point): trace(q) for q in qs}
    else:
        series = {n: trace(q) for n, q in plots.outputs(elements, points).items()}
    return Shown({"type": "plot", **plots.trace({"name": "t", "unit": "s"}, trace.t, series)})


def bode(problem: Problem, *qs: str | Quantity) -> Shown:
    """The frequency response of ``qs`` (by default as ``plot``'s), per the circuit's source."""
    elements, points = naming(problem.circuit)
    name, source = plots.input_of(elements)
    shown = _quantities(problem, qs) if qs else plots.outputs(elements, points)
    return Shown({"type": "plot", **plots.bode(problem, shown, source, name)})


def spread(problem: Problem, *qs: str | Quantity, tol: float = 0.05) -> Shown:
    """``qs`` over 500 builds, every R, C and L within ``tol``."""
    return Shown({"type": "plot", **plots.histogram(problem, _quantities(problem, qs), tol)})


def task(problem: Problem, find: str | Quantity, prompt: str = "", *, tol: float = 0.01) -> tasks.Task:
    """A field to answer ``find`` in, the answer checked (``task.py``)."""
    return tasks.task(problem, find, prompt, tol=tol, units=units)


def to_output(obj: object) -> dict:
    if isinstance(obj, Problem | Circuit):
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
    problems = {name: from_netlist(data).problem for name, data in json.loads(problems_json).items()}

    def schemat(name: str) -> Problem:
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
