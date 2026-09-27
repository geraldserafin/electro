"""The solution trace as Markdown with LaTeX math (``$...$``).

That format works in Jupyter, in a web notebook (markdown + KaTeX) and in a PDF export.
"""

from __future__ import annotations

import re

import sympy as sp
from electro.values import fmt
from sympy.printing.latex import LatexPrinter


class Markdown(str):
    """Markdown text; shows itself in Jupyter-like notebooks."""

    def _repr_markdown_(self) -> str:
        return str(self)


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


_LABEL = re.compile(r"\b([A-Z]+_\w+)\b")


def _reason(text: str) -> str:
    return _LABEL.sub(lambda m: f"${name(m.group(1))}$", text)


def _pairs(solution, items) -> str:
    return ", ".join(f"${name(s.name)} = {value(v, solution.unit(s))}$" for s, v in items)


def steps(solution) -> Markdown:
    """The whole worked solution: data, assumptions, numbered steps, answer."""
    out = []
    if solution.data:
        out.append(f"**Dane:** {_pairs(solution, solution.data.items())}")
    if solution.assumed:
        out.append(f"**Założenia** (najprostszy element zgodny z danymi): {_pairs(solution, solution.assumed.items())}")
    values = dict(solution.system.known) | solution.given | solution.assumed
    lines = []
    for i, step in enumerate(solution.shown_steps(), 1):
        if step.formula is not None:
            (target, result), = step.targets.items()
            chain = [name(target.name)]
            for part in (expr(step.formula), "" if step.formula.is_Symbol else expr(step.formula, values)):
                if part and part not in chain:
                    chain.append(part)
            final = value(result, solution.unit(target))
            if chain[-1] != final.split(r"\,")[0]:
                chain.append(final)
            else:
                chain[-1] = final
            lines.append(f"{i}. ${' = '.join(chain)}$ — {_reason(step.laws[0].reason)}")
        else:
            rows = r" \\ ".join(f"{expr(law.expr)} &= 0" for law in step.laws)
            results = _pairs(solution, step.targets.items())
            lines.append(f"{i}. Układ równań:\n\n   $$\\begin{{aligned}} {rows} \\end{{aligned}}$$\n\n   Stąd: {results}")
        values.update(step.targets)
    if lines:
        out.append("**Rozwiązanie:**\n\n" + "\n".join(lines))
    if solution.find:
        out.append(f"**Odpowiedź:** {_pairs(solution, ((s, solution._value(s)) for s in solution.find))}")
    elif solution.missing:
        out.append(f"**Brakuje danych:** {_reason(str(solution.diagnose()))}")
    return Markdown("\n\n".join(out) + "\n")
