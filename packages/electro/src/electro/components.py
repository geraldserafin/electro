"""Components = generators of the circuit category.

A component with terminals ``left + right`` is a morphism ``len(left) → len(right)``.
Its meaning is a relation between terminal potentials and currents, given as a
list of laws (sympy expressions equal to zero). Adding a new kind of component
means subclassing ``Component`` (or ``TwoTerminal``) and writing its laws.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sympy as sp

from .circuit import GROUND, Circuit, Netlist, ground, open_end, wire

OPEN = open_end + open_end.transpose()  # 1 → 1 with nothing between: a break in the circuit
from .values import UNKNOWN, fmt, parse


@dataclass(frozen=True)
class Law:
    """``expr == 0``, with a human-readable justification used in the solution trace."""

    expr: sp.Expr
    reason: str
    kind: str = "law"  # "given" | "reading" | "law" | "kvl" | "kcl" — also the order the solver tries them


@dataclass(frozen=True)
class Context:
    """Analysis settings: DC (``omega=None``) or AC phasors at angular frequency ``omega``."""

    omega: sp.Expr | None = None


@dataclass
class Model:
    """What a component contributes to the equation system once placed in a circuit."""

    inflow: dict[str, sp.Expr]  # terminal -> current flowing from the node into the component
    laws: list[Law]
    variables: dict[str, sp.Symbol] = field(default_factory=dict)  # "U", "I", ...
    param: sp.Symbol | None = None


class Component(Circuit):
    """A single component; it is itself a circuit (a generator of the category)."""

    prefix = "X"
    unit = ""
    left: tuple[str, ...] = ()
    right: tuple[str, ...] = ()
    has_value = True
    positive = True  # assumption for an unknown value (R, C, L > 0)

    def __init__(self, value=None, label: str | None = None):
        self.value = parse(value, positive=self.positive) if self.has_value else None
        self.label = label

    @property
    def terminals(self) -> tuple[str, ...]:
        return self.left + self.right

    def param_symbol(self, label: str) -> sp.Symbol | None:
        if not self.has_value:
            return None
        if isinstance(self.value, sp.Symbol):
            return self.value
        # positive=False in sympy would mean "not positive", so plain real symbols for sources
        return sp.Symbol(label, positive=True) if self.positive else sp.Symbol(label, real=True)

    def build(self, label: str, V: dict[str, sp.Expr], param, ctx: Context) -> Model:
        raise NotImplementedError

    @property
    def dom(self) -> int:
        return len(self.left)

    @property
    def cod(self) -> int:
        return len(self.right)

    def _netlist(self) -> Netlist:
        k = len(self.terminals)
        return Netlist(k, ((self, tuple(range(k))),), tuple(range(self.dom)), tuple(range(self.dom, k)))

    def _replace(self, fn) -> Circuit:
        return fn(self)

    def __repr__(self) -> str:
        args = []
        if self.has_value:
            args.append("?" if self.value is UNKNOWN else fmt(self.value, self.unit))
        if self.label:
            args.append(f"label={self.label!r}")
        return f"{type(self).__name__}({', '.join(args)})"


class NoValue(Component):
    """Components without a value (meters, op-amps): the only argument is the label."""

    has_value = False

    def __init__(self, label: str | None = None):
        super().__init__(label=label)


class TwoTerminal(Component):
    """Terminal ``a`` on the left, ``b`` on the right; current ``I`` flows a → b through it.

    Passive elements: ``U = V_a − V_b`` (drop). Sources (``active``): ``U = V_b − V_a`` (rise),
    so ``P = U·I`` is absorbed power for passives and delivered power for sources.
    """

    left, right = ("a",), ("b",)
    active = False

    def build(self, label, V, param, ctx):
        U, I = sp.Symbol(f"U_{label}"), sp.Symbol(f"I_{label}")
        drop = V["b"] - V["a"] if self.active else V["a"] - V["b"]
        laws = [Law(U - drop, f"napięcie na {label} (różnica potencjałów)", "kvl")]
        laws += [Law(e, r.format(label=label), *kind) for e, r, *kind in self.law(U, I, param, ctx)]
        return Model({"a": I, "b": -I}, laws, {"U": U, "I": I}, param)

    def law(self, U, I, x, ctx) -> list[tuple]:
        """``(expr, reason)`` or ``(expr, reason, kind)`` for each law; ``{label}`` in reason is filled in."""
        raise NotImplementedError


class Resistor(TwoTerminal):
    prefix, unit = "R", "Ω"

    def law(self, U, I, x, ctx):
        return [(U - x * I, "prawo Ohma ({label})")]


class Capacitor(TwoTerminal):
    prefix, unit = "C", "F"

    def law(self, U, I, x, ctx):
        if ctx.omega is None:
            return [(I, "kondensator w stanie ustalonym DC nie przewodzi ({label})")]
        return [(U - I / (sp.I * ctx.omega * x), "impedancja kondensatora 1/(jωC) ({label})")]


class Inductor(TwoTerminal):
    prefix, unit = "L", "H"

    def law(self, U, I, x, ctx):
        if ctx.omega is None:
            return [(U, "cewka w stanie ustalonym DC to zwarcie ({label})")]
        return [(U - sp.I * ctx.omega * x * I, "impedancja cewki jωL ({label})")]


class VoltageSource(TwoTerminal):
    """Ideal EMF; ``+`` is the right terminal."""

    prefix, unit, active, positive = "E", "V", True, False

    def law(self, U, I, x, ctx):
        return [(U - x, "źródło napięcia ({label})")]


class CurrentSource(TwoTerminal):
    """Ideal current source pushing current left → right."""

    prefix, unit, active, positive = "J", "A", True, False

    def law(self, U, I, x, ctx):
        return [(I - x, "źródło prądu ({label})")]


class Ammeter(TwoTerminal):
    """Ideal ammeter (U = 0); its value is the reading. ``Ammeter(2)`` is a measured current
    (a datum, unlike ``CurrentSource(2)`` which forces it), ``Ammeter()`` a reading to find."""

    prefix, unit, positive = "A", "A", False

    def law(self, U, I, x, ctx):
        return [(U, "idealny amperomierz: U = 0 ({label})"), (I - x, "odczyt amperomierza ({label})", "reading")]


class Voltmeter(TwoTerminal):
    """Ideal voltmeter (I = 0); its value is the reading, like ``Ammeter``."""

    prefix, unit, positive = "V", "V", False

    def law(self, U, I, x, ctx):
        return [(I, "idealny woltomierz: I = 0 ({label})"), (U - x, "odczyt woltomierza ({label})", "reading")]


class OpAmp(NoValue):
    """Ideal op-amp with negative feedback, as a morphism 2 → 1: (plus, minus) → out.

    The output current is supplied from the (implicit) ground rails.
    """

    prefix = "OA"
    left, right = ("plus", "minus"), ("out",)

    def build(self, label, V, param, ctx):
        I = sp.Symbol(f"I_{label}")
        laws = [Law(V["plus"] - V["minus"], f"idealny wzmacniacz: V+ = V− ({label})")]
        return Model({"plus": sp.Integer(0), "minus": sp.Integer(0), "out": -I}, laws, {"I": I})


class Hole(NoValue, TwoTerminal):
    """An unknown two-terminal element: the solver decides what it is.

    Any linear two-terminal element is ``VoltageSource(E) + Resistor(Z)`` (Thévenin), so a hole
    is the relation ``V_a − V_b = Z·I − E`` with unknown ``E`` and ``Z ≥ 0``. When the data
    leave that open, the simplest fitting element is taken: a resistor (E = 0), else a break
    (I = 0, ``OPEN``), else a source (Z = 0).
    """

    prefix = "X"

    def build(self, label, V, param, ctx):
        model = super().build(label, V, param, ctx)
        E = sp.Symbol(f"E_{label}")
        Z = sp.Symbol(f"Z_{label}", nonnegative=True) if ctx.omega is None else sp.Symbol(f"Z_{label}")
        U, I = model.variables["U"], model.variables["I"]
        model.laws.append(Law(U - (Z * I - E), f"nieznany element: U = Z·I − E ({label})"))
        model.variables |= {"E": E, "Z": Z}
        return model

    def law(self, U, I, x, ctx):
        return []

    @staticmethod
    def realize(E, Z) -> Circuit:
        """The simplest circuit with this Thévenin pair."""
        source = VoltageSource(E) if E >= 0 else VoltageSource(-E).transpose()
        if Z == 0:
            return wire if E == 0 else source
        return Resistor(Z) if E == 0 else source + Resistor(Z)


def supply(value=None, label: str | None = None) -> Circuit:
    """Voltage source from ground, 0 → 1: ``ground.transpose() + VoltageSource(value)``."""
    return ground.transpose() + VoltageSource(value, label)
