"""The semantic functor: a netlist becomes a system of equations (a relation).

Variables: node potentials ``V_<node>``, component quantities (``U_R_1``, ``I_R_1``),
unknown component values (``R_2``) and — for an open circuit — boundary potentials
and currents. Laws: component laws, ``U = ΔV`` and Kirchhoff's current law per node.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import sympy as sp

from .circuit import GROUND, Circuit, Netlist
from .components import Component, Context, Law, Model
from .issues import DuplicateLabel, NoSuchElement, NoSuchQuantity
from .reasons import KirchhoffCurrent, Terminal
from .values import UNKNOWN

KIND_ORDER = {"given": 0, "reading": 0, "law": 1, "kvl": 2, "kcl": 3}


@dataclass
class Placed:
    """A component instance inside a concrete circuit."""

    label: str
    component: Component
    nodes: dict[str, str]  # terminal -> node name
    model: Model


@dataclass
class System:
    laws: list[Law]
    unknowns: list[sp.Symbol]
    known: dict[sp.Symbol, sp.Expr]
    parts: dict[str, Placed]
    potentials: dict[str, sp.Symbol]  # node name -> V symbol
    boundary: list[sp.Symbol] = field(default_factory=list)  # V_in1, I_in1, ..., V_out1, I_out1, ...
    ctx: Context = field(default_factory=Context)

    def symbol(self, name: str) -> sp.Symbol:
        """Find a variable or parameter by name (``"I_R_1"``, ``"R_2"``, ``"V_A"``).

        Underscores are optional: ``"I_R1"`` finds ``I_R_1``.
        """
        symbols = self._symbols()
        for s in symbols:
            if s.name == name:
                return s
        for s in symbols:
            if _loose(s.name) == _loose(name):
                return s
        raise NoSuchQuantity(name, sorted(self._symbols(), key=lambda s: s.name))

    def part(self, label: str) -> Placed:
        """Find a component by label; ``"R1"`` also finds ``R_1``."""
        if label in self.parts:
            return self.parts[label]
        for key, placed in self.parts.items():
            if _loose(key) == _loose(label):
                return placed
        raise NoSuchElement(label, [sp.Symbol(p) for p in self.parts])

    def _symbols(self):
        seen = set(self.unknowns) | set(self.known) | set(self.potentials.values())
        for law in self.laws:
            seen |= law.expr.free_symbols
        return seen


def _loose(name: str) -> str:
    return name.replace("_", "")


def _labels(parts) -> list[str]:
    explicit = [c.label for c, _ in parts if c.label]
    dupes = [name for name, n in Counter(explicit).items() if n > 1]
    if dupes:
        raise DuplicateLabel(sp.Symbol(dupes[0]))
    taken, counters, out = {_loose(e) for e in explicit}, Counter(), []
    for c, _ in parts:
        if c.label:
            out.append(c.label)
            continue
        while True:
            counters[c.prefix] += 1
            name = f"{c.prefix}_{counters[c.prefix]}"
            if _loose(name) not in taken:
                break
        taken.add(_loose(name))
        out.append(name)
    return out


def _node_names(net: Netlist) -> list[str]:
    named = dict(net.labels)
    taken, k, out = set(named.values()), 0, []
    for n in range(net.size):
        if n in named:
            out.append(named[n])
            continue
        while True:
            k += 1
            if f"n{k}" not in taken:
                break
        out.append(f"n{k}")
    return out


def compile_netlist(
    net: Netlist,
    *,
    ctx: Context = Context(),  # noqa: B008
    open_boundary: bool = False,
    unknowns_as_symbols: bool = False,
) -> System:
    names = _node_names(net)
    V = {name: sp.Symbol(f"V_{name}") for name in names}
    known: dict[sp.Symbol, sp.Expr] = {}
    unknowns: list[sp.Symbol] = []
    laws: list[Law] = []
    placed: dict[str, Placed] = {}
    inflow: dict[int, list[sp.Expr]] = {n: [] for n in range(net.size)}

    for label, (c, nodes) in zip(_labels(net.parts), net.parts):
        term_nodes = dict(zip(c.terminals, nodes))
        param = c.param_symbol(label)
        model = c.build(label, {t: V[names[n]] for t, n in term_nodes.items()}, param, ctx)
        placed[label] = Placed(label, c, {t: names[n] for t, n in term_nodes.items()}, model)
        laws += model.laws
        unknowns += model.variables.values()
        for t, n in term_nodes.items():
            inflow[n].append(model.inflow[t])
        if param is not None and param not in known and param not in unknowns:
            if c.value is UNKNOWN:
                if not unknowns_as_symbols:
                    unknowns.append(param)
            elif not isinstance(c.value, sp.Symbol):
                known[param] = c.value

    # boundary (open circuits only): external current entering on the left, leaving on the right
    external: dict[int, list[sp.Expr]] = {n: [] for n in range(net.size)}
    boundary: list[sp.Symbol] = []
    if open_boundary:
        for side, nodes, sign in (("in", net.left, 1), ("out", net.right, -1)):
            for i, n in enumerate(nodes, 1):
                v, cur = sp.Symbol(f"V_{side}{i}"), sp.Symbol(f"I_{side}{i}")
                boundary += [v, cur]
                laws.append(Law(v - V[names[n]], Terminal(side, i), "kvl"))
                external[n].append(sign * cur)

    # potential references: ground, or one node per floating piece
    parent = list(range(net.size))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for _, nodes in net.parts:
        for a in nodes[1:]:
            parent[find(a)] = find(nodes[0])
    on_boundary = {find(n) for n in net.left + net.right} if open_boundary else set()
    grounded = {find(n) for n in range(net.size) if names[n] == GROUND}
    references = set()
    for n in range(net.size):
        root = find(n)
        if names[n] == GROUND:
            references.add(n)
        elif root not in grounded and root not in on_boundary and root not in {find(r) for r in references}:
            references.add(n)
    for n in references:
        known[V[names[n]]] = sp.Integer(0)

    for n in range(net.size):
        if n in references:
            continue  # KCL at the reference node is implied by the others
        total = sp.Add(*inflow[n]) - sp.Add(*external[n])
        if total != 0:
            laws.append(Law(total, KirchhoffCurrent(sp.Symbol(names[n])), "kcl"))

    unknowns += [V[names[n]] for n in range(net.size) if n not in references]
    unknowns += [s for s in boundary if s not in unknowns]
    laws.sort(key=lambda law: KIND_ORDER[law.kind])
    return System(laws, list(dict.fromkeys(unknowns)), known, placed, {nm: V[nm] for nm in names}, boundary, ctx)


def compile_circuit(c: Circuit, **kw) -> System:
    return compile_netlist(c.netlist, **kw)
