"""
Interactive pavement plots for HoloViews.

The matplotlib renderer in the top-level package draws static artists.
This module builds the same pavement geometry as HoloViews elements, so
it renders through any HoloViews backend — ``bokeh`` and ``plotly`` for
interactivity (hover, pan, zoom, legends), or ``matplotlib`` for a
static image. Backend-specific styling (fill colors, the hover tool) is
resolved for whichever backend is active when the plot is *built*, so
select it with ``hv.extension(...)`` first, as usual.

A pavement row is a stack of equal-mass bins, drawn here as a
`holoviews.Rectangles`: every bin is one rectangle, so the shared bin
borders *are* the quantile ticks and the outermost borders *are* the box
outline — all for free, and every bin is a hover target carrying its
value range and quantile band. Repeated quantile values (data piled up)
get whisker marks as a `holoviews.Segments` overlay, mirroring the
matplotlib renderer.

The headline function is `pavement`, which mirrors the top-level
`pavement.plot`: it accepts a single dataset, a wide list of datasets,
or tidy data plus *categories*, and returns a HoloViews object. Because
the result is a plain HoloViews element, framework features compose on
top of it — overlay it on a scatter, adjoin it as a marginal with the
``<<`` operator, or split it by category into a colored, legended
``NdOverlay``.

Examples
--------
>>> import holoviews as hv
>>> import pavement.holoviews as phv
>>> hv.extension('bokeh')                       # doctest: +SKIP
>>> phv.pavement([1, 2, 3, 4, 5])               # doctest: +SKIP
>>> phv.pavement(values, categories=labels)     # doctest: +SKIP
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Iterable, Sequence
from numbers import Integral, Number
from typing import Any, Literal

import holoviews as hv

from . import pavement_stats

__all__ = ["pavement_elements", "pavement"]

# A bin's value range and quantile band, shown on hover.
_VDIMS = ["low", "high", "band"]

# Each backend names the same style differently; map them so one call
# styles correctly whichever backend is active when it runs. Rectangles
# and Segments don't even share a line-color keyword on matplotlib, so
# they get separate maps.
_RECT_FILL_COLOR = {"bokeh": "fill_color", "matplotlib": "facecolor",
                    "plotly": "fillcolor"}
_RECT_LINE_COLOR = {"bokeh": "line_color", "matplotlib": "edgecolor",
                    "plotly": "line_color"}
_RECT_FILL_ALPHA = {"bokeh": "fill_alpha", "matplotlib": "alpha",
                    "plotly": "opacity"}
_SEG_LINE_COLOR = {"bokeh": "line_color", "matplotlib": "color",
                   "plotly": "line_color"}

# Default per-row color cycle (matplotlib's "tab10"), so categories are
# distinguishable across backends without depending on a backend's own
# cycling of overlay elements.
_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


def _row_geometry(
    values: Sequence[float],
    position: float,
    width: float,
    orientation: Literal["vertical", "horizontal"],
    whisker_extent: float,
    show_whiskers: bool,
    group: Hashable | None,
) -> tuple[list[tuple], list[tuple]]:
    """Build the (rectangle, whisker-segment) tuples for one row.

    Returns ``(rects, segments)``. Each rectangle is
    ``(x0, y0, x1, y1, low, high, band[, group])``; each segment is
    ``(x0, y0, x1, y1)``.
    """
    n_bins = len(values) - 1
    half = width / 2
    rects: list[tuple] = []
    for i, (low, high) in enumerate(zip(values, values[1:])):
        band = f"{i/n_bins:.0%}–{(i+1)/n_bins:.0%}" if n_bins else ""
        if orientation == "vertical":
            box = (position - half, low, position + half, high)
        else:
            box = (low, position - half, high, position + half)
        extra = (low, high, band) if group is None else (low, high, band, group)
        rects.append((*box, *extra))

    segments: list[tuple] = []
    if show_whiskers:
        reach = half + whisker_extent
        for value, count in Counter(values).items():
            if count > 1:
                if orientation == "vertical":
                    segments.append(
                        (position - reach, value, position + reach, value))
                else:
                    segments.append(
                        (value, position - reach, value, position + reach))
    return rects, segments


def pavement_elements(
    data: Iterable[float],
    bins: int | None = 4,
    weights: Sequence[float] | None = None,
    position: float = 1,
    width: float = 0.6,
    whisker_extent: float = 0.1,
    show_whiskers: bool = True,
    orientation: Literal["vertical", "horizontal"] = "vertical",
    group: Hashable | None = None,
) -> tuple[Any, Any]:
    """
    Build the raw HoloViews elements for a single pavement row.

    The lower-level companion to `pavement`: it computes one row's
    quantile values and returns the unstyled
    ``(Rectangles, Segments | None)`` pair, leaving styling, overlaying,
    and axis labelling to the caller. `pavement` wraps this.

    Parameters
    ----------
    data : iterable of float
        The values to summarize.
    bins : int or None, default: 4
        Number of equal-mass bins, or None to show every data point (a
        rug). Passed to `pavement.pavement_stats`.
    weights : sequence of float, optional
        Positive weights parallel to *data*.
    position : float, default: 1
        Center of the row on the axis perpendicular to the value axis.
    width : float, default: 0.6
        Thickness of the row.
    whisker_extent : float, default: 0.1
        How far whisker marks extend beyond the box at repeated values.
    show_whiskers : bool, default: True
        Whether to draw whisker marks at repeated quantile values.
    orientation : {'vertical', 'horizontal'}, default: 'vertical'
        Direction of the value axis. 'vertical' puts values on the
        y-axis; 'horizontal' puts them on the x-axis.
    group : hashable, optional
        If given, added as a ``group`` value dimension on every
        rectangle so it shows on hover and can drive coloring.

    Returns
    -------
    tuple
        ``(rectangles, segments)``. *rectangles* is a
        `holoviews.Rectangles` of the equal-mass bins, with value
        dimensions ``low``, ``high``, ``band`` (and ``group`` if given).
        *segments* is a `holoviews.Segments` of whisker marks, or None
        if none were drawn.

    See Also
    --------
    pavement : The headline, multi-row function built on this.
    pavement.pavement_stats : The underlying quantile computation.
    """
    values = pavement_stats(data, bins=bins, weights=weights)
    rects, segments = _row_geometry(
        values, position, width, orientation,
        whisker_extent, show_whiskers, group)
    vdims = _VDIMS if group is None else [*_VDIMS, "group"]
    rectangles = hv.Rectangles(rects, vdims=vdims)
    whiskers = hv.Segments(segments) if segments else None
    return rectangles, whiskers


def _style(element: Any, color: str, fill_alpha: float, hover: bool) -> Any:
    """Apply per-backend fill/line styling (and a hover tool) to an element."""
    backend = hv.Store.current_backend
    opts: dict[str, Any] = {}
    if isinstance(element, hv.Rectangles):
        if backend in _RECT_LINE_COLOR:
            opts[_RECT_LINE_COLOR[backend]] = color
            opts[_RECT_FILL_COLOR[backend]] = color
            opts[_RECT_FILL_ALPHA[backend]] = fill_alpha
        # Hover is interactive-backend only; matplotlib silently has none.
        # Name the meaningful dimensions so the tooltip shows the band
        # and value range, not the raw x0/y0/x1/y1 corners.
        if hover and backend == "bokeh":
            names = [d.name for d in element.vdims]
            opts["hover_tooltips"] = [
                name for name in ("band", "low", "high", "group")
                if name in names]
    else:  # Segments (whiskers)
        if backend in _SEG_LINE_COLOR:
            opts[_SEG_LINE_COLOR[backend]] = color
    return element.opts(**opts)


def pavement(
    data: Sequence[float] | Sequence[Iterable[float]],
    weights: Sequence[float] | Sequence[Sequence[float]] | None = None,
    positions: Sequence[float] | None = None,
    categories: Sequence[Hashable] | None = None,
    labels: Sequence[Hashable] | None = None,
    bins: int | None | Sequence[int | None] = 4,
    widths: float | Sequence[float] = 0.6,
    whisker_extent: float = 0.1,
    show_whiskers: bool = True,
    orientation: Literal["vertical", "horizontal"] = "vertical",
    value_label: str = "value",
    color: str | Sequence[str] | None = None,
    fill_alpha: float = 0.3,
    hover: bool = True,
) -> Any:
    """
    Build an interactive pavement plot as a HoloViews object.

    The HoloViews counterpart of `pavement.plot`. Accepts the same three
    input shapes — a single 1D dataset, a wide sequence of datasets, or
    tidy data plus *categories* — and returns a HoloViews object that
    renders through any backend.

    A single dataset returns a `holoviews.Overlay` (the bins, plus any
    whiskers). Multiple rows return a `holoviews.NdOverlay` keyed by
    *labels*, which gives a legend and a consistent per-row color cycle;
    in tidy form this is the "split by category" case. Either result is
    a plain HoloViews object, so it composes with the framework: overlay
    it with ``*``, adjoin it as a marginal with ``<<``, or restyle it
    with ``.opts``.

    Parameters
    ----------
    data : sequence of float, or sequence of iterables of float
        The values to plot. Shape determines the mode, as in
        `pavement.plot`.
    weights : sequence, optional
        Positive weights, matching the shape of *data*.
    positions : sequence of float, optional
        Position of each row on the axis perpendicular to the value
        axis. Defaults to ``[1, 2, ..., N]``.
    categories : sequence, optional
        Category label per entry in *data* (tidy/long form). If given,
        *data* is split by category.
    labels : sequence, optional
        One label per row, used as the legend key and color order. In
        tidy form, also selects which categories to include and their
        order. Defaults to ``[1, 2, ..., N]`` (wide) or the sorted
        categories (tidy).
    bins : int, None, or sequence, default: 4
        Equal-mass bins per row; None shows all the data (a rug). A
        scalar applies to every row; a sequence sets each row and may
        mix None with integers. See `pavement.pavement_stats`.
    widths : float or sequence of float, default: 0.6
        Thickness of each row.
    whisker_extent : float, default: 0.1
        How far whisker marks extend beyond the box.
    show_whiskers : bool, default: True
        Whether to draw whisker marks at repeated quantile values.
    orientation : {'vertical', 'horizontal'}, default: 'vertical'
        Direction of the value axis.
    value_label : str, default: 'value'
        Axis label for the value axis (x for horizontal, y otherwise).
    color : str or sequence of str, optional
        Per-row color(s). A single color applies to every row; a
        sequence sets each row and must match the number of rows.
        Defaults to a ten-color cycle.
    fill_alpha : float, default: 0.3
        Opacity of the bin fills. Bin borders (the ticks and box) are
        drawn opaque.
    hover : bool, default: True
        Whether to enable a hover tool (bokeh only; plotly hovers by
        default, matplotlib has none).

    Returns
    -------
    holoviews.Overlay or holoviews.NdOverlay
        An ``Overlay`` for a single dataset, or an ``NdOverlay`` keyed
        by *labels* for multiple rows.

    Raises
    ------
    ValueError
        If *data* is empty; if *positions*, *bins*, *widths*, *color*,
        or *labels* is given as a sequence of the wrong length; or for
        any reason raised by `pavement.pavement_stats`.

    See Also
    --------
    pavement.plot : The matplotlib equivalent.
    pavement_elements : The single-row element builder this wraps.

    Examples
    --------
    >>> import holoviews as hv
    >>> import pavement.holoviews as phv
    >>> hv.extension('bokeh')                              # doctest: +SKIP
    >>> phv.pavement([1, 2, 3, 4, 5])                      # doctest: +SKIP

    Split tidy data by category, then adjoin it as a top marginal::

        main = hv.Scatter((x, y))
        top = phv.pavement(x, categories=group, orientation='horizontal')
        layout = main << top                               # doctest: +SKIP
    """
    # Whether to label the position axis with per-row ticks: only when
    # the rows mean something nameable (categories or explicit labels),
    # not for an anonymous single row at position 1.
    labelled = labels is not None or categories is not None
    if categories is not None:
        if labels is None:
            labels = sorted(set(categories))
        data = [[d for d, c in zip(data, categories) if c == label]
                for label in labels]
        if weights is not None:
            weights = [[w for w, c in zip(weights, categories) if c == label]
                       for label in labels]
    if len(data) == 0:
        raise ValueError("data must be non-empty")
    if not hasattr(data[0], "__iter__"):
        data = [data]
        weights = [weights] if weights is not None else None
    n = len(data)

    if positions is None:
        positions = list(range(1, n + 1))
    elif len(positions) != n:
        raise ValueError(f"positions has length {len(positions)}, expected {n}")
    if bins is None or isinstance(bins, Integral):
        bins = [bins] * n
    elif len(bins) != n:
        raise ValueError(f"bins has length {len(bins)}, expected {n}")
    if isinstance(widths, Number):
        widths = [widths] * n
    elif len(widths) != n:
        raise ValueError(f"widths has length {len(widths)}, expected {n}")
    if color is None:
        colors = [_PALETTE[i % len(_PALETTE)] for i in range(n)]
    elif isinstance(color, str):
        colors = [color] * n
    elif len(color) != n:
        raise ValueError(f"color has length {len(color)}, expected {n}")
    else:
        colors = list(color)
    if labels is None:
        labels = list(range(1, n + 1))
    elif len(labels) != n:
        raise ValueError(f"labels has length {len(labels)}, expected {n}")

    weight_iter = weights if weights is not None else [None] * n
    rows = {}
    for label, dataset, w, pos, b, width, col in zip(
            labels, data, weight_iter, positions, bins, widths, colors):
        rects, whiskers = pavement_elements(
            dataset, bins=b, weights=w, position=pos, width=width,
            whisker_extent=whisker_extent, show_whiskers=show_whiskers,
            orientation=orientation, group=label if n > 1 else None)
        parts = [_style(rects, col, fill_alpha, hover)]
        if whiskers is not None:
            parts.append(_style(whiskers, col, fill_alpha, hover))
        rows[label] = hv.Overlay(parts)

    if n == 1:
        result = rows[labels[0]]
    else:
        result = hv.NdOverlay(rows, kdims="group")

    # Label the value axis; the perpendicular (position) axis carries
    # the row labels as ticks when the rows are nameable, else nothing —
    # its bare "x0"/"y0" dimension name is never meaningful here.
    value_axis = "x" if orientation == "horizontal" else "y"
    pos_axis = "y" if orientation == "horizontal" else "x"
    opts: dict[str, Any] = {f"{value_axis}label": value_label, f"{pos_axis}label": ""}
    if labelled:
        opts[f"{pos_axis}ticks"] = [
            (pos, str(label)) for pos, label in zip(positions, labels)]
    if n > 1:
        # matplotlib can't build a legend handle for Rectangles glyphs;
        # the legend is an interactive-backend (bokeh/plotly) feature.
        opts["show_legend"] = hv.Store.current_backend != "matplotlib"
    return result.opts(**opts)
