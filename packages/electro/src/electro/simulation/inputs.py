"""What the world sets while a circuit runs, as one function of time: a switch's position, the light on a
sensor, a board's pin in one of its chip's modes (``"high"``, ``"pullup"``)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

from ..circuit.elements import BY_NAME
from ..circuit.tree import Element
from ..solver.step import StepFunction
from ..solver.symbols import Symbols
from .errors import NoSuchInput
from .run import Schedule

Setter = Callable[[object], list[tuple[int, float]]]
Key = Element | tuple[Element, str] | str
"""An element (its one input), an element and its input's or its pin's name, or that as text:
``"S_1"``, ``"S_1_closed"``, ``"ARD_1.D13"``."""


def schedule(phi: StepFunction, s: Symbols, inputs: Mapping[Key, object] | None) -> Schedule | None:
    if not inputs:
        return None
    parts = [(_setter(phi, _name(key, s)), value) for key, value in inputs.items()]
    return lambda now: [pair for setter, value in parts for pair in setter(value(now) if callable(value) else value)]


def _name(key: Key, s: Symbols) -> str:
    match key:
        case Element():
            return s.labels[s.index(key)]
        case (Element() as e, str(which)):
            return f"{s.labels[s.index(e)]}.{which}"
    return str(key)


def _setter(phi: StepFunction, name: str) -> Setter:
    label, _, pin = name.partition(".")
    if pin:
        pin_mode = _pin(phi, label, pin)
        if pin_mode is not None:
            return pin_mode
    for candidate in _candidates(phi, name):
        if candidate in phi.inputs:
            index = phi.inputs[candidate]
            return lambda value: [(index, float(cast(float, value)))]
    raise NoSuchInput(name, _available(phi))


def _pin(phi: StepFunction, label: str, pin: str) -> Setter | None:
    kind = BY_NAME.get(phi.kinds.get(label, ""))
    modes = dict(kind.modes) if kind is not None and kind.modes else None
    g, e = f"{label}_{pin}_G", f"{label}_{pin}_E"
    if modes is None or g not in phi.inputs:
        return None
    gi, ei = phi.inputs[g], phi.inputs[e]

    def set_mode(mode: object) -> list[tuple[int, float]]:
        conductance, volts = modes[mode] if isinstance(mode, str) else (modes["high"][0], float(cast(float, mode)))
        return [(gi, conductance), (ei, volts)]

    return set_mode


def _candidates(phi: StepFunction, name: str) -> list[str]:
    kind = BY_NAME.get(phi.kinds.get(name, ""))
    return [name, *(f"{name}_{which}" for which in (kind.inputs if kind else ()))]


def _available(phi: StepFunction) -> list[str]:
    out = []
    for label, kind_name in phi.kinds.items():
        kind = BY_NAME[kind_name]
        if kind.modes:
            out += [f"{label}.{w[:-2]}" for w in kind.inputs if w.endswith("_G")]
        else:
            out += [label] if len(kind.inputs) == 1 else [f"{label}_{w}" for w in kind.inputs]
    return out
