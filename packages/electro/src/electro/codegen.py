"""Circuit → Python code: the plain ``electro`` expression for any circuit.

Series–parallel circuits come back as ``+`` / ``|`` expressions, found by the classic
reduction: two elements between the same two nodes become ``a | b``; a node where
exactly two elements meet disappears and they become ``a + b``. Anything that does not
reduce to one expression (a bridge, an op-amp) is written as ``net(...)``.
"""

from __future__ import annotations

import re

from . import components as comp
from .circuit import GROUND, Circuit
from .semantics import _labels, _node_names
from .values import UNKNOWN, to_text

SYMMETRIC = (comp.Resistor, comp.Capacitor, comp.Inductor)  # direction only changes the sign of I


class _Leaf:
    def __init__(self, component, index, flipped=False):
        self.component, self.index, self.flipped = component, index, flipped  # index into the netlist parts

    def reversed(self):
        return _Leaf(self.component, self.index, not self.flipped)

    def leaves(self):
        return [self]


class _Node:
    """A named point inside a series chain: ``node("A")``."""

    def __init__(self, name):
        self.name = name

    def reversed(self):
        return self

    def leaves(self):
        return []


class _Series:
    def __init__(self, parts):
        self.parts = [q for p in parts for q in (p.parts if isinstance(p, _Series) else [p])]

    def reversed(self):
        return _Series([p.reversed() for p in reversed(self.parts)])

    def leaves(self):
        return [leaf for p in self.parts for leaf in p.leaves()]


class _Parallel:
    def __init__(self, parts):
        flat = [q for p in parts for q in (p.parts if isinstance(p, _Parallel) else [p])]
        # branches in the order their elements were drawn / written
        self.parts = sorted(flat, key=lambda p: min(leaf.index for leaf in p.leaves()))

    def reversed(self):
        return _Parallel([p.reversed() for p in self.parts])

    def leaves(self):
        return [leaf for p in self.parts for leaf in p.leaves()]


def _reduce(edges: list, named: set[str]):
    """Series–parallel reduction on ``[(expr, u, v)]``; returns what is left."""
    while _parallel_step(edges) or _series_step(edges, named):
        pass
    return edges


def _series_step(edges, named) -> bool:
    """Merge the two elements at a node where exactly two element ends meet."""
    degree: dict[str, list[int]] = {}
    for i, (_, u, v) in enumerate(edges):
        degree.setdefault(u, []).append(i)
        degree.setdefault(v, []).append(i)
    candidates = [(n, inc) for n, inc in degree.items() if len(inc) == 2 and inc[0] != inc[1]]
    # smallest pieces first (short chains before big blocks), the ground rail last: this keeps
    # the branches the way they are usually drawn
    candidates.sort(key=lambda c: (c[0] == GROUND, sum(len(edges[i][0].leaves()) for i in c[1])))
    for n, incident in candidates[:1]:
        (e1, a1, b1), (e2, a2, b2) = edges[incident[0]], edges[incident[1]]
        first, x = (e1, a1) if b1 == n else (e1.reversed(), b1)
        second, y = (e2, b2) if a2 == n else (e2.reversed(), a2)
        middle = [_Node(n)] if n in named else []
        for i in sorted(incident, reverse=True):
            del edges[i]
        edges.append((_Series([first, *middle, second]), x, y))
        return True
    return False


def _parallel_step(edges) -> bool:
    """Merge two elements between the same two (distinct) nodes."""
    seen: dict[frozenset, int] = {}
    for i, (e, u, v) in enumerate(edges):
        if u == v:
            continue
        pair = frozenset((u, v))
        if pair in seen:
            j = seen[pair]
            f, a, b = edges[j]
            edges[j] = (_Parallel([f, e if (u, v) == (a, b) else e.reversed()]), a, b)
            del edges[i]
            return True
        seen[pair] = i
    return False


def _has_source(e) -> bool:
    return any(isinstance(leaf.component, (comp.VoltageSource, comp.CurrentSource)) for leaf in e.leaves())


def _against(e) -> int:
    """How many direction-sensitive elements a reading direction has to transpose."""
    return sum(1 for leaf in e.leaves() if leaf.flipped and not isinstance(leaf.component, SYMMETRIC))


def _nicest(e):
    """Read the expression in the direction that needs fewer ``.transpose()``."""
    flipped = e.reversed()
    return flipped if _against(flipped) < _against(e) else e


def _literal(value) -> str:
    text = to_text(value)
    try:
        float(text)
        return text
    except ValueError:
        return repr(text)  # "18/11", or a symbol name like "R"


def _component_code(c: comp.Component, label: str | None) -> str:
    args = []
    if c.has_value and c.value is not UNKNOWN:
        args.append(_literal(c.value))
    if label:
        args.append(f"label={label!r}")
    return f"{type(c).__name__}({', '.join(args)})"


def _labels_to_write(components: list[comp.Component], wanted: list[str]) -> list[str | None]:
    """Write a label only where automatic labelling (in this order) would give a different one."""

    class Stub:
        def __init__(self, c, label):
            self.prefix, self.label = c.prefix, label

    # labels that could never come from automatic numbering must be written
    keep = {i for i, (c, w) in enumerate(zip(components, wanted)) if not re.fullmatch(rf"{c.prefix}_\d+", w)}
    while True:
        auto = _labels([(Stub(c, wanted[i] if i in keep else None), None) for i, c in enumerate(components)])
        wrong = {i for i, (got, want) in enumerate(zip(auto, wanted)) if got != want} - keep
        if not wrong:
            return [wanted[i] if i in keep else None for i in range(len(components))]
        keep |= wrong


def _expr_code(e, labels: dict[int, str | None], top: bool = False) -> str:
    if isinstance(e, _Leaf):
        text = _component_code(e.component, labels[id(e)])
        return text + ".transpose()" if e.flipped and not isinstance(e.component, SYMMETRIC) else text
    if isinstance(e, _Node):
        return f"node({e.name!r})"
    if isinstance(e, _Series):
        # + binds tighter than |, so a parallel group inside a chain needs parentheses
        text = " + ".join(f"({_expr_code(p, labels)})" if isinstance(p, _Parallel) else _expr_code(p, labels)
                          for p in e.parts)
        return text if top else f"({text})"
    return " | ".join(_expr_code(p, labels) for p in e.parts)


def _assign(name: str, e, labels, width: int = 88) -> str:
    text = _expr_code(e, labels, top=True)
    if len(name) + len(text) + 3 <= width or not isinstance(e, _Parallel):
        return f"{name} = {text}"
    branches = "\n    | ".join(_expr_code(p, labels, top=False) for p in e.parts)  # one branch per line
    return f"{name} = (\n    {branches}\n)"


def code(circuit: Circuit, name: str = "uklad") -> str:
    """Python code (plain ``electro``) that builds the same circuit, e.g. from a drawing."""
    net = circuit.netlist
    names = _node_names(net)
    parts = [(c, [names[n] for n in nodes]) for c, nodes in net.parts]
    wanted = _labels(net.parts)
    named = {n for n in names if n != GROUND and not (n[0] == "n" and n[1:].isdigit())}

    if all(len(c.terminals) == 2 for c, _ in parts):
        edges = _reduce([(_Leaf(c, i), u, v) for i, (c, (u, v)) in enumerate(parts)], named)
        if len(edges) == 1:
            expr, u, v = edges[0]
            if isinstance(expr, _Parallel):
                with_source = [p for p in expr.parts if _has_source(p)]
                if len(with_source) <= 1:
                    # one source: a loop through it and the rest of the circuit, e.g. loop(E, R1, R2 | R3);
                    # several source branches stay branches (as drawn for superposition)
                    first = with_source[0] if with_source else expr.parts[0]
                    rest = [p for p in expr.parts if p is not first]
                    load = rest[0] if len(rest) == 1 else _Parallel(rest)
                    expr, v = _Series([first, load.reversed()]), u
            expr = _nicest(expr)
            if u == v and isinstance(expr, _Series):  # a loop: start it at a source, like on paper
                k = next((i for i, p in enumerate(expr.parts) if isinstance(p, _Leaf)
                          and isinstance(p.component, (comp.VoltageSource, comp.CurrentSource))), 0)
                expr = _Series(expr.parts[k:] + expr.parts[:k])
            order = expr.leaves()
            written = _labels_to_write([leaf.component for leaf in order], [wanted[leaf.index] for leaf in order])
            labels = {id(leaf): label for leaf, label in zip(order, written)}
            if u == v:  # everything in one loop
                inner = expr.parts if isinstance(expr, _Series) else [expr]
                return f"{name} = loop({', '.join(_expr_code(p, labels, top=True) for p in inner)})"
            return _assign(name, expr, labels)

    written = _labels_to_write([c for c, _ in parts], wanted)
    rows = [
        f"    ({_component_code(c, label)}, {', '.join(repr(n) for n in nodes)}),"
        for (c, nodes), label in zip(parts, written)
    ]
    return f"{name} = net(\n" + "\n".join(rows) + "\n)"
