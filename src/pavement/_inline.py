"""
Shared helpers for the dataframe-library integrations (`pavement.pandas`,
`pavement.polars`).

These two modules are parallel: each registers a ``.pave`` accessor/namespace
and an opt-in summary repr on its library's frame and series types. The pieces
that don't depend on which library it is live here, computed and tested once:

- `SVG`, the ``str`` subclass the single-column helpers return so a glyph's
  ``<svg>`` renders inline in Jupyter while still behaving as the plain string
  everywhere else;
- `present`, the non-missing filter the numeric spark needs; and
- `enable_summary_repr` / `disable_summary_repr`, which register or remove an
  IPython HTML formatter that renders given types as their `pavement.summary`.

Nothing here imports pandas or polars, so it stays library-agnostic.
"""

from __future__ import annotations

from typing import Any, Iterable

from .core import _is_missing
from .svg import summary


class SVG(str):
    """An ``<svg>`` string that also renders inline in Jupyter.

    A ``str`` subclass, so it embeds in HTML, saves, slices, and compares
    exactly like the plain string the svg backend returns — but in a notebook
    the rich display shows the rendered graphic (via ``_repr_html_``) instead
    of the source text.
    """

    def _repr_html_(self) -> str:
        return str(self)


def present(values: Iterable[Any]) -> list[Any]:
    """A column's non-missing values, for the numeric spark (which can't plot
    a missing value). `tally` and `proportion` handle missing themselves."""
    return [v for v in values if not _is_missing(v)]


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


def enable_summary_repr(types: Iterable[type], **summary_kwargs: Any) -> None:
    """Render each type in *types* as its `pavement.summary` in the notebook.

    Registers an IPython HTML formatter for each type, **replacing** that
    type's normal display. *summary_kwargs* are forwarded to `summary`.
    """
    formatter = _html_formatter()

    def render(obj: Any) -> str:
        return summary(obj, **summary_kwargs)._repr_html_()

    for typ in types:
        formatter.for_type(typ, render)


def disable_summary_repr(types: Iterable[type]) -> None:
    """Undo `enable_summary_repr` for each type in *types*."""
    formatter = _html_formatter()
    for typ in types:
        formatter.pop(typ, None)
