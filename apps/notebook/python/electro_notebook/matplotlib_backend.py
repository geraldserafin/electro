"""matplotlib's backend in the notebook (``MPLBACKEND``, set by ``cells``): figures drawn in memory (Agg), shown
among the cell's outputs (``figures``)."""

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas  # noqa: F401 — the backend's canvas

from .figures import take


def show(*args, **kwargs) -> None:
    """``plt.show()``: the figures so far, here among the outputs."""
    take()
