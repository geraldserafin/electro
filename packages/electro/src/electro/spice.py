"""SPICE netlists, both ways: ``to_spice(c)`` for ngspice or LTspice, ``from_spice(text)`` for a
netlist from them (LTspice: View → SPICE Netlist) as a circuit.

The elements SPICE and electro both have: R, C, L (coupled with K), V and I sources (DC, SIN,
PULSE), diodes and bipolar transistors with their ``.model``s, controlled sources (E, G, F, H)
and op-amps (as a VCVS of gain 10⁶). The rest raises ``NoSpice``.
"""

from __future__ import annotations

import math
import re

import sympy as sp

from . import components as comp
from . import devices as dev
from .circuit import GROUND, Circuit, net
from .issues import BadValue, NoSpice
from .semantics import structure

OPAMP_GAIN = 1e6


def _num(x) -> str:
    return f"{float(x):.12g}"


def to_spice(c: Circuit, title: str = "electro") -> str:
    """The circuit as a SPICE netlist (no analysis lines: add ``.op``, ``.ac``, ``.tran``)."""
    lines, models = [f"* {title}"], {}
    for label, placed in structure(c).parts.items():
        x, n = placed.component, {t: ("0" if v == GROUND else v) for t, v in placed.nodes.items()}
        plain = label.replace("_", "")

        def ref(letter: str, plain=plain) -> str:  # R_1 → R1 (not RR1), E_1 → VE1
            return plain if plain[:1].upper() == letter else letter + plain

        if x.has_value and sp.sympify(x.value).free_symbols:  # unknown, or a symbol: SPICE takes numbers
            raise NoSpice(label)
        value = x.value if x.has_value else None
        if isinstance(x, dev.SquareSource):
            f = float(x.frequency)
            lines.append(
                f"{ref('V')} {n['b']} {n['a']} PULSE(0 {_num(value)} 0 1n 1n {_num(x.duty / f)} {_num(1 / f)})"
            )
        elif isinstance(x, dev.SineSource):
            amp, ph = _num(value), _num(x.phase)
            lines.append(f"{ref('V')} {n['b']} {n['a']} SIN(0 {amp} {_num(x.frequency)} 0 0 {ph}) AC {amp} {ph}")
        elif isinstance(x, comp.Resistor):
            lines.append(f"{ref('R')} {n['a']} {n['b']} {_num(value)}")
        elif isinstance(x, comp.Capacitor):
            lines.append(f"{ref('C')} {n['a']} {n['b']} {_num(value)}")
        elif isinstance(x, comp.Inductor):
            lines.append(f"{ref('L')} {n['a']} {n['b']} {_num(value)}")
        elif isinstance(x, comp.VoltageSource):
            v = complex(value)
            ac = (
                f" AC {_num(abs(v))} {_num(math.degrees(math.atan2(v.imag, v.real)))}"
                if v.imag
                else f" AC {_num(v.real)}"
            )
            lines.append(f"{ref('V')} {n['b']} {n['a']} DC {_num(v.real)}{ac}")
        elif isinstance(x, comp.CurrentSource):
            lines.append(f"{ref('I')} {n['a']} {n['b']} DC {_num(value)} AC {_num(value)}")
        elif isinstance(x, (comp.Ammeter,)):
            lines.append(f"{ref('V')} {n['a']} {n['b']} 0")
        elif isinstance(x, comp.Voltmeter):
            lines.append(f"{ref('R')} {n['a']} {n['b']} 1e12")
        elif isinstance(x, dev.LED) or type(x) is dev.Diode:
            model = f"{ref('D')}_{x.part or 'model'}"
            models[model] = f".model {model} D(IS={x.IS:.6g} N={x.N:.6g})"
            lines.append(f"{ref('D')} {n['a']} {n['b']} {model}")
        elif isinstance(x, dev.NPN):
            kind = "PNP" if x.POLARITY < 0 else "NPN"
            model = f"{ref('Q')}_{x.part or 'model'}"
            models[model] = (
                f".model {model} {kind}(IS={x.IS:.6g} BF={x.BF:.6g} BR={x.BR:.6g} CJE={x.CJE:.6g} CJC={x.CJC:.6g})"
            )
            lines.append(f"{ref('Q')} {n['c']} {n['b']} {n['e']} {model}")
        elif isinstance(x, comp.OpAmp):
            lines.append(f"{ref('E')} {n['out']} 0 {n['plus']} {n['minus']} {_num(OPAMP_GAIN)}")
        elif isinstance(x, comp.VCVS):
            lines.append(f"{ref('E')} {n['p']} {n['n']} {n['cp']} {n['cn']} {_num(value)}")
        elif isinstance(x, comp.VCCS):
            lines.append(f"{ref('G')} {n['n']} {n['p']} {n['cp']} {n['cn']} {_num(value)}")
        elif isinstance(x, (comp.CCVS, comp.CCCS)):
            lines.append(f"Vs{plain} {n['cp']} {n['cn']} 0")
            letter, (p, q) = ("H", ("p", "n")) if isinstance(x, comp.CCVS) else ("F", ("n", "p"))
            lines.append(f"{ref(letter)} {n[p]} {n[q]} Vs{plain} {_num(value)}")
        elif isinstance(x, comp.Coupled):
            k = float(value) / math.sqrt(float(x.L1) * float(x.L2))
            lines += [
                f"{ref('L')}a {n['p1']} {n['p2']} {_num(x.L1)}",
                f"{ref('L')}b {n['s1']} {n['s2']} {_num(x.L2)}",
                f"{ref('K')} {ref('L')}a {ref('L')}b {_num(k)}",
            ]
        else:
            raise NoSpice(label)
    return "\n".join([*lines, *models.values(), ""])


# ------------------------------------------------------------------ reading one

_SUFFIX = {
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "µ": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "meg": 1e6,
    "g": 1e9,
    "t": 1e12,
}
_NUMBER = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)(meg|[fpnuµmkgt])?[a-z]*$", re.I)


def _value(text: str) -> sp.Rational:
    """SPICE's numbers: ``4.7k``, ``10u``, ``1meg``, ``2.2uF`` (a unit after the suffix is ignored)."""
    m = _NUMBER.match(text.strip())
    if not m:
        raise BadValue(text)
    return sp.Rational(m.group(1)) * sp.Rational(
        repr(_SUFFIX.get((m.group(2) or "").lower(), 1))
    )  # exact: 100n is 1/10⁷


def _params(text: str) -> dict[str, float]:
    """``IS=2.52n N=1.752 mfg=OnSemi`` → the numbers (the words LTspice adds are left out)."""
    pairs = re.findall(r"(\w+)\s*=\s*([^\s,()]+)", text)
    return {k.upper(): float(_value(v)) for k, v in pairs if _NUMBER.match(v)}


def _part(cls, model: str) -> str | None:
    """A known part by its model's name: ``1N4148``, or ``D1_1N4148`` as ``to_spice`` names it."""
    model = model.upper()
    return next((p for p in cls.PARTS if model == p or model.endswith("_" + p)), None)


def _node(name: str) -> str:
    return GROUND if name in ("0", "gnd", "GND") else name


def from_spice(text: str) -> Circuit:
    """A SPICE netlist (R, C, L, K, V, I, D, Q, E, G, F, H; ``.model`` for D and Q) as a circuit,
    joined by its node names (``0`` is ground); each element keeps its SPICE name as its label.
    Analysis lines (``.op``, ``.tran``…) and ``.control`` blocks are skipped."""
    lines: list[str] = []
    for raw in text.splitlines()[1:]:  # the first line is the title
        line = raw.split(";")[0].rstrip()
        if not line.strip() or line.lstrip().startswith("*"):
            continue
        if line.startswith("+") and lines:
            lines[-1] += " " + line[1:]
        else:
            lines.append(line.strip())
    models, skip = {}, False
    for line in lines:
        words = line.split()
        if words[0].lower() == ".model":
            models[words[1].lower()] = (words[2].split("(")[0].upper(), _params(line))
    items, inductors, couplings = [], {}, []
    for line in lines:
        words = line.split()
        head = words[0].lower()
        if head == ".control":
            skip = True
        if skip or head.startswith("."):
            skip = skip and head != ".endc"
            continue
        name, kind = words[0], words[0][0].upper()
        if kind in "RCL":
            cls = {"R": comp.Resistor, "C": comp.Capacitor, "L": comp.Inductor}[kind]
            items.append((cls(_value(words[3]), label=name), _node(words[1]), _node(words[2])))
            if kind == "L":
                inductors[name.lower()] = len(items) - 1
        elif kind == "K":
            couplings.append((words[1].lower(), words[2].lower(), _value(words[3]), name))
        elif kind in "VI":
            plus, minus, rest = _node(words[1]), _node(words[2]), " ".join(words[3:])
            sine = re.search(r"SINE?\s*\(\s*([^)]*)\)", rest, re.I)
            pulse = re.search(r"PULSE\s*\(\s*([^)]*)\)", rest, re.I)
            if kind == "V" and sine:
                a = [_value(w) for w in sine.group(1).split()] + [0] * 6
                items.append((dev.SineSource(a[1], a[2] or 50, a[5], label=name), minus, plus))
            elif kind == "V" and pulse:
                a = [_value(w) for w in pulse.group(1).split()] + [0] * 7
                period = a[6] or 1e-3
                items.append(
                    (dev.SquareSource(a[1], 1 / period, (a[5] or period / 2) / period, label=name), minus, plus)
                )
            else:
                dc = re.search(r"(?:^|\s)DC\s+(\S+)", rest, re.I)
                bare = words[3] if len(words) > 3 and _NUMBER.match(words[3]) else None
                value = _value(dc.group(1)) if dc else _value(bare) if bare else 0.0
                if kind == "V":
                    items.append((comp.VoltageSource(value, label=name), minus, plus))
                else:
                    items.append((comp.CurrentSource(value, label=name), plus, minus))
        elif kind == "D":
            _, params = models.get(words[3].lower(), ("D", {}))
            d = dev.Diode(label=name, part=_part(dev.Diode, words[3]))
            d.IS, d.N = params.get("IS", d.IS), params.get("N", d.N)
            items.append((d, _node(words[1]), _node(words[2])))
        elif kind == "Q":
            polarity, params = models.get(words[4].lower(), ("NPN", {}))
            cls = dev.PNP if polarity == "PNP" else dev.NPN
            q = cls(label=name, part=_part(cls, words[4]))
            for key in ("IS", "BF", "BR", "CJE", "CJC"):
                setattr(q, key, params.get(key, getattr(q, key)))
            items.append((q, _node(words[2]), _node(words[1]), _node(words[3])))  # b, c, e
        elif kind == "E":
            p, n, cp, cn = map(_node, words[1:5])
            items.append((comp.VCVS(_value(words[5]), label=name), cp, cn, n, p))
        elif kind == "G":
            p, n, cp, cn = map(_node, words[1:5])
            items.append((comp.VCCS(_value(words[5]), label=name), cp, cn, p, n))
        elif kind in "FH":
            raise NoSpice(f"{name} (F and H sense a source's current: use E or G)")
        else:
            raise NoSpice(name)
    for a, b, k, name in couplings:  # two inductors coupled: one element of the pair
        (la, *na), (lb, *nb) = items[inductors[a]], items[inductors[b]]
        m = k * math.sqrt(float(la.value) * float(lb.value))
        items[inductors[a]] = (comp.Coupled(m, L1=float(la.value), L2=float(lb.value), label=name), *na, nb[1], nb[0])
        items[inductors[b]] = None
    return net(*(i for i in items if i is not None))
