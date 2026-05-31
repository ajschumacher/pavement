"""
Quantile-based pavement plots: every box holds an equal share of the data.

The top-level package exposes only the backend-agnostic statistics
(`quantiles`, `pavement_stats`, `pavement_stats2d`). Pick a rendering
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
"""

from __future__ import annotations

from .core import pavement_stats, pavement_stats2d, quantiles

__all__ = ["quantiles", "pavement_stats", "pavement_stats2d"]
