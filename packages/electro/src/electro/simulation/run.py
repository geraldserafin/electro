"""A program running: steps as long as what is remembered allows, Newton's method in each. The same loop as
the page's engine (``simulation/engine.ts``), so both give the same numbers."""

from __future__ import annotations

import math
from collections.abc import Callable

from .errors import NoConvergence
from .linear import solve_linear
from .program import Program

RELTOL, VNTOL = 1e-6, 1e-6
MAX_NEWTON = 60

Schedule = Callable[[float], list[tuple[int, float]]]
"""What the world sets at a time: ``[(param index, value)]``."""


def junction_step(new: float, old: float, nvt: float, vcrit: float) -> float:
    """SPICE's: along the exponential, never far past its bend in one go."""
    if new > vcrit and abs(new - old) > 2 * nvt:
        if old > 0:
            arg = 1 + (new - old) / nvt
            return old + nvt * math.log(arg) if arg > 0 else vcrit
        return nvt * math.log(new / nvt)
    return new


class Simulation:
    """``advance_to(t)`` from where it is, ``run(t)`` from rest."""

    def __init__(self, program: Program):
        self.program = program
        self.kernel, self.update, self.flow = program.functions()
        self.n = len(program.unknowns)
        self.x = [0.0] * self.n
        self.p = list(program.initial)
        self.t = 0.0
        self.switched = False
        self.step = 0.0

    def set_input(self, name: str, value: float) -> None:
        self.p[self.program.inputs[name]] = float(value)

    def newton(self, dt: float) -> list[float] | None:
        n, p = self.n, self.p
        p[0], p[1] = dt, self.t + dt
        x = list(self.x)
        F, J = [0.0] * n, [0.0] * (n * n)
        for iteration in range(1, MAX_NEWTON + 1):
            J[:] = [0.0] * (n * n)
            self.kernel(x, p, F, J)
            dx = solve_linear(J, [-f for f in F], n)
            if dx is None or any(math.isnan(d) for d in dx):
                return None
            new = [a + d for a, d in zip(x, dx)]
            for i, nvt, vcrit in self.program.junctions:
                new[i] = junction_step(new[i], x[i], nvt, vcrit)
            done = all(abs(a - b) <= RELTOL * max(abs(a), abs(b)) + VNTOL for a, b in zip(new, x))
            x = new
            if done and iteration > 1:
                return x
        return None

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
