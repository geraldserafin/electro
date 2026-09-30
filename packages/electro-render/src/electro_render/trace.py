"""The solution trace as data, its math in LaTeX — the same in every language; the words around
it ("Data:", why each step holds) are up to whoever shows it.
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp
from electro.issues import Underdetermined
from electro.reasons import Reason
from electro.values import fmt
from sympy.printing.latex import LatexPrinter


def name(symbol_name: str) -> str:
    """``U_R_1`` → ``U_{R_{1}}``; words like ``GND`` are upright: ``V_{\\mathrm{GND}}``."""
    base, _, sub = symbol_name.partition("_")
    if len(base) > 1 and base.isalpha():
        base = rf"\mathrm{{{base}}}"
    return f"{base}_{{{name(sub)}}}" if sub else base


def _unit(unit: str) -> str:
    unit = unit.replace("Ω", r"\Omega").replace("µ", r"\mu ")
    return rf"\,\mathrm{{{unit}}}" if unit else ""


def value(v, unit: str = "") -> str:
    """A value with its unit, in engineering notation: ``500\\,\\mathrm{mA}``."""
    v = sp.sympify(v)
    if v.free_symbols:
        return expr(v) + (_unit(unit) if unit else "")
    text = fmt(v, unit)
    if "∠" in text:
        magnitude, angle = text.split(" ∠ ")
        return value_text(magnitude) + r" \angle " + angle.replace("°", r"^{\circ}")
    return value_text(text)


def value_text(text: str) -> str:
    number, _, unit = text.partition(" ")
    return number + _unit(unit)


def expr(e, values: dict | None = None) -> str:
    """LaTeX of an expression; with ``values``, known symbols are shown as numbers."""
    e = sp.sympify(e)
    names = {s: name(s.name) for s in e.free_symbols}
    for s, v in (values or {}).items():
        if s in names and v.is_number and v.is_real:
            number = f"{float(v):.6g}"
            names[s] = rf"\left({number}\right)" if float(v) < 0 else number
    return _Latex({"symbol_names": names, "mul_symbol": "dot"}).doprint(e)


class _Latex(LatexPrinter):
    """Positive terms first: ``V_{A} - U_{R_{1}}`` rather than ``- U_{R_{1}} + V_{A}``."""

    def _as_ordered_terms(self, expr, order=None):
        return sorted(super()._as_ordered_terms(expr, order), key=lambda t: t.could_extract_minus_sign())


@dataclass
class FormulaStep:
    """One quantity from one law: ``chain`` is target = formula = with the numbers = value."""

    chain: str
    reason: Reason


@dataclass
class SystemStep:
    """Quantities from equations solved together: each ``… = 0``, and what came out."""

    equations: list[str]
    results: list[str]


@dataclass
class Steps:
    """The worked solution as data — whoever shows it says it (the notebook: in the reader's
    language). Math is LaTeX: ``R_{2} = 14\\,\\mathrm{\\Omega}``. ``assumed``: how holes were
    filled (the simplest element that fits); ``answer``: what ``find`` asked for; ``missing``:
    what is not determined, when nothing was asked."""

    data: list[str]
    assumed: list[str]
    steps: list[FormulaStep | SystemStep]
    answer: list[str] | None
    missing: Underdetermined | None


def _pairs(solution, items) -> list[str]:
    return [f"{name(s.name)} = {value(v, solution.unit(s))}" for s, v in items]


def steps(solution) -> Steps:
    """The whole worked solution: data, assumptions, numbered steps, answer."""
    values = dict(solution.system.known) | solution.given | solution.assumed
    shown: list[FormulaStep | SystemStep] = []
    for step in solution.shown_steps():
        if step.formula is not None:
            ((target, result),) = step.targets.items()
            chain = [name(target.name)]
            for part in (expr(step.formula), "" if step.formula.is_Symbol else expr(step.formula, values)):
                if part and part not in chain:
                    chain.append(part)
            final = value(result, solution.unit(target))
            if chain[-1] != final.split(r"\,")[0]:
                chain.append(final)
            else:
                chain[-1] = final
            shown.append(FormulaStep(" = ".join(chain), step.laws[0].reason))
        else:
            shown.append(
                SystemStep([f"{expr(law.expr)} = 0" for law in step.laws], _pairs(solution, step.targets.items()))
            )
        values.update(step.targets)
    answer = _pairs(solution, ((s, solution._value(s)) for s in solution.find)) if solution.find else None
    missing = Underdetermined(**solution.diagnose().fields()) if not solution.find and solution.missing else None
    return Steps(
        _pairs(solution, solution.data.items()), _pairs(solution, solution.assumed.items()), shown, answer, missing
    )
