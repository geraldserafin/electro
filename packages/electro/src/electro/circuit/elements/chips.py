"""Chips: the 555 timer, a real op-amp."""

from __future__ import annotations

import sympy as sp

from ..kind import Kind, Params, Terminals
from ..time import D, Pre, when

TIMER_R_OUT, TIMER_R_DIS, TIMER_DROP = 10, 10, sp.Rational(17, 10)
OPAMP_R_OUT = 75

OPAMP_PARTS = {
    "LM358": {"A": 1e5, "GBW": 1e6, "SR": 0.3e6, "LOW": -15.0, "HIGH": 13.5},
    "TL072": {"A": 2e5, "GBW": 3e6, "SR": 13e6, "LOW": -13.5, "HIGH": 13.5},
    "MCP6002": {"A": 4e5, "GBW": 1e6, "SR": 0.6e6, "LOW": 0.0, "HIGH": 5.0},
}
"""Real op-amps: gain, gain-bandwidth (Hz), slew rate (V/s), the rails its output reaches on its usual
supply."""


def _timer(t: Terminals, _: Params) -> list[sp.Expr]:
    """The NE555: a 5k–10k divider sets ``ctrl`` to ⅔ of the supply; ``trig`` below half of ``ctrl``
    sets its flip-flop ``q`` (the output high, the discharge off), ``thr`` above ``ctrl`` resets it
    (the output low, ``dis`` to ``gnd``); ``reset`` low holds it reset. It decides from how its pins
    were just before; ``reset`` has a weak pull-up, so it may be left unconnected."""
    q = t.inner("q")
    trig, thr, ctrl, reset = (Pre(t.across(pin, "gnd")) for pin in ("trig", "thr", "ctrl", "reset"))
    supply = t.across("vcc", "gnd")
    top, bottom = t.across("vcc", "ctrl") / 5000, t.across("ctrl", "gnd") / 10000
    pull_up = t.across("vcc", "reset") / 100000
    out = (t.across("out", "gnd") - q * (supply - TIMER_DROP)) / TIMER_R_OUT
    dis = (1 - q) * t.across("dis", "gnd") / TIMER_R_DIS
    return [
        q - when(reset < sp.Rational(7, 10), 0, when(trig < ctrl / 2, 1, when(thr > ctrl, 0, Pre(q)))),
        t.I["trig"],
        t.I["thr"],
        t.I["out"] - out,
        t.I["reset"] + pull_up,
        t.I["ctrl"] - (bottom - top),
        t.I["dis"] - dis,
        t.I["gnd"] + bottom + (1 - q) * out + dis,
    ]


def _op_amp_model(t: Terminals, p: Params) -> list[sp.Expr]:
    """Gain ``A`` with one pole at ``GBW``; the output (``y``, behind ``OPAMP_R_OUT``) moving at most at
    ``SR`` and never past its rails ``LOW``, ``HIGH`` (against ``gnd``)."""
    y = t.inner("y")
    tau = p["A"] / (2 * sp.pi * p["GBW"])
    drive = (p["A"] * t.across("plus", "minus") - y) / tau
    slope = p["SR"] * sp.tanh(drive / p["SR"])
    below_top, above_bottom = (1 - sp.tanh(20 * (y - p["HIGH"]))) / 2, (1 + sp.tanh(20 * (y - p["LOW"]))) / 2
    rising = (1 + sp.tanh(slope / 1000)) / 2
    return [
        t.I["plus"],
        t.I["minus"],
        D(y) - slope * (rising * below_top + (1 - rising) * above_bottom),
        t.I["out"] - (t.across("out", "gnd") - y) / OPAMP_R_OUT,
    ]


Timer555 = Kind("timer555", "IC", ("gnd", "trig", "out", "reset", "ctrl", "thr", "dis", "vcc"), _timer, parameters=())
"""Its pins in DIP order."""

OpAmpModel = Kind(
    "opamp_model",
    "OA",
    ("plus", "minus", "out", "gnd"),
    _op_amp_model,
    parameters=("A", "GBW", "SR", "LOW", "HIGH"),
    defaults=tuple(OPAMP_PARTS["LM358"].items()),
)
"""A real op-amp (``OPAMP_PARTS``; an LM358 unless given)."""
