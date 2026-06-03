"""
Polars integration: a ``.pave`` namespace and an opt-in summary repr.

The polars counterpart of `pavement.pandas`. Importing this module registers a
``.pave`` namespace on polars ``DataFrame`` and ``Series`` (through polars'
``register_*_namespace`` API), putting the pavement strips a method away::

    import pavement.polars         # registers .pave

    df.pave()                      # the whole-frame summary (renders inline)
    df.pave.summary()              # the same, spelled out
    df.pave.spark("price")         # a numeric column's pavement sparkline
    df.pave.tally("plan")          # a column's distinct/repeated/missing strip
    df.pave.proportion("plan")     # a column's value-counts strip

    s = df["price"]
    s.pave()                       # a Series summarizes as one row
    s.pave.spark()                 # the column helpers take no column name

``df.pave()`` / ``.summary()`` return the `pavement.summary` result (a
`Summary`, which renders inline in Jupyter); the single-column helpers return
the matching `pavement.svg` glyph's string, wrapped so it *also* renders
inline (it is a ``str`` subclass — see `pavement._inline.SVG`).

Optionally make the summary a frame's default notebook display::

    pavement.polars.enable_repr()   # every DataFrame/Series previews as a summary
    pavement.polars.disable_repr()  # restore polars' normal display

That *replaces* the usual data-table preview (it does not append), so it is
strictly opt-in, and needs a running IPython/Jupyter. The integration
activates on ``import pavement.polars`` only, never on a bare ``import
pavement``, keeping the core dependency-free.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ._inline import SVG, disable_summary_repr, enable_summary_repr, present
from .svg import proportion, spark, summary, tally


__all__ = ["enable_repr", "disable_repr"]


@pl.api.register_dataframe_namespace("pave")
class _PaveFrame:
    """The ``.pave`` namespace on a polars DataFrame (see the module docstring)."""

    def __init__(self, frame: pl.DataFrame) -> None:
        self._frame = frame

    def __call__(self, **kwargs: Any) -> Any:
        return summary(self._frame, **kwargs)

    def summary(self, **kwargs: Any) -> Any:
        return summary(self._frame, **kwargs)

    def spark(self, column: str, **kwargs: Any) -> SVG:
        return SVG(spark(present(self._frame.get_column(column).to_list()), **kwargs))

    def tally(self, column: str, **kwargs: Any) -> SVG:
        return SVG(tally(self._frame.get_column(column).to_list(), **kwargs))

    def proportion(self, column: str, **kwargs: Any) -> SVG:
        return SVG(proportion(self._frame.get_column(column).to_list(), **kwargs))


@pl.api.register_series_namespace("pave")
class _PaveSeries:
    """The ``.pave`` namespace on a Series — the column helpers take no name."""

    def __init__(self, series: pl.Series) -> None:
        self._series = series

    def __call__(self, **kwargs: Any) -> Any:
        return summary(self._series, **kwargs)

    def summary(self, **kwargs: Any) -> Any:
        return summary(self._series, **kwargs)

    def spark(self, **kwargs: Any) -> SVG:
        return SVG(spark(present(self._series.to_list()), **kwargs))

    def tally(self, **kwargs: Any) -> SVG:
        return SVG(tally(self._series.to_list(), **kwargs))

    def proportion(self, **kwargs: Any) -> SVG:
        return SVG(proportion(self._series.to_list(), **kwargs))


def enable_repr(series: bool = True, **summary_kwargs: Any) -> None:
    """Make `pavement.summary` the default inline display of polars objects.

    Registers an IPython HTML formatter so that every ``DataFrame`` (and,
    unless *series* is False, every ``Series``) renders as its pavement
    summary in the notebook, **replacing** polars' usual data-table preview.
    Extra keyword arguments are forwarded to `summary` (e.g. ``height``,
    ``color``). Undo with `disable_repr`.

    Raises ``RuntimeError`` if there is no running IPython/Jupyter session.
    """
    types = [pl.DataFrame] + ([pl.Series] if series else [])
    enable_summary_repr(types, **summary_kwargs)


def disable_repr() -> None:
    """Restore polars' normal display, undoing `enable_repr`."""
    disable_summary_repr([pl.DataFrame, pl.Series])
