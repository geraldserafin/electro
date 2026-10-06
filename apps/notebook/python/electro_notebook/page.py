"""In the page, a run goes to the page's engine (``electroSim``): electro's own, printed as JavaScript, many
times faster than Python under Pyodide."""

from __future__ import annotations

import importlib
import sys
from array import array

from electro import NoConvergence


def install() -> None:
    """Runs go to the page's engine (``electro.simulate.RUNNER``)."""
    if sys.platform == "emscripten":
        importlib.import_module("electro.simulate").RUNNER = run


def run(phi, until: float, dt_max: float, when):
    """A run in the page's engine; None before the page has one."""
    engine = getattr(importlib.import_module("js"), "electroSim", None)
    if engine is None:
        return None
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
    times, rows, params = array("d"), array("d"), array("d")
    times.frombytes(result.t.to_bytes())
    rows.frombytes(result.rows.to_bytes())
    params.frombytes(result.params.to_bytes())
    return times.tolist(), rows, params
