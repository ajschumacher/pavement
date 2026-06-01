"""
Interactive pavement plots for Plotly.

The `pavement.matplotlib` renderer draws static matplotlib artists and
the `pavement.holoviews` module builds backend-agnostic HoloViews
elements. This module targets Plotly directly, so it speaks Plotly's own
vocabulary — `plotly.graph_objects` traces, `plotly.subplots` grids — and
slots into a Plotly workflow with native hover, pan, zoom, and legends.

A pavement is a richer drop-in for a rug plot: where a rug draws one tick
per data point, a pavement bins the data into equal-mass quantile boxes
(or, with ``bins=None``, falls back to a tick per point — a literal rug).
The headline use is the same place rugs show up most: as marginals on a
scatter, like Plotly's own ``marginal_x`` / ``marginal_y`` rugs
(https://plotly.com/python/marginal-plots/). `with_marginals` adjoins
pavement marginals to a scatter figure in one call.

Each pavement row is built from plain `~plotly.graph_objects.Scatter`
traces — no figure-level *shapes* — so a row drops into any subplot cell
with ``row=``/``col=`` and carries its own hover. A row is:

- one borderless filled rectangle per equal-mass bin, each its own trace
  with ``hoveron='fills'`` so hovering anywhere inside the box shows that
  bin's quantile band and value range;
- a single line trace for the quantile ticks and box edges (with whiskers
  where a value repeats, so every line is drawn once); and
- an invisible marker at each quantile tick, carrying that tick's single
  quantile and value on hover — the rug-style read.

Plotly hovers filled areas and markers but not lines, so the line trace
is purely visual and the two hover layers (box fills, tick markers) carry
the text. Hover reads the same as the other backends: the box hover is a
quantile band and value range, the tick hover a single quantile and value
(both led by the row's name when it has one).

The functions mirror the rest of the package:

- `pavement_traces` builds one row's traces (the low-level piece).
- `plot` builds a whole `~plotly.graph_objects.Figure`, accepting a
  single dataset, a wide list of datasets, or tidy data plus
  *categories* — the counterpart of `pavement.matplotlib.plot` and
  `pavement.holoviews.plot`.
- `add_pavement` adds those rows to an existing figure (optionally into a
  subplot cell), the building block the other two share.
- `with_marginals` builds a scatter-with-marginals joint plot.

Examples
--------
>>> import pavement.plotly as ppl
>>> ppl.plot([1, 2, 3, 4, 5]).show()                # doctest: +SKIP
>>> ppl.plot(values, categories=labels).show()      # doctest: +SKIP
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Sequence
from numbers import Integral, Number
from typing import Any, Literal

import plotly.graph_objects as go
from plotly.colors import qualitative
from plotly.subplots import make_subplots

from .core import pavement_stats
from ._geometry import (
    bin_polygon,
    box_edges,
    broadcast,
    complete_color_map,
    normalize_rows,
    resolve_colors,
    row_spec,
    tick_segment,
    ValueFormat,
)

__all__ = ["pavement_traces", "add_pavement", "plot", "with_marginals"]

# Hover text is shown verbatim via ``hovertemplate="%{text}..."``, which
# inserts the ``text`` string literally — so the "%" in a quantile like
# "25%" needs no escaping (unlike putting it directly in the template).
_HOVERTEMPLATE = "%{text}<extra></extra>"


def _default_colors(n: int) -> list[str]:
    """Plotly's own default qualitative color cycle, *n* entries.

    Sharing the exact cycle means a default-colored category-split
    pavement matches a default-colored Plotly Express scatter group for
    group, in the same order — handy when used as a marginal.
    """
    cycle = qualitative.Plotly
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
    """Build one row's bin rectangles, visible lines, and tick hovers.

    Returns a dict with:

    - ``bins``: one ``(xs, ys, band, value_range)`` per equal-mass bin —
      a closed rectangle plus its hover strings ("X% to Y%", "X to Y").
    - ``line_x`` / ``line_y``: the quantile ticks and the two box edges as
      flat coordinate lists, ``None`` breaking between segments (Plotly's
      lift-the-pen convention). A tick reaches past the box into a whisker
      where its value repeats, so every line is drawn exactly once.
    - ``ticks``: one ``(x, y, quantile, value)`` per distinct quantile
      value — the point (at the row center, on the value axis) and hover
      strings for the rug-style tick hover. A repeated value reads as a
      span ("X% to Y%").

    The shared `row_spec` does the binning and one-tick-per-distinct-value
    (whisker) logic; this lays the result out the way Plotly's traces want.
    """
    spec = row_spec(values, position, width, orientation,
                    whisker_extent, show_whiskers, value_format)

    # Bins: one borderless rectangle per equal-mass bin, as a closed polygon.
    bins: list[tuple[list[float], list[float], str, str]] = []
    for b in spec.bins:
        xs, ys = bin_polygon(b.low, b.high, position, spec.half, orientation)
        bins.append((xs, ys, b.band, b.value_range))

    # Ticks: the quantile ticks as line segments (None lifts the pen between
    # them), plus a hover point per distinct value at the row center.
    line_x: list[float | None] = []
    line_y: list[float | None] = []
    ticks: list[tuple[float, float, str, str]] = []
    for t in spec.ticks:
        x0, y0, x1, y1 = tick_segment(position, t.reach, t.value, orientation)
        line_x += [x0, x1, None]
        line_y += [y0, y1, None]
        tx, ty = (position, t.value) if orientation == "vertical" \
            else (t.value, position)
        ticks.append((tx, ty, t.quantile, t.value_str))

    # Box edges: the two long sides, spanning the full value range.
    for x0, y0, x1, y1 in box_edges(position, spec.half, spec.value_low,
                                    spec.value_high, orientation):
        line_x += [x0, x1, None]
        line_y += [y0, y1, None]

    return {"bins": bins, "line_x": line_x, "line_y": line_y, "ticks": ticks}


def pavement_traces(
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
    name: str | None = None,
    hover: bool = True,
    value_format: ValueFormat | None = None,
    show_legend: bool = False,
) -> list[go.Scatter]:
    """
    Build the Plotly traces for a single pavement row.

    The low-level piece the rest of the module is built on: it computes
    one row's quantile values and returns the `~plotly.graph_objects`
    traces that draw it, ready to ``add_trace`` (optionally into a
    subplot cell). Use `plot` or `add_pavement` for the usual
    single/wide/tidy entry points.

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
    color : str, optional
        Color of the lines and (translucent) fill. Any hex, named, or
        ``rgb(...)`` color Plotly accepts. Defaults to the first Plotly
        color.
    fill_alpha : float, default: 0.3
        Opacity of the bin fills. The ticks and box are drawn opaque. Set
        to 0 to omit the fill entirely.
    line_width : float, default: 1.0
        Width of the tick and box-edge lines.
    name : str, optional
        Legend/hover name for the row (e.g. its category).
    hover : bool, default: True
        Whether to enable hover: ``hoveron='fills'`` on each bin (so the
        box hovers anywhere inside) plus an invisible marker at each tick.
    value_format : callable, optional
        Function mapping a value to its hover display string, e.g.
        ``lambda v: f"${v:,.2f}"``. Applies to the bin value ranges and
        tick values; defaults to 3 significant figures.
    show_legend : bool, default: False
        Whether the row contributes a legend entry (one per row, on its
        first bin or, if there is no fill, its lines).

    Returns
    -------
    list of plotly.graph_objects.Scatter
        One trace per bin fill, then the line trace, then (if *hover*) the
        tick-marker trace — all sharing a ``legendgroup`` so toggling the
        legend hides the whole row.

    See Also
    --------
    pavement : Build a whole figure from one or more datasets.
    add_pavement : Add rows to an existing figure.
    pavement.pavement_stats : The underlying quantile computation.
    """
    values = pavement_stats(data, bins=bins, weights=weights)
    geom = _row_geometry(values, position, width, orientation,
                         whisker_extent, show_whiskers, value_format)
    if color is None:
        color = _default_colors(1)[0]
    legendgroup = name if name is not None else None
    # Hover lines: the name (when present), then the band/value — same
    # layout and order as the other backends' hover.
    prefix = [] if name is None else [str(name)]

    traces: list[go.Scatter] = []
    # The first visible trace carries the (single) legend entry; the rest
    # share its legendgroup so a legend click toggles the whole row.
    legend_taken = False

    # Bins: one filled rectangle each, hovering anywhere inside the box.
    # The translucent fill is the row color at fill_alpha opacity: the line
    # is zero-width, so the trace opacity applies to the fill alone — no
    # need to bake an alpha into the color string (and no matplotlib).
    if fill_alpha > 0:
        for xs, ys, band, value_range in geom["bins"]:
            text = "<br>".join(prefix + [band, value_range])
            traces.append(go.Scatter(
                x=xs, y=ys, mode="lines", line=dict(width=0), fill="toself",
                fillcolor=color, opacity=fill_alpha, hoveron="fills",
                text=text if hover else None,
                hovertemplate=_HOVERTEMPLATE if hover else None,
                hoverinfo=None if hover else "skip",
                name=name, legendgroup=legendgroup,
                showlegend=show_legend and not legend_taken))
            legend_taken = True

    # Lines: the quantile ticks and box edges, purely visual (Plotly does
    # not hover lines); the tick markers below carry their hover.
    traces.append(go.Scatter(
        x=geom["line_x"], y=geom["line_y"],
        mode="lines", line=dict(color=color, width=line_width),
        name=name, legendgroup=legendgroup,
        showlegend=show_legend and not legend_taken, hoverinfo="skip"))

    # Tick markers: an invisible point at each quantile value, hovering as
    # a single quantile and value — the rug-style read of a line.
    if hover:
        texts = ["<br>".join(prefix + [quantile, value])
                 for _, _, quantile, value in geom["ticks"]]
        traces.append(go.Scatter(
            x=[t[0] for t in geom["ticks"]],
            y=[t[1] for t in geom["ticks"]],
            mode="markers", marker=dict(color=color, opacity=0),
            text=texts, hovertemplate=_HOVERTEMPLATE,
            name=name, legendgroup=legendgroup, showlegend=False))

    return traces


def add_pavement(
    fig: go.Figure,
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
    row: int | None = None,
    col: int | None = None,
) -> go.Figure:
    """
    Add one or more pavement rows to an existing figure.

    The building block `plot` and `with_marginals` share: it accepts
    the same single/wide/tidy input shapes as `pavement.matplotlib.plot`, builds the
    traces for each row, and adds them to *fig* — into a specific subplot
    cell when *row*/*col* are given. The figure is mutated and returned.

    Parameters
    ----------
    fig : plotly.graph_objects.Figure
        The figure to add to. Mutated in place.
    data : sequence of float, or sequence of iterables of float
        The values to plot; shape selects the mode, as in
        `pavement.matplotlib.plot`.
    weights : sequence, optional
        Positive weights, matching the shape of *data*.
    positions : sequence of float, optional
        Position of each row on the axis perpendicular to the value axis.
        Defaults to ``[1, 2, ..., N]``.
    categories : sequence, optional
        Category label per entry in *data* (tidy/long form). If given,
        *data* is split by category.
    labels : sequence, optional
        One label per row, used as the legend/hover name. In tidy form,
        also selects which categories to include and their order.
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
        sets each and must match the number of rows. Defaults to Plotly's
        qualitative color cycle.
    fill_alpha : float, default: 0.3
        Opacity of the bin fills (0 omits them).
    line_width : float, default: 1.0
        Width of the tick and box-edge lines.
    hover : bool, default: True
        Whether to add the invisible hover layer to each row.
    value_format : callable, optional
        Function mapping a value to its hover display string (e.g.
        ``lambda v: f"${v:,.2f}"``); defaults to 3 significant figures.
    show_legend : bool, default: True
        Whether multi-row plots contribute a legend entry per row. A
        single anonymous row never does.
    row, col : int, optional
        Subplot cell to add the traces to, for a figure built with
        `plotly.subplots.make_subplots`. Both or neither.

    Returns
    -------
    plotly.graph_objects.Figure
        *fig*, with the rows added.

    Raises
    ------
    ValueError
        If *data* is empty; if *positions*, *bins*, *widths*, *color*, or
        *labels* is a sequence of the wrong length; or for any reason
        raised by `pavement.pavement_stats`.

    See Also
    --------
    pavement : Create a new figure (calls this).
    pavement_traces : Build a single row's traces.
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

    add = dict(row=row, col=col) if row is not None or col is not None else {}
    for label, dataset, w, pos, b, width, col_ in zip(
            labels, data, weight_rows, positions, bins, widths, colors):
        # An anonymous single row has no legend or hover name; multiple
        # rows are named so they get a legend and named hover.
        name = str(label) if n > 1 else None
        traces = pavement_traces(
            dataset, bins=b, weights=w, position=pos, width=width,
            whisker_extent=whisker_extent, show_whiskers=show_whiskers,
            orientation=orientation, color=col_, fill_alpha=fill_alpha,
            line_width=line_width, name=name, hover=hover,
            value_format=value_format, show_legend=show_legend and n > 1)
        for trace in traces:
            fig.add_trace(trace, **add)
    return fig


def _position_axis_kwargs(
    labelled: bool, positions: Sequence[float], labels: Sequence[Hashable],
    width: float,
) -> dict[str, Any]:
    """Axis settings for the (perpendicular) position axis.

    Ticks the position axis with the row labels when the rows are
    nameable, and pads the range so the boxes don't touch the frame.
    """
    lo = min(positions) - width
    hi = max(positions) + width
    kw: dict[str, Any] = {"range": [lo, hi]}
    if labelled:
        kw["tickmode"] = "array"
        kw["tickvals"] = list(positions)
        kw["ticktext"] = [str(label) for label in labels]
    else:
        kw["showticklabels"] = False
    return kw


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
    fig: go.Figure | None = None,
) -> go.Figure:
    """
    Build an interactive pavement plot as a Plotly figure.

    The Plotly counterpart of `pavement.matplotlib.plot` and
    `pavement.holoviews.plot`. Accepts the same three input shapes — a
    single 1D dataset, a wide sequence of datasets, or tidy data plus
    *categories* — and returns a `~plotly.graph_objects.Figure` with the
    value axis labelled and the position axis ticked by the row labels.

    Parameters
    ----------
    data : sequence of float, or sequence of iterables of float
        The values to plot; shape selects the mode, as in
        `pavement.matplotlib.plot`.
    weights : sequence, optional
        Positive weights, matching the shape of *data*.
    positions : sequence of float, optional
        Position of each row on the axis perpendicular to the value axis.
        Defaults to ``[1, 2, ..., N]``.
    categories : sequence, optional
        Category label per entry in *data* (tidy/long form). If given,
        *data* is split by category.
    labels : sequence, optional
        One label per row, used as the legend name and position-axis tick.
        In tidy form, also selects which categories to include and their
        order.
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
        Axis title for the value axis (x for horizontal, y otherwise).
    value_format : callable, optional
        Function mapping a value to its hover display string, e.g.
        ``lambda v: f"${v:,.2f}"``. Applies to the bin value ranges and
        tick values; defaults to 3 significant figures.
    color : str or sequence of str, optional
        Per-row color(s). Defaults to Plotly's qualitative color cycle, so
        a category-split pavement matches a default Plotly Express scatter
        group for group.
    fill_alpha : float, default: 0.3
        Opacity of the bin fills (0 omits them).
    line_width : float, default: 1.0
        Width of the tick and box-edge lines.
    hover : bool, default: True
        Whether to enable hover (via the invisible marker layer).
    show_legend : bool, default: True
        Whether to show the legend (only relevant with multiple rows).
    fig : plotly.graph_objects.Figure, optional
        Figure to draw into. Defaults to a fresh one. (Passing a subplot
        figure here draws into its default cell; for a specific cell, use
        `add_pavement` with *row*/*col*.)

    Returns
    -------
    plotly.graph_objects.Figure
        A figure containing the pavement, with axes labelled and ticked.

    Raises
    ------
    ValueError
        If *data* is empty; if *positions*, *bins*, *widths*, *color*, or
        *labels* is a sequence of the wrong length; or for any reason
        raised by `pavement.pavement_stats`.

    See Also
    --------
    pavement.matplotlib.plot : The matplotlib equivalent.
    pavement.holoviews.plot : The HoloViews equivalent.
    with_marginals : Adjoin pavement marginals to a scatter.
    add_pavement : The lower-level adder this wraps.

    Examples
    --------
    >>> import pavement.plotly as ppl
    >>> ppl.plot([1, 2, 3, 4, 5]).show()                # doctest: +SKIP
    >>> ppl.plot(values, categories=labels).show()      # doctest: +SKIP
    """
    if fig is None:
        fig = go.Figure()
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

    pos_kw = _position_axis_kwargs(labelled, positions, resolved_labels,
                                   max_width)
    if orientation == "horizontal":
        fig.update_xaxes(title_text=value_label)
        fig.update_yaxes(**pos_kw)
    else:
        fig.update_yaxes(title_text=value_label)
        fig.update_xaxes(**pos_kw)
    # 'closest' resolves hover to the nearest box or tick, rather than
    # stacking every trace sharing an axis coordinate.
    fig.update_layout(showlegend=show_legend and n > 1, hovermode="closest")
    return fig


def _color_map(main: go.Figure, labels: Sequence[Hashable]) -> dict[Hashable, str]:
    """Map each category label to the color the *main* figure uses for it.

    So the marginals match the scatter group for group. A trace counts
    for a label if its ``name`` equals the label; its marker (or line)
    color is taken. Labels the figure doesn't color fall back to Plotly's
    default cycle, in label order, skipping colors already claimed.
    """
    found: dict[Hashable, str] = {}
    for trace in main.data:
        name = getattr(trace, "name", None)
        if name is None:
            continue
        color = (getattr(getattr(trace, "marker", None), "color", None)
                 or getattr(getattr(trace, "line", None), "color", None))
        if isinstance(color, str):
            for label in labels:
                if str(label) == name and label not in found:
                    found[label] = color
    return complete_color_map(found, labels, _default_colors)


def with_marginals(
    main: go.Figure,
    x: Sequence[float] | None = None,
    y: Sequence[float] | None = None,
    categories: Sequence[Hashable] | None = None,
    size: float = 0.15,
    spacing: float = 0.02,
    **kwargs: Any,
) -> go.Figure:
    """
    Adjoin pavement marginals to a scatter figure — x on top, y on right.

    A pavement-flavored take on Plotly's ``marginal_x`` / ``marginal_y``
    rugs (https://plotly.com/python/marginal-plots/): pass the figure you
    would otherwise show and the marginal data, and get back a joint plot
    with the scatter in the main cell and a thin pavement strip on the top
    (for x) and the right (for y). The marginals share the scatter's data
    axes, so they stay aligned through pan and zoom.

    The *main* figure's traces are moved into a fresh subplot grid, so
    *main* should be a finished scatter (any styling on its traces is
    preserved). With *categories*, each marginal is split by category and
    colored to match the scatter group for group — colors are read off
    *main*'s traces by name, so a Plotly Express colored scatter and its
    marginals share one scheme for free.

    Parameters
    ----------
    main : plotly.graph_objects.Figure
        The central scatter figure. Its traces are re-added to the joint
        plot's main cell.
    x, y : sequence of float, optional
        Data for the top (x) and right (y) marginals. Provide either or
        both; at least one is required. For a category split these are the
        per-point values in tidy form, parallel to *categories*.
    categories : sequence, optional
        Category label per point, parallel to *x* and *y*. Splits each
        marginal by category, as in `plot`.
    size : float, default: 0.15
        Thickness of each marginal strip, as a fraction of the figure.
    spacing : float, default: 0.02
        Gap between the marginal strips and the main cell, as a fraction
        of the figure.
    **kwargs
        Forwarded to `add_pavement` for both marginals (e.g. *bins*,
        *fill_alpha*, *show_whiskers*, *whisker_extent*, *line_width*,
        *value_format*). *orientation*, *color*, and *show_legend* are
        managed here.

    Returns
    -------
    plotly.graph_objects.Figure
        A new figure: the scatter with the requested marginals adjoined.

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
    >>> import plotly.express as px
    >>> import pavement.plotly as ppl
    >>> df = px.data.iris()                                 # doctest: +SKIP
    >>> fig = px.scatter(df, x="sepal_width", y="sepal_length",
    ...                  color="species")                   # doctest: +SKIP
    >>> ppl.with_marginals(fig, x=df.sepal_width, y=df.sepal_length,
    ...                    categories=df.species).show()    # doctest: +SKIP
    """
    if x is None and y is None:
        raise ValueError("provide x and/or y data for the marginals")
    for managed in ("orientation", "color", "show_legend"):
        if managed in kwargs:
            raise ValueError(
                f"{managed} is managed by with_marginals; call add_pavement "
                "directly if you need to set it")

    # Categories that color the marginals: match the scatter group for
    # group when split, else let the marginals use their own default.
    if categories is not None:
        labels = sorted(set(categories))
        cmap = _color_map(main, labels)
        colors = [cmap[label] for label in labels]
    else:
        colors = None

    main_row, main_col = 2, 1
    fig = make_subplots(
        rows=2, cols=2,
        column_widths=[1 - size, size], row_heights=[size, 1 - size],
        horizontal_spacing=spacing, vertical_spacing=spacing,
        shared_xaxes=True, shared_yaxes=True)

    for trace in main.data:
        fig.add_trace(trace, row=main_row, col=main_col)

    marg = dict(categories=categories, color=colors, show_legend=False,
                **kwargs)
    if x is not None:
        add_pavement(fig, x, orientation="horizontal", row=1, col=1, **marg)
    if y is not None:
        add_pavement(fig, y, orientation="vertical", row=2, col=2, **marg)

    # Carry over the scatter's axis titles to the main cell's axes, and
    # hide the marginal strips' perpendicular axes so they read as strips.
    x_title = main.layout.xaxis.title.text
    y_title = main.layout.yaxis.title.text
    fig.update_xaxes(title_text=x_title, row=main_row, col=main_col)
    fig.update_yaxes(title_text=y_title, row=main_row, col=main_col)
    fig.update_yaxes(showticklabels=False, row=1, col=1)  # x-marginal
    fig.update_xaxes(showticklabels=False, row=2, col=2)  # y-marginal
    fig.update_layout(
        showlegend=any(getattr(t, "showlegend", None) for t in main.data)
        or main.layout.showlegend is True,
        hovermode="closest")
    return fig
