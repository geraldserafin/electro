"""matplotlib in a cell (``figures``): each figure an SVG output, where ``plt.show()`` is or at the cell's end; what
``plt.plot`` gives back not printed."""

import json

import pytest

pytest.importorskip("matplotlib")

from electro_notebook import cells  # noqa: E402 — after matplotlib is known to be there


def test_figures_are_shown_where_show_is_and_at_the_end():
    code = "import matplotlib.pyplot as plt\nplt.plot([0, 1], [1, 0])\nplt.show()\nprint('po')\nplt.plot([0, 1])"
    out = json.loads(cells.run(code))
    assert [o["type"] for o in out] == ["stream", "svg", "svg"]
    assert all(o["data"].startswith("<svg") for o in out[1:])
