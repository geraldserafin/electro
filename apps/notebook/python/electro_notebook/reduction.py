"""A circuit of one source and resistors in series and parallel, every value given, solved as a school does:
the resistors joined into one, a pair at a time (``R_23 = R_2·R_3/(R_2 + R_3)``), the source's current
through that one (``I = E/R_z``), then back down to each resistor: a series piece's voltage from the current
through it, a parallel piece's current from the voltage across it."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import sympy as sp
from electro import DC, Element, Point, Solution

from . import latex as tex

SOURCES = ("voltage_source", "current_source")


@dataclass(frozen=True)
class Piece:
    """Resistors joined: one (``element``), or ``parts`` in ``"series"`` or in ``"parallel"``."""

    how: str
    parts: tuple[Piece, ...] = ()
    element: Element | None = None

    def leaves(self) -> tuple[Element, ...]:
        return (self.element,) if self.element is not None else tuple(e for p in self.parts for e in p.leaves())


def by_reduction(solution: Solution, labels: Mapping[Element, str]) -> list[dict] | None:
    """The steps by joining resistors, when the circuit allows it; else None."""
    source = _source(solution)
    piece = _piece(solution.circuit, source) if source is not None else None
    if source is None or piece is None:
        return None
    school = School(labels, {e: solution.data[e.P[""]] for e in piece.leaves()}, piece)
    return [*school.joined(piece), *school.through(source, solution.data[source.P[""]])]


def _source(solution: Solution) -> Element | None:
    """Its one source, when the rest are resistors, every value given as a number and nothing else given."""
    members = solution.circuit.members
    sources = [e for e in members if e.kind in SOURCES]
    values = [solution.data.get(e.P.get("")) for e in members]
    plain = all(isinstance(k, Element) for k in solution.given) and not solution.unknowns
    if not plain or not isinstance(solution.frame, DC) or len(sources) != 1:
        return None
    if any(e.kind != "resistor" for e in members if e not in sources):
        return None
    return sources[0] if all(v is not None and v.is_number for v in values) else None


Edge = list  # [Piece, Point, Point]


def _piece(circuit, source: Element) -> Piece | None:
    """What the source sees: its resistors joined into one piece, or None when they are not series and
    parallel."""
    a, b = dict(circuit.parts)[source]
    edges: list[Edge] = [[Piece("leaf", element=e), *at] for e, at in circuit.parts if e is not source]
    while _parallel(edges) or _series(edges, {a, b}):
        pass
    if a != b and len(edges) == 1 and {edges[0][1], edges[0][2]} == {a, b}:
        return edges[0][0]
    return None


def _parallel(edges: list[Edge]) -> bool:
    """Two between the same two points, joined."""
    for i, (t, u, v) in enumerate(edges):
        for j in range(i):
            s, x, y = edges[j]
            if u != v and {u, v} == {x, y}:
                edges[j] = [_joined("parallel", s, t), x, y]
                del edges[i]
                return True
    return False


def _series(edges: list[Edge], ends: set[Point]) -> bool:
    """The two at a point where only they meet (not the source's), joined."""
    for p in dict.fromkeys(q for _, u, v in edges for q in (u, v)):
        at = [i for i, (_, u, v) in enumerate(edges) if p in (u, v)]
        if p in ends or len(at) != 2:
            continue
        (s, *one), (t, *two) = edges[at[0]], edges[at[1]]
        if p in one and p in two and one.count(p) == two.count(p) == 1:
            edges[at[0]] = [_joined("series", s, t), _other(one, p), _other(two, p)]
            del edges[at[1]]
            return True
    return False


def _other(ends: list[Point], p: Point) -> Point:
    return ends[1] if ends[0] == p else ends[0]


def _joined(how: str, a: Piece, b: Piece) -> Piece:
    """``a`` and ``b`` joined ``how``; a piece joined the same way already is opened up."""
    return Piece(how, tuple(q for p in (a, b) for q in (p.parts if p.how == how else (p,))))


@dataclass(frozen=True)
class School:
    """The steps' names and numbers: each resistor's label and value, and ``whole`` (named ``R_z``)."""

    labels: Mapping[Element, str]
    r: Mapping[Element, sp.Expr]
    whole: Piece

    def name(self, piece: Piece) -> str:
        """``R_1`` for one, ``R_23`` for R_2 and R_3 joined, ``R_z`` for all of them."""
        if piece.element is not None:
            return self.labels[piece.element]
        if piece is self.whole:
            return "R_z"
        return "R_" + "".join(self.labels[e].removeprefix("R_").replace("_", "") for e in piece.leaves())

    def of(self, piece: Piece, letter: str) -> sp.Symbol:
        """Its current (``"I"``) or voltage (``"U"``): ``I_R_1``, ``I_23``."""
        name = self.name(piece)
        return sp.Symbol(f"{letter}_{name if piece.element is not None else name.removeprefix('R_')}")

    def value(self, piece: Piece) -> sp.Expr:
        if piece.element is not None:
            return self.r[piece.element]
        values = [self.value(p) for p in piece.parts]
        return sp.Add(*values) if piece.how == "series" else 1 / sp.Add(*(1 / v for v in values))

    def joined(self, piece: Piece) -> list[dict]:
        """Each piece's resistance, the smallest first: in series their sum, in parallel R·R/(R + R)."""
        if piece.element is not None:
            return []
        parts = [sp.Symbol(self.name(p)) for p in piece.parts]
        if piece.how == "series":
            formula = sp.Add(*parts)
        elif len(parts) == 2:
            formula = parts[0] * parts[1] / (parts[0] + parts[1])
        else:
            formula = 1 / sp.Add(*(1 / x for x in parts))
        known = {x: self.value(p) for x, p in zip(parts, piece.parts)}
        name = self.name(piece)
        reason = {"type": "Series" if piece.how == "series" else "Parallel", "label": tex.name(name)}
        step = formula_step(sp.Symbol(name), formula, known, self.value(piece), "Ω", reason)
        return [*(s for p in piece.parts for s in self.joined(p)), step]

    def through(self, source: Element, given: sp.Expr) -> list[dict]:
        """The source's current through the whole (a current source's: the voltage across it), then each
        piece's."""
        rz, s = sp.Symbol(self.name(self.whole)), sp.Symbol(self.labels[source])
        total = self.value(self.whole)
        known = {rz: total, s: given}
        ohm = {"type": "OhmsLaw", "label": tex.name(self.name(self.whole))}
        if source.kind == "voltage_source":
            i, iv = sp.Symbol("I"), given / total
            return [formula_step(i, s / rz, known, iv, "A", ohm), *self.down(self.whole, i, iv, s, given)]
        u, uv = sp.Symbol("U"), given * total
        return [formula_step(u, s * rz, known, uv, "V", ohm), *self.down(self.whole, s, given, u, uv)]

    def down(self, piece: Piece, i: sp.Symbol, iv: sp.Expr, u: sp.Symbol, uv: sp.Expr) -> list[dict]:
        """``piece``'s parts, its current ``i`` and voltage ``u`` known: in series each one's voltage, I·R; in
        parallel each one's current, U/R; then their parts."""
        out = []
        for p in piece.parts:
            r, rv = sp.Symbol(self.name(p)), self.value(p)
            ohm = {"type": "OhmsLaw", "label": tex.name(self.name(p))}
            if piece.how == "series":
                pu, puv = self.of(p, "U"), iv * rv
                out += [formula_step(pu, i * r, {i: iv, r: rv}, puv, "V", ohm), *self.down(p, i, iv, pu, puv)]
            else:
                pi, piv = self.of(p, "I"), uv / rv
                out += [formula_step(pi, u / r, {u: uv, r: rv}, piv, "A", ohm), *self.down(p, pi, piv, u, uv)]
        return out


def formula_step(x: sp.Symbol, formula: sp.Expr, known: Mapping, value: sp.Expr, unit: str, reason: dict) -> dict:
    """``x = formula = the formula's numbers = value``, each written once."""
    chain = [tex.name(x.name)]
    for part in (tex.expr(formula), "" if formula.is_Symbol else tex.expr(formula, known)):
        if part and part not in chain:
            chain.append(part)
    final = tex.value(value, unit)
    if chain[-1] == final.split(r"\,")[0]:
        chain[-1] = final
    else:
        chain.append(final)
    return {"type": "FormulaStep", "chain": " = ".join(chain), "reason": reason}
