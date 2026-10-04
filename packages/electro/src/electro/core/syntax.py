"""Circuits as an immutable tree of a few primitives, and its normal form (a netlist), by pure functions.

The prototype of DESIGN.md §9: elements (a kind and the name of their parameter, no value), spiders
(ends meeting in a point), nodes (a point with an identity) and nets (a point everyone named alike
shares); ``>>`` series, ``@`` side by side. Everything else is built from these.

An element's kind says what it is as a relation (DESIGN.md §12–13): its terminals, and a list of
equations over their potentials and the currents into it (and its own inner quantities) — any number of
them, in time (``D``, ``Pre``, …). A two-terminal law of ``U`` and ``I`` is only a shorthand of that.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache, reduce

import sympy as sp

D = sp.Function("D")  # the derivative in time
Pre = sp.Function("Pre")  # the value just before (memory)
TIME = sp.Symbol("t")  # time, for data that changes in it (a clock, a switch closed at 1 s)


def when(condition: sp.Basic, then: sp.Expr | float, otherwise: sp.Expr | float) -> sp.Expr:
    """``then`` while ``condition`` holds, else ``otherwise``."""
    return sp.Piecewise((then, condition), (otherwise, True))


def rising(x: sp.Expr, threshold: sp.Expr | float) -> sp.Basic:
    """``x`` crossing ``threshold`` upwards, now: above it, and not just before (an edge of a clock)."""
    return sp.And(x > threshold, Pre(x) <= threshold)


def square(high: sp.Expr | float, period: sp.Expr | float, low: sp.Expr | float = 0) -> sp.Expr:
    """A square wave in time: ``low`` the first half of each period, ``high`` the second."""
    return when(sp.Mod(TIME, period) < sp.Rational(1, 2) * period, low, high)


class JoinsNodes(ValueError):
    """``>>`` would glue two different nodes into one: say it with the same ``Node`` instead."""


class ElementTwice(ValueError):
    """One element in two places: two elements are two objects (``Resistor("R")`` twice)."""


class Circuit:
    """``n → m``: a tree of primitives. Operators are sugar for the functions below."""

    __slots__ = ()

    def __rshift__(self, other: Circuit) -> Circuit:
        return Seq(self, other)

    def __matmul__(self, other: Circuit) -> Circuit:
        return Tensor(self, other)

    def __or__(self, other: Circuit) -> Circuit:
        return parallel(self, other)


@dataclass(frozen=True)
class Terminals:
    """What an element's law speaks of: each terminal's potential, the current into it there, and its
    own inner quantities by name (a flux, a charge, a state)."""

    V: Mapping[str, sp.Expr]
    I: Mapping[str, sp.Expr]  # noqa: E741
    inner: Callable[[str], sp.Symbol]


Params = Mapping[str, sp.Symbol]  # an element's parameters by name ("": its main one, R, C, E)


@dataclass(frozen=True)
class Case:
    """One way an element may be (a diode on, or off): its laws then, and what must hold for it to be the
    one — each ``holds`` ≥ 0 (checked once the circuit is solved in this case)."""

    name: str
    laws: tuple[sp.Expr, ...]
    holds: tuple[sp.Expr, ...] = ()


@dataclass(frozen=True)
class Cases:
    """An element that is one of several ways (piecewise: a textbook diode, a switch, a saturating amp):
    which one, the circuit decides — the one whose ``holds`` hold."""

    cases: tuple[Case, ...]


Laws = Callable[[Terminals, Params], Sequence[sp.Expr] | Cases]  # what is zero (any number), or ways to be


@dataclass(frozen=True)
class Kind:
    """What an element is apart from any one of them: its terminals and its laws, said once, in time.

    Currents into it always add up to zero (charge kept): the engine gives the last terminal's as minus
    the others', so no law can break it."""

    name: str
    prefix: str
    unit: str
    terminals: tuple[str, ...]
    laws: Laws = field(repr=False)
    symmetric: bool = True  # turned around: the same circuit (only its arrows' signs change)
    parameters: tuple[str, ...] = ("",)  # its parameters' names ("": the main one, given as its value)
    defaults: tuple[tuple[str, object], ...] = ()  # what a parameter is when nothing is given for it
    positive: tuple[str, ...] = ()  # parameters never negative (a resistance): a negative one found is a contradiction

    def __call__(self, name: str | None = None) -> Element:
        return Element(self, name)

    def __repr__(self) -> str:
        return self.name


def two_terminal(
    name: str,
    prefix: str,
    unit: str,
    law: Callable[[sp.Expr, sp.Expr, sp.Symbol], sp.Expr],
    symmetric: bool = True,
    positive: bool = False,
) -> Kind:
    """The shorthand: one law of ``U`` (the drop from ``a`` to ``b``) and ``I`` (from ``a`` to ``b``)."""
    return Kind(
        name,
        prefix,
        unit,
        ("a", "b"),
        lambda t, p: [law(t.V["a"] - t.V["b"], t.I["a"], p[""])],
        symmetric,
        positive=("",) if positive else (),
    )


@dataclass(frozen=True, eq=False)  # (eq=False: an element is itself — two are two, whatever their names)
class Element(Circuit):
    kind: Kind
    name: str | None = None  # its parameter's name: elements named alike share its value

    def __repr__(self) -> str:
        return f"{self.kind.name}({self.name!r})"


@dataclass(frozen=True, eq=False)
class Node(Circuit):
    """A point with an identity (1 → 1): the same object twice is one point. ``label`` only shows."""

    label: str | None = None


@dataclass(frozen=True)
class Net(Circuit):
    """A point every ``Net`` of that name is (1 → 1): GND, VCC."""

    name: str


@dataclass(frozen=True)
class Spider(Circuit):
    """``dom`` ends on the left and ``cod`` on the right, all in one point."""

    dom: int
    cod: int


@dataclass(frozen=True)
class Seq(Circuit):
    first: Circuit
    then: Circuit

    def __post_init__(self) -> None:
        netlist(self)  # (a wrong one is never built: said here, not when it is first used)


@dataclass(frozen=True)
class Tensor(Circuit):
    left: Circuit
    right: Circuit

    def __post_init__(self) -> None:
        netlist(self)


GND = Net("GND")
wire = Spider(1, 1)
cap = Spider(0, 2)  # two ends out of nothing
cup = Spider(2, 0)  # two ends into nothing


def series(*parts: Circuit) -> Circuit:
    return reduce(Seq, parts)


def beside(*parts: Circuit) -> Circuit:
    return reduce(Tensor, parts)


def parallel(f: Circuit, g: Circuit) -> Circuit:
    """Both between the same two points (one end each side: 1 → 1)."""
    return Spider(1, 2) >> (f @ g) >> Spider(2, 1)


def close(f: Circuit) -> Circuit:
    """A 1 → 1 piece's ends joined: ``cap`` makes two ends of one point, ``f`` goes from one, ``cup``
    joins its other end with the second."""
    return cap >> (f @ wire) >> cup


def loop(*parts: Circuit) -> Circuit:
    return close(series(*parts))


def at(e: Element, *points: Circuit) -> Circuit:
    """An element with each terminal on a point, in its terminals' order: ``at(t, b, c, e)``."""
    if len(e.kind.terminals) == 2:
        return points[0] >> e >> points[1]
    return e >> beside(*points)


# --------------------------------------------------------------------------------------- netlist

Point = Node | Net
Part = tuple[Element, tuple[int, ...]]  # an element and the point of each of its terminals


@dataclass(frozen=True)
class Netlist:
    """The normal form: points ``0..size-1``, each element with the point of each terminal, the ends on
    each side, and which points are a ``Node`` or a ``Net`` (bound: not free ends)."""

    size: int
    parts: tuple[Part, ...]
    left: tuple[int, ...]
    right: tuple[int, ...]
    named: tuple[tuple[int, Point], ...] = ()


def _point(dom: int, cod: int, at: Point | None = None) -> Netlist:
    return Netlist(1, (), (0,) * dom, (0,) * cod, ((0, at),) if at is not None else ())


def _shift(net: Netlist, k: int) -> Netlist:
    return Netlist(
        net.size,
        tuple((e, tuple(n + k for n in ns)) for e, ns in net.parts),
        tuple(n + k for n in net.left),
        tuple(n + k for n in net.right),
        tuple((n + k, p) for n, p in net.named),
    )


def _glued(net: Netlist, pairs: Iterable[tuple[int, int]], left: tuple[int, ...], right: tuple[int, ...]) -> Netlist:
    """Points identified (each pair, and points of the same Node / Net), renumbered in order."""
    parent = list(range(net.size))

    def find(x: int) -> int:
        while parent[x] != x:
            x = parent[x]
        return x

    first: dict[Point, int] = {}
    for n, p in net.named:
        pairs = (*pairs, (n, first.setdefault(p, n)))
    for a, b in pairs:
        parent[find(a)] = find(b)
    roots = sorted({find(n) for n in range(net.size)})
    new = {r: i for i, r in enumerate(roots)}

    def to(n: int) -> int:
        return new[find(n)]

    return Netlist(
        len(roots),
        tuple((e, tuple(to(n) for n in ns)) for e, ns in net.parts),
        tuple(to(n) for n in left),
        tuple(to(n) for n in right),
        tuple(dict((to(n), p) for n, p in net.named).items()),
    )


@cache
def netlist(c: Circuit) -> Netlist:
    match c:
        case Element(kind):
            n = len(kind.terminals)
            ends = tuple(range(n))
            # (two terminals: 1 → 1, one each side; any other number: 0 → n, all on the right — see ``at``)
            return Netlist(n, ((c, ends),), (0,), (1,)) if n == 2 else Netlist(n, ((c, ends),), (), ends)
        case Spider(dom, cod):
            return _point(dom, cod)
        case Node() | Net():
            return _point(1, 1, c)
        case Seq(f, g):
            a, b = netlist(f), netlist(g)
            if len(a.right) != len(b.left):
                raise ValueError(f"series: {len(a.right)} ends into {len(b.left)}")
            b = _shift(b, a.size)
            names = dict(a.named) | dict(b.named)
            for x, y in zip(a.right, b.left, strict=True):
                if x in names and y in names and names[x] != names[y]:
                    raise JoinsNodes(f"{names[x]} and {names[y]}")
            both = Netlist(a.size + b.size, a.parts + b.parts, (), (), a.named + b.named)
            return _checked(_glued(both, zip(a.right, b.left, strict=True), a.left, b.right))
        case Tensor(f, g):
            a, b = netlist(f), _shift(netlist(g), netlist(f).size)
            both = Netlist(a.size + b.size, a.parts + b.parts, a.left + b.left, a.right + b.right, a.named + b.named)
            return _checked(_glued(both, (), both.left, both.right))
    raise TypeError(f"not a circuit: {c!r}")


def _checked(net: Netlist) -> Netlist:
    elements = [e for e, _ in net.parts]
    if len(set(elements)) != len(elements):
        raise ElementTwice(next(e for e in elements if elements.count(e) > 1).name or "an element")
    return net


def rebuild(parts: Iterable[Part], named: Iterable[tuple[int, Point]] = ()) -> Circuit:
    """A closed circuit from its points: each element on its points; a point keeps its ``Node`` or ``Net``,
    the others get fresh nodes (the inverse of ``netlist`` for a closed one)."""
    shown = dict(named)
    points: dict[int, Point] = {}

    def point(n: int) -> Point:
        return points.setdefault(n, shown.get(n) or Node())

    return beside(*(at(e, *(point(n) for n in ns)) for e, ns in parts))


def free(c: Circuit) -> tuple[int, int]:
    """Its ends not on a ``Node`` / ``Net`` (left, right): the ones still to be connected."""
    net = netlist(c)
    bound = {n for n, _ in net.named}
    return sum(n not in bound for n in net.left), sum(n not in bound for n in net.right)


def is_closed(c: Circuit) -> bool:
    """Nothing left to connect: every end on a point (``a >> E >> R >> a``) or joined (``close``)."""
    return free(c) == (0, 0)


# --------------------------------------------------------------------------------------- elements

Resistor = two_terminal("resistor", "R", "Ω", lambda U, I, R: U - R * I, positive=True)
Capacitor = two_terminal("capacitor", "C", "F", lambda U, I, C: I - C * D(U), positive=True)
Inductor = two_terminal("inductor", "L", "H", lambda U, I, L: U - L * D(I), positive=True)
# a source's + on its second end: V_b − V_a = E, i.e. U = −E; a current source pushes J from a to b
VoltageSource = two_terminal("voltage_source", "E", "V", lambda U, I, E: U + E, symmetric=False)
CurrentSource = two_terminal("current_source", "J", "A", lambda U, I, J: I - J, symmetric=False)
# the nullor's halves: a nullator neither drops nor passes anything (two laws), a norator anything (none)
Nullator = Kind("nullator", "N", "", ("a", "b"), lambda t, _: [t.V["a"] - t.V["b"], t.I["a"]], parameters=())
Norator = Kind("norator", "O", "", ("a", "b"), lambda t, _: [], parameters=())
# a hole: an element not known — no law at all (anything); ``methods.fill`` finds the simplest that fits
Hole = Kind("hole", "X", "", ("a", "b"), lambda t, _: [], symmetric=False, parameters=())
# a wire and a break, as elements (what a hole may turn out to be)
Wire = Kind("wire", "W", "", ("a", "b"), lambda t, _: [t.V["a"] - t.V["b"]], parameters=())
Open = Kind("open", "O", "", ("a", "b"), lambda t, _: [t.I["a"]], parameters=())

# an ideal ammeter: a wire, its current what is read (a meter is an observation: F5)
Ammeter = Kind("ammeter", "A", "A", ("a", "b"), lambda t, _: [t.V["a"] - t.V["b"]], parameters=())
# an ideal op-amp: its inputs at one potential, taking nothing; its output whatever it takes — returned
# through its supply (gnd): charge is kept, so the current out of a real one comes back somewhere
OpAmp = Kind(
    "opamp",
    "OA",
    "",
    ("+", "-", "out", "gnd"),
    lambda t, _: [t.V["+"] - t.V["-"], t.I["+"], t.I["-"]],
    symmetric=False,
    parameters=(),
)


def _controlled(
    name: str, prefix: str, unit: str, out: Callable[[Terminals, sp.Symbol], sp.Expr], senses_current: bool
) -> Kind:
    """A controlled source: its input senses a voltage (taking no current) or a current (dropping no
    voltage); its output a voltage or a current of it."""

    def laws(t: Terminals, p: Params) -> list[sp.Expr]:
        sense = [t.V["in+"] - t.V["in-"]] if senses_current else [t.I["in+"]]
        return [*sense, t.I["in+"] + t.I["in-"], out(t, p[""])]

    return Kind(name, prefix, unit, ("in+", "in-", "out+", "out-"), laws, symmetric=False)


def _u_in(t: Terminals) -> sp.Expr:
    return t.V["in+"] - t.V["in-"]


VCCS = _controlled("vccs", "VCCS", "S", lambda t, g: -t.I["out+"] - g * _u_in(t), senses_current=False)
CCVS = _controlled("ccvs", "CCVS", "Ω", lambda t, r: t.V["out+"] - t.V["out-"] - r * t.I["in+"], senses_current=True)
CCCS = _controlled("cccs", "CCCS", "", lambda t, k: -t.I["out+"] - k * t.I["in+"], senses_current=True)


def _windings(t: Terminals) -> tuple[sp.Expr, sp.Expr, sp.Expr, sp.Expr]:
    """Two windings' voltages and the currents into them (primary p+ p-, secondary s+ s-)."""
    return t.V["p+"] - t.V["p-"], t.V["s+"] - t.V["s-"], t.I["p+"], t.I["s+"]


def _transformer(t: Terminals, p: Params) -> list[sp.Expr]:
    u1, u2, i1, i2 = _windings(t)
    flux = t.inner("flux")
    return [
        u1 - D(flux),  # each winding sees the flux change (n turns to the secondary's one)
        p[""] * u2 - D(flux),
        flux - p["L_m"] * (i1 + i2 / p[""]),  # what is left over magnetizes the core
        t.I["p+"] + t.I["p-"],  # (each winding its own loop)
    ]


# a transformer of ratio n (U₁ = n·U₂ — through its flux, so in DC a winding is a short: the flux does not
# change), L_m its magnetizing inductance (large: what it takes to magnetize the core, next to nothing)
Transformer = Kind(
    "transformer",
    "TR",
    "",
    ("p+", "p-", "s+", "s-"),
    _transformer,
    symmetric=False,
    parameters=("", "L_m"),
    defaults=(("L_m", 10**6),),
)


def _coupled(t: Terminals, p: Params) -> list[sp.Expr]:
    u1, u2, i1, i2 = _windings(t)
    return [
        u1 - p["L1"] * D(i1) - p[""] * D(i2),
        u2 - p[""] * D(i1) - p["L2"] * D(i2),
        t.I["p+"] + t.I["p-"],
    ]


# two coupled inductors: L1, L2, and M (main) between them
Coupled = Kind("coupled", "M", "H", ("p+", "p-", "s+", "s-"), _coupled, symmetric=False, parameters=("", "L1", "L2"))

# a voltage-controlled voltage source: U_out = μ·U_in, its input takes no current
VCVS = Kind(
    "vcvs",
    "VCVS",
    "",
    ("in+", "in-", "out+", "out-"),
    lambda t, p: [
        (t.V["out+"] - t.V["out-"]) - p[""] * (t.V["in+"] - t.V["in-"]),
        t.I["in+"],
        t.I["in-"],
    ],
    symmetric=False,
)

# a p-n junction (Shockley): I = I_S·(e^(U/(n·V_T)) − 1); V_T at 300 K; a real part's I_S, n are data
V_T = sp.Rational(25852, 1000000)
Diode = Kind(
    "diode",
    "D",
    "",
    ("a", "b"),
    lambda t, p: [t.I["a"] - p["I_S"] * (sp.exp((t.V["a"] - t.V["b"]) / (p["n"] * V_T)) - 1)],
    symmetric=False,
    parameters=("I_S", "n"),
    defaults=(("I_S", sp.Rational(1, 10**14)), ("n", 1)),
)

# the textbook's diode: conducts at its forward drop (U_F, 0.7 V by default; any current in), or blocks
# (no current, below U_F) — two straight pieces for Shockley's curve; which, the circuit decides
DiodeDrop = Kind(
    "diode_drop",
    "D",
    "V",
    ("a", "b"),
    lambda t, p: Cases(
        (
            Case("on", (t.V["a"] - t.V["b"] - p[""],), (t.I["a"],)),
            Case("off", (t.I["a"],), (p[""] - (t.V["a"] - t.V["b"]),)),
        )
    ),
    symmetric=False,
    defaults=(("", sp.Rational(7, 10)),),
)

# a D flip-flop: on a clock's rising edge it takes what was on d just before it (the instant before the
# edge: causal — a loop through it, q back to d, never asks for its own answer), and holds it on q till
# the next edge; inputs take no current, q is a source of the level it holds (V_HIGH or 0 against gnd)
V_HIGH = 5


def _flip_flop(t: Terminals, _: Params) -> list[sp.Expr]:
    s = t.inner("s")  # what it holds: 1 or 0
    clk, d = t.V["clk"] - t.V["gnd"], t.V["d"] - t.V["gnd"]
    return [
        t.I["d"],
        t.I["clk"],
        t.V["q"] - t.V["gnd"] - V_HIGH * s,
        s - when(rising(clk, V_HIGH / 2), when(Pre(d) > V_HIGH / 2, 1, 0), Pre(s)),
    ]


def _not(t: Terminals, _: Params) -> list[sp.Expr]:
    return [t.I["in"], t.V["out"] - t.V["gnd"] - when(t.V["in"] - t.V["gnd"] > V_HIGH / 2, 0, V_HIGH)]


# a NOT gate: its output the other level of its input (no memory: no Pre)
Not = Kind("not_gate", "U", "", ("in", "out", "gnd"), _not, symmetric=False, parameters=())

DFlipFlop = Kind("d_flip_flop", "FF", "", ("d", "clk", "q", "gnd"), _flip_flop, symmetric=False, parameters=())

KINDS: tuple[Kind, ...] = (Resistor, Capacitor, Inductor, VoltageSource, CurrentSource)
