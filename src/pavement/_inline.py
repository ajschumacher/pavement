"""
Shared helpers for the dataframe-library integrations (`pavement.pandas`,
`pavement.polars`).

These two modules are parallel: each registers a ``.pave`` accessor/namespace
and an opt-in summary repr on its library's frame and series types. The pieces
that don't depend on which library it is live here, computed and tested once:

- `SVG`, the ``str`` subclass the single-column helpers return so a glyph's
  ``<svg>`` renders inline in Jupyter while still behaving as the plain string
  everywhere else;
- `present`, the non-missing filter the numeric spark needs;
- `enable_summary_repr` / `disable_summary_repr`, which register or remove an
  IPython HTML formatter that renders given types as their `pavement.summary`;
- `_GroupByAccessor` and `_register_groupby_accessor`, shared machinery for
  attaching a ``.pave`` descriptor to a library's GroupBy class (pandas and
  polars both lack a public registration hook for GroupBy types).

Nothing here imports pandas or polars, so it stays library-agnostic.
"""

from __future__ import annotations

import warnings
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


class _GroupByAccessor:
    """Descriptor that attaches a ``.pave`` accessor to a GroupBy class.

    Pandas and polars expose no public registration hook for GroupBy types, so
    the descriptor is set directly on the class — the same mechanism pandas
    uses internally for ``register_dataframe_accessor``.  Accessing ``.pave``
    on a class (not an instance) returns the accessor class itself, matching
    the behaviour of pandas' own ``_CachedAccessor``.
    """

    def __init__(self, accessor_cls: type) -> None:
        self._accessor_cls = accessor_cls

    def __get__(self, obj: Any, cls: Any) -> Any:
        if obj is None:
            return self._accessor_cls
        return self._accessor_cls(obj)


def _register_groupby_accessor(name: str, groupby_cls: type,
                                accessor_cls: type) -> None:
    """Attach *accessor_cls* as a ``.pave``-style descriptor on *groupby_cls*."""
    if hasattr(groupby_cls, name):
        warnings.warn(
            f"registration of accessor '{name}' on {groupby_cls.__name__} "
            f"overrides a preexisting attribute with the same name.",
            UserWarning, stacklevel=3,
        )
    setattr(groupby_cls, name, _GroupByAccessor(accessor_cls))
