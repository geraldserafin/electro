"""Circuits as morphisms of a hypergraph category.

Three layers, connected by functors:

    Circuit (syntax tree, free category)  --netlist-->  Netlist (cospan of nodes)
                                          --semantics--> equations (relations)

The syntax tree is kept as built, so a renderer can draw it; the netlist is its
normal form, where composition is gluing of boundary nodes (a pushout).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from .issues import (
    CloseNeedsNToN,
    NotACircuit,
    ParallelMismatch,
    SeriesMismatch,
    ShuntNeedsOneToOne,
    WrongNodeCount,
)

if TYPE_CHECKING:
    from .components import Component

GROUND = "GND"


# --------------------------------------------------------------------------- netlist


@dataclass(frozen=True)
class Netlist:
    """A cospan ``left → nodes ← right`` decorated with components.

    ``parts[i] = (component, node per terminal)``; ``labels`` names nodes (net labels:
    nodes with the same name are the same node, ``GND`` is ground).
    """

    size: int
    parts: tuple[tuple[Component, tuple[int, ...]], ...]
    left: tuple[int, ...]
    right: tuple[int, ...]
    labels: tuple[tuple[int, str], ...] = ()

    def shifted(self, k: int) -> Netlist:
        return Netlist(
            self.size,
            tuple((c, tuple(n + k for n in ns)) for c, ns in self.parts),
            tuple(n + k for n in self.left),
            tuple(n + k for n in self.right),
            tuple((n + k, s) for n, s in self.labels),
        )

    @staticmethod
    def disjoint(*nets: Netlist) -> Netlist:
        size, parts, left, right, labels = 0, (), (), (), ()
        for net in nets:
            s = net.shifted(size)
            size += net.size
            parts, left, right, labels = parts + s.parts, left + s.left, right + s.right, labels + s.labels
        return Netlist(size, parts, left, right, labels)

    def glue(self, pairs=(), *, left=None, right=None, labels=()) -> Netlist:
        """Identify nodes (quotient), replace the boundary, and renumber to normal form."""
        parent = list(range(self.size))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        all_labels = self.labels + tuple(labels)
        by_name: dict[str, int] = {}
        for n, name in all_labels:
            if name in by_name:
                pairs = (*pairs, (by_name[name], n))
            else:
                by_name[name] = n
        for x, y in pairs:
            parent[find(x)] = find(y)

        left = self.left if left is None else left
        right = self.right if right is None else right
        order: dict[int, int] = {}

        def new(n):
            return order.setdefault(find(n), len(order))

        new_left = tuple(new(n) for n in left)
        new_parts = tuple((c, tuple(new(n) for n in ns)) for c, ns in self.parts)
        new_right = tuple(new(n) for n in right)
        new_labels = {}
        for n, name in all_labels:
            new_labels.setdefault(new(n), name)
        return Netlist(len(order), new_parts, new_left, new_right, tuple(sorted(new_labels.items())))


# --------------------------------------------------------------------------- syntax


class Circuit:
    """A morphism ``dom → cod``: ``dom`` terminals on the left, ``cod`` on the right.

    Combinators::

        f + g          series / sequential composition (glue f's right side to g's left side)
        f | g          parallel connection (same boundary, glued on both sides)
        f @ g          side by side (monoidal product), no connection
        f.transpose()  transpose (dagger): swap left and right
        f.close()      connect each right terminal back to its left one (trace)

    Python precedence: ``@`` > ``+`` > ``|``, so ``a + b | c`` means ``(a + b) | c``.
    """

    dom: int
    cod: int

    @cached_property
    def netlist(self) -> Netlist:
        net = self._netlist()
        assert len(net.left) == self.dom and len(net.right) == self.cod
        return net

    def _netlist(self) -> Netlist:
        raise NotImplementedError

    # combinators
    def __add__(self, other: Circuit) -> Circuit:
        return Seq((self, _check(other)))

    def __or__(self, other: Circuit) -> Circuit:
        return Par((self, _check(other)))

    def __matmul__(self, other: Circuit) -> Circuit:
        return Tensor((self, _check(other)))

    def transpose(self) -> Circuit:
        """Transpose (dagger): left and right swap sides (for a source: reversed polarity)."""
        return Transpose(self)

    def close(self) -> Circuit:
        return Close(self)

    def replace(self, fn) -> Circuit:
        """Rebuild the tree with every component ``c`` replaced by ``fn(c)`` (a circuit)."""
        return self._replace(fn)

    def _replace(self, fn) -> Circuit:
        return self  # leaves without components: wires, spiders, swaps

    def __call__(self, **data) -> Circuit:
        """The circuit with data applied — each element named given that value (``obwod(R_1=10,
        E_1="12")``), the rest as they were (an unknown stays one): the same circuit, to solve or to
        simulate. Built once, given data apart, as a problem is set."""
        import copy

        from .issues import NoSuchElement
        from .values import parse

        valued: list[str] = []

        def collect(c):
            if c.has_value and c.label:
                valued.append(c.label)
            return c

        self.replace(collect)
        for label in data:
            if label not in valued:
                raise NoSuchElement(label, valued)

        def given(c):
            if c.label not in data:
                return c
            out = copy.copy(c)
            out.__dict__.pop("netlist", None)  # (its netlist, cached, has the old one in it)
            out.value = parse(data[c.label], positive=c.positive)
            return out

        return self.replace(given)

    def fill(self, solution) -> Circuit:
        """This circuit with every ``Hole`` replaced by the element the solution found."""
        return self.replace(solution.realize_component)

    def solve(self, *equations, omega=None, find=None, **given):
        from .solver import solve

        return solve(self, *equations, omega=omega, find=find, **given)

    @property
    def type(self) -> str:
        return f"{self.dom} → {self.cod}"


def _check(x) -> Circuit:
    if not isinstance(x, Circuit):
        raise NotACircuit(repr(x))
    return x


def _flatten(cls, parts):
    out = []
    for p in parts:
        out.extend(p.parts if type(p) is cls else (p,))
    return tuple(out)


@dataclass(frozen=True, eq=False)
class Spider(Circuit):
    """A single node with ``dom`` wires on the left and ``cod`` on the right (Frobenius spider).

    ``Spider(1, 1)`` is a wire, ``Spider(1, 2)`` splits, ``Spider(2, 1)`` joins,
    ``Spider(1, 0)`` is an open end, ``Spider(0, 2)`` / ``Spider(2, 0)`` bend a wire.
    """

    dom: int
    cod: int
    name: str | None = None  # net label

    def _netlist(self):
        labels = ((0, self.name),) if self.name else ()
        return Netlist(1, (), (0,) * self.dom, (0,) * self.cod, labels)

    def __repr__(self):
        if self.name == GROUND:
            return "ground" if self.dom else "ground.transpose()"
        if self.name:
            return f"node({self.name!r})"
        return f"spider({self.dom}, {self.cod})"


@dataclass(frozen=True, eq=False)
class Id(Circuit):
    """``n`` parallel bare wires."""

    n: int

    def __post_init__(self):
        object.__setattr__(self, "dom", self.n)
        object.__setattr__(self, "cod", self.n)

    def _netlist(self):
        return Netlist(self.n, (), tuple(range(self.n)), tuple(range(self.n)))

    def __repr__(self):
        return "wire" if self.n == 1 else f"wires({self.n})"


@dataclass(frozen=True, eq=False)
class Swap(Circuit):
    """Two wires crossing."""

    dom = 2
    cod = 2

    def _netlist(self):
        return Netlist(2, (), (0, 1), (1, 0))

    def __repr__(self):
        return "swap"


@dataclass(frozen=True, eq=False)
class Seq(Circuit):
    parts: tuple[Circuit, ...]

    def __post_init__(self):
        parts = _flatten(Seq, self.parts)
        for f, g in zip(parts, parts[1:]):
            if f.cod != g.dom:
                raise SeriesMismatch(repr(f), repr(g), f.cod, g.dom)
        object.__setattr__(self, "parts", parts)
        object.__setattr__(self, "dom", parts[0].dom)
        object.__setattr__(self, "cod", parts[-1].cod)

    def _netlist(self):
        nets = [p.netlist for p in self.parts]
        whole = Netlist.disjoint(*nets)
        pairs, offset = [], 0
        for f, g in zip(nets, nets[1:]):
            pairs += [(offset + a, offset + f.size + b) for a, b in zip(f.right, g.left)]
            offset += f.size
        last = whole.size - nets[-1].size
        return whole.glue(pairs, left=nets[0].left, right=tuple(last + n for n in nets[-1].right))

    def _replace(self, fn):
        return type(self)(tuple(p._replace(fn) for p in self.parts))

    def __repr__(self):
        return " + ".join(_paren(p, (Par, Tensor)) for p in self.parts)


@dataclass(frozen=True, eq=False)
class Tensor(Circuit):
    parts: tuple[Circuit, ...]

    def __post_init__(self):
        parts = _flatten(Tensor, self.parts)
        object.__setattr__(self, "parts", parts)
        object.__setattr__(self, "dom", sum(p.dom for p in parts))
        object.__setattr__(self, "cod", sum(p.cod for p in parts))

    def _netlist(self):
        return Netlist.disjoint(*(p.netlist for p in self.parts)).glue()

    def _replace(self, fn):
        return type(self)(tuple(p._replace(fn) for p in self.parts))

    def __repr__(self):
        return " @ ".join(_paren(p, (Seq, Par)) for p in self.parts)


@dataclass(frozen=True, eq=False)
class Par(Circuit):
    """Parallel connection: ``split + (f @ g) + join``, generalised to any arity."""

    parts: tuple[Circuit, ...]

    def __post_init__(self):
        parts = _flatten(Par, self.parts)
        first = parts[0]
        for p in parts[1:]:
            if (p.dom, p.cod) != (first.dom, first.cod):
                raise ParallelMismatch(repr(first), str(first.type), repr(p), str(p.type))
        object.__setattr__(self, "parts", parts)
        object.__setattr__(self, "dom", first.dom)
        object.__setattr__(self, "cod", first.cod)

    def _netlist(self):
        nets = [p.netlist for p in self.parts]
        whole = Netlist.disjoint(*nets)
        offsets = [sum(n.size for n in nets[:i]) for i in range(len(nets))]
        pairs = []
        for net, off in zip(nets[1:], offsets[1:]):
            pairs += [(a, off + b) for a, b in zip(nets[0].left, net.left)]
            pairs += [(a, off + b) for a, b in zip(nets[0].right, net.right)]
        return whole.glue(pairs, left=nets[0].left, right=nets[0].right)

    def _replace(self, fn):
        return type(self)(tuple(p._replace(fn) for p in self.parts))

    def __repr__(self):
        return " | ".join(_paren(p, (Seq, Tensor)) for p in self.parts)


@dataclass(frozen=True, eq=False)
class Shunt(Circuit):
    """A 1 → 1 element hung from the line to ground: ``split + (wire @ (x + ground))``."""

    part: Circuit
    dom = 1
    cod = 1

    def __post_init__(self):
        if (self.part.dom, self.part.cod) != (1, 1):
            raise ShuntNeedsOneToOne(repr(self.part), str(self.part.type))

    def _netlist(self):
        return (Spider(1, 2) + (Id(1) @ (self.part + ground))).netlist

    def _replace(self, fn):
        return type(self)(self.part._replace(fn))

    def __repr__(self):
        return f"shunt({self.part!r})"


@dataclass(frozen=True, eq=False)
class Transpose(Circuit):
    part: Circuit

    def __post_init__(self):
        object.__setattr__(self, "dom", self.part.cod)
        object.__setattr__(self, "cod", self.part.dom)

    def _netlist(self):
        n = self.part.netlist
        return Netlist(n.size, n.parts, n.right, n.left, n.labels)

    def _replace(self, fn):
        return type(self)(self.part._replace(fn))

    def __repr__(self):
        return f"{_paren(self.part, (Seq, Par, Tensor))}.transpose()"


@dataclass(frozen=True, eq=False)
class Close(Circuit):
    """Trace: glue right terminal ``i`` to left terminal ``i`` (e.g. close a series loop)."""

    part: Circuit
    dom = 0
    cod = 0

    def __post_init__(self):
        if self.part.dom != self.part.cod:
            raise CloseNeedsNToN(str(self.part.type))

    def _netlist(self):
        n = self.part.netlist
        return n.glue(zip(n.left, n.right), left=(), right=())

    def _replace(self, fn):
        return type(self)(self.part._replace(fn))

    def __repr__(self):
        return f"{_paren(self.part, (Seq, Par, Tensor))}.close()"


@dataclass(frozen=True, eq=False)
class Net(Circuit):
    """Place circuits between named nodes (a netlist, like in SPICE). Result: 0 → 0."""

    items: tuple[tuple[Circuit, tuple[str, ...]], ...]
    dom = 0
    cod = 0

    def __post_init__(self):
        for c, names in self.items:
            if len(names) != c.dom + c.cod:
                raise WrongNodeCount(repr(c), c.dom + c.cod, [str(n) for n in names])

    def _netlist(self):
        nets = [c.netlist for c, _ in self.items]
        whole = Netlist.disjoint(*nets)
        labels, offset = [], 0
        for net, (_, names) in zip(nets, self.items):
            nodes = [offset + n for n in net.left + net.right]
            labels += [(n, _node_name(s)) for n, s in zip(nodes, names)]
            offset += net.size
        return whole.glue(left=(), right=(), labels=labels)

    def _replace(self, fn):
        return Net(tuple((c._replace(fn), names) for c, names in self.items))

    def __repr__(self):
        return "net(" + ", ".join(f"({c!r}, {', '.join(map(repr, ns))})" for c, ns in self.items) + ")"


def _paren(c: Circuit, kinds) -> str:
    return f"({c!r})" if isinstance(c, kinds) else repr(c)


def _node_name(name: str) -> str:
    return GROUND if str(name).upper() in ("0", "GND") else str(name)


# --------------------------------------------------------------------------- public API

wire = Id(1)
swap = Swap()
split = Spider(1, 2)
join = Spider(2, 1)
ground = Spider(1, 0, GROUND)
open_end = Spider(1, 0)


def wires(n: int) -> Circuit:
    return Id(n)


def spider(dom: int, cod: int) -> Circuit:
    return Spider(dom, cod)


def node(name: str) -> Circuit:
    """A named point on a wire (1 → 1). Same name = same node, ``"GND"``/``"0"`` = ground."""
    return Spider(1, 1, _node_name(name))


def series(*parts: Circuit) -> Circuit:
    return Seq(parts)


def parallel(*parts: Circuit) -> Circuit:
    return Par(parts)


def shunt(part: Circuit) -> Circuit:
    return Shunt(part)


def loop(*parts: Circuit) -> Circuit:
    """Series elements closed into a loop: ``series(*parts).close()``."""
    return Close(Seq(parts))


def net(*items) -> Circuit:
    """``net((VoltageSource(12), "0", "A"), (Resistor(10), "A", "B"), ...)`` — circuit between named nodes."""
    return Net(tuple((c, tuple(names)) for c, *names in items))
