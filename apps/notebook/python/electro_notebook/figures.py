"""matplotlib's figures as a cell's outputs: ``plt.show()`` (``matplotlib_backend``) — or the cell's end — puts each
open figure among them as SVG, then closes it. matplotlib is imported only when a cell imports it."""

from __future__ import annotations

import io
import sys

outputs: list[dict] | None = None
"""Where the cell running now puts what it shows (``cells.run``)."""


def take() -> None:
    """Each open figure into the outputs, then closed."""
    pyplot = sys.modules.get("matplotlib.pyplot")
    if pyplot is None or outputs is None:
        return
    for number in pyplot.get_fignums():
        outputs.append(picture(pyplot.figure(number)))
    pyplot.close("all")


def picture(figure) -> dict:
    """A figure as an SVG output."""
    svg = io.StringIO()
    figure.savefig(svg, format="svg", bbox_inches="tight")
    data = svg.getvalue()
    return {"type": "svg", "data": data[data.index("<svg") :]}  # (no XML prolog: it goes into the page's HTML)


def of_matplotlib(value: object) -> bool:
    """A figure, an axes, a line… or a list of them: what ``plt.plot(…)`` gives back, not worth printing."""
    if isinstance(value, list | tuple) and value:
        return all(of_matplotlib(v) for v in value)
    return type(value).__module__.startswith("matplotlib.")
