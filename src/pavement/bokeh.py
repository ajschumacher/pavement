"""
Interactive pavement plots for Bokeh.

The matplotlib renderer in the top-level package draws static artists, the
`pavement.holoviews` module builds backend-agnostic HoloViews elements, and
`pavement.plotly` targets Plotly directly. This module targets Bokeh in the
same spirit: it speaks Bokeh's own vocabulary — `bokeh.plotting.figure`,
glyphs backed by `~bokeh.models.ColumnDataSource`, a `~bokeh.models.HoverTool`
and an interactive `~bokeh.models.Legend` — and slots into a Bokeh workflow
with native hover, pan, zoom, and a clickable legend.

A pavement is a richer drop-in for a rug plot: where a rug draws one tick per
data point, a pavement bins the data into equal-mass quantile boxes (or, with
``bins=None``, falls back to a tick per point — a literal rug). The headline
use is the same place rugs show up most: as marginals on a scatter.
`with_marginals` arranges a scatter with pavement marginals on the top and
right, with their ranges linked to the scatter's, in one call.

Each pavement row is drawn with plain Bokeh glyphs, so it carries its own
hover and drops onto any figure:

- one borderless filled `quad <bokeh.plotting.figure.quad>` per equal-mass bin,
  hovering its quantile band and value range;
- a `segment <bokeh.plotting.figure.segment>` of quantile ticks (reaching past
  the box into a whisker where a value repeats, so every line is drawn once),
  each hovering its single quantile and value — the rug-style read; and
- a `segment <bokeh.plotting.figure.segment>` of the two box edges, purely
  visual, sharing the ticks' style.

Hover reads the same as the other backends: the box hover is a quantile band
and value range, the tick hover a single quantile and value (both led by the
row's name when it has one). Unlike Plotly's figure-level shapes, Bokeh glyphs
hover directly, so no invisible marker layer is needed.

The functions mirror the rest of the package:

- `pavement_glyphs` adds one row's glyphs to a figure (the low-level piece).
- `add_pavement` adds one or more rows — accepting a single dataset, a wide
  list of datasets, or tidy data plus *categories* — and wires up the shared
  hover and legend.
- `plot` builds a whole `~bokeh.plotting.figure`, the counterpart of
  `pavement.matplotlib.plot`, `pavement.holoviews.plot`, and `pavement.plotly.plot`.
- `with_marginals` builds a scatter-with-marginals joint plot.

Examples
--------
>>> import pavement.bokeh as pbk
>>> from bokeh.plotting import show
>>> show(pbk.plot([1, 2, 3, 4, 5]))                 # doctest: +SKIP
>>> show(pbk.plot(values, categories=labels))       # doctest: +SKIP
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Sequence
from numbers import Integral, Number
from typing import Any, Literal

from bokeh.layouts import gridplot
from bokeh.models import (
    ColumnDataSource,
    GlyphRenderer,
    HoverTool,
    Legend,
    LegendItem,
    Range1d,
)
from bokeh.palettes import Category10
from bokeh.plotting import figure

from .core import pavement_stats
from ._geometry import (
    bin_corners,
    box_edges,
    broadcast,
    complete_color_map,
    normalize_rows,
    resolve_colors,
    row_spec,
    tick_segment,
    ValueFormat,
)

__all__ = ["pavement_glyphs", "add_pavement", "plot", "with_marginals"]


def _default_colors(n: int) -> list[str]:
    """Bokeh's standard categorical palette, *n* entries.

    ``Category10`` is Bokeh's default qualitative palette (and matches
    matplotlib's ``tab10``); cycling it means a default-colored
    category-split pavement matches a scatter colored from the same palette
    group for group — handy when used as a marginal.
    """
    cycle = Category10[10]
    return [cycle[i % len(cycle)] for i in range(n)]


def _row_geometry(
    values: Sequence[float],
    position: float,
    width: float,
    orientation: Literal["vertical", "horizontal"],
    whisker_extent: float,
    show_whiskers: bool,
    value_format: ValueFormat | None,
) -> dict[str, Any]:
    """Build one row's bin rectangles, quantile ticks, and box edges.

    Returns a dict with:

    - ``bins``: one ``(left, right, bottom, top, band, value_range)`` per
      equal-mass bin — a `quad`'s extents plus its hover strings ("X% to Y%",
      "X to Y").
    - ``ticks``: one ``(x0, y0, x1, y1, quantile, value)`` per distinct
      quantile value — a segment crossing the value axis, plus its rug-style
      hover strings. A repeated value reaches past the box as a whisker and
      reads as a span ("X% to Y%"), so every line is drawn exactly once.
    - ``box``: the two long box edges as ``(x0, y0, x1, y1)`` segments,
      spanning the full value range.

    The shared `row_spec` does the binning and one-tick-per-distinct-value
    (whisker) logic; this lays the result out the way Bokeh's glyphs want.
    """
    spec = row_spec(values, position, width, orientation,
                    whisker_extent, show_whiskers, value_format)

    # Bins: one borderless quad per equal-mass bin (left, right, bottom,
    # top), carrying its quantile band and value range for hover.
    bins: list[tuple[float, float, float, float, str, str]] = []
    for b in spec.bins:
        (x0, y0), (x1, y1) = bin_corners(b.low, b.high, position, spec.half,
                                         orientation)
        bins.append((x0, x1, y0, y1, b.band, b.value_range))

    # Ticks: a segment per distinct value, reaching past the box as a
    # whisker where it repeats. Hover reads as a single quantile and value.
    ticks: list[tuple[float, float, float, float, str, str]] = []
    for t in spec.ticks:
        x0, y0, x1, y1 = tick_segment(position, t.reach, t.value, orientation)
        ticks.append((x0, y0, x1, y1, t.quantile, t.value_str))

    # Box edges: the two long sides, spanning the full value range.
    box = list(box_edges(position, spec.half, spec.value_low,
                         spec.value_high, orientation))

    return {"bins": bins, "ticks": ticks, "box": box}


def pavement_glyphs(
    fig: figure,
    data: Iterable[float],
    bins: int | None = 4,
    weights: Sequence[float] | None = None,
    position: float = 1,
    width: float = 0.6,
    whisker_extent: float = 0.1,
    show_whiskers: bool = True,
    orientation: Literal["vertical", "horizontal"] = "vertical",
    color: str | None = None,
    fill_alpha: float = 0.3,
    line_width: float = 1.0,
    name: Hashable | None = None,
    value_format: ValueFormat | None = None,
) -> dict[str, GlyphRenderer]:
    """
    Add a single pavement row's glyphs to a Bokeh figure.

    The low-level piece the rest of the module is built on: it computes one
    row's quantile values and draws them onto *fig* as Bokeh glyphs,
    returning the renderers. It draws only the glyphs — the shared hover
    tool and legend are figure-level concerns wired up by `add_pavement`, so
    reach for `plot` or `add_pavement` for the usual single/wide/tidy
    entry points and interactivity.

    Parameters
    ----------
    fig : bokeh.plotting.figure
        The figure to draw on. Mutated in place.
    data : iterable of float
        The values to summarize.
    bins : int or None, default: 4
        Number of equal-mass bins, or None to show every data point (a rug).
        Passed to `pavement.pavement_stats`.
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
        Direction of the value axis. 'vertical' puts values on the y-axis;
        'horizontal' puts them on the x-axis.
    color : str, optional
        Color of the lines and (translucent) fill. Defaults to the first
        Bokeh ``Category10`` color.
    fill_alpha : float, default: 0.3
        Opacity of the bin fills. The ticks and box are drawn opaque. Set to
        0 to omit the fills entirely.
    line_width : float, default: 1.0
        Width of the tick and box-edge lines.
    name : hashable, optional
        Row name (e.g. its category). Carried as a ``group`` column on the
        hover sources so it can lead the hover text, and set as each
        renderer's ``name``.
    value_format : callable, optional
        Function mapping a value to its hover display string, e.g.
        ``lambda v: f"${v:,.2f}"``. Applies to the bin value ranges and
        tick values; defaults to 3 significant figures.

    Returns
    -------
    dict
        Maps component name to the `~bokeh.models.GlyphRenderer` added:

        - ``"fills"``: the bin quads (a hover target), or ``None`` if
          *fill_alpha* is 0.
        - ``"ticks"``: the quantile-tick segments (a hover target).
        - ``"box"``: the two box-edge segments (purely visual).

    See Also
    --------
    add_pavement : Add one or more rows and wire up hover and the legend.
    pavement : Build a whole figure from one or more datasets.
    pavement.pavement_stats : The underlying quantile computation.
    """
    values = pavement_stats(data, bins=bins, weights=weights)
    geom = _row_geometry(values, position, width, orientation,
                         whisker_extent, show_whiskers, value_format)
    if color is None:
        color = _default_colors(1)[0]
    group = None if name is None else [str(name)] * len(geom["bins"])
    tick_group = None if name is None else [str(name)] * len(geom["ticks"])

    renderers: dict[str, GlyphRenderer] = {"fills": None}

    # Bins: one borderless filled quad each, hovering anywhere inside.
    if fill_alpha > 0:
        left, right, bottom, top, band, value_range = zip(*geom["bins"])
        fill_data = dict(left=left, right=right, bottom=bottom, top=top,
                         quantiles=band, values=value_range)
        if group is not None:
            fill_data["group"] = group
        renderers["fills"] = fig.quad(
            left="left", right="right", bottom="bottom", top="top",
            source=ColumnDataSource(fill_data),
            fill_color=color, fill_alpha=fill_alpha, line_color=None,
            name=None if name is None else str(name))

    # Ticks: a segment per distinct quantile value, hovering its single
    # quantile and value. Drawn opaque, like the box.
    x0, y0, x1, y1, quantile, value = zip(*geom["ticks"])
    tick_data = dict(x0=x0, y0=y0, x1=x1, y1=y1,
                     quantiles=quantile, values=value)
    if tick_group is not None:
        tick_data["group"] = tick_group
    renderers["ticks"] = fig.segment(
        x0="x0", y0="y0", x1="x1", y1="y1",
        source=ColumnDataSource(tick_data),
        line_color=color, line_width=line_width,
        name=None if name is None else str(name))

    # Box edges: the two long sides, purely visual (no hover), same style.
    bx0, by0, bx1, by1 = zip(*geom["box"])
    renderers["box"] = fig.segment(
        x0=list(bx0), y0=list(by0), x1=list(bx1), y1=list(by1),
        line_color=color, line_width=line_width)

    return renderers


def add_pavement(
    fig: figure,
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
    color: str | Sequence[str] | None = None,
    fill_alpha: float = 0.3,
    line_width: float = 1.0,
    hover: bool = True,
    value_format: ValueFormat | None = None,
    show_legend: bool = True,
) -> figure:
    """
    Add one or more pavement rows to an existing figure.

    The building block `plot` and `with_marginals` share: it accepts the
    same single/wide/tidy input shapes as `pavement.matplotlib.plot`, draws each row's
    glyphs, and wires up the shared interactivity — one `~bokeh.models.HoverTool`
    over all the rows' bins and ticks, and, for multiple rows, a clickable
    `~bokeh.models.Legend` (each entry toggles its whole row). The figure is
    mutated and returned.

    Parameters
    ----------
    fig : bokeh.plotting.figure
        The figure to add to. Mutated in place.
    data : sequence of float, or sequence of iterables of float
        The values to plot; shape selects the mode, as in `pavement.matplotlib.plot`.
    weights : sequence, optional
        Positive weights, matching the shape of *data*.
    positions : sequence of float, optional
        Position of each row on the axis perpendicular to the value axis.
        Defaults to ``[1, 2, ..., N]``.
    categories : sequence, optional
        Category label per entry in *data* (tidy/long form). If given,
        *data* is split by category.
    labels : sequence, optional
        One label per row, used as the legend/hover name. In tidy form, also
        selects which categories to include and their order.
    bins : int, None, or sequence, default: 4
        Equal-mass bins per row; None shows all the data (a rug). A scalar
        applies to every row; a sequence sets each and may mix None with
        integers. See `pavement.pavement_stats`.
    widths : float or sequence of float, default: 0.6
        Thickness of each row.
    whisker_extent : float, default: 0.1
        How far whisker marks extend beyond the box.
    show_whiskers : bool, default: True
        Whether to draw whisker marks at repeated quantile values.
    orientation : {'vertical', 'horizontal'}, default: 'vertical'
        Direction of the value axis.
    color : str or sequence of str, optional
        Per-row color(s). A single color applies to every row; a sequence
        sets each and must match the number of rows. Defaults to Bokeh's
        ``Category10`` palette.
    fill_alpha : float, default: 0.3
        Opacity of the bin fills (0 omits them).
    line_width : float, default: 1.0
        Width of the tick and box-edge lines.
    hover : bool, default: True
        Whether to add a hover tool over the rows' bins and ticks.
    value_format : callable, optional
        Function mapping a value to its hover display string (e.g.
        ``lambda v: f"${v:,.2f}"``); defaults to 3 significant figures.
    show_legend : bool, default: True
        Whether multi-row plots get a legend (one clickable entry per row). A
        single anonymous row never does.

    Returns
    -------
    bokeh.plotting.figure
        *fig*, with the rows added.

    Raises
    ------
    ValueError
        If *data* is empty; if *positions*, *bins*, *widths*, *color*, or
        *labels* is a sequence of the wrong length; or for any reason raised
        by `pavement.pavement_stats`.

    See Also
    --------
    pavement : Create a new figure (calls this).
    pavement_glyphs : Draw a single row's glyphs.
    """
    data, weight_rows, labels, _ = normalize_rows(
        data, weights, categories, labels)
    n = len(data)
    if positions is None:
        positions = list(range(1, n + 1))
    elif len(positions) != n:
        raise ValueError(f"positions has length {len(positions)}, expected {n}")
    bins = broadcast(bins, n, "bins",
                     lambda v: v is None or isinstance(v, Integral))
    widths = broadcast(widths, n, "widths", lambda v: isinstance(v, Number))
    colors = resolve_colors(color, n, _default_colors)

    fill_renderers: list[GlyphRenderer] = []
    tick_renderers: list[GlyphRenderer] = []
    legend_items: list[LegendItem] = []
    for label, dataset, w, pos, b, width, col in zip(
            labels, data, weight_rows, positions, bins, widths, colors):
        # An anonymous single row has no legend or hover name; multiple rows
        # are named so they get a legend and named hover.
        name = label if n > 1 else None
        rends = pavement_glyphs(
            fig, dataset, bins=b, weights=w, position=pos, width=width,
            whisker_extent=whisker_extent, show_whiskers=show_whiskers,
            orientation=orientation, color=col, fill_alpha=fill_alpha,
            line_width=line_width, name=name, value_format=value_format)
        if rends["fills"] is not None:
            fill_renderers.append(rends["fills"])
        tick_renderers.append(rends["ticks"])
        if n > 1:
            # One legend entry per row, toggling its whole row (fill, ticks,
            # box) — the box hides too, so a click clears the row entirely.
            row_renderers = [rends[r] for r in ("fills", "ticks", "box")
                             if rends[r] is not None]
            legend_items.append(
                LegendItem(label=str(label), renderers=row_renderers))

    if hover:
        # One hover tool over every bin and tick. The bins and ticks share
        # the column names 'quantiles' and 'values' (and 'group' when named),
        # so a single tooltip template reads correctly off either: a hovered
        # bin shows its band and value range, a hovered tick its single
        # quantile and value — the same layout and order as the other
        # backends, led by the name when present.
        has_group = n > 1
        rows = (["@group"] if has_group else []) + ["@quantiles", "@values"]
        fig.add_tools(HoverTool(
            renderers=fill_renderers + tick_renderers,
            tooltips="<br>".join(rows)))

    if legend_items and show_legend:
        legend = Legend(items=legend_items, click_policy="hide")
        fig.add_layout(legend)

    return fig


def _setup_position_axis(
    fig: figure,
    orientation: Literal["vertical", "horizontal"],
    labelled: bool,
    positions: Sequence[float],
    labels: Sequence[Hashable],
    max_width: float,
) -> None:
    """Range and ticks for the (perpendicular) position axis.

    Pads the range so the boxes don't touch the frame, and ticks the axis
    with the row labels when the rows are nameable, else hides them.
    """
    lo = min(positions) - max_width
    hi = max(positions) + max_width
    # The position axis is x for 'vertical', y for 'horizontal'.
    if orientation == "vertical":
        fig.x_range = Range1d(lo, hi)
        axis = fig.xaxis
    else:
        fig.y_range = Range1d(lo, hi)
        axis = fig.yaxis
    if labelled:
        axis.ticker = list(positions)
        axis.major_label_overrides = {
            pos: str(label) for pos, label in zip(positions, labels)}
    else:
        # Anonymous rows: keep the range padding but drop the position ticks.
        axis.ticker = []


def plot(
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
    value_format: ValueFormat | None = None,
    color: str | Sequence[str] | None = None,
    fill_alpha: float = 0.3,
    line_width: float = 1.0,
    hover: bool = True,
    show_legend: bool = True,
    fig: figure | None = None,
    **figure_kwargs: Any,
) -> figure:
    """
    Build an interactive pavement plot as a Bokeh figure.

    The Bokeh counterpart of `pavement.matplotlib.plot`, `pavement.holoviews.plot`,
    and `pavement.plotly.plot`. Accepts the same three input shapes — a
    single 1D dataset, a wide sequence of datasets, or tidy data plus
    *categories* — and returns a `~bokeh.plotting.figure` with the value axis
    labelled and the position axis ticked by the row labels.

    Parameters
    ----------
    data : sequence of float, or sequence of iterables of float
        The values to plot; shape selects the mode, as in `pavement.matplotlib.plot`.
    weights : sequence, optional
        Positive weights, matching the shape of *data*.
    positions : sequence of float, optional
        Position of each row on the axis perpendicular to the value axis.
        Defaults to ``[1, 2, ..., N]``.
    categories : sequence, optional
        Category label per entry in *data* (tidy/long form). If given, *data*
        is split by category.
    labels : sequence, optional
        One label per row, used as the legend name and position-axis tick. In
        tidy form, also selects which categories to include and their order.
    bins : int, None, or sequence, default: 4
        Equal-mass bins per row; None shows all the data (a rug). See
        `pavement.pavement_stats`.
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
    value_format : callable, optional
        Function mapping a value to its hover display string, e.g.
        ``lambda v: f"${v:,.2f}"``. Applies to the bin value ranges and
        tick values; defaults to 3 significant figures.
    color : str or sequence of str, optional
        Per-row color(s). Defaults to Bokeh's ``Category10`` palette, so a
        category-split pavement matches a scatter colored from the same
        palette group for group.
    fill_alpha : float, default: 0.3
        Opacity of the bin fills (0 omits them).
    line_width : float, default: 1.0
        Width of the tick and box-edge lines.
    hover : bool, default: True
        Whether to enable hover.
    show_legend : bool, default: True
        Whether to show the legend (only relevant with multiple rows).
    fig : bokeh.plotting.figure, optional
        Figure to draw into. Defaults to a fresh one built from
        *figure_kwargs*.
    **figure_kwargs
        Forwarded to `bokeh.plotting.figure` when *fig* is None (e.g.
        *width*, *height*, *title*).

    Returns
    -------
    bokeh.plotting.figure
        A figure containing the pavement, with axes labelled and ticked.

    Raises
    ------
    ValueError
        If *data* is empty; if *positions*, *bins*, *widths*, *color*, or
        *labels* is a sequence of the wrong length; or for any reason raised
        by `pavement.pavement_stats`.

    See Also
    --------
    pavement.matplotlib.plot : The matplotlib equivalent.
    pavement.plotly.plot : The Plotly equivalent.
    with_marginals : Arrange a scatter with pavement marginals.
    add_pavement : The lower-level adder this wraps.

    Examples
    --------
    >>> import pavement.bokeh as pbk
    >>> from bokeh.plotting import show
    >>> show(pbk.plot([1, 2, 3, 4, 5]))                 # doctest: +SKIP
    >>> show(pbk.plot(values, categories=labels))       # doctest: +SKIP
    """
    if fig is None:
        fig = figure(**figure_kwargs)
    # Resolve labels/positions once here so the axes match the rows added.
    rows, _, resolved_labels, labelled = normalize_rows(
        data, weights, categories, labels)
    n = len(rows)
    if positions is None:
        positions = list(range(1, n + 1))
    max_width = max(broadcast(
        widths, n, "widths", lambda v: isinstance(v, Number)))

    add_pavement(
        fig, data, weights=weights, positions=positions,
        categories=categories, labels=labels, bins=bins, widths=widths,
        whisker_extent=whisker_extent, show_whiskers=show_whiskers,
        orientation=orientation, color=color, fill_alpha=fill_alpha,
        line_width=line_width, hover=hover, value_format=value_format,
        show_legend=show_legend)

    # Label the value axis (x for horizontal, y otherwise); tick/pad the
    # perpendicular position axis.
    if orientation == "horizontal":
        fig.xaxis.axis_label = value_label
    else:
        fig.yaxis.axis_label = value_label
    _setup_position_axis(fig, orientation, labelled, positions,
                         resolved_labels, max_width)
    return fig


def _color_map(main: figure, labels: Sequence[Hashable]) -> dict[Hashable, str]:
    """Map each category label to the color the *main* figure uses for it.

    So the marginals match the scatter group for group. A glyph renderer
    counts for a label if its ``name`` equals the label; its fill (or line)
    color is taken, when that color is a plain string. Labels the figure
    doesn't color fall back to Bokeh's default palette, in label order,
    skipping colors already claimed.
    """
    found: dict[Hashable, str] = {}
    for r in main.renderers:
        if not isinstance(r, GlyphRenderer) or r.name is None:
            continue
        glyph = r.glyph
        color = getattr(glyph, "fill_color", None)
        if not isinstance(color, str):
            color = getattr(glyph, "line_color", None)
        if isinstance(color, str):
            for label in labels:
                if str(label) == r.name and label not in found:
                    found[label] = color
    return complete_color_map(found, labels, _default_colors)


def with_marginals(
    main: figure,
    x: Sequence[float] | None = None,
    y: Sequence[float] | None = None,
    categories: Sequence[Hashable] | None = None,
    size: int = 120,
    **kwargs: Any,
) -> Any:
    """
    Arrange a scatter with pavement marginals — x on top, y on the right.

    A pavement-flavored take on a joint plot: pass the scatter figure you
    would otherwise show and the marginal data, and get back a
    `~bokeh.models.GridPlot` with the scatter in the main cell and a thin
    pavement strip on the top (for x) and the right (for y). The marginals'
    ranges are linked to the scatter's, so they stay aligned through pan and
    zoom.

    With *categories*, each marginal is split by category and colored to
    match the scatter group for group — colors are read off *main*'s
    renderers by name (so set ``name=`` on the scatter's per-category
    renderers), and any label the scatter doesn't color falls back to
    Bokeh's default palette.

    Parameters
    ----------
    main : bokeh.plotting.figure
        The central scatter figure. Reused as the main cell; its ranges are
        shared with the marginals.
    x, y : sequence of float, optional
        Data for the top (x) and right (y) marginals. Provide either or both;
        at least one is required. For a category split these are the
        per-point values in tidy form, parallel to *categories*.
    categories : sequence, optional
        Category label per point, parallel to *x* and *y*. Splits each
        marginal by category, as in `plot`.
    size : int, default: 120
        Thickness of each marginal strip in pixels.
    **kwargs
        Forwarded to `add_pavement` for both marginals (e.g. *bins*,
        *fill_alpha*, *show_whiskers*, *whisker_extent*, *line_width*,
        *value_format*). *orientation*, *color*, and *show_legend* are
        managed here.

    Returns
    -------
    bokeh.models.GridPlot
        A grid laying out the scatter with the requested marginals adjoined.

    Raises
    ------
    ValueError
        If neither *x* nor *y* is given, or if *orientation*, *color*, or
        *show_legend* is passed in *kwargs* (they are managed here).

    See Also
    --------
    pavement : Builds the marginal rows; call it for a standalone plot.

    Examples
    --------
    >>> import pavement.bokeh as pbk
    >>> from bokeh.plotting import figure, show
    >>> p = figure()                                        # doctest: +SKIP
    >>> p.scatter(xs, ys)                                   # doctest: +SKIP
    >>> show(pbk.with_marginals(p, x=xs, y=ys))             # doctest: +SKIP
    """
    if x is None and y is None:
        raise ValueError("provide x and/or y data for the marginals")
    for managed in ("orientation", "color", "show_legend"):
        if managed in kwargs:
            raise ValueError(
                f"{managed} is managed by with_marginals; call add_pavement "
                "directly if you need to set it")

    # Categories that color the marginals: match the scatter group for group
    # when split, else let the marginals use their own default.
    if categories is not None:
        labels = sorted(set(categories))
        cmap = _color_map(main, labels)
        colors = [cmap[label] for label in labels]
    else:
        colors = None

    main_w = main.width or 600
    main_h = main.height or 600
    main.width, main.height = main_w, main_h
    marg = dict(categories=categories, color=colors, show_legend=False,
                **kwargs)

    top = right = None
    if x is not None:
        # The top strip's value axis (x) is shared with the scatter; its
        # position axis (y) is a meaningless thin strip, so hide it.
        top = figure(width=main_w, height=size, x_range=main.x_range,
                     tools="", toolbar_location=None)
        add_pavement(top, x, orientation="horizontal", **marg)
        top.yaxis.visible = False
        top.xaxis.visible = False
    if y is not None:
        right = figure(width=size, height=main_h, y_range=main.y_range,
                       tools="", toolbar_location=None)
        add_pavement(right, y, orientation="vertical", **marg)
        right.xaxis.visible = False
        right.yaxis.visible = False

    # `<<`-style layout: x on top spanning the scatter, y on the right.
    # Skip the top row entirely when there is no x-marginal, so a y-only
    # joint plot doesn't carry an empty strip above the scatter.
    grid = []
    if top is not None:
        grid.append([top, None])
    grid.append([main, right])
    return gridplot(grid, toolbar_location="right", merge_tools=True)
