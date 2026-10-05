"""A problem in time, from rest: compiled once, then run — in the notebook by the page's engine (the same
loop, JIT-compiled), elsewhere here."""

from __future__ import annotations

import importlib
import sys
from array import array
from collections.abc import Mapping

from ..problem.problem import Problem
from ..solver.symbols import symbols
from .errors import NoConvergence
from .inputs import Key, schedule
from .program import Program, compile_program
from .run import Schedule, Simulation
from .trace import Trace


def simulate(
    problem: Problem, until: float, dt: float | None = None, inputs: Mapping[Key, object] | None = None
) -> Trace:
    """``until`` seconds from rest (every capacitor empty, every inductor still). ``dt``: the longest step
    (by default ``until``/500; steps shrink by themselves where things move fast). ``inputs``: what the world
    sets (``inputs.Key``), each a value or a function of time."""
    program = compile_program(problem)
    when = schedule(program, symbols(problem.circuit), inputs)
    dt_max = dt or until / 500
    engine = _engine()
    if engine is not None:
        t, data = _in_the_page(engine, program, until, dt_max, when)
    else:
        t, data = _here(program, until, dt_max, when)
    return Trace(problem, program, t, data)


def _here(program: Program, until: float, dt_max: float, when: Schedule | None) -> tuple[list[float], array]:
    sim = Simulation(program)
    times: list[float] = []
    rows = array("d")

    def record() -> None:
        times.append(sim.t)
        rows.extend(sim.x)

    sim.run(until, dt_max, when, record)
    return times, rows


def _engine():
    if sys.platform != "emscripten":
        return None
    return getattr(importlib.import_module("js"), "electroSim", None)


def _in_the_page(engine, program: Program, until: float, dt_max: float, when: Schedule | None):
    create_proxy = importlib.import_module("pyodide.ffi").create_proxy
    callback = create_proxy(lambda now: [list(pair) for pair in when(now)]) if when else None
    try:
        result = engine.run(program.to_json(), until, dt_max, callback)
    except Exception as err:
        if "NoConvergence" in str(err):
            raise NoConvergence(float(str(err).rsplit(" ", 1)[-1])) from None
        raise
    finally:
        if callback is not None:
            callback.destroy()
    times, rows = array("d"), array("d")
    times.frombytes(result.t.to_bytes())
    rows.frombytes(result.rows.to_bytes())
    return times.tolist(), rows
