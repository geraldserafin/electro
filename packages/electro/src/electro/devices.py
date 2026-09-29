"""Elements that live in time: sine and square sources, diodes, LEDs (single, RGB, seven-segment)
and Zener diodes, sensors (light, temperature, distance), buzzers, a servo and a character LCD,
switches, a potentiometer, bipolar transistors and MOSFETs, the 555 timer and an Arduino board.

Semiconductors and chips are not linear, so they have laws only in time
(``ctx.transient``), for ``electro.sim``: the solver on paper says ``NeedsSimulation``.
Switches, the potentiometer and the Arduino's supply are linear and work on paper too.

The models are the textbook ones, kept small: Shockley's diode, Ebers–Moll's transistor,
Shichman–Hodges' MOSFET, a 555 as two comparators and a flip-flop, an Arduino pin as a source
with a resistance (what the microcontroller sets it to comes from outside — ``Model.inputs`` —
e.g. an emulated chip).
"""

from __future__ import annotations

import math

import sympy as sp

from .components import Component, Context, Law, Model, NoValue, TwoTerminal
from .issues import BadValue, NeedsSimulation
from .reasons import DeviceModel, OhmsLaw, PotentiometerDivider, SourceVoltage, SwitchClosed, SwitchOpen
from .values import UNKNOWN, fmt, parse

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


# ------------------------------------------------------------------ sources in time


def _frequency(text) -> sp.Expr:
    """``"50"``, ``"1k"``, ``"1 kHz"`` → Hz."""
    f = parse(text or None)
    if not (isinstance(f, sp.Number) and f > 0):
        raise BadValue(str(text))
    return f


class SineSource(TwoTerminal):
    """``U = value·sin(2π·f·t)``, ``+`` on the right like ``VoltageSource``; ``value`` is the amplitude.

    On paper only as a phasor (``solve(omega=...)``: the amplitude, phase 0); with DC, it needs time.
    """

    prefix, unit, active, positive = "E", "V", True, False
    on_paper = True  # as a phasor
    STEPS = 40  # at least this many steps a period

    def __init__(self, value=None, frequency=50, label: str | None = None):
        super().__init__(value, label)
        self.frequency = _frequency(frequency)

    def build(self, label, V, param, ctx):
        if not ctx.transient and (ctx.omega is None or not self.on_paper):
            raise NeedsSimulation(sp.Symbol(label))
        model = super().build(label, V, param, ctx)
        if ctx.transient:  # the time as a state: it may move at most a period/STEPS a step
            model.states[sp.Symbol(f"{label}_t")] = (ctx.t, 0.0, float(1 / self.frequency) / self.STEPS)
        return model

    def wave(self, x, t):
        return x * sp.sin(2 * sp.pi * self.frequency * t)

    def law(self, U, I, x, ctx):
        if ctx.transient:
            return [(U - self.wave(x, ctx.t), DeviceModel)]
        return [(U - x, SourceVoltage)]

    def options(self):
        return [f"frequency={float(self.frequency):g}"]

    @classmethod
    def from_schematic(cls, value, text, label):
        """``text``: the frequency (``"50"``, ``"1 kHz"``)."""
        return cls(parse(value), text or 50, label=label)

    def __repr__(self):
        args = ["?" if self.value is UNKNOWN else fmt(self.value, self.unit), *self.options()]
        return f"{type(self).__name__}({', '.join(args + ([f'label={self.label!r}'] if self.label else []))})"


class SquareSource(SineSource):
    """``value`` for the first ``duty`` of every period, then 0 V: a clock, a PWM signal. In time only."""

    on_paper = False
    STEPS = 100

    def __init__(self, value=None, frequency=1000, duty: float = 0.5, label: str | None = None):
        super().__init__(value, frequency, label)
        self.duty = min(1.0, max(0.0, float(duty)))

    def build(self, label, V, param, ctx):
        model = super().build(label, V, param, ctx)
        if ctx.transient:  # the level as a state that jumps: after an edge the steps start short again
            high = sp.Symbol(f"{label}_high")
            model.states[high] = (self.high(ctx.t), 1.0, None)
        return model

    def high(self, t):
        phase = self.frequency * t
        return sp.Piecewise((1, phase - sp.floor(phase) < self.duty), (0, True))

    def wave(self, x, t):
        return x * self.high(t)

    def options(self):
        return super().options() + ([] if self.duty == 0.5 else [f"duty={self.duty:g}"])

    @classmethod
    def from_schematic(cls, value, text, label):
        """``text``: the frequency, then the duty in per cent if not 50: ``"1k"``, ``"1 kHz 25%"``."""
        words = (text or "").split()
        duty = 0.5
        if words and words[-1].endswith("%"):
            try:
                duty = float(words.pop().rstrip("%").replace(",", ".")) / 100
            except ValueError:
                raise BadValue(text) from None
        return cls(parse(value), " ".join(words) or 1000, duty, label=label)


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
LED_N, LED_RATED = 2.0, 0.02  # an LED's emission coefficient; its current at full brightness (A)


def _led_is(forward: float) -> float:
    """The saturation current of an LED with ``forward`` volts at ``LED_RATED``."""
    return LED_RATED / math.exp(forward / (LED_N * VT))


def _leds(label: str, V, anodes: dict[str, float], common: str) -> Model:
    """LEDs from each of ``anodes`` (terminal → forward voltage) to one ``common`` cathode: an RGB
    LED, a seven-segment display. Each has its own ``U_<terminal>`` and ``I_<terminal>``."""
    name = DeviceModel(sp.Symbol(label))
    inflow: dict[str, sp.Expr] = {}
    model = Model(inflow, [], {})
    nvt = LED_N * VT
    for pin, forward in anodes.items():
        U, I = sp.Symbol(f"U_{label}_{pin}"), sp.Symbol(f"I_{label}_{pin}")
        i_s = _led_is(forward)
        model.laws += [Law(U - (V[pin] - V[common]), name, "kvl"), Law(I - (i_s * (limexp(U / nvt) - 1) + GMIN * U), name)]
        model.variables |= {f"U_{pin}": U, f"I_{pin}": I}
        model.junctions.append((U, nvt, i_s))
        inflow[pin] = I
    inflow[common] = -sp.Add(*inflow.values())
    return model


class RGBLED(NoValue):
    """Three LEDs in one — red, green, blue — with a common cathode: pins ``r``, ``g``, ``b``, ``k``.
    Green and blue are InGaN (about 3 V), red about 2 V; each lights fully at 20 mA."""

    prefix = "LED"
    left, right = ("r", "g", "b"), ("k",)
    FORWARD = {"r": 2.0, "g": 3.0, "b": 3.1}

    def build(self, label, V, param, ctx):
        _paper_only(label, ctx)
        return _leds(label, V, self.FORWARD, "k")


SEGMENTS = ("a", "b", "c", "d", "e", "f", "g", "dp")


class SevenSegment(NoValue):
    """A seven-segment digit with a common cathode (a 5161AS): segments ``a``–``g`` and the dot
    ``dp``, each a red LED to ``com``. ``a`` is on top, then clockwise, ``g`` in the middle."""

    prefix = "DS"
    left, right = SEGMENTS, ("com",)

    def build(self, label, V, param, ctx):
        _paper_only(label, ctx)
        return _leds(label, V, dict.fromkeys(SEGMENTS, LED_COLORS["red"]), "com")


class LED(Diode):
    """A diode that lights: ``color`` sets its forward voltage (red ≈ 2 V, blue ≈ 3.1 V at 20 mA)."""

    prefix = "LED"
    N = LED_N
    RATED = LED_RATED

    def __init__(self, color: str = "red", label: str | None = None):
        super().__init__(label=label)
        self.color = color if color in LED_COLORS else "red"
        self.IS = _led_is(LED_COLORS[self.color])

    def options(self):
        return [] if self.color == "red" else [repr(self.color)]

    @classmethod
    def from_schematic(cls, value, text, label):
        return cls(text or "red", label=label)

    def __repr__(self):
        return f"LED({self.color!r}{f', label={self.label!r}' if self.label else ''})"


class Zener(TwoTerminal):
    """A Zener diode: ``a`` anode, ``b`` cathode, ``value`` its breakdown voltage ``U_Z``.

    Forward, a diode; reverse, it breaks down: ``I_ZT`` flows at ``U = −U_Z`` and every ``V_T``
    further multiplies it by e (so it holds ``U_Z`` within a few tenths of a volt from 1 to 50 mA).
    The breakdown is a junction of its own, ``U_<label>_br = −U − U_Z``, for Newton's step limiting.
    """

    prefix, unit = "DZ", "V"
    IS, IZT = 1e-14, 5e-3  # A: saturation current, the current at which U_Z is given (datasheets: 5 mA)

    def build(self, label, V, param, ctx):
        _paper_only(label, ctx)
        model = super().build(label, V, param, ctx)
        U, I = model.variables["U"], model.variables["I"]
        br = sp.Symbol(f"U_{label}_br")
        name = DeviceModel(sp.Symbol(label))
        model.laws += [
            Law(br + U + param, name, "kvl"),
            Law(I - (self.IS * (limexp(U / VT) - 1) - self.IZT * limexp(br / VT) + GMIN * U), name),
        ]
        model.variables["U_br"] = br
        model.junctions += [(U, VT, self.IS), (br, VT, self.IZT)]
        return model

    def law(self, U, I, x, ctx):
        return []


# ------------------------------------------------------------------ sensors


class Sensor(TwoTerminal):
    """A resistor whose resistance depends on what it senses: ``value`` at ``reading`` = ``NOMINAL``,
    times ``factor(reading)``. At a given reading it is a resistor, on paper too; while simulating
    the reading is set from outside: input ``<label>_<INPUT>``."""

    unit = "Ω"
    INPUT, NOMINAL, DEFAULT = "", 0.0, 0.0

    def __init__(self, value=None, reading: float | None = None, label: str | None = None):
        super().__init__(value, label)
        self.reading = float(self.DEFAULT if reading is None else reading)

    def factor(self, reading):
        raise NotImplementedError

    def build(self, label, V, param, ctx):
        model = super().build(label, V, param, ctx)
        U, I = model.variables["U"], model.variables["I"]
        if ctx.transient:
            reading = sp.Symbol(f"{label}_{self.INPUT}")
            model.inputs[reading] = self.reading
            factor = self.factor(reading)
        else:
            # exact, as every value on paper is (the solver's arithmetic is exact); 4 digits are plenty
            factor = parse(f"{float(self.factor(sp.Float(self.reading))):.4g}")
        model.laws.append(Law(U - param * factor * I, OhmsLaw(sp.Symbol(label))))
        return model

    def law(self, U, I, x, ctx):
        return []

    def options(self):
        return [] if self.reading == self.DEFAULT else [f"{self.INPUT}={self.reading:g}"]

    @classmethod
    def from_schematic(cls, value, text, label):
        """``text``: the reading (``"300"`` lux, ``"-5"`` °C)."""
        try:
            reading = float(text.replace(",", ".")) if text else None
        except ValueError:
            raise BadValue(text) from None
        return cls(parse(value), reading, label=label)


class Photoresistor(Sensor):
    """A light-dependent resistor: ``value`` is its resistance at 10 lux, ``R = value·(E/10 lx)^−γ``
    (γ = 0.7, a GL5528's); ``lux`` the light on it (100: a room)."""

    prefix = "LDR"
    INPUT, NOMINAL, DEFAULT = "lux", 10.0, 100.0
    GAMMA = 0.7

    def __init__(self, value=None, lux: float | None = None, label: str | None = None):
        super().__init__(value, None if lux is None else max(0.1, float(lux)), label)

    def factor(self, lux):
        return (lux / self.NOMINAL) ** -self.GAMMA


class Thermistor(Sensor):
    """An NTC thermistor: ``value`` is its resistance at 25 °C, ``R = value·e^{B·(1/T − 1/T₂₅)}``
    (B = 3950 K); ``temperature`` in °C."""

    prefix = "RT"
    INPUT, NOMINAL, DEFAULT = "temperature", 25.0, 25.0
    B, KELVIN = 3950.0, 273.15

    def __init__(self, value=None, temperature: float | None = None, label: str | None = None):
        super().__init__(value, temperature, label)

    def factor(self, t):
        return sp.exp(self.B * (1 / (t + self.KELVIN) - 1 / (self.NOMINAL + self.KELVIN)))


# ------------------------------------------------------------------ what makes a sound or moves


class Buzzer(NoValue, TwoTerminal):
    """An active buzzer (its own oscillator inside): ``+`` is ``a``. It sounds, at ``TONE``, above
    ``ON``; electrically a resistor (a 5 V one draws about 30 mA)."""

    prefix = "BZ"
    R, ON, TONE = 160, 2.5, 2300.0  # Ω (whole: exact on paper), V, Hz

    def law(self, U, I, x, ctx):
        return [(U - self.R * I, OhmsLaw)]


class PassiveBuzzer(Buzzer):
    """A passive (magnetic) buzzer: it sounds at the frequency it is driven with (``tone()``);
    electrically its coil, 16 Ω."""

    R = 16


class Servo(NoValue):
    """A hobby servo: signal ``sig``, supply ``vcc``, ground ``gnd`` (orange, red, brown). Its
    angle follows the signal's pulses — 544 µs: 0°, 2400 µs: 180°, as Arduino's Servo library
    sends them — which the page reads off ``U_sig``. Electrically: the signal input a high
    resistance, the motor at rest a resistor across the supply."""

    prefix = "M"
    left, right = ("sig",), ("vcc", "gnd")
    R_IN, R_LOAD = 100_000, 500  # Ω (whole: exact on paper)

    def build(self, label, V, param, ctx):
        Us, U, I = sp.Symbol(f"U_{label}_sig"), sp.Symbol(f"U_{label}"), sp.Symbol(f"I_{label}")
        name = DeviceModel(sp.Symbol(label))
        laws = [
            Law(Us - (V["sig"] - V["gnd"]), name, "kvl"),
            Law(U - (V["vcc"] - V["gnd"]), name, "kvl"),
            Law(U - self.R_LOAD * I, name),
        ]
        inflow = {"sig": Us / self.R_IN, "vcc": I, "gnd": -(I + Us / self.R_IN)}
        return Model(inflow, laws, {"U_sig": Us, "U": U, "I": I})


class Ultrasonic(NoValue):
    """An HC-SR04 distance sensor: ``vcc``, ``trig``, ``echo``, ``gnd`` (its pins' order). A pulse of
    10 µs on ``trig`` sends a ping; ``echo`` then goes high for as long as sound takes there and back,
    58 µs a centimetre. The page does the timing (``distance`` in cm is set while it runs) through
    the input ``<label>_echo`` (0 or 1): ``echo`` is a source of ``vcc`` or 0 V behind ``R_OUT``."""

    prefix = "US"
    left, right = ("vcc", "trig", "echo", "gnd"), ()
    # (whole numbers: on paper the solver's arithmetic is exact)
    R_SUPPLY, R_IN, R_OUT = 333, 100_000, 100  # Ω: 15 mA from 5 V; the trigger's input; the echo's output
    DISTANCE = 100.0  # cm

    def __init__(self, distance: float = DISTANCE, label: str | None = None):
        super().__init__(label=label)
        self.distance = float(distance)

    def build(self, label, V, param, ctx):
        U, I, Ut = sp.Symbol(f"U_{label}"), sp.Symbol(f"I_{label}"), sp.Symbol(f"U_{label}_trig")
        name = DeviceModel(sp.Symbol(label))
        high: sp.Expr = sp.Integer(0)
        model = Model({}, [], {"U": U, "I": I, "U_trig": Ut})
        if ctx.transient:
            high = sp.Symbol(f"{label}_echo")
            model.inputs[high] = 0.0
        echo = (V["echo"] - V["gnd"] - high * U) / self.R_OUT
        model.laws += [
            Law(U - (V["vcc"] - V["gnd"]), name, "kvl"),
            Law(Ut - (V["trig"] - V["gnd"]), name, "kvl"),
            Law(U - self.R_SUPPLY * I, name),
        ]
        model.inflow |= {"vcc": I, "trig": Ut / self.R_IN, "echo": echo, "gnd": -(I + Ut / self.R_IN + echo)}
        return model

    def options(self):
        return [] if self.distance == self.DISTANCE else [f"distance={self.distance:g}"]

    @classmethod
    def from_schematic(cls, value, text, label):
        try:
            return cls(float(text.replace(",", ".")) if text else cls.DISTANCE, label=label)
        except ValueError:
            raise BadValue(text) from None

    def __repr__(self):
        args = self.options() + ([f"label={self.label!r}"] if self.label else [])
        return f"Ultrasonic({', '.join(args)})"


LCD_INPUTS = ("rs", "rw", "e", "d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7")


class LCD1602(NoValue):
    """A 16×2 character LCD (an HD44780 controller), its 16 pins in order: ``vss``, ``vdd``, ``v0``
    (contrast: the lower, the darker), ``rs``, ``rw``, ``e``, ``d0``–``d7``, and the backlight's
    ``a``, ``k``. The page runs the controller (it latches on ``e`` falling, 8- or 4-bit, as
    Arduino's LiquidCrystal drives it) from ``U_<pin>`` (each input against ``vss``); electrically
    the inputs are high resistances, the logic a load across the supply, the backlight an LED."""

    prefix = "LCD"
    left, right = ("vss", "vdd", "v0", *LCD_INPUTS, "a", "k"), ()
    R_LOGIC, R_IN = 5000.0, 1e6  # Ω: 1 mA from 5 V; an input
    BACKLIGHT = 3.0  # V at 20 mA

    def build(self, label, V, param, ctx):
        _paper_only(label, ctx)
        name = DeviceModel(sp.Symbol(label))
        U, I = sp.Symbol(f"U_{label}"), sp.Symbol(f"I_{label}")
        model = _leds(label, V, {"a": self.BACKLIGHT}, "k")
        model.laws += [Law(U - (V["vdd"] - V["vss"]), name, "kvl"), Law(U - self.R_LOGIC * I, name)]
        model.variables |= {"U": U, "I": I}
        taken = I
        for pin in ("v0", *LCD_INPUTS):
            u = sp.Symbol(f"U_{label}_{pin}")
            model.laws.append(Law(u - (V[pin] - V["vss"]), name, "kvl"))
            model.variables[f"U_{pin}"] = u
            model.inflow[pin] = u / self.R_IN
            taken += u / self.R_IN
        model.inflow |= {"vdd": I, "vss": -taken}
        return model


class I2CModule(NoValue):
    """A module on I²C: ``gnd``, ``vcc``, ``sda``, ``scl`` (in the order its pins are in), at
    ``address``. Electrically its load across the supply and the pull-ups it has on SDA and SCL;
    what it does on the bus the page emulates, talking to the Arduino whose A4 (SDA) and A5 (SCL)
    it is wired to."""

    left, right = ("gnd", "vcc", "sda", "scl"), ()
    R_LOAD, PULLUP = 1000, 4700  # Ω (whole: exact on paper)
    ADDRESSES: tuple[int, ...] = (0,)  # the one it comes set to first

    def __init__(self, address: int | None = None, label: str | None = None):
        super().__init__(label=label)
        self.address = int(address) if address is not None else self.ADDRESSES[0]

    def build(self, label, V, param, ctx):
        U, I = sp.Symbol(f"U_{label}"), sp.Symbol(f"I_{label}")
        name = DeviceModel(sp.Symbol(label))
        pull = {line: (V[line] - V["vcc"]) / self.PULLUP for line in ("sda", "scl")}
        laws = [Law(U - (V["vcc"] - V["gnd"]), name, "kvl"), Law(U - self.R_LOAD * I, name)]
        inflow = pull | {"vcc": I - pull["sda"] - pull["scl"], "gnd": -I}
        return Model(inflow, laws, {"U": U, "I": I})

    def options(self):
        return [] if self.address == self.ADDRESSES[0] else [f"address=0x{self.address:02X}"]

    @classmethod
    def from_schematic(cls, value, text, label):
        try:
            return cls(int(text.split()[0], 0) if text and text.strip() else None, label=label)  # "0x27 70%": the address first
        except ValueError:
            raise BadValue(text) from None

    def __repr__(self):
        args = self.options() + ([f"label={self.label!r}"] if self.label else [])
        return f"{type(self).__name__}({', '.join(args)})"


class LCD1602I2C(I2CModule):
    """A 16×2 LCD with an I²C backpack (a PCF8574: LiquidCrystal_I2C), at 0x27 or 0x3F; the backlight
    included in its load."""

    prefix = "LCD"
    R_LOAD = 200  # 25 mA
    ADDRESSES = (0x27, 0x3F)


class SSD1306(I2CModule):
    """A 0.96" 128×64 OLED (an SSD1306: Adafruit_SSD1306), at 0x3C or 0x3D; its pins GND, VCC, SCL, SDA."""

    prefix = "OLED"
    left = ("gnd", "vcc", "scl", "sda")
    R_LOAD = 250  # 20 mA
    ADDRESSES = (0x3C, 0x3D)


class DS1307(I2CModule):
    """A real-time clock (a DS1307: RTClib), at 0x68; it starts at the page's time."""

    prefix = "RTC"
    R_LOAD = 3300  # 1.5 mA
    ADDRESSES = (0x68,)


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


class NMOS(NoValue):
    """An enhancement MOSFET (Shichman–Hodges, SPICE level 1): gate ``g``, drain ``d``, source ``s``.

    Off below ``VTH``; above it, with ``U_ov = U_GS − VTH``, the channel carries
    ``K·(U_ov·U_DS − U_DS²/2)`` while ``U_DS < U_ov`` (a resistor, ``1/(K·U_ov)`` near 0 V) and
    ``K/2·U_ov²`` beyond (a current source), times ``1 + λ·U_DS``. With ``U_DS < 0`` drain and source
    swap roles. The body diode (source → drain) and the gate's capacitances are there too: a
    power MOSFET switching a motor from an Arduino's pin. The values are a logic-level one's.
    """

    prefix = "Q"
    left, right = ("g",), ("d", "s")
    POLARITY = 1
    VTH, K, LAMBDA = 2.0, 0.5, 0.01  # V, A/V², 1/V
    IS = 1e-14  # A: the body diode
    CGS, CGD = 1e-9, 2e-10  # F

    def channel(self, ugs, uds):
        """Drain → source through the channel, for ``uds ≥ 0``."""
        ov = ugs - self.VTH
        return sp.Piecewise(
            (0, ov <= 0),
            (self.K * (ov * uds - uds**2 / 2) * (1 + self.LAMBDA * uds), uds < ov),
            (self.K / 2 * ov**2 * (1 + self.LAMBDA * uds), True),
        )

    def build(self, label, V, param, ctx):
        _paper_only(label, ctx)
        s = self.POLARITY
        Ugs, Uds, body = sp.Symbol(f"U_{label}_GS"), sp.Symbol(f"U_{label}_DS"), sp.Symbol(f"U_{label}_body")
        Id, Ig = sp.Symbol(f"I_{label}_D"), sp.Symbol(f"I_{label}_G")
        Ugs0, Ugd0 = sp.Symbol(f"U_{label}_GS_prev"), sp.Symbol(f"U_{label}_GD_prev")
        Ugd = Ugs - Uds
        channel = sp.Piecewise((self.channel(Ugs, Uds), Uds >= 0), (-self.channel(Ugd, -Uds), True))
        diode = self.IS * (limexp(body / VT) - 1) + GMIN * body
        cgs, cgd = self.CGS * (Ugs - Ugs0) / ctx.dt, self.CGD * (Ugd - Ugd0) / ctx.dt
        name = DeviceModel(sp.Symbol(label))
        laws = [
            Law(Ugs - s * (V["g"] - V["s"]), name, "kvl"),
            Law(Uds - s * (V["d"] - V["s"]), name, "kvl"),
            Law(body + Uds, name, "kvl"),
            Law(Id - s * (channel - diode - cgd), name),
            Law(Ig - s * (cgs + cgd), name),
        ]
        model = Model({"d": Id, "g": Ig, "s": -(Id + Ig)}, laws,
                      {"U_GS": Ugs, "U_DS": Uds, "U_body": body, "I_D": Id, "I_G": Ig})
        model.junctions.append((body, VT, self.IS))
        model.states |= {Ugs0: (Ugs, 0.0, 0.5), Ugd0: (Ugd, 0.0, 0.5)}
        return model


class PMOS(NMOS):
    """``NMOS`` with every voltage and current the other way: on with the gate ``VTH`` below the source."""

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
