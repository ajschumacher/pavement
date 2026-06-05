"""
Quantile-based pavement plots: every box holds an equal share of the data.

The top-level package exposes the backend-agnostic statistics: the
pavement quantiles (`quantiles`, `pavement_stats`, `pavement_stats2d`) and
the column summaries (`tally_stats`, `proportion_stats`). Pick a rendering
backend by importing its submodule — they share one ``plot`` API, so the
import line is the only thing that changes::

    import pavement.matplotlib as pavement   # or .bokeh / .plotly / .holoviews
    pavement.plot([1, 2, 3, 4, 5])

Backends:

- `pavement.matplotlib` — static plots (also 2D pavements, marginal
  strips, and a raster ``spark`` sparkline).
- `pavement.bokeh`, `pavement.plotly` — interactive plots (hover, pan,
  zoom, legends) drawn with each library's native glyphs/traces.
- `pavement.holoviews` — backend-agnostic HoloViews elements.
- `pavement.svg` — self-contained inline SVG sparklines (``spark``) for
  HTML; no dependencies, always available.

Each plotting backend except `pavement.svg` is an optional dependency;
install the ones you want with, e.g., ``pip install pavement[bokeh]``.

One convenience is re-exported at the top level: `summary`, which renders a
dataframe, Series, or sequence as an inline HTML summary table (tally plus
distribution per column) that displays itself in Jupyter::

    import pavement
    pavement.summary(df)        # shows the table inline in a notebook cell

It lives in `pavement.svg` (and so, like that backend, needs no extra), and
is exposed here as the package's headline data-summary entry point.

pandas and polars users can go further: ``import pavement.pandas`` (or
``import pavement.polars``) registers a ``.pave`` accessor (``df.pave()``,
``df.pave.spark("col")``, …) and an opt-in summary-as-default-display toggle.
That activates on its own import, never on a bare ``import pavement``, so the
core stays dependency-free.
"""

from __future__ import annotations

from .core import (
    pavement_stats,
    pavement_stats2d,
    proportion_stats,
    quantiles,
    tally_stats,
)
from .svg import summary

__all__ = [
    "quantiles",
    "pavement_stats",
    "pavement_stats2d",
    "tally_stats",
    "proportion_stats",
    "summary",
]
