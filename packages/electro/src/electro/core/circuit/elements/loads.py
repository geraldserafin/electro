"""What makes light, sound or motion: a bulb, buzzers, a DC motor, a servo, a relay."""

from __future__ import annotations

import sympy as sp

from ..kind import Kind, Params, Terminals
from ..time import D, Pre, when

MOTOR_R, MOTOR_K, MOTOR_J, MOTOR_B = 5, sp.Rational(1, 100), sp.Rational(1, 10**6), sp.Rational(16, 10**7)
SERVO_R_IN, SERVO_R_LOAD = 100_000, 500
RELAY_R, RELAY_L, RELAY_R_LOSS = 70, sp.Rational(2, 100), 10_000
RELAY_PULL, RELAY_DROP = sp.Rational(5, 100), sp.Rational(15, 1000)
CONTACT_ON, CONTACT_OFF = 1000, sp.Rational(1, 10**10)


def _resistance(r: sp.Expr | float):
    def laws(t: Terminals, _: Params) -> list[sp.Expr]:
        return [t.across("a", "b") - r * t.I["a"]]

    return laws


def _lamp(t: Terminals, p: Params) -> list[sp.Expr]:
    """Its filament, hot: a resistor."""
    return [t.across("a", "b") - p[""] * t.I["a"]]


def _motor(t: Terminals, _: Params) -> list[sp.Expr]:
    """Its winding and its back-EMF, K·ω; its rotor J·dω/dt = K·I − B·ω (``w``: ω, in rad/s)."""
    w, i = t.inner("w"), t.I["a"]
    return [t.across("a", "b") - MOTOR_R * i - MOTOR_K * w, MOTOR_J * D(w) - (MOTOR_K * i - MOTOR_B * w)]


def _servo(t: Terminals, _: Params) -> list[sp.Expr]:
    """Its signal input a high resistance, its motor at rest a resistor across the supply."""
    return [t.I["sig"] - t.across("sig", "gnd") / SERVO_R_IN, t.I["vcc"] - t.across("vcc", "gnd") / SERVO_R_LOAD]


def _relay(t: Terminals, _: Params) -> list[sp.Expr]:
    """Its coil (``I``: its current, ``on``: whether it holds the contact) pulls in above
    ``RELAY_PULL`` and lets go below ``RELAY_DROP``, as it was just before; switched off with nothing
    across it only its own losses hold its voltage. The contact: ``com`` to ``nc`` at rest, to ``no``
    pulled in."""
    i, on = t.inner("I"), t.inner("on")
    u = t.across("a", "b")
    was = sp.Abs(Pre(i))
    no = _contact(on) * t.across("com", "no")
    nc = _contact(1 - on) * t.across("com", "nc")
    return [
        u - RELAY_R * i - RELAY_L * D(i),
        t.I["a"] - (i + u / RELAY_R_LOSS),
        t.I["a"] + t.I["b"],
        on - when(was > RELAY_PULL, 1, when(was < RELAY_DROP, 0, Pre(on))),
        t.I["com"] - (no + nc),
        t.I["nc"] + nc,
    ]


def _contact(closed: sp.Expr) -> sp.Expr:
    return CONTACT_ON * closed + CONTACT_OFF * (1 - closed)


Lamp = Kind("lamp", "H", ("a", "b"), _lamp, positive=("",))
"""An incandescent bulb: its main parameter its resistance, hot."""

Buzzer = Kind("buzzer", "BZ", ("a", "b"), _resistance(160), parameters=())
"""An active buzzer (``a`` its +): it sounds above 2.5 V; electrically a resistor."""

PassiveBuzzer = Kind("passive_buzzer", "BZ", ("a", "b"), _resistance(16), parameters=())
"""A passive buzzer: it sounds at what drives it; electrically its coil."""

Motor = Kind("motor", "M", ("a", "b"), _motor, parameters=())
"""A small DC motor (a 130-size one, for 3–6 V)."""

Servo = Kind("servo", "M", ("sig", "vcc", "gnd"), _servo, parameters=())
"""A hobby servo: its angle follows the pulses on ``sig`` (the page reads them)."""

Relay = Kind("relay", "K", ("a", "b", "com", "nc", "no"), _relay, parameters=())
"""A relay with a 5 V coil (an SRD-05VDC's: 70 Ω, 20 mH) between ``a`` and ``b``."""
