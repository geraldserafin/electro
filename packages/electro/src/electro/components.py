"""Components = generators of the circuit category.

A component with terminals ``left + right`` is a morphism ``len(left) → len(right)``.
Its meaning is a relation between terminal potentials and currents, given as a
list of laws (sympy expressions equal to zero). Adding a new kind of component
means subclassing ``Component`` (or ``TwoTerminal``) and writing its laws.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sympy as sp

from .circuit import Circuit, Netlist, Seq, Transpose, ground, open_end, wire
from .reasons import (
    AmmeterReading,
    CapacitorImpedance,
    CapacitorOpenDC,
    CapacitorStep,
    ControlCurrent,
    ControlledSource,
    ControlVoltage,
    IdealAmmeter,
    IdealOpAmp,
    IdealVoltmeter,
    InductorImpedance,
    InductorShortDC,
    InductorStep,
    MutualInductance,
    OhmsLaw,
    Reason,
    SourceCurrent,
    SourceVoltage,
    TransformerCurrent,
    TransformerVoltage,
    UnknownElement,
    VoltageAcross,
    VoltmeterReading,
    WindingShortDC,
)

OPEN = open_end + open_end.transpose()  # 1 → 1 with nothing between: a break in the circuit
from .values import UNKNOWN, fmt, parse  # noqa: E402


@dataclass(frozen=True)
class Law:
    """``expr == 0``, with why it holds (a ``reasons`` type) for the solution's steps."""

    expr: sp.Expr
    reason: Reason
    kind: str = "law"  # "given" | "reading" | "law" | "kvl" | "kcl" — also the order the solver tries them


@dataclass(frozen=True)
class Context:
    """Analysis settings: DC (``omega=None``), AC phasors at angular frequency ``omega``, or one
    step in time (``dt``: its length, ``t``: the time at its end, both symbols): what ``electro.sim``
    solves over and over."""

    omega: sp.Expr | None = None
    dt: sp.Expr | None = None
    t: sp.Expr | None = None

    @property
    def transient(self) -> bool:
        return self.dt is not None


@dataclass
class Model:
    """What a component contributes to the equation system once placed in a circuit."""

    inflow: dict[str, sp.Expr]  # terminal -> current flowing from the node into the component
    laws: list[Law]
    variables: dict[str, sp.Symbol] = field(default_factory=dict)  # "U", "I", ...
    param: sp.Symbol | None = None
    # in time only (``ctx.transient``), for electro.sim:
    # what the element remembers between steps: symbol -> (its value after a step, as an
    # expression of this step's quantities; its value at t = 0; the most it may change in one
    # step, else the step is shortened — None: it jumps, like a flip-flop, and nothing is shortened)
    states: dict[sp.Symbol, tuple[sp.Expr, float, float | None]] = field(default_factory=dict)
    # set from outside while it runs (a switch's position, an Arduino's pin): symbol -> default
    inputs: dict[sp.Symbol, float] = field(default_factory=dict)
    # p-n junctions, for Newton's step limiting: (the junction's voltage variable, n·V_T, I_S)
    junctions: list[tuple[sp.Symbol, float, float]] = field(default_factory=list)


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

    def options(self) -> list[str]:
        """Arguments besides the value and the label, as code (``closed=True``): for ``code()``."""
        return []

    def schematic_text(self) -> str | None:
        """What a drawing keeps beside the value (a source's frequency, an LED's colour): the
        inverse of ``from_schematic``, for ``layout()``."""
        return None

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
        laws = [Law(U - drop, VoltageAcross(sp.Symbol(label)), "kvl")]
        laws += [Law(e, reason(sp.Symbol(label)), *kind) for e, reason, *kind in self.law(U, I, param, ctx)]
        return Model({"a": I, "b": -I}, laws, {"U": U, "I": I}, param)

    def law(self, U, I, x, ctx) -> list[tuple]:
        """``(expr, reason)`` or ``(expr, reason, kind)`` for each law; ``reason``: a ``reasons`` type, given the label."""
        raise NotImplementedError


class Resistor(TwoTerminal):
    prefix, unit = "R", "Ω"

    def law(self, U, I, x, ctx):
        return [(U - x * I, OhmsLaw)]


class Capacitor(TwoTerminal):
    prefix, unit = "C", "F"

    def build(self, label, V, param, ctx):
        model = super().build(label, V, param, ctx)
        if ctx.transient:  # backward Euler; U_prev: the voltage one step earlier
            prev = sp.Symbol(f"U_{label}_prev")
            U, I = model.variables["U"], model.variables["I"]
            model.laws.append(Law(I - param * (U - prev) / ctx.dt, CapacitorStep(sp.Symbol(label))))
            model.states[prev] = (U, 0.0, 0.05)
        return model

    def law(self, U, I, x, ctx):
        if ctx.transient:
            return []  # in build: it needs the state
        if ctx.omega is None:
            return [(I, CapacitorOpenDC)]
        return [(U - I / (sp.I * ctx.omega * x), CapacitorImpedance)]


class Inductor(TwoTerminal):
    prefix, unit = "L", "H"

    def build(self, label, V, param, ctx):
        model = super().build(label, V, param, ctx)
        if ctx.transient:  # I_prev: the current one step earlier
            prev = sp.Symbol(f"I_{label}_prev")
            U, I = model.variables["U"], model.variables["I"]
            model.laws.append(Law(U - param * (I - prev) / ctx.dt, InductorStep(sp.Symbol(label))))
            model.states[prev] = (I, 0.0, 1e-3)
        return model

    def law(self, U, I, x, ctx):
        if ctx.transient:
            return []
        if ctx.omega is None:
            return [(U, InductorShortDC)]
        return [(U - sp.I * ctx.omega * x * I, InductorImpedance)]


class VoltageSource(TwoTerminal):
    """Ideal EMF; ``+`` is the right terminal."""

    prefix, unit, active, positive = "E", "V", True, False

    def law(self, U, I, x, ctx):
        return [(U - x, SourceVoltage)]


class CurrentSource(TwoTerminal):
    """Ideal current source pushing current left → right."""

    prefix, unit, active, positive = "J", "A", True, False

    def law(self, U, I, x, ctx):
        return [(I - x, SourceCurrent)]


class Ammeter(TwoTerminal):
    """Ideal ammeter (U = 0); its value is the reading. ``Ammeter(2)`` is a measured current
    (a datum, unlike ``CurrentSource(2)`` which forces it), ``Ammeter()`` a reading to find."""

    prefix, unit, positive = "A", "A", False

    def law(self, U, I, x, ctx):
        return [(U, IdealAmmeter), (I - x, AmmeterReading, "reading")]


class Voltmeter(TwoTerminal):
    """Ideal voltmeter (I = 0); its value is the reading, like ``Ammeter``."""

    prefix, unit, positive = "V", "V", False

    def law(self, U, I, x, ctx):
        return [(I, IdealVoltmeter), (U - x, VoltmeterReading, "reading")]


class Controlled(Component):
    """A controlled (dependent) source, 2 → 2: control terminals (``cp``, ``cn``) → output (``n``, ``p``).

    The output is a source like ``VoltageSource`` (``+`` on ``p``; ``U = V_p − V_n``, ``I`` flowing
    through it from ``n`` to ``p``). The control side senses either a voltage ``U_c = V_cp − V_cn``
    (drawing no current, like a voltmeter) or the current ``I_c`` through a branch from ``cp`` to
    ``cn`` (dropping no voltage, like an ammeter put in series where the current is measured).
    ``value``: the gain — the output quantity over the control one.
    """

    left, right = ("cp", "cn"), ("n", "p")
    positive = False  # a gain may be negative (an inverting amplifier)
    senses, drives = "U", "U"  # the control quantity, the output quantity

    def build(self, label, V, param, ctx):
        U, I = sp.Symbol(f"U_{label}"), sp.Symbol(f"I_{label}")
        name = sp.Symbol(label)
        if self.senses == "U":
            control = sp.Symbol(f"U_{label}_c")
            laws = [Law(control - (V["cp"] - V["cn"]), ControlVoltage(name), "kvl")]
            inflow = {"cp": sp.Integer(0), "cn": sp.Integer(0)}
        else:
            control = sp.Symbol(f"I_{label}_c")
            laws = [Law(V["cp"] - V["cn"], ControlCurrent(name))]
            inflow = {"cp": control, "cn": -control}
        laws += [
            Law(U - (V["p"] - V["n"]), VoltageAcross(name), "kvl"),
            Law((U if self.drives == "U" else I) - param * control, ControlledSource(name)),
        ]
        return Model(inflow | {"n": I, "p": -I}, laws, {"U": U, "I": I, f"{self.senses}_c": control}, param)


class VCVS(Controlled):
    """Voltage-controlled voltage source: ``U = μ·U_c``."""

    prefix = "VCVS"


class VCCS(Controlled):
    """Voltage-controlled current source: ``I = g·U_c`` (``g`` in siemens)."""

    prefix, unit, drives = "VCCS", "S", "I"


class CCVS(Controlled):
    """Current-controlled voltage source: ``U = r·I_c`` (``r`` in ohms)."""

    prefix, unit, senses = "CCVS", "Ω", "I"


class CCCS(Controlled):
    """Current-controlled current source: ``I = β·I_c``."""

    prefix, senses, drives = "CCCS", "I", "I"


class OpAmp(NoValue):
    """Ideal op-amp with negative feedback, as a morphism 2 → 1: (plus, minus) → out.

    The output current is supplied from the (implicit) ground rails.
    """

    prefix = "OA"
    left, right = ("plus", "minus"), ("out",)

    def build(self, label, V, param, ctx):
        I = sp.Symbol(f"I_{label}")
        laws = [Law(V["plus"] - V["minus"], IdealOpAmp(sp.Symbol(label)))]
        return Model({"plus": sp.Integer(0), "minus": sp.Integer(0), "out": -I}, laws, {"I": I})


class Transformer(Component):
    """Ideal transformer, 2 → 2 like a controlled source: the primary (``p1`` above ``p2``) on the
    left, the secondary (``s2`` below ``s1``) on the right, the dots at ``p1`` and ``s1``.

    ``value``: the turns ratio ``n = N₁/N₂``; ``U₁ = n·U₂`` and ``I₂ = n·I₁`` (``I₁`` into ``p1``,
    ``I₂`` out of ``s1``), so the power in is the power out. In a DC steady state both windings are
    short circuits; in time it stays ideal (it passes DC too).
    """

    prefix, unit = "TR", ""
    left, right = ("p1", "p2"), ("s2", "s1")

    def build(self, label, V, param, ctx):
        name = sp.Symbol(label)
        U1, I1, U2, I2 = (sp.Symbol(f"{q}_{label}") for q in ("U1", "I1", "U2", "I2"))
        laws = [
            Law(U1 - (V["p1"] - V["p2"]), VoltageAcross(name), "kvl"),
            Law(U2 - (V["s1"] - V["s2"]), VoltageAcross(name), "kvl"),
        ]
        if ctx.omega is None and not ctx.transient:
            laws += [Law(U1, WindingShortDC(name)), Law(U2, WindingShortDC(name))]
        else:
            laws += [Law(U1 - param * U2, TransformerVoltage(name)), Law(I2 - param * I1, TransformerCurrent(name))]
        inflow = {"p1": I1, "p2": -I1, "s1": -I2, "s2": I2}
        return Model(inflow, laws, {"U1": U1, "I1": I1, "U2": U2, "I2": I2}, param)


class Coupled(Component):
    """Two magnetically coupled inductors ``L1``, ``L2`` (henries), 2 → 2 like ``Transformer``;
    ``value``: the mutual inductance ``M``. Both currents flow in at the dots (``p1``, ``s1``):
    ``U₁ = jωL₁·I₁ + jωM·I₂``, ``U₂ = jωM·I₁ + jωL₂·I₂``; in DC both are short circuits."""

    prefix, unit = "M", "H"
    left, right = ("p1", "p2"), ("s2", "s1")
    positive = False  # M < 0: a dot on the other end

    def __init__(self, value=None, L1=None, L2=None, label: str | None = None):
        super().__init__(value, label)
        self.L1, self.L2 = parse(L1, positive=True), parse(L2, positive=True)

    def options(self):
        return [f"L1={fmt(self.L1, 'H')!r}", f"L2={fmt(self.L2, 'H')!r}"]

    def build(self, label, V, param, ctx):
        name = sp.Symbol(label)
        U1, I1, U2, I2 = (sp.Symbol(f"{q}_{label}") for q in ("U1", "I1", "U2", "I2"))
        laws = [
            Law(U1 - (V["p1"] - V["p2"]), VoltageAcross(name), "kvl"),
            Law(U2 - (V["s1"] - V["s2"]), VoltageAcross(name), "kvl"),
        ]
        model = Model({"p1": I1, "p2": -I1, "s1": I2, "s2": -I2}, laws, {"U1": U1, "I1": I1, "U2": U2, "I2": I2}, param)
        if ctx.transient:  # backward Euler on both fluxes
            p1, p2 = sp.Symbol(f"I1_{label}_prev"), sp.Symbol(f"I2_{label}_prev")
            laws.append(Law(U1 - (self.L1 * (I1 - p1) + param * (I2 - p2)) / ctx.dt, MutualInductance(name)))
            laws.append(Law(U2 - (param * (I1 - p1) + self.L2 * (I2 - p2)) / ctx.dt, MutualInductance(name)))
            model.states[p1], model.states[p2] = (I1, 0.0, 1e-3), (I2, 0.0, 1e-3)
        elif ctx.omega is None:
            laws += [Law(U1, WindingShortDC(name)), Law(U2, WindingShortDC(name))]
        else:
            jw = sp.I * ctx.omega
            laws.append(Law(U1 - jw * (self.L1 * I1 + param * I2), MutualInductance(name)))
            laws.append(Law(U2 - jw * (param * I1 + self.L2 * I2), MutualInductance(name)))
        return model


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
        model.laws.append(Law(U - (Z * I - E), UnknownElement(sp.Symbol(label))))
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


def notation(c: Circuit, sign: int = 1) -> str:
    """What a filled hole turned out to be, in values rather than words: ``R = 2 Ω``, ``E = −17 V``
    (a source the other way round), ``R = ∞`` (a break), ``R = 0 Ω`` (a wire)."""
    if c is OPEN:
        return "R = ∞"
    if isinstance(c, Transpose):
        return notation(c.part, -sign)
    if isinstance(c, Seq):
        return ", ".join(notation(p, sign) for p in c.parts)
    if isinstance(c, Component) and c.has_value:
        return f"{c.prefix} = {fmt(sign * c.value if c.active else c.value, c.unit)}"
    return f"R = {fmt(0, 'Ω')}"


def supply(value=None, label: str | None = None) -> Circuit:
    """Voltage source from ground, 0 → 1: ``ground.transpose() + VoltageSource(value)``."""
    return ground.transpose() + VoltageSource(value, label)


# ---------------------------------------------------------------- three-phase (in AC: solve(omega=…))

LINES = ("L1", "L2", "L3")
_PHASES = (
    sp.Integer(1),
    sp.exp(-2 * sp.pi * sp.I / 3).expand(complex=True),
    sp.exp(2 * sp.pi * sp.I / 3).expand(complex=True),
)


def three_phase(E=230, lines=LINES, neutral: str = "N") -> Circuit:
    """A symmetric three-phase source in a star: phase voltage ``E`` (amplitude, as every phasor
    here) from ``neutral`` to each line, at 0°, −120° and 120°. Joined to loads by the nodes'
    names: ``three_phase(230) | star(Resistor(10), Resistor(20), Resistor(30))``."""
    from .circuit import net

    e = parse(E)
    return net(*((VoltageSource(e * p), neutral, line) for p, line in zip(_PHASES, lines)))


def star(*loads: Circuit, lines=LINES, neutral: str = "N") -> Circuit:
    """A star load: one load (``1 → 1``) from each line to ``neutral`` — the source's (four
    wires), or a name of its own for a floating star point (three wires). One load for all three
    is copied."""
    from .circuit import net

    return net(*((z, line, neutral) for z, line in zip(_three(loads), lines)))


def delta(*loads: Circuit, lines=LINES) -> Circuit:
    """A delta load: L1–L2, L2–L3, L3–L1. One load for all three is copied."""
    from .circuit import net

    a, b, c = lines
    return net(*((z, x, y) for z, (x, y) in zip(_three(loads), ((a, b), (b, c), (c, a)))))


def _three(loads):
    if len(loads) == 1:
        from copy import deepcopy

        return [loads[0], deepcopy(loads[0]), deepcopy(loads[0])]
    if len(loads) != 3:
        raise ValueError(f"three loads, or one for all three (got {len(loads)})")
    return loads
