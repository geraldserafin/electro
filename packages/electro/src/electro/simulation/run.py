"""A program running: steps as long as what is remembered allows, each step ``solve``'s Newton
(``solver.numeric``). The same loop as the page's engine (``simulation/engine.ts``), so both give the same
numbers."""

from __future__ import annotations

import math
from collections.abc import Callable

from .errors import NoConvergence
from .program import Program

Schedule = Callable[[float], list[tuple[int, float]]]
"""What the world sets at a time: ``[(param index, value)]``."""


class Simulation:
    """``advance_to(t)`` from where it is, ``run(t)`` from rest."""

    def __init__(self, program: Program):
        self.program = program
        self.update, _ = program.functions()
        self.n = len(program.unknowns)
        self.x = [0.0] * self.n
        self.p = list(program.initial)
        self.t = 0.0
        self.switched = False
        self.step = 0.0

    def newton(self, dt: float) -> list[float] | None:
        self.p[0], self.p[1] = dt, self.t + dt
        return self.program.equations.newton(self.x, self.p)

    def advance(self, dt: float, jump: bool = False) -> tuple[bool, float]:
        """One step of ``dt``: (taken?, how much of its allowed move a remembered value used). ``jump``: taken
        whatever it moved, once Newton got there."""
        x = self.newton(dt)
        if x is None:
            return False, math.inf
        after = [0.0] * len(self.program.states)
        self.update(x, self.p, after)
        change = max(
            (abs(v - self.p[i]) / most for (i, most), v in zip(self.program.states, after) if most is not None),
            default=0.0,
        )
        if change > 1 and not jump:
            return False, change
        self.x, self.t = x, self.t + dt
        self.switched = any(most is None and v != self.p[i] for (i, most), v in zip(self.program.states, after))
        for (i, _), v in zip(self.program.states, after):
            self.p[i] = v
        return True, change

    def advance_to(self, target: float, dt_max: float, schedule: Schedule | None = None, on_step=None) -> None:
        """Steps up to ``target``, at most ``dt_max``: shorter while what is remembered moves fast, after
        something jumped, or when Newton did not get there; in the shortest step a value may jump for real
        (a capacitor put across an ideal source)."""
        dt_min = dt_max * 1e-9
        self.step = min(self.step or min(dt_max, 1e-6), dt_max)
        while self.t < target - 1e-15:
            h = min(self.step, target - self.t)
            self._set(schedule, self.t)
            ok, change = self.advance(h, jump=h <= dt_min)
            if not ok:
                if h <= dt_min:
                    raise NoConvergence(self.t)
                self.step = h / 4 if change == math.inf else h / 2
                continue
            if on_step is not None:
                on_step()
            if self.switched:
                self.step = max(dt_min, h / 8)
            elif change < 0.25 and h >= self.step * 0.999:
                self.step = min(dt_max, h * 2)

    def run(self, t_end: float, dt_max: float, schedule: Schedule | None = None, on_step=None) -> None:
        """From rest to ``t_end``; ``on_step`` at t = 0 too, after a first tiny step (the circuit the instant
        it starts)."""
        self._set(schedule, 0.0)
        self.advance_to(min(1e-9, t_end), dt_max, schedule)
        self.t = 0.0
        if on_step is not None:
            on_step()
        self.advance_to(t_end, dt_max, schedule, on_step)

    def _set(self, schedule: Schedule | None, t: float) -> None:
        for i, value in schedule(t) if schedule is not None else ():
            self.p[i] = value
