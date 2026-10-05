"""What the world sets while a circuit runs, as one function of time: a switch's position, the light on a
sensor, a board's pin in one of its chip's modes (``"high"``, ``"pullup"``)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

from ..circuit.elements import BY_NAME, MODES
from ..circuit.tree import Element
from ..solver.symbols import Symbols
from .errors import NoSuchInput
from .program import Program
from .run import Schedule

Setter = Callable[[object], list[tuple[int, float]]]
Key = Element | tuple[Element, str] | str
"""An element (its one input), an element and its input's or its pin's name, or that as text:
``"S_1"``, ``"S_1_closed"``, ``"ARD_1.D13"``."""


def schedule(program: Program, s: Symbols, inputs: Mapping[Key, object] | None) -> Schedule | None:
    if not inputs:
        return None
    parts = [(_setter(program, _name(key, s)), value) for key, value in inputs.items()]
    return lambda now: [pair for setter, value in parts for pair in setter(value(now) if callable(value) else value)]


def _name(key: Key, s: Symbols) -> str:
    match key:
        case Element():
            return s.labels[s.index(key)]
        case (Element() as e, str(which)):
            return f"{s.labels[s.index(e)]}.{which}"
    return str(key)


def _setter(program: Program, name: str) -> Setter:
    label, _, pin = name.partition(".")
    if pin:
        pin_mode = _pin(program, label, pin)
        if pin_mode is not None:
            return pin_mode
    for candidate in _candidates(program, name):
        if candidate in program.inputs:
            index = program.inputs[candidate]
            return lambda value: [(index, float(cast(float, value)))]
    raise NoSuchInput(name, _available(program))


def _pin(program: Program, label: str, pin: str) -> Setter | None:
    modes = MODES.get(program.kinds.get(label, ""))
    g, e = f"{label}_{pin}_G", f"{label}_{pin}_E"
    if modes is None or g not in program.inputs:
        return None
    gi, ei = program.inputs[g], program.inputs[e]

    def set_mode(mode: object) -> list[tuple[int, float]]:
        conductance, volts = modes[mode] if isinstance(mode, str) else (modes["high"][0], float(cast(float, mode)))
        return [(gi, conductance), (ei, volts)]

    return set_mode


def _candidates(program: Program, name: str) -> list[str]:
    kind = BY_NAME.get(program.kinds.get(name, ""))
    return [name, *(f"{name}_{which}" for which in (kind.inputs if kind else ()))]


def _available(program: Program) -> list[str]:
    out = []
    for label, kind_name in program.kinds.items():
        kind = BY_NAME[kind_name]
        if kind_name in MODES:
            out += [f"{label}.{w[:-2]}" for w in kind.inputs if w.endswith("_G")]
        else:
            out += [label] if len(kind.inputs) == 1 else [f"{label}_{w}" for w in kind.inputs]
    return out
