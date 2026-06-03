"""
Backend-agnostic pavement geometry and input handling.

The shared kernel every renderer (`pavement.matplotlib`,
`pavement.holoviews`, `pavement.plotly`, `pavement.bokeh`) translates into
its own glyphs. Keeping the geometry, the single/wide/tidy input
expansion, the argument broadcasting, the hover-text formatting, and the
color resolution here — computed once and tested once — is what keeps the
backends from drifting apart.

The centerpiece is `row_spec`, which turns one row's sorted quantile
values into a `RowSpec`: the equal-mass bins and the quantile ticks, each
carrying the display strings every backend shows on hover, plus the
perpendicular geometry (center *position* and *half* width). A `RowSpec`
holds value-axis coordinates and a center position; `place` and the
``*_segment`` / ``bin_*`` helpers map those onto screen ``(x, y)`` for a
given *orientation*, so the orientation branch lives here once rather than
in every backend.

Nothing here imports a plotting library.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Any, Callable, Literal

Orientation = Literal["vertical", "horizontal"]


def fmt(value: float) -> str:
    """Format a value for hover: concise, 3 significant figures.

    The default `ValueFormat`: every backend's hover runs each value
    through one of these before display, and a caller can pass their own
    (e.g. ``lambda v: f"${v:,.2f}"``) to override it.
    """
    return f"{float(value):.3g}"


def pct(count: int, total: int) -> str:
    """Format a share as a whole-percent string for a hover line.

    A nonzero share that would round down to ``0%`` shows ``<1%`` instead,
    so a real-but-tiny slice (a stray value among thousands) never reads as
    nothing. Shared by every hover that reports a count's share — the
    pavement bins/ticks here and the tally/proportion strips in
    `pavement.svg` — so they round and render percentages identically.
    """
    frac = count / total
    if 0 < frac < 0.005:
        return "<1%"
    return f"{frac:.0%}"


# A caller-supplied value formatter: maps one numeric value to its hover
# display string. The package threads one of these from each backend's
# public functions down into `row_spec`, defaulting to `fmt`. It formats
# only the *values* (a tick's value, a bin's low/high) — never the
# quantile/percent strings, which aren't data values.
ValueFormat = Callable[[float], str]


# ---------------------------------------------------------------------------
# Row geometry
# ---------------------------------------------------------------------------

@dataclass
class Bin:
    """One equal-mass bin: a value-axis span plus its hover strings."""
    low: float            # value-axis low edge
    high: float           # value-axis high edge
    band: str             # percentile-band hover string, e.g. "p0 to p25"
    value_range: str      # value-range hover string, e.g. "1 to 2"
    count: str = ""       # count hover string, e.g. "15% (3 of 20 values)"
                          # (the data strictly inside the bin, and its share);
                          # "" if not computed


@dataclass
class Tick:
    """One quantile tick: a value plus how far it reaches and its hover."""
    value: float          # value-axis position of the tick
    reach: float          # half-extent on the perpendicular axis (a whisker
                          # when it exceeds the row half-width)
    quantile: str         # percentile hover string ("p25" or "p25 to p50")
    value_str: str        # value hover string
    count: str = ""       # count hover string, e.g. "25% (5 of 20 values)"
                          # (the data exactly at this value, and its share);
                          # "" if not computed


@dataclass
class RowSpec:
    """One pavement row's precomputed, orientation-free geometry."""
    bins: list[Bin]
    ticks: list[Tick]
    position: float       # center on the axis perpendicular to the value axis
    half: float           # half the row width
    orientation: Orientation
    value_low: float      # value-axis extent of the box (= values[0])
    value_high: float     # = values[-1]


def row_spec(
    values: Sequence[float],
    position: float = 1,
    width: float = 0.6,
    orientation: Orientation = "vertical",
    whisker_extent: float = 0.1,
    show_whiskers: bool = True,
    value_format: ValueFormat | None = None,
    data: Sequence[float] | None = None,
) -> RowSpec:
    """
    Build one row's `RowSpec` from sorted quantile *values*.

    *values* is the output of `pavement.core.pavement_stats`: ``bins + 1``
    ascending quantile values, or every data point for a rug. There is one
    bin per consecutive pair, and one tick per *distinct* value — a tick
    whose value repeats reaches past the box as a whisker, so every line is
    drawn exactly once rather than stacking a whisker on a bin border.

    *value_format* maps a value to its hover display string (a bin's value
    range, a tick's value); it defaults to `fmt`. The quantile/percent
    strings are unaffected, as they aren't data values.

    *data*, if given, is the raw values the plot is drawn from — the
    non-missing values, of which there are ``len(data)``. When present, each
    bin and tick gets a ``count`` hover string, ``"P% (X of Y values)"``,
    where Y is ``len(data)``, X is how many data points fall *strictly
    inside* the bin (low < d < high) or fall *exactly* at the tick's value,
    and P is that share. Every data point lands in exactly one bin or tick —
    a point on a bin edge is the edge's tick, never either neighbouring bin —
    so the counts (and shares) partition the data. Counts are unweighted,
    even when *values* came from weighted quantiles.

    Percentile cut points are rendered ``"pNN"`` (a bin spans ``"p0 to
    p25"``, a tick sits at ``"p25"``, a repeated tick spans ``"p25 to
    p50"``), distinct from the count's ``"P%"`` share.
    """
    show = value_format or fmt
    n_bins = len(values) - 1
    half = width / 2

    ordered = sorted(data) if data is not None else None
    total = len(ordered) if ordered is not None else 0

    def pctl(frac: float) -> str:
        """A percentile cut point, e.g. 0.25 -> ``"p25"``."""
        return f"p{frac * 100:.0f}"

    def count(lo: float | None, hi: float | None, value: float | None) -> str:
        """The ``"P% (X of Y values)"`` line: a strict ``lo``..``hi`` interior
        (a bin) or an exact ``value`` match (a tick). Empty without *data*."""
        if ordered is None:
            return ""
        if value is not None:
            x = bisect_right(ordered, value) - bisect_left(ordered, value)
        else:
            # The open interval (lo, hi); a zero-width bin (lo == hi, from a
            # repeated quantile value) has no strict interior, so clamp the
            # otherwise-negative difference to 0.
            x = max(0, bisect_left(ordered, hi) - bisect_right(ordered, lo))
        noun = 'value' if total == 1 else 'values'
        return f"{pct(x, total)} ({x:,} of {total:,} {noun})"

    bins: list[Bin] = []
    for i, (low, high) in enumerate(zip(values, values[1:])):
        band = f"{pctl(i/n_bins)} to {pctl((i+1)/n_bins)}" if n_bins else ""
        bins.append(Bin(low, high, band, f"{show(low)} to {show(high)}",
                        count(low, high, None)))

    ticks: list[Tick] = []
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[j + 1] == values[i]:
            j += 1
        repeated = j > i
        reach = half + (whisker_extent if show_whiskers and repeated else 0)
        if not n_bins:
            quantile = ""
        elif repeated:
            quantile = f"{pctl(i/n_bins)} to {pctl(j/n_bins)}"
        else:
            quantile = pctl(i/n_bins)
        ticks.append(Tick(values[i], reach, quantile, show(values[i]),
                          count(None, None, values[i])))
        i = j + 1

    return RowSpec(bins=bins, ticks=ticks, position=position, half=half,
                   orientation=orientation,
                   value_low=values[0], value_high=values[-1])


# ---------------------------------------------------------------------------
# Orientation: map (perpendicular-axis, value-axis) coords onto (x, y)
# ---------------------------------------------------------------------------

def place(perp: float, value: float,
          orientation: Orientation) -> tuple[float, float]:
    """Map a (perpendicular-axis, value-axis) coordinate to ``(x, y)``.

    For ``'vertical'`` the value axis is y, so ``(perp, value)``; for
    ``'horizontal'`` it is x, so ``(value, perp)``. Building every shape
    through this keeps the two orientations exact transposes of each
    other.
    """
    return (perp, value) if orientation == "vertical" else (value, perp)


def tick_segment(position: float, reach: float, value: float,
                 orientation: Orientation) -> tuple[float, float, float, float]:
    """A tick/whisker segment crossing the value axis at *value*.

    Runs perpendicular to the value axis, ``reach`` to each side of
    *position*. Returns ``(x0, y0, x1, y1)``.
    """
    x0, y0 = place(position - reach, value, orientation)
    x1, y1 = place(position + reach, value, orientation)
    return x0, y0, x1, y1


def box_edges(position: float, half: float, low: float, high: float,
              orientation: Orientation) -> list[tuple[float, float, float, float]]:
    """The two long box edges, each spanning *low*..*high* along the value axis."""
    edges = []
    for side in (position - half, position + half):
        x0, y0 = place(side, low, orientation)
        x1, y1 = place(side, high, orientation)
        edges.append((x0, y0, x1, y1))
    return edges


def resolve_show_box(show_box: bool | None, bins: int | None) -> bool:
    """Whether to draw a row's box edges (the long sides parallel to the
    value axis), given the *show_box* override and the row's *bins*.

    The two long edges are what visually distinguish a binned pavement from
    a plain rug: dropping them leaves only the value ticks, so a rug
    (``bins=None``) reads like an ordinary rug plot and the presence of the
    box signals "these are quantiles, not raw points". So the default
    (``show_box=None``) draws the box for a binned row and omits it for a
    rug; an explicit ``True``/``False`` overrides that either way.
    """
    return bins is not None if show_box is None else show_box


def bin_corners(low: float, high: float, position: float, half: float,
                orientation: Orientation) -> tuple[tuple[float, float],
                                                    tuple[float, float]]:
    """The two opposite corners ``((x0, y0), (x1, y1))`` of a bin rectangle."""
    return (place(position - half, low, orientation),
            place(position + half, high, orientation))


def bin_polygon(low: float, high: float, position: float, half: float,
                orientation: Orientation) -> tuple[list[float], list[float]]:
    """A bin rectangle as a closed polygon path ``(xs, ys)``.

    Built in (perpendicular, value) space then mapped through `place`, so
    the path stays a simple closed rectangle in either orientation (and an
    exact transpose between them).
    """
    perp = [position - half, position + half, position + half,
            position - half, position - half]
    val = [low, low, high, high, low]
    pts = [place(p, v, orientation) for p, v in zip(perp, val)]
    return [x for x, _ in pts], [y for _, y in pts]


# ---------------------------------------------------------------------------
# Input handling shared by every backend's headline function
# ---------------------------------------------------------------------------

def normalize_rows(
    data: Any,
    weights: Any,
    categories: Sequence[Hashable] | None,
    labels: Sequence[Hashable] | None,
) -> tuple[list[list[float]], list[Any], list[Hashable], bool]:
    """Resolve the single/wide/tidy input shapes into per-row lists.

    Returns ``(data_rows, weight_rows, labels, labelled)``. *labelled*
    records whether the rows are nameable (categories or explicit labels
    were given), so the caller knows whether to tick the position axis.
    """
    labelled = labels is not None or categories is not None
    if categories is not None:
        if labels is None:
            labels = sorted(set(categories))
        data = [[d for d, c in zip(data, categories) if c == label]
                for label in labels]
        empty = [label for label, row in zip(labels, data) if not row]
        if empty:
            raise ValueError(
                f"no data for categor{'y' if len(empty) == 1 else 'ies'} "
                f"{', '.join(map(repr, empty))}")
        if weights is not None:
            weights = [[w for w, c in zip(weights, categories) if c == label]
                       for label in labels]
    data = list(data)
    if len(data) == 0:
        raise ValueError("data must be non-empty")
    if not hasattr(data[0], "__iter__"):
        data = [data]
        weights = [weights] if weights is not None else None
    n = len(data)
    if labels is None:
        labels = list(range(1, n + 1))
    elif len(labels) != n:
        raise ValueError(f"labels has length {len(labels)}, expected {n}")
    weight_rows = list(weights) if weights is not None else [None] * n
    return data, weight_rows, list(labels), labelled


def broadcast(value: Any, n: int, name: str,
              is_scalar: Callable[[Any], bool]) -> list[Any]:
    """Expand a scalar to *n* copies, or validate a length-*n* sequence."""
    if is_scalar(value):
        return [value] * n
    if len(value) != n:
        raise ValueError(f"{name} has length {len(value)}, expected {n}")
    return list(value)


def resolve_colors(color: str | Sequence[str] | None, n: int,
                   default: Callable[[int], list[str]]) -> list[str]:
    """Per-row colors: the *default* palette, one shared color, or a sequence."""
    if color is None:
        return default(n)
    return broadcast(color, n, "color", lambda v: isinstance(v, str))


# ---------------------------------------------------------------------------
# Hover layout and marginal color matching, shared across backends
# ---------------------------------------------------------------------------

def hover_fields(has_group: bool) -> list[str]:
    """The hover field order every backend renders: group?, value, percentile, count."""
    return (["group"] if has_group else []) + ["values", "quantiles", "counts"]


def complete_color_map(
    found: dict[Hashable, str],
    labels: Sequence[Hashable],
    default: Callable[[int], list[str]],
) -> dict[Hashable, str]:
    """Fill in a partial label->color map from *default*, skipping used colors.

    *found* holds the colors already read off a main plot (by the backend,
    whose object model differs). Labels it doesn't cover fall back to the
    *default* palette, in label order, skipping colors already claimed — so
    a scatter and its marginals stay matched group for group.
    """
    fallback = iter(c for c in default(len(labels)) if c not in found.values())
    # Only un-found labels draw from the fallback (the conditional keeps
    # next() out of the found branch, so a found label can't consume a
    # color a later un-found one needs).
    return {label: found[label] if label in found else next(fallback, default(1)[0])
            for label in labels}
