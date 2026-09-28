"""Elements that live in time: diodes and LEDs, switches, a potentiometer, transistors, the 555
timer and an Arduino board.

Semiconductors and chips are not linear, so they have laws only in time
(``ctx.transient``), for ``electro.sim``: the solver on paper says ``NeedsSimulation``.
Switches, the potentiometer and the Arduino's supply are linear and work on paper too.

The models are the textbook ones, kept small: Shockley's diode, Ebers–Moll's transistor, a
555 as two comparators and a flip-flop, an Arduino pin as a source with a resistance (what
the microcontroller sets it to comes from outside — ``Model.inputs`` — e.g. an emulated chip).
"""

from __future__ import annotations

import math

import sympy as sp

from .components import Component, Context, Law, Model, NoValue, TwoTerminal
from .issues import NeedsSimulation
from .reasons import DeviceModel, PotentiometerDivider, SourceVoltage, SwitchClosed, SwitchOpen
from .values import parse

VT = 0.025852  # thermal voltage at 27 °C
GMIN = 1e-12  # S: a tiny leak across every junction, so a reverse-biased one is never an open end
EXP_LIMIT = 80.0  # exp beyond this grows linearly: Newton's first guesses do not overflow


class limexp(sp.Function):
    """``exp(x)``, continued by its tangent beyond ``EXP_LIMIT``."""

    @classmethod
    def eval(cls, x):
        if x.is_Number:
            x = float(x)
            return sp.Float(math.exp(x) if x <= EXP_LIMIT else math.exp(EXP_LIMIT) * (1 + x - EXP_LIMIT))

    def fdiff(self, argindex=1):
        return dlimexp(self.args[0])

    def _pythoncode(self, printer):
        return f"limexp({printer._print(self.args[0])})"

    def _javascript(self, printer):
        return f"limexp({printer._print(self.args[0])})"


class dlimexp(sp.Function):
    """The derivative of ``limexp``: ``exp(min(x, EXP_LIMIT))``."""

    @classmethod
    def eval(cls, x):
        if x.is_Number:
            return sp.Float(math.exp(min(float(x), EXP_LIMIT)))

    def _pythoncode(self, printer):
        return f"dlimexp({printer._print(self.args[0])})"

    def _javascript(self, printer):
        return f"dlimexp({printer._print(self.args[0])})"


def _paper_only(label: str, ctx: Context) -> None:
    if not ctx.transient:
        raise NeedsSimulation(sp.Symbol(label))


# ------------------------------------------------------------------ diodes


class Diode(NoValue, TwoTerminal):
    """``a``: anode, ``b``: cathode; ``I = I_S·(e^{U/(n·V_T)} − 1)``."""

    prefix = "D"
    IS, N = 1e-14, 1.0

    def build(self, label, V, param, ctx):
        _paper_only(label, ctx)
        model = super().build(label, V, param, ctx)
        U, I = model.variables["U"], model.variables["I"]
        nvt = self.N * VT
        model.laws.append(Law(I - (self.IS * (limexp(U / nvt) - 1) + GMIN * U), DeviceModel(sp.Symbol(label))))
        model.junctions.append((U, nvt, self.IS))
        return model

    def law(self, U, I, x, ctx):
        return []


# forward voltage at 20 mA by colour
LED_COLORS = {"red": 2.0, "orange": 2.05, "yellow": 2.1, "green": 2.2, "blue": 3.1, "white": 3.2}


class LED(Diode):
    """A diode that lights: ``color`` sets its forward voltage (red ≈ 2 V, blue ≈ 3.1 V at 20 mA)."""

    prefix = "LED"
    N = 2.0
    RATED = 0.02  # A: full brightness

    def __init__(self, color: str = "red", label: str | None = None):
        super().__init__(label=label)
        self.color = color if color in LED_COLORS else "red"
        self.IS = self.RATED / math.exp(LED_COLORS[self.color] / (self.N * VT))

    def options(self):
        return [] if self.color == "red" else [repr(self.color)]

    @classmethod
    def from_schematic(cls, value, text, label):
        return cls(text or "red", label=label)

    def __repr__(self):
        return f"LED({self.color!r}{f', label={self.label!r}' if self.label else ''})"


# ------------------------------------------------------------------ switches

G_ON, G_OFF = 1e3, 1e-10  # S: a closed switch is 1 mΩ, an open one 10 GΩ


class Switch(NoValue, TwoTerminal):
    """Closed (``U = 0``) or open (``I = 0``). While simulating, flipped from outside: input ``<label>``."""

    prefix = "S"

    def __init__(self, closed: bool = False, label: str | None = None):
        super().__init__(label=label)
        self.closed = bool(closed)

    def build(self, label, V, param, ctx):
        model = super().build(label, V, param, ctx)
        U, I = model.variables["U"], model.variables["I"]
        name = sp.Symbol(label)
        if ctx.transient:
            closed = sp.Symbol(f"{label}_closed")
            model.inputs[closed] = float(self.closed)
            model.laws.append(Law(I - (G_ON * closed + G_OFF * (1 - closed)) * U, DeviceModel(name)))
        else:
            model.laws.append(Law(U, SwitchClosed(name)) if self.closed else Law(I, SwitchOpen(name)))
        return model

    def law(self, U, I, x, ctx):
        return []

    def options(self):
        return ["closed=True"] if self.closed else []

    @classmethod
    def from_schematic(cls, value, text, label):
        return cls(text == "closed", label=label)

    def __repr__(self):
        args = (["closed=True"] if self.closed else []) + ([f"label={self.label!r}"] if self.label else [])
        return f"{type(self).__name__}({', '.join(args)})"


class Button(Switch):
    """A push button: closed only while pressed (in the live simulation: while held down)."""

    prefix = "B"


class Potentiometer(Component):
    """``R`` between ``a`` and ``b``; the wiper ``w`` at ``position`` (0: at ``a``, 1: at ``b``).
    While simulating, the position is set from outside: input ``<label>``."""

    prefix, unit = "P", "Ω"
    left, right = ("a",), ("b", "w")
    RMIN = 1e-3  # Ω: an end of the track is never a short circuit

    def __init__(self, value=None, position: float = 0.5, label: str | None = None):
        super().__init__(value, label)
        self.position = min(1.0, max(0.0, float(position)))

    def build(self, label, V, param, ctx):
        Ia, Ib = sp.Symbol(f"I_{label}_a"), sp.Symbol(f"I_{label}_b")
        model = Model({"a": Ia, "b": Ib, "w": -(Ia + Ib)}, [], {"I_a": Ia, "I_b": Ib}, param)
        pos: sp.Expr = sp.Float(self.position)
        if ctx.transient:
            pos = sp.Symbol(f"{label}_position")
            model.inputs[pos] = self.position
        name = sp.Symbol(label)
        model.laws += [
            Law(V["a"] - V["w"] - (param * pos + self.RMIN) * Ia, PotentiometerDivider(name)),
            Law(V["b"] - V["w"] - (param * (1 - pos) + self.RMIN) * Ib, PotentiometerDivider(name)),
        ]
        return model

    def options(self):
        return [] if self.position == 0.5 else [f"position={self.position:g}"]

    @classmethod
    def from_schematic(cls, value, text, label):
        try:
            position = float(text) if text else 0.5
        except ValueError:
            position = 0.5
        return cls(parse(value), position, label=label)


# ------------------------------------------------------------------ transistors


class NPN(NoValue):
    """A bipolar transistor (Ebers–Moll): base ``b``, collector ``c``, emitter ``e``."""

    prefix = "Q"
    left, right = ("b",), ("c", "e")
    POLARITY = 1
    IS, BF, BR = 1e-14, 100.0, 1.0
    CJE, CJC = 8e-12, 4e-12  # F: the junctions' capacitances — without them switching (in a flip-flop
    # of two transistors) would take no time at all, and the step across it would have no solution

    def build(self, label, V, param, ctx):
        _paper_only(label, ctx)
        s = self.POLARITY
        Ube, Ubc = sp.Symbol(f"U_{label}_BE"), sp.Symbol(f"U_{label}_BC")
        Ic, Ib = sp.Symbol(f"I_{label}_C"), sp.Symbol(f"I_{label}_B")
        Ube0, Ubc0 = sp.Symbol(f"U_{label}_BE_prev"), sp.Symbol(f"U_{label}_BC_prev")
        forward, reverse = limexp(Ube / VT) - 1, limexp(Ubc / VT) - 1
        charge_be, charge_bc = self.CJE * (Ube - Ube0) / ctx.dt, self.CJC * (Ubc - Ubc0) / ctx.dt
        name = DeviceModel(sp.Symbol(label))
        laws = [
            Law(Ube - s * (V["b"] - V["e"]), name, "kvl"),
            Law(Ubc - s * (V["b"] - V["c"]), name, "kvl"),
            Law(Ic - s * (self.IS * (forward - reverse) - self.IS / self.BR * reverse - GMIN * Ubc - charge_bc), name),
            Law(Ib - s * (self.IS / self.BF * forward + self.IS / self.BR * reverse + GMIN * (Ube + Ubc)
                          + charge_be + charge_bc), name),
        ]
        model = Model({"c": Ic, "b": Ib, "e": -(Ic + Ib)}, laws, {"U_BE": Ube, "U_BC": Ubc, "I_C": Ic, "I_B": Ib})
        model.junctions += [(Ube, VT, self.IS), (Ubc, VT, self.IS)]
        model.states |= {Ube0: (Ube, 0.0, 0.5), Ubc0: (Ubc, 0.0, 0.5)}
        return model


class PNP(NPN):
    POLARITY = -1


# ------------------------------------------------------------------ chips


class Timer555(NoValue):
    """The NE555 timer: pins in DIP order (1 ``gnd``, 2 ``trig``, 3 ``out``, 4 ``reset``, 5 ``ctrl``,
    6 ``thr``, 7 ``dis``, 8 ``vcc``).

    Inside: a 5k–10k divider sets ``ctrl`` to ⅔·Vcc; below ``ctrl``/2 on ``trig`` the flip-flop
    sets (output high, discharge off), above ``ctrl`` on ``thr`` it resets (output low, ``dis``
    shorted to ground). The flip-flop is the element's state, checked after every step.
    ``reset`` has a weak pull-up here, so it may be left unconnected.
    """

    prefix = "IC"
    left, right = ("gnd", "trig", "out", "reset"), ("ctrl", "thr", "dis", "vcc")
    R_OUT, R_DIS, DROP = 10.0, 10.0, 1.7

    def build(self, label, V, param, ctx):
        _paper_only(label, ctx)
        q = sp.Symbol(f"{label}_q")
        g = V["gnd"]
        top, bottom, pullup = (V["vcc"] - V["ctrl"]) / 5000, (V["ctrl"] - g) / 10000, (V["vcc"] - V["reset"]) / 100000
        out = (V["out"] - (g + q * (V["vcc"] - g - self.DROP))) / self.R_OUT
        dis = (1 - q) * (V["dis"] - g) / self.R_DIS
        inflow = {
            "out": out,
            "vcc": top + pullup - q * out,
            "ctrl": bottom - top,
            "reset": -pullup,
            "dis": dis,
            "gnd": -bottom - (1 - q) * out - dis,
            "trig": sp.Integer(0),
            "thr": sp.Integer(0),
        }
        model = Model(inflow, [], {})
        after = sp.Piecewise(
            (0, V["reset"] - g < 0.7),
            (1, V["trig"] - g < (V["ctrl"] - g) / 2),
            (0, V["thr"] - g > V["ctrl"] - g),
            (q, True),
        )
        model.states[q] = (after, 0.0, None)
        return model


ARDUINO_PINS = tuple(f"D{i}" for i in range(14)) + tuple(f"A{i}" for i in range(6))
PIN_MODES = {  # what the microcontroller makes of a pin: (conductance to the pin's source, its voltage)
    "input": (1e-8, 0.0),
    "pullup": (1 / 35000, 5.0),
    "low": (1 / 25, 0.0),
    "high": (1 / 25, 5.0),
}


class Arduino(NoValue):
    """An Arduino Uno board: pins ``D0``–``D13``, ``A0``–``A5``, and its ``5V`` supply against ``GND``.

    On paper every pin is an input (no current). While simulating, each pin is a voltage
    source with a resistance, set from outside (inputs ``<label>_<pin>_G`` and ``_E``,
    e.g. by an emulated ATmega328P): see ``PIN_MODES``.
    """

    prefix = "ARD"
    left, right = ARDUINO_PINS[:14], ARDUINO_PINS[14:] + ("5V", "GND")

    def build(self, label, V, param, ctx):
        g = V["GND"]
        supply = sp.Symbol(f"I_{label}_5V")
        name = sp.Symbol(label)
        laws = [Law(V["5V"] - g - 5, SourceVoltage(name))]
        inflow: dict[str, sp.Expr] = {"5V": -supply}
        model = Model(inflow, laws, {"I_5V": supply})
        for pin in ARDUINO_PINS:
            if ctx.transient:
                G, E = sp.Symbol(f"{label}_{pin}_G"), sp.Symbol(f"{label}_{pin}_E")
                model.inputs |= {G: PIN_MODES["input"][0], E: PIN_MODES["input"][1]}
                inflow[pin] = G * (V[pin] - g - E)
            else:
                inflow[pin] = sp.Integer(0)
        inflow["GND"] = supply - sp.Add(*(inflow[p] for p in ARDUINO_PINS))
        return model
