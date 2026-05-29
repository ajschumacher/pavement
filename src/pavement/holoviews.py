"""
Interactive pavement plots for HoloViews.

The matplotlib renderer in the top-level package draws static artists.
This module builds the same pavement geometry as HoloViews elements, so
it renders through any HoloViews backend — ``bokeh`` and ``plotly`` for
interactivity (hover, pan, zoom, legends), or ``matplotlib`` for a
static image. Backend-specific styling (fill colors, the hover tool) is
resolved for whichever backend is active when the plot is *built*, so
select it with ``hv.extension(...)`` first, as usual.

A pavement row is built from three overlaid components: a borderless
`holoviews.Rectangles` of the equal-mass bins (a hover target carrying
each bin's value range and quantile band), and two `holoviews.Segments`
— the quantile ticks and the box edges. Keeping the lines separate from
the fill means the ticks and box share one consistent style; a repeated
quantile value (data piled up) simply extends its own tick into a
whisker, so every line is drawn exactly once. The ticks carry their own
hover, like a rug plot's.

The headline function is `pavement`, which mirrors the top-level
`pavement.plot`: it accepts a single dataset, a wide list of datasets,
or tidy data plus *categories*, and returns a HoloViews object. Because
the result is a plain HoloViews element, framework features compose on
top of it — overlay it on a scatter, adjoin it as a marginal with the
``<<`` operator, or split it by category into a colored, legended
``NdOverlay``. To adjoin pavements as joint-plot marginals, reach for
`with_marginals`, which places an x-marginal on top and a y-marginal on
the right with the correct orientation handled for you.

Examples
--------
>>> import holoviews as hv
>>> import pavement.holoviews as phv
>>> hv.extension('bokeh')                       # doctest: +SKIP
>>> phv.pavement([1, 2, 3, 4, 5])               # doctest: +SKIP
>>> phv.pavement(values, categories=labels)     # doctest: +SKIP
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Sequence
from numbers import Integral, Number
from typing import Any, Literal

import holoviews as hv

from . import pavement_stats

__all__ = ["pavement_elements", "pavement", "with_marginals"]

# Hover dimensions: a fill bin reports its value range and quantile
# band; a tick reports its value and the cumulative quantile there.
_FILL_VDIMS = ["low", "high", "band"]
_TICK_VDIMS = ["value", "level"]

# Each backend names the same style differently; map them so one call
# styles correctly whichever backend is active when it runs. The fills
# are borderless Rectangles (line width 0); the ticks and box edges are
# Segments, which don't even share a line-color keyword with Rectangles
# on matplotlib, so they get separate maps.
_RECT_FILL_COLOR = {"bokeh": "fill_color", "matplotlib": "facecolor",
                    "plotly": "fillcolor"}
_RECT_FILL_ALPHA = {"bokeh": "fill_alpha", "matplotlib": "alpha",
                    "plotly": "opacity"}
_RECT_LINE_WIDTH = {"bokeh": "line_width", "matplotlib": "linewidth",
                    "plotly": "line_width"}
_SEG_LINE_COLOR = {"bokeh": "line_color", "matplotlib": "color",
                   "plotly": "line_color"}


def _default_palette() -> list[str]:
    """HoloViews' own default color cycle.

    HoloViews auto-cycles this for the elements that support it (Scatter,
    Curve, ...) but not for Rectangles, so we apply it ourselves. Sharing
    the exact cycle means a default-colored pavement's groups match a
    default-colored main plot's groups, in the same key order — on every
    backend, since this cycle is backend-independent.
    """
    return list(hv.Cycle().values)


def _perp(position: float, reach: float, value: float,
          orientation: str) -> tuple[float, float, float, float]:
    """A segment crossing the value axis at *value*, ``reach`` to each side."""
    if orientation == "vertical":
        return (position - reach, value, position + reach, value)
    return (value, position - reach, value, position + reach)


def _row_geometry(
    values: Sequence[float],
    position: float,
    width: float,
    orientation: Literal["vertical", "horizontal"],
    whisker_extent: float,
    show_whiskers: bool,
    group: Hashable | None,
) -> tuple[list[tuple], list[tuple], list[tuple]]:
    """Build the (fill, tick, box-edge) tuples for one row.

    Returns ``(fills, ticks, edges)``. A fill is
    ``(x0, y0, x1, y1, low, high, band[, group])``; a tick is
    ``(x0, y0, x1, y1, value, level[, group])``; an edge is
    ``(x0, y0, x1, y1)``.

    Each distinct quantile value gets exactly one tick — reaching past
    the box (a whisker) where the value repeats — so every line is drawn
    once and shares one style, rather than stacking a whisker on top of a
    bin border.
    """
    n_bins = len(values) - 1
    half = width / 2
    extra = () if group is None else (group,)

    # Fills: one borderless rectangle per equal-mass bin.
    fills: list[tuple] = []
    for i, (low, high) in enumerate(zip(values, values[1:])):
        band = f"{i/n_bins:.0%}–{(i+1)/n_bins:.0%}" if n_bins else ""
        if orientation == "vertical":
            box = (position - half, low, position + half, high)
        else:
            box = (low, position - half, high, position + half)
        fills.append((*box, low, high, band, *extra))

    # Ticks: one per distinct value (values are sorted, so equal ones are
    # adjacent). A repeated value spans levels i..j and gets a whisker.
    ticks: list[tuple] = []
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[j + 1] == values[i]:
            j += 1
        repeated = j > i
        reach = half + (whisker_extent if show_whiskers and repeated else 0)
        if not n_bins:
            level = ""
        elif repeated:
            level = f"{i/n_bins:.0%}–{j/n_bins:.0%}"
        else:
            level = f"{i/n_bins:.0%}"
        seg = _perp(position, reach, values[i], orientation)
        ticks.append((*seg, values[i], level, *extra))
        i = j + 1

    # Box edges: the two long sides, spanning the full value range.
    low, high = values[0], values[-1]
    if orientation == "vertical":
        edges = [(position - half, low, position - half, high),
                 (position + half, low, position + half, high)]
    else:
        edges = [(low, position - half, high, position - half),
                 (low, position + half, high, position + half)]
    return fills, ticks, edges


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
) -> dict[str, Any]:
    """
    Build the raw HoloViews elements for a single pavement row.

    The lower-level companion to `pavement`: it computes one row's
    quantile values and returns the unstyled component elements, leaving
    styling, overlaying, and axis labelling to the caller. `pavement`
    wraps this.

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
        If given, added as a ``group`` value dimension on the fills and
        ticks so it shows on hover and can drive coloring.

    Returns
    -------
    dict
        Maps component name to the unstyled HoloViews element:

        - ``"fill"``: a `holoviews.Rectangles` of the equal-mass bins,
          with value dimensions ``low``, ``high``, ``band`` (and
          ``group`` if given). Meant to be drawn borderless, as a hover
          target behind the lines.
        - ``"ticks"``: a `holoviews.Segments`, one tick per distinct
          quantile value (extended into a whisker where the value
          repeats), with value dimensions ``value``, ``level`` (and
          ``group`` if given).
        - ``"box"``: a `holoviews.Segments` of the two long box edges.

    See Also
    --------
    pavement : The headline, multi-row function built on this.
    pavement.pavement_stats : The underlying quantile computation.
    """
    values = pavement_stats(data, bins=bins, weights=weights)
    fills, ticks, edges = _row_geometry(
        values, position, width, orientation,
        whisker_extent, show_whiskers, group)
    fill_vdims = _FILL_VDIMS if group is None else [*_FILL_VDIMS, "group"]
    tick_vdims = _TICK_VDIMS if group is None else [*_TICK_VDIMS, "group"]
    return {
        "fill": hv.Rectangles(fills, vdims=fill_vdims),
        "ticks": hv.Segments(ticks, vdims=tick_vdims),
        "box": hv.Segments(edges),
    }


def _hover_tooltips(element: Any, candidates: tuple[str, ...]) -> list[str]:
    """The element's own vdims among *candidates*, so hover skips x0/y0/x1/y1."""
    names = [d.name for d in element.vdims]
    return [name for name in candidates if name in names]


def _style(element: Any, role: str, color: str, fill_alpha: float,
           hover: bool) -> Any:
    """Apply per-backend styling for one component (fill / ticks / box)."""
    backend = hv.Store.current_backend
    opts: dict[str, Any] = {}
    if role == "fill":
        if backend in _RECT_FILL_COLOR:
            opts[_RECT_FILL_COLOR[backend]] = color
            opts[_RECT_FILL_ALPHA[backend]] = fill_alpha
            opts[_RECT_LINE_WIDTH[backend]] = 0  # borderless; lines are Segments
        # Hover is interactive-backend only; matplotlib silently has none.
        if hover and backend == "bokeh":
            opts["hover_tooltips"] = _hover_tooltips(
                element, ("band", "low", "high", "group"))
    else:  # "ticks" or "box": Segments lines, styled identically
        if backend in _SEG_LINE_COLOR:
            opts[_SEG_LINE_COLOR[backend]] = color
        if role == "ticks" and hover and backend == "bokeh":
            opts["hover_tooltips"] = _hover_tooltips(
                element, ("value", "level", "group"))
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
        Defaults to HoloViews' own color cycle, so a category-split
        pavement's groups match a default-colored main plot's groups
        (in the same key order) when used as a marginal.
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
        palette = _default_palette()
        colors = [palette[i % len(palette)] for i in range(n)]
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
        els = pavement_elements(
            dataset, bins=b, weights=w, position=pos, width=width,
            whisker_extent=whisker_extent, show_whiskers=show_whiskers,
            orientation=orientation, group=label if n > 1 else None)
        # Fill behind (hover target), then the box edges, then the ticks.
        rows[label] = hv.Overlay([
            _style(els[role], role, col, fill_alpha, hover)
            for role in ("fill", "box", "ticks")])

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


def with_marginals(
    main: Any,
    x: Sequence[float] | None = None,
    y: Sequence[float] | None = None,
    categories: Sequence[Hashable] | None = None,
    x_label: str = "x",
    y_label: str = "y",
    **kwargs: Any,
) -> Any:
    """
    Adjoin pavement marginals to a plot — x on top, y on the right.

    A one-call joint-plot helper that hides the two things you would
    otherwise have to know to adjoin a pavement with HoloViews' ``<<``
    operator: that each marginal must be built with
    ``orientation='horizontal'`` (HoloViews orients each adjoined slot to
    share the main plot's axis), and that ``<<`` fills the right slot
    before the top. Pass the marginal data and it places them correctly.

    With *categories*, each marginal is split by category; leaving
    *color* at its default (see `pavement`) makes the groups match a
    default-colored *main* plot, so a colored scatter and its marginals
    share one color scheme for free.

    Parameters
    ----------
    main : holoviews object
        The central plot, e.g. a `holoviews.Scatter` or an
        ``NdOverlay`` of them.
    x, y : sequence of float, optional
        Data for the top (x) and right (y) marginals. Provide either or
        both; at least one is required. For a category split, these are
        the per-point x and y values in tidy form, parallel to
        *categories*.
    categories : sequence, optional
        Category label per point, parallel to *x* and *y*. Splits each
        marginal by category, as in `pavement`.
    x_label, y_label : str, default: 'x', 'y'
        Value-axis labels for the top and right marginals.
    **kwargs
        Forwarded to `pavement` for both marginals (e.g. *bins*,
        *color*, *fill_alpha*, *show_whiskers*). *orientation* is set
        automatically and must not be passed.

    Returns
    -------
    holoviews.AdjointLayout
        *main* with the requested marginals adjoined.

    Raises
    ------
    ValueError
        If neither *x* nor *y* is given, or if *orientation* is passed
        in *kwargs* (it is chosen automatically).

    See Also
    --------
    pavement : Builds each marginal; call it directly for finer control.

    Examples
    --------
    >>> import pavement.holoviews as phv
    >>> scatter = hv.NdOverlay(...)                          # doctest: +SKIP
    >>> phv.with_marginals(scatter, x=xs, y=ys,
    ...                    categories=groups)                # doctest: +SKIP
    """
    if x is None and y is None:
        raise ValueError("provide x and/or y data for the marginals")
    if "orientation" in kwargs:
        raise ValueError(
            "orientation is chosen automatically by with_marginals; "
            "call pavement directly if you need to set it")

    def strip(data: Sequence[float], label: str) -> Any:
        return pavement(data, categories=categories, orientation="horizontal",
                        value_label=label, **kwargs)

    layout = main
    # `<<` fills the right slot first, then the top. Add y (right) before
    # x (top); for an x-only marginal, hold the right slot open with an
    # Empty so x still lands on top rather than the right.
    if y is not None:
        layout = layout << strip(y, y_label)
    elif x is not None:
        layout = layout << hv.Empty()
    if x is not None:
        layout = layout << strip(x, x_label)
    return layout
