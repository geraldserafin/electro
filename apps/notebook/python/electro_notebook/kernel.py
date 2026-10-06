"""The notebook's kernel: what the page's Python worker calls (``features/python/worker.ts``). Each takes and
returns JSON; nothing here is said in words — what goes wrong is data (``errors``), said in the reader's
language by the page."""

from .ai import task_values
from .board import frequency, live, solve, spread, sweep_plot
from .cells import reset, run
from .code_view import from_code, variable

__all__ = [
    "frequency",
    "from_code",
    "live",
    "reset",
    "run",
    "solve",
    "spread",
    "sweep_plot",
    "task_values",
    "variable",
]
