"""SPICE netlists, both ways: ``to_spice(problem)`` for ngspice or LTspice, ``from_spice(text)`` for a netlist
from them (LTspice: View → SPICE Netlist) as a problem. Both go through the problem as data
(``problem.netlist``).

The elements SPICE and electro both have: R, C, L (coupled with K), V and I sources (DC, SIN, PULSE), diodes
and bipolar transistors with their ``.model``s, controlled sources (E, G, F, H), meters, and the ideal op-amp
(as a VCVS of gain 10⁶). The rest raises ``NoSpice``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from typing import cast

import sympy as sp

from electro.values import parse

from ..circuit.elements import BY_NAME
from ..circuit.elements.parts import CATALOGUE
from .netlist import GROUND_NAMES, from_netlist, to_netlist
from .problem import Problem

OPAMP_GAIN = 1e6

SUFFIXES = {"f": "1e-15", "p": "1e-12", "n": "1e-9", "u": "1e-6", "µ": "1e-6", "m": "1e-3", "k": "1e3", "meg": "1e6",
            "g": "1e9", "t": "1e12"}  # fmt: skip

PASSIVE = {"resistor": "R", "capacitor": "C", "inductor": "L"}

NUMBER = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)(meg|[fpnuµmkgt])?[a-z]*$", re.I)


class NoSpice(ValueError):
    """``element`` has no SPICE counterpart here (or no number for its value)."""

    def __init__(self, element: str) -> None:
        super().__init__(element)
        self.element = element


class BadValue(ValueError):
    def __init__(self, value: str) -> None:
        super().__init__(value)
        self.value = value


def to_spice(problem: Problem, title: str = "electro") -> str:
    """The circuit as a SPICE netlist (no analysis lines: add ``.op``, ``.ac``, ``.tran``)."""
    lines, models = [f"* {title}"], {}
    for item in to_netlist(problem)["elements"]:
        lines += _written(item, models)
    return "\n".join([*lines, *models.values(), ""])


def from_spice(text: str) -> Problem:
    """A SPICE netlist (R, C, L, K, V, I, D, Q, E, G; ``.model`` for D and Q) as a problem, its points by
    their node names (``0`` is ground), each element by its SPICE name. A part the catalogue knows is that
    part; another model gives its parameters. Analysis lines (``.op``, ``.tran``…) and ``.control`` blocks
    are skipped."""
    lines = _logical_lines(text)
    models = dict(_model(line) for line in lines if line.split()[0].lower() == ".model")
    items: list[dict] = []
    couplings = []
    for words in _element_lines(lines):
        letter = words[0][0].upper()
        if letter == "K":
            couplings.append(words)
        elif letter in READERS:
            items.append(READERS[letter](words, models))
        else:
            raise NoSpice(words[0])
    for words in couplings:
        items = _coupled(items, words)
    return from_netlist({"elements": items}).problem


def number(text: str) -> sp.Rational:
    """SPICE's numbers, exact: ``4.7k``, ``10u``, ``1meg``, ``2.2uF`` (a unit after the suffix is ignored)."""
    m = NUMBER.match(text.strip())
    if not m:
        raise BadValue(text)
    return sp.Rational(m.group(1)) * sp.Rational(SUFFIXES.get((m.group(2) or "").lower(), "1"))


def _text(x) -> str:
    return f"{float(x):.12g}"


def _ref(letter: str, id: str) -> str:
    """``R_1`` → ``R1``; another letter in front where the name does not start with it: ``E_1`` → ``VE1``."""
    plain = id.replace("_", "")
    return plain if plain[:1].upper() == letter else letter + plain


def _numbers(item: Mapping) -> dict[str, sp.Expr]:
    """The element's value (``""``) and parameters as numbers, its part's where it has one."""
    part = CATALOGUE.get(item["kind"], {}).get(item.get("part") or "", {})
    texts = {**part, **(item.get("params") or {}), "": item.get("value")}
    out = {}
    for w, x in texts.items():
        if x is None:
            continue
        value = parse(x)
        if not isinstance(value, sp.Basic) or value.free_symbols:
            raise NoSpice(item["id"])
        out[w] = value
    return out


def _written(item: Mapping, models: dict[str, str]) -> list[str]:
    id, kind = item["id"], item["kind"]
    n = ["0" if x in GROUND_NAMES else x for x in item["nodes"]]
    p = _numbers(item)

    def value() -> str:
        if "" not in p:
            raise NoSpice(id)
        return _text(p[""])

    def model(letter: str, kind_name: str, keys: Mapping[str, str]) -> str:
        name = f"{_ref(letter, id)}_{item.get('part') or 'model'}"
        numbers = {**{k: cast(sp.Expr, sp.sympify(v)) for k, v in BY_NAME[kind].defaults}, **p}
        given = " ".join(f"{s}={float(numbers[k]):.6g}" for k, s in keys.items())
        models[name] = f".model {name} {kind_name}({given})"
        return name

    match kind:
        case "resistor" | "capacitor" | "inductor":
            return [f"{_ref(PASSIVE[kind], id)} {n[0]} {n[1]} {value()}"]
        case "voltage_source":
            v = complex(p.get("", 0))
            phase = _text(math.degrees(math.atan2(v.imag, v.real)))
            ac = f" AC {_text(abs(v))} {phase}" if v.imag else f" AC {_text(v.real)}"
            return [f"{_ref('V', id)} {n[1]} {n[0]} DC {_text(v.real)}{ac}"]
        case "sine_source":
            amp, f, phase = value(), _text(p.get("f", 50)), _text(p.get("phase", 0))
            return [f"{_ref('V', id)} {n[1]} {n[0]} SIN(0 {amp} {f} 0 0 {phase}) AC {amp} {phase}"]
        case "square_source":
            f, duty = float(p.get("f", 1000)), float(p.get("duty", 0.5))
            return [f"{_ref('V', id)} {n[1]} {n[0]} PULSE(0 {value()} 0 1n 1n {_text(duty / f)} {_text(1 / f)})"]
        case "current_source":
            return [f"{_ref('I', id)} {n[0]} {n[1]} DC {value()} AC {value()}"]
        case "ammeter":
            return [f"{_ref('V', id)} {n[0]} {n[1]} 0"]
        case "voltmeter":
            return [f"{_ref('R', id)} {n[0]} {n[1]} 1e12"]
        case "diode":
            return [f"{_ref('D', id)} {n[0]} {n[1]} {model('D', 'D', {'I_S': 'IS', 'n': 'N'})}"]
        case "npn" | "pnp":
            keys = {k: k for k in ("IS", "BF", "BR", "CJE", "CJC")}
            return [f"{_ref('Q', id)} {n[1]} {n[0]} {n[2]} {model('Q', kind.upper(), keys)}"]
        case "opamp":
            return [f"{_ref('E', id)} {n[2]} 0 {n[0]} {n[1]} {_text(OPAMP_GAIN)}"]
        case "vcvs":
            return [f"{_ref('E', id)} {n[3]} {n[2]} {n[0]} {n[1]} {value()}"]
        case "vccs":
            return [f"{_ref('G', id)} {n[2]} {n[3]} {n[0]} {n[1]} {value()}"]
        case "ccvs" | "cccs":
            sense = f"Vs{id.replace('_', '')}"
            letter, out = ("H", (n[3], n[2])) if kind == "ccvs" else ("F", (n[2], n[3]))
            return [f"{sense} {n[0]} {n[1]} 0", f"{_ref(letter, id)} {out[0]} {out[1]} {sense} {value()}"]
        case "coupled":
            k = float(p[""]) / math.sqrt(float(p["L1"]) * float(p["L2"]))
            pair = _ref("K", id)
            la, lb = f"L{pair[1:]}a", f"L{pair[1:]}b"
            return [
                f"{la} {n[0]} {n[1]} {_text(p['L1'])}",
                f"{lb} {n[3]} {n[2]} {_text(p['L2'])}",
                f"{pair} {la} {lb} {_text(k)}",
            ]
    raise NoSpice(id)


def _logical_lines(text: str) -> list[str]:
    """Without the title, comments and empty lines; a ``+`` line joined to the one before."""
    lines: list[str] = []
    for raw in text.splitlines()[1:]:
        line = raw.split(";")[0].rstrip()
        if not line.strip() or line.lstrip().startswith("*"):
            continue
        if line.startswith("+") and lines:
            lines[-1] += " " + line[1:]
        else:
            lines.append(line.strip())
    return lines


def _element_lines(lines: list[str]) -> list[list[str]]:
    """The element lines' words: no dot lines, nothing inside ``.control`` … ``.endc``."""
    out, skip = [], False
    for line in lines:
        words = line.split()
        head = words[0].lower()
        skip = (skip or head == ".control") and head != ".endc"
        if not skip and not head.startswith("."):
            out.append(words)
    return out


def _params(text: str) -> dict[str, sp.Rational]:
    """``IS=2.52n N=1.752 mfg=OnSemi`` → the numbers (the words LTspice adds are left out)."""
    pairs = re.findall(r"(\w+)\s*=\s*([^\s,()]+)", text)
    return {k.upper(): number(v) for k, v in pairs if NUMBER.match(v)}


def _model(line: str) -> tuple[str, tuple[str, dict[str, sp.Rational]]]:
    """``.model 1N4148 D(IS=2.52n N=1.752)`` → ``("1n4148", ("D", {"IS": …, "N": …}))``."""
    words = line.split()
    return words[1].lower(), (words[2].split("(")[0].upper(), _params(line))


def _node(name: str) -> str:
    return "GND" if name.upper() in ("0", "GND") else name


def _known(kind: str, model: str) -> str | None:
    """A catalogue part by its model's name: ``1N4148``, or ``D1_1N4148`` as ``to_spice`` names it."""
    model = model.upper()
    return next((p for p in CATALOGUE[kind] if model == p.upper() or model.endswith("_" + p.upper())), None)


def _passive(words: list[str], models) -> dict:
    kind = next(k for k, letter in PASSIVE.items() if letter == words[0][0].upper())
    return {"id": words[0], "kind": kind, "nodes": [_node(words[1]), _node(words[2])], "value": str(number(words[3]))}


def _source(words: list[str], models) -> dict:
    name, plus, minus, rest = words[0], _node(words[1]), _node(words[2]), " ".join(words[3:])
    if name[0].upper() == "I":
        return {"id": name, "kind": "current_source", "nodes": [plus, minus], "value": str(_dc(words, rest))}
    sine = re.search(r"SINE?\s*\(\s*([^)]*)\)", rest, re.I)
    pulse = re.search(r"PULSE\s*\(\s*([^)]*)\)", rest, re.I)
    nodes = [minus, plus]
    if sine:
        a = [number(w) for w in sine.group(1).split()] + [sp.S(0)] * 6
        params = {"f": str(a[2] or 50), "phase": str(a[5])}
        return {"id": name, "kind": "sine_source", "nodes": nodes, "value": str(a[1]), "params": params}
    if pulse:
        a = [number(w) for w in pulse.group(1).split()] + [sp.S(0)] * 7
        period = a[6] or sp.Rational(1, 1000)
        params = {"f": str(1 / period), "duty": str((a[5] or period / 2) / period)}
        return {"id": name, "kind": "square_source", "nodes": nodes, "value": str(a[1]), "params": params}
    if words[3:4] == ["0"] and len(words) == 4:
        return {"id": name, "kind": "ammeter", "nodes": [plus, minus]}
    return {"id": name, "kind": "voltage_source", "nodes": nodes, "value": str(_dc(words, rest))}


def _dc(words: list[str], rest: str) -> sp.Expr:
    dc = re.search(r"(?:^|\s)DC\s+(\S+)", rest, re.I)
    bare = words[3] if len(words) > 3 and NUMBER.match(words[3]) else None
    return number(dc.group(1)) if dc else number(bare) if bare else sp.S(0)


def _with_model(item: dict, kind: str, model: str, models, keys: Mapping[str, str]) -> dict:
    """A catalogue part when the model's name is one, else the model's parameters."""
    known = _known(kind, model)
    if known:
        return {**item, "part": known}
    _, params = models.get(model.lower(), ("", {}))
    return {**item, "params": {k: str(params[s]) for k, s in keys.items() if s in params}}


def _diode(words: list[str], models) -> dict:
    item = {"id": words[0], "kind": "diode", "nodes": [_node(words[1]), _node(words[2])]}
    return _with_model(item, "diode", words[3], models, {"I_S": "IS", "n": "N"})


def _transistor(words: list[str], models) -> dict:
    polarity, _ = models.get(words[4].lower(), ("NPN", {}))
    kind = "pnp" if polarity == "PNP" else "npn"
    item = {"id": words[0], "kind": kind, "nodes": [_node(words[2]), _node(words[1]), _node(words[3])]}
    return _with_model(item, kind, words[4], models, {k: k for k in ("IS", "BF", "BR", "CJE", "CJC")})


def _controlled(words: list[str], models) -> dict:
    p, n, cp, cn = map(_node, words[1:5])
    letter = words[0][0].upper()
    if letter in "FH":
        raise NoSpice(f"{words[0]} (F and H sense a source's current: use E or G)")
    kind, out = ("vcvs", [n, p]) if letter == "E" else ("vccs", [p, n])
    return {"id": words[0], "kind": kind, "nodes": [cp, cn, *out], "value": str(number(words[5]))}


def _coupled(items: list[dict], words: list[str]) -> list[dict]:
    """Two inductors coupled by ``K``: one element of the pair, its mutual inductance the value."""
    names = (words[1].lower(), words[2].lower())
    a, b = (next(i for i in items if i["id"].lower() == x) for x in names)
    la, lb = sp.sympify(a["value"]), sp.sympify(b["value"])
    m = number(words[3]) * sp.sqrt(la * lb)
    pair = {"id": words[0], "kind": "coupled", "nodes": [*a["nodes"], b["nodes"][1], b["nodes"][0]],
            "value": _text(m), "params": {"L1": str(la), "L2": str(lb)}}  # fmt: skip
    return [pair if i is a else i for i in items if i is not b]


READERS: dict[str, Callable[[list[str], Mapping], dict]] = {
    "R": _passive,
    "C": _passive,
    "L": _passive,
    "V": _source,
    "I": _source,
    "D": _diode,
    "Q": _transistor,
    "E": _controlled,
    "G": _controlled,
    "F": _controlled,
    "H": _controlled,
}
