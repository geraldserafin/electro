"""A problem in time, from rest: Φ, its step function (``solve(problem, Step())``), again and again — in the
notebook by the page's engine (the same loop, JIT-compiled), elsewhere here."""

from __future__ import annotations

import importlib
import sys
from array import array
from collections.abc import Mapping

from ..problem.problem import Problem
from ..solver.analysis import Step
from ..solver.solve import solve
from ..solver.step import Frame, StepFunction
from ..solver.symbols import symbols
from .errors import NoConvergence
from .inputs import Key, schedule
from .run import Schedule, run
from .trace import Trace


def simulate(
    problem: Problem, until: float, dt: float | None = None, inputs: Mapping[Key, object] | None = None
) -> Trace:
    """``until`` seconds from rest (every capacitor empty, every inductor still). ``dt``: the longest step
    (by default ``until``/500; steps shrink by themselves where things move fast). ``inputs``: what the world
    sets (``inputs.Key``), each a value or a function of time."""
    phi = solve(problem, Step())
    when = schedule(phi, symbols(problem.circuit), inputs)
    dt_max = dt or until / 500
    engine = _engine()
    if engine is not None:
        t, data = _in_the_page(engine, phi, until, dt_max, when)
    else:
        t, data = _here(phi, until, dt_max, when)
    return Trace(problem, phi, t, data)


def _here(phi: StepFunction, until: float, dt_max: float, when: Schedule | None) -> tuple[list[float], array]:
    times: list[float] = []
    rows = array("d")

    def record(frame: Frame) -> None:
        times.append(frame.t)
        rows.extend(frame.x)

    run(phi, until, dt_max, when, record)
    return times, rows


def _engine():
    if sys.platform != "emscripten":
        return None
    return getattr(importlib.import_module("js"), "electroSim", None)


def _in_the_page(engine, phi: StepFunction, until: float, dt_max: float, when: Schedule | None):
    create_proxy = importlib.import_module("pyodide.ffi").create_proxy
    callback = create_proxy(lambda now: [list(pair) for pair in when(now)]) if when else None
    try:
        result = engine.run(phi.to_json(), until, dt_max, callback)
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
