import sympy as sp

from ...circuit.element import Element
from ...circuit.time import Pre, when

R_OUT, R_DIS, DROP = 10, 10, sp.Rational(17, 10)


class Timer555(Element):
    """The NE555, its pins in DIP order: a 5k–10k divider sets ``ctrl`` to ⅔ of the supply; ``trig`` below
    half of ``ctrl`` sets its flip-flop ``q`` (the output high, the discharge off), ``thr`` above ``ctrl``
    resets it (the output low, ``dis`` to ``gnd``); ``reset`` low holds it reset. It decides from how its
    pins were just before; ``reset`` has a weak pull-up, so it may be left unconnected."""

    kind, prefix = "timer555", "IC"
    terminals = ("gnd", "trig", "out", "reset", "ctrl", "thr", "dis", "vcc")
    parameters = ()

    def laws(self, t, p):
        q = t.inner("q")
        trig, thr, ctrl, reset = (Pre(t.across(pin, "gnd")) for pin in ("trig", "thr", "ctrl", "reset"))
        supply = t.across("vcc", "gnd")
        top, bottom = t.across("vcc", "ctrl") / 5000, t.across("ctrl", "gnd") / 10000
        pull_up = t.across("vcc", "reset") / 100000
        out = (t.across("out", "gnd") - q * (supply - DROP)) / R_OUT
        dis = (1 - q) * t.across("dis", "gnd") / R_DIS
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
