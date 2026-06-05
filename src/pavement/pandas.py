"""
Pandas integration: a ``.pave`` accessor and an opt-in summary repr.

Importing this module registers a ``.pave`` accessor on pandas ``DataFrame``
and ``Series`` (through pandas' own accessor API, so it is namespaced and
won't clash), putting the pavement strips a method away::

    import pavement.pandas          # registers .pave

    df.pave()                       # the whole-frame summary (renders inline)
    df.pave.summary()               # the same, spelled out
    df.pave.spark("price")          # a numeric column's pavement sparkline
    df.pave.tally("plan")           # a column's distinct/duplicate/missing strip
    df.pave.proportion("plan")      # a column's value-counts strip

    s = df["price"]
    s.pave()                        # a Series summarizes as one row
    s.pave.spark()                  # the column helpers take no column name

    summary(df["score"].groupby(df["team"]))  # one row per group

``df.pave()`` and ``.summary()`` return the same `pavement.summary` result (a
`Summary`, which renders inline in Jupyter). The single-column helpers return
the svg string of the matching `pavement.svg` glyph, wrapped so it *also*
renders inline in a notebook while still behaving as the plain string
everywhere else (it is a ``str`` subclass).

Optionally make the summary a frame's default notebook display::

    pavement.pandas.enable_repr()   # every DataFrame/Series previews as a summary
    pavement.pandas.disable_repr()  # restore pandas' normal display

That one *replaces* the usual data-table preview (it does not append to it), so
it is strictly opt-in. It needs a running IPython/Jupyter; importing the
accessor needs only pandas.

This module follows the same pattern as ``import hvplot.pandas`` — the
integration activates on import, never on a bare ``import pavement``, so the
core package stays dependency-free.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._inline import SVG, disable_summary_repr, enable_summary_repr, present
from .svg import proportion, spark, summary, tally

__all__ = ["enable_repr", "disable_repr"]


class _PaveFrame:
    """The ``.pave`` accessor on a DataFrame (see the module docstring)."""

    def __init__(self, frame: pd.DataFrame) -> None:
        self._frame = frame

    def __call__(self, **kwargs: Any) -> Any:
        return summary(self._frame, **kwargs)

    def summary(self, **kwargs: Any) -> Any:
        return summary(self._frame, **kwargs)

    def spark(self, column: Any, **kwargs: Any) -> SVG:
        return SVG(spark(present(self._frame[column]), **kwargs))

    def tally(self, column: Any, **kwargs: Any) -> SVG:
        return SVG(tally(self._frame[column], **kwargs))

    def proportion(self, column: Any, **kwargs: Any) -> SVG:
        return SVG(proportion(self._frame[column], **kwargs))


class _PaveSeries:
    """The ``.pave`` accessor on a Series — the column helpers take no name."""

    def __init__(self, series: pd.Series) -> None:
        self._series = series

    def __call__(self, **kwargs: Any) -> Any:
        return summary(self._series, **kwargs)

    def summary(self, **kwargs: Any) -> Any:
        return summary(self._series, **kwargs)

    def spark(self, **kwargs: Any) -> SVG:
        return SVG(spark(present(self._series), **kwargs))

    def tally(self, **kwargs: Any) -> SVG:
        return SVG(tally(self._series, **kwargs))

    def proportion(self, **kwargs: Any) -> SVG:
        return SVG(proportion(self._series, **kwargs))


# Register on import. pandas caches the accessor per object and warns only if
# the name is already taken; importing this module once (the usual case) does
# it cleanly.
pd.api.extensions.register_dataframe_accessor("pave")(_PaveFrame)
pd.api.extensions.register_series_accessor("pave")(_PaveSeries)


def enable_repr(series: bool = True, **summary_kwargs: Any) -> None:
    """Make `pavement.summary` the default inline display of pandas objects.

    Registers an IPython HTML formatter so that every ``DataFrame`` (and,
    unless *series* is False, every ``Series``) renders as its pavement
    summary in the notebook, **replacing** the usual data-table preview rather
    than adding to it. Extra keyword arguments are forwarded to `summary`
    (e.g. ``height``, ``color``). Undo with `disable_repr`.

    Raises ``RuntimeError`` if there is no running IPython/Jupyter session.
    """
    types = [pd.DataFrame] + ([pd.Series] if series else [])
    enable_summary_repr(types, **summary_kwargs)


def disable_repr() -> None:
    """Restore pandas' normal display, undoing `enable_repr`."""
    disable_summary_repr([pd.DataFrame, pd.Series])
