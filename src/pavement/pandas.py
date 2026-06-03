"""
Pandas integration: a ``.pave`` accessor and an opt-in summary repr.

Importing this module registers a ``.pave`` accessor on pandas ``DataFrame``
and ``Series`` (through pandas' own accessor API, so it is namespaced and
won't clash), putting the pavement strips a method away::

    import pavement.pandas          # registers .pave

    df.pave()                       # the whole-frame summary (renders inline)
    df.pave.summary()               # the same, spelled out
    df.pave.spark("price")          # a numeric column's pavement sparkline
    df.pave.tally("plan")           # a column's distinct/repeated/missing strip
    df.pave.proportion("plan")      # a column's value-counts strip

    s = df["price"]
    s.pave()                        # a Series summarizes as one row
    s.pave.spark()                  # the column helpers take no column name

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

from .core import _is_missing
from .svg import proportion, spark, summary, tally

__all__ = ["enable_repr", "disable_repr"]


class _SVG(str):
    """An ``<svg>`` string that also renders inline in Jupyter.

    A ``str`` subclass, so it embeds in HTML, saves, slices, and compares
    exactly like the plain string the svg backend returns — but in a notebook
    the rich display shows the rendered graphic (via ``_repr_html_``) instead
    of the source text.
    """

    def _repr_html_(self) -> str:
        return str(self)


def _present(values: Any) -> list[Any]:
    """A column's non-missing values, for the numeric spark (which can't plot
    a missing value). `tally` and `proportion` handle missing themselves."""
    return [v for v in values if not _is_missing(v)]


class _PaveFrame:
    """The ``.pave`` accessor on a DataFrame (see the module docstring)."""

    def __init__(self, frame: pd.DataFrame) -> None:
        self._frame = frame

    def __call__(self, **kwargs: Any) -> Any:
        return summary(self._frame, **kwargs)

    def summary(self, **kwargs: Any) -> Any:
        return summary(self._frame, **kwargs)

    def spark(self, column: Any, **kwargs: Any) -> _SVG:
        return _SVG(spark(_present(self._frame[column]), **kwargs))

    def tally(self, column: Any, **kwargs: Any) -> _SVG:
        return _SVG(tally(self._frame[column], **kwargs))

    def proportion(self, column: Any, **kwargs: Any) -> _SVG:
        return _SVG(proportion(self._frame[column], **kwargs))


class _PaveSeries:
    """The ``.pave`` accessor on a Series — the column helpers take no name."""

    def __init__(self, series: pd.Series) -> None:
        self._series = series

    def __call__(self, **kwargs: Any) -> Any:
        return summary(self._series, **kwargs)

    def summary(self, **kwargs: Any) -> Any:
        return summary(self._series, **kwargs)

    def spark(self, **kwargs: Any) -> _SVG:
        return _SVG(spark(_present(self._series), **kwargs))

    def tally(self, **kwargs: Any) -> _SVG:
        return _SVG(tally(self._series, **kwargs))

    def proportion(self, **kwargs: Any) -> _SVG:
        return _SVG(proportion(self._series, **kwargs))


# Register on import. pandas caches the accessor per object and warns only if
# the name is already taken; importing this module once (the usual case) does
# it cleanly.
pd.api.extensions.register_dataframe_accessor("pave")(_PaveFrame)
pd.api.extensions.register_series_accessor("pave")(_PaveSeries)


def _html_formatter() -> Any:
    """The active IPython ``text/html`` formatter, or a clear error if there
    is no running IPython/Jupyter to register one on."""
    try:
        from IPython import get_ipython
    except ModuleNotFoundError as exc:  # pragma: no cover - env without IPython
        raise RuntimeError(
            "enable_repr/disable_repr need IPython; run inside Jupyter/IPython."
        ) from exc
    ip = get_ipython()
    if ip is None:
        raise RuntimeError(
            "enable_repr/disable_repr must be called inside a running "
            "IPython/Jupyter session."
        )
    return ip.display_formatter.formatters["text/html"]


def enable_repr(series: bool = True, **summary_kwargs: Any) -> None:
    """Make `pavement.summary` the default inline display of pandas objects.

    Registers an IPython HTML formatter so that every ``DataFrame`` (and,
    unless *series* is False, every ``Series``) renders as its pavement
    summary in the notebook, **replacing** the usual data-table preview rather
    than adding to it. Extra keyword arguments are forwarded to `summary`
    (e.g. ``height``, ``color``). Undo with `disable_repr`.

    Raises ``RuntimeError`` if there is no running IPython/Jupyter session.
    """
    formatter = _html_formatter()
    formatter.for_type(
        pd.DataFrame, lambda frame: summary(frame, **summary_kwargs)._repr_html_())
    if series:
        formatter.for_type(
            pd.Series, lambda s: summary(s, **summary_kwargs)._repr_html_())


def disable_repr() -> None:
    """Restore pandas' normal display, undoing `enable_repr`."""
    formatter = _html_formatter()
    formatter.pop(pd.DataFrame, None)
    formatter.pop(pd.Series, None)
