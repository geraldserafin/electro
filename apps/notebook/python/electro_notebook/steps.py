"""A solution's steps as data, for whoever shows them (the notebook: ``Steps`` in ``shared/model/issues.ts``):
the data; each step — one unknown from one equation as a chain, ``U_{R_{1}} = R_{1} I_{R_{1}} = 10·0.5 =
5 V``, and why it holds, or several unknowns together, their equations and what they came to; and the answer
to what is sought."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import sympy as sp
from electro import AC, DC, Element, Node, Solution, SolutionStep
from electro.circuit.algebra import Origin
from electro.circuit.quantities import Quantity
from electro.errors import MissingData
from electro.values import parse

from . import latex as tex
from .issues import issue

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
    """``find``: what is sought; ``units``: each element's value's, by its label."""
    units = units or {}
    known: dict[sp.Symbol, sp.Expr] = {}
    shown = []
    for step in solution.steps:
        if step.how == "alone" and step.equations and step.because[0].what != "given":
            shown.append(_formula(step, known, solution, units))
        elif step.how == "together":
            results = [_equals(x, v, units) for x, v in zip(step.found, step.values)]
            shown.append(
                {"type": "SystemStep", "equations": [f"{tex.expr(e)} = 0" for e in step.equations], "results": results}
            )
        known |= dict(zip(step.found, step.values))
    answer, missing = None, None
    try:
        answer = _answer(solution, find, units) if find else None
    except MissingData as err:
        missing = {**(issue(err, units) or {}), "type": "Underdetermined"}
    if solution.unknowns and not find:
        missing = _missing(solution)
    return {
        "type": "Steps",
        "data": _data(solution, units),
        "assumed": [],
        "steps": shown,
        "answer": answer,
        "missing": missing,
    }


def _formula(step: SolutionStep, known: Mapping[sp.Symbol, sp.Expr], solution: Solution, units) -> dict:
    """``x = formula = the formula's numbers = value``, each written once."""
    (x,), (value,), (equation,) = step.found, step.values, step.equations
    roots = sp.solve(equation, x)
    formula = roots[0] if len(roots) == 1 else value
    chain = [tex.name(x.name)]
    for part in (tex.expr(formula), "" if formula.is_Symbol else tex.expr(formula, known)):
        if part and part not in chain:
            chain.append(part)
    final = tex.value(value, _unit(x, units))
    if chain[-1] == final.split(r"\,")[0]:
        chain[-1] = final
    else:
        chain.append(final)
    return {"type": "FormulaStep", "chain": " = ".join(chain), "reason": reason(step.because[0], solution)}


def reason(origin: Origin, solution: Solution) -> dict:
    n = solution.names
    match origin:
        case Origin("law", Element() as e) if e in n.labels:
            name = BY_ANALYSIS.get((e.kind, type(solution.frame))) or REASONS.get(e.kind, "DeviceModel")
            return {"type": name, "label": tex.name(n.labels[e])}
        case Origin("kcl", Node() as p):
            point = n.points.get(p)
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
    n = solution.names
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
    n = solution.names
    return [f"{tex.quantity(q, n)} = {tex.value(v, tex.unit(q, units, n))}" for q, v in solution.answers(*find).items()]


def _missing(solution: Solution) -> dict:
    return {
        "type": "Underdetermined",
        "targets": [tex.name(x.name) for x in sorted(solution.unknowns, key=str)],
        "needed": None,
        "options": [],
    }
