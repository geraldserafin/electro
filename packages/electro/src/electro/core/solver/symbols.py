"""A circuit's quantities as the variables of its relation, named as a book names them."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import sympy as sp

from ..circuit.kind import Terminals
from ..circuit.netlist import Netlist, pieces
from ..circuit.tree import GND, Circuit, Element, Net, Node, netlist
from ..problem.quantities import Across, Current, Parameter, Potential, Power, Quantity, Scaled, Voltage


@dataclass(frozen=True)
class Symbols:
    """``labels``: each element's, in the netlist's order; ``potentials``: each point's, 0 at a reference."""

    net: Netlist
    labels: tuple[str, ...]
    potentials: tuple[sp.Expr, ...]

    def index(self, e: Element) -> int:
        return next(k for k, (x, _) in enumerate(self.net.parts) if x is e)

    def currents(self, k: int) -> dict[str, sp.Expr]:
        """Into element ``k`` at each terminal: a variable for each but the last, which is minus their sum,
        so charge is kept."""
        e, _ = self.net.parts[k]
        ts = e.kind.terminals
        name = (lambda t: f"I_{self.labels[k]}") if len(ts) == 2 else (lambda t: f"I_{self.labels[k]}_{t}")
        own = {t: sp.Symbol(name(t)) for t in ts[:-1]}
        return {**own, ts[-1]: -sp.Add(*own.values())}

    def terminals(self, k: int) -> Terminals:
        e, ns = self.net.parts[k]
        label = self.labels[k]
        potentials = dict(zip(e.kind.terminals, (self.potentials[n] for n in ns)))
        return Terminals(potentials, self.currents(k), lambda name: sp.Symbol(f"{name}_{label}"))

    def param(self, e: Element, which: str = "") -> sp.Symbol:
        base = e.name or self.labels[self.index(e)]
        return sp.Symbol(f"{which}_{base}" if which else base)

    def params(self, e: Element) -> dict[str, sp.Symbol]:
        return {w: self.param(e, w) for w in e.kind.parameters}

    def V(self, p: Node | Net) -> sp.Expr:
        return self.potentials[next(n for n, q in self.net.named if q == p)]

    def of(self, q: Quantity | Scaled) -> sp.Expr:
        match q:
            case Current(e, at):
                return self.currents(self.index(e))[at or e.kind.terminals[0]]
            case Voltage(e):
                t = self.terminals(self.index(e))
                a, b = e.kind.terminals[:2]
                return t.V[a] - t.V[b]
            case Parameter(e, which):
                return self.param(e, which)
            case Potential(p):
                return self.V(p)
            case Across(a, b):
                return self.V(a) - self.V(b)
            case Power(e):
                return self.of(Voltage(e)) * self.of(Current(e))
            case Scaled(k, x):
                return k * self.of(x)
        raise TypeError(q)


@cache
def symbols(c: Circuit) -> Symbols:
    net = netlist(c)
    return Symbols(net, _labels(net), _potentials(net))


def _labels(net: Netlist) -> tuple[str, ...]:
    """An element's name when no other element has it, else its prefix and number."""
    names = [e.name for e, _ in net.parts]
    return tuple(
        e.name if e.name and names.count(e.name) == 1 else f"{e.kind.prefix}{k + 1}"
        for k, (e, _) in enumerate(net.parts)
    )


def _potentials(net: Netlist) -> tuple[sp.Expr, ...]:
    """0 at a reference; else ``V_<label>`` when no other point shows that label, else ``V_<number>``."""
    references = _references(net)
    shown = {n: p.name if isinstance(p, Net) else p.label for n, p in net.named}
    taken = list(shown.values())

    def potential(n: int) -> sp.Expr:
        if n in references:
            return sp.Integer(0)
        label = shown.get(n)
        return sp.Symbol(f"V_{label}" if label and taken.count(label) == 1 else f"V_{n}")

    return tuple(potential(n) for n in range(net.size))


def _references(net: Netlist) -> set[int]:
    """Ground, and the first point of each piece not on ground."""
    piece = pieces(net)
    grounded = {n for n, p in net.named if p == GND}
    floating = set(piece) - {piece[n] for n in grounded}
    return grounded | {piece.index(r) for r in floating}
