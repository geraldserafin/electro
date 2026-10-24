"""A solution's steps as data, for whoever shows them (the notebook: ``Steps`` in ``shared/model/issues.ts``):
the data; each step — one unknown from one equation as a chain, ``U_{R_{1}} = R_{1} I_{R_{1}} = 10·0.5 =
5 V``, and why it holds, or several unknowns together the way a school solves them (the nodal method: the
currents by Ohm's law put into Kirchhoff's at the nodes, the potentials from those, then each current); one
source and resistors in series and parallel by joining the resistors (``reduction``); and the answer to what
is sought."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import sympy as sp
from electro import AC, DC, Element, Origin, Solution, SolutionStep
from electro.errors import MissingData
from electro.frame import is_before
from electro.quantities import Quantity
from electro.structure import Block, structure
from electro.values import parse

from . import latex as tex
from .issues import issue
from .names import Names, names
from .reduction import by_reduction, formula_step

REASONS = {
    "resistor": "OhmsLaw",
    "voltage_source": "SourceVoltage",
    "current_source": "SourceCurrent",
    "ammeter": "IdealAmmeter",
    "voltmeter": "IdealVoltmeter",
    "opamp": "IdealOpAmp",
    "vcvs": "ControlledSource",
    "vccs": "ControlledSource",
    "ccvs": "ControlledSource",
    "cccs": "ControlledSource",
    "hole": "UnknownElement",
}
"""Why an element's law holds, by its kind (the rest: its model)."""

BY_ANALYSIS = {
    ("capacitor", DC): "CapacitorOpenDC",
    ("capacitor", AC): "CapacitorImpedance",
    ("inductor", DC): "InductorShortDC",
    ("inductor", AC): "InductorImpedance",
}


def steps(solution: Solution, find: Sequence[Quantity] = (), units: Mapping[str, str] | None = None) -> dict:
    """``find``: what is sought (by default the solution's); ``units``: each element's value's, by its label."""
    units = units or {}
    answer, missing = _answer_or_missing(solution, find or solution.find, units)
    return {
        "type": "Steps",
        "data": _data(solution, units),
        "assumed": [],
        "steps": by_reduction(solution, names(solution.circuit).labels) or _shown(solution, units),
        "answer": answer,
        "missing": missing,
    }


def _shown(solution: Solution, units: Mapping[str, str]) -> list[dict]:
    """The steps a book shows, in its names: one unknown from one equation as a chain, several together by
    the nodal method (``Page.together``). A datum is no step."""
    n = names(solution.circuit)
    page = Page(solution, n, _letters(solution, n), _references(solution), units)
    known = {n.rename(x): v for x, v in solution.data.items()}
    shown = []
    for step in (_renamed(s, n) for s in solution.steps):
        if step.how == "alone" and step.equations and step.because[0].what != "given":
            (x,), (value,), (origin,), (equation,) = step.found, step.values, step.because, step.equations
            shown.append(page.formula(x, value, origin, page.law(origin, equation), known))
        elif step.how == "together":
            shown += page.together(step, known)
        known |= dict(zip(step.found, step.values))
    return shown


Formulas = dict[sp.Symbol, tuple[sp.Expr, Origin]]
"""Each unknown an element's law gives, in letters, and that law."""


@dataclass(frozen=True)
class Page:
    """What showing the steps needs: the solution, its names, each law in letters by its origin
    (``letters``), the potentials set to 0 (``references``) and the units."""

    solution: Solution
    names: Names
    letters: Mapping[Origin, sp.Expr]
    references: frozenset[sp.Expr]
    units: Mapping[str, str]

    def law(self, origin: Origin, numbers: sp.Expr) -> sp.Expr:
        """The equation in letters when it is a law of the circuit, else as it was solved."""
        return self.letters.get(origin, numbers)

    def formula(self, x: sp.Symbol, value: sp.Expr, origin: Origin, equation: sp.Expr, known: Mapping) -> dict:
        """``x`` from ``equation``: ``x = formula = the formula's numbers = value``."""
        roots = sp.solve(equation, x) if x in equation.free_symbols else []
        formula = roots[0] if len(roots) == 1 else value
        return formula_step(x, formula, known, value, _unit(x, self.units), reason(origin, self.solution))

    def together(self, step: SolutionStep, known: Mapping) -> list[dict]:
        """Several unknowns found together, as a school does it: each element's current by its law (Ohm's)
        in the potentials, put into Kirchhoff's law at each node; the potentials from those, block by block;
        then each current from its law."""
        values = dict(zip(step.found, step.values))
        laws = [self.law(o, e) for o, e in zip(step.because, step.equations)]
        currents = _formulas(laws, step.because, {x for x in step.found if not x.name.startswith("V_")})
        if not currents:
            return [self.system([*zip(step.because, laws)], {}, step.found, values, known)]
        used = {o for _, o in currents.values()}
        rest = [(o, e) for o, e in zip(step.because, laws) if o not in used and not self.redundant(o)]
        put = {x: f for x, (f, _) in currents.items()}
        order = _order([e.xreplace(put) for _, e in rest], set(values) - set(currents))
        first = [b for b in order if all(x.name.startswith("V_") for x in b[1])]
        shown, known = self.blocks(first, rest, put, values, known)
        shown += [self.formula(x, values[x], o, x - f, known) for x, (f, o) in currents.items()]
        later, _ = self.blocks([b for b in order if b not in first], rest, {}, values, {**known, **values})
        return shown + later

    def blocks(self, order: list[Block], rest: list[tuple[Origin, sp.Expr]], put: Mapping, values, known):
        """Each block of ``rest``, ``put`` put in: one equation with nothing put in as a formula, else as
        equations solved together; and what is known after them."""
        shown, known = [], dict(known)
        for places, xs in order:
            rows = [rest[i] for i in places]
            if len(rows) == 1 and len(xs) == 1 and not rows[0][1].free_symbols & set(put):
                shown.append(self.formula(xs[0], values[xs[0]], *rows[0], known))
            else:
                shown.append(self.system(rows, put, xs, values, known))
            known |= {x: values[x] for x in xs}
        return shown, known

    def system(self, rows, put: Mapping, xs: Sequence[sp.Symbol], values: Mapping, known: Mapping) -> dict:
        """Equations solved together, each as what flows in = what flows out, in letters and then in numbers;
        ``nodes``: the points of those that are Kirchhoff's."""
        equations = []
        for _, e in rows:
            for side in _sides(e, put, {}), _sides(e, put, known):
                if side not in equations:
                    equations.append(side)
        nodes = [self.point(o.subject) for o, _ in rows if o.what == "kcl"]
        results = [_equals(x, values[x], self.units) for x in xs]
        return {"type": "SystemStep", "equations": equations, "results": results, "nodes": nodes}

    def redundant(self, origin: Origin) -> bool:
        """Kirchhoff's law at the point set to 0: the others say it already."""
        return origin.what == "kcl" and origin.subject.potential in self.references

    def point(self, p) -> str:
        named = self.names.to.get(p.potential)
        return tex.name(str(named)[2:] if named is not None else "GND")


def _letters(solution: Solution, n: Names) -> dict[Origin, sp.Expr]:
    """Each law of the circuit in letters (its parameters not put in), read in the solution's frame."""
    laws = solution.circuit.closed()
    memory = {x: v for x, v in solution.data.items() if is_before(x)}
    read = solution.frame.reading(memory)
    every = [*laws.equations, *(q for c in laws.ways for w in c for q in w.equations)]
    return {q.origin: n.rename(read(q.expr)) for q in every}


def _references(solution: Solution) -> frozenset[sp.Expr]:
    return frozenset(o.subject for s in solution.steps for o in s.because if o.what == "reference")


def _order(eqs: Sequence[sp.Expr], unknowns: set[sp.Symbol]) -> list[Block]:
    """The blocks ``eqs`` are solved in (``structure``)."""
    s = structure([e.free_symbols & unknowns for e in eqs])
    return [(places, xs) for places, xs in (s.over, *s.blocks, s.under) if places]


def _formulas(laws: Sequence[sp.Expr], origins: Sequence[Origin], unknowns: set[sp.Symbol]) -> Formulas:
    """Each of ``unknowns`` an element's law gives alone (a current, by Ohm's law), in letters."""
    out: Formulas = {}
    for o, e in zip(origins, laws):
        holds = e.free_symbols & unknowns
        if o.what == "law" and len(holds) == 1:
            (x,) = holds
            if x not in out and x not in sp.diff(e, x).free_symbols:
                out[x] = (sp.solve(e, x)[0], o)
    return out


def _sides(e: sp.Expr, put: Mapping, known: Mapping) -> str:
    """``e`` = 0 as what flows in = what flows out (its terms with a minus on the left), ``put`` put in each
    term, ``known`` shown as numbers."""
    terms = sp.Add.make_args(e)
    ins = sp.Add(*(-t.xreplace(put) for t in terms if t.could_extract_minus_sign()))
    outs = sp.Add(*(t.xreplace(put) for t in terms if not t.could_extract_minus_sign()))
    return f"{tex.expr(ins, known)} = {tex.expr(outs, known)}"


def _answer_or_missing(solution: Solution, find: Sequence[Quantity], units: Mapping[str, str]):
    """What is sought, found; or what is missing to find it (all that is unknown, when nothing is sought)."""
    if not find:
        return None, _missing(solution) if solution.unknowns else None
    try:
        return _answer(solution, find, units), None
    except MissingData as err:
        return None, {**(issue(err, units) or {}), "type": "Underdetermined"}


def _renamed(step: SolutionStep, n) -> SolutionStep:
    """A step in the book's names."""
    return SolutionStep(
        tuple(n.rename(x) for x in step.found),
        tuple(n.rename(v) for v in step.values),
        step.because,
        step.how,
        tuple(n.rename(e) for e in step.equations),
    )


def reason(origin: Origin, solution: Solution) -> dict:
    n = names(solution.circuit)
    match origin:
        case Origin("law", Element() as e) if e in n.labels:
            name = BY_ANALYSIS.get((e.kind, type(solution.frame))) or REASONS.get(e.kind, "DeviceModel")
            return {"type": name, "label": tex.name(n.labels[e])}
        case Origin("kcl", p):
            point = n.to.get(p.potential)
            return {"type": "KirchhoffCurrent", "node": tex.name(str(point)[2:] if point is not None else "GND")}
    return {"type": "Given"}


def _unit(x: sp.Symbol, units: Mapping[str, str]) -> str:
    """A variable's unit by its name: a current's (``I_…``), a potential's (``V_…``), else its element's."""
    if x.name in units:
        return units[x.name]
    return {"I": "A", "V": "V"}.get(x.name.partition("_")[0], "")


def _equals(x: sp.Symbol, v: sp.Expr, units: Mapping[str, str]) -> str:
    return f"{tex.name(x.name)} = {tex.value(v, _unit(x, units))}"


def _data(solution: Solution, units: Mapping[str, str]) -> list[str]:
    n = names(solution.circuit)
    out = []
    for key, given in solution.given.items():
        value = parse(given) if isinstance(given, str | int | float) else given
        if isinstance(key, Element) and not isinstance(value, Mapping) and getattr(value, "is_number", False):
            label = n.labels[key]
            out.append(f"{tex.name(label)} = {tex.value(value, units.get(label, ''))}")
        elif isinstance(key, Quantity) and isinstance(value, sp.Basic):
            out.append(f"{tex.quantity(key, n)} = {tex.value(value, tex.unit(key, units, n))}")
    return out


def _answer(solution: Solution, find: Sequence[Quantity], units: Mapping[str, str]) -> list[str]:
    n = names(solution.circuit)
    return [f"{tex.quantity(q, n)} = {tex.value(v, tex.unit(q, units, n))}" for q, v in solution.answers(*find).items()]


def _missing(solution: Solution) -> dict:
    return {
        "type": "Underdetermined",
        "targets": [tex.name(x.name) for x in sorted(solution.unknowns, key=str)],
        "needed": None,
        "options": [],
    }
