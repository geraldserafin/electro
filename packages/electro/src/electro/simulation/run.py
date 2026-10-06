"""Φ again and again (``solver.step``): each frame the step function of the one before. All that is the
simulation's own is how long a step is — as long as what is remembered allows. The same loop as the page's
engine (``simulation/engine.ts``), so both give the same numbers."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import replace

from ..solver.step import Frame, StepFunction
from .errors import NoConvergence

Schedule = Callable[[float], list[tuple[int, float]]]
"""What the world sets at a time: ``[(param index, value)]``."""

OnFrame = Callable[[Frame], None]


def run(phi: StepFunction, until: float, dt_max: float, schedule: Schedule | None = None, on_frame=None) -> Frame:
    """From rest to ``until``; ``on_frame`` gets every frame, at t = 0 too, after a first tiny step (the
    circuit the instant it starts)."""
    frame, step = _walk(phi, _set(phi.rest, schedule), min(1e-9, until), dt_max, schedule, 0.0)
    frame = replace(frame, t=0.0)
    if on_frame is not None:
        on_frame(frame)
    return _walk(phi, frame, until, dt_max, schedule, step, on_frame)[0]


def _walk(
    phi: StepFunction,
    frame: Frame,
    target: float,
    dt_max: float,
    schedule: Schedule | None,
    step: float,
    on_frame: OnFrame | None = None,
) -> tuple[Frame, float]:
    """Steps up to ``target``, at most ``dt_max``: shorter while what is remembered moves fast, after
    something jumped, or when Newton did not get there; in the shortest step a value may jump for real
    (a capacitor put across an ideal source). Returns the last frame and the step it would take next."""
    dt_min = dt_max * 1e-9
    step = min(step or min(dt_max, 1e-6), dt_max)
    while frame.t < target - 1e-15:
        h = min(step, target - frame.t)
        frame = _set(frame, schedule)
        after = phi(frame, h)
        change = math.inf if after is None else _change(phi, frame, after)
        if after is None or (change > 1 and h > dt_min):
            if h <= dt_min:
                raise NoConvergence(frame.t)
            step = h / 4 if change == math.inf else h / 2
            continue
        switched = any(most is None and after.p[i] != frame.p[i] for i, most in phi.states)
        frame = after
        if on_frame is not None:
            on_frame(frame)
        if switched:
            step = max(dt_min, h / 8)
        elif change < 0.25 and h >= step * 0.999:
            step = min(dt_max, h * 2)
    return frame, step


def _change(phi: StepFunction, before: Frame, after: Frame) -> float:
    """How much of its allowed move a remembered value used."""
    return max((abs(after.p[i] - before.p[i]) / most for i, most in phi.states if most is not None), default=0.0)


def _set(frame: Frame, schedule: Schedule | None) -> Frame:
    if schedule is None:
        return frame
    p = list(frame.p)
    for i, value in schedule(frame.t):
        p[i] = value
    return replace(frame, p=p)
