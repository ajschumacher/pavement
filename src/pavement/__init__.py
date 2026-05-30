"""Quantile-based pavement plots with matplotlib."""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Iterable, Mapping, Sequence
from numbers import Integral, Number
from typing import Any, Literal

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.patches import Rectangle
from matplotlib.transforms import blended_transform_factory

from .core import pavement_stats, pavement_stats2d, quantiles

__all__ = [
    "quantiles",
    "pavement_stats",
    "draw_pavement",
    "plot",
    "margin",
    "pavement_stats2d",
    "draw_pavement2d",
    "plot2d",
]

# Assumed axes-fraction extent of tick labels, used to place a
# margin() strip clear of them on the tick-label side ('bottom'/'left').
_TICK_LABEL_CLEARANCE = 0.1


def draw_pavement(
    values: Sequence[float],
    position: float = 1,
    width: float = 0.6,
    whisker_extent: float = 0.1,
    show_whiskers: bool = True,
    orientation: Literal['vertical', 'horizontal'] = 'vertical',
    line_props: Mapping[str, Any] | None = None,
    box_props: Mapping[str, Any] | None = None,
    ax: Axes | None = None,
) -> dict[str, Any]:
    """
    Draw a single pavement row from precomputed quantile values.

    Renders a tick at each value perpendicular to the value axis, a
    box outline spanning ``values[0]`` to ``values[-1]``, and whisker
    marks at any value that occurs more than once (a sign that the
    data is concentrated there).

    Parameters
    ----------
    values : sequence of float
        Quantile values in ascending order, as returned by
        `pavement_stats`.
    position : float, default: 1
        Center of the row along the axis perpendicular to the value
        axis. For ``orientation='vertical'`` this is an x-coordinate;
        for ``orientation='horizontal'`` it is a y-coordinate. The
        default matches matplotlib's ``boxplot``, which places a
        single box at position 1.
    width : float, default: 0.6
        Total thickness of the box outline (perpendicular to the
        value axis).
    whisker_extent : float, default: 0.1
        How far the whisker marks extend beyond the box, perpendicular
        to the value axis. Unrelated to matplotlib's ``boxplot(whis=)``,
        which controls outlier cutoffs on the value axis.
    show_whiskers : bool, default: True
        If False, suppress the whisker marks even at repeated values.
    orientation : {'vertical', 'horizontal'}, default: 'vertical'
        Direction of the value axis. 'vertical' puts values on the
        y-axis (matplotlib's boxplot default); 'horizontal' puts them
        on the x-axis.
    line_props : dict, optional
        Line2D properties (color, linewidth, linestyle, alpha, ...)
        passed through to the underlying ``Axes.vlines`` /
        ``Axes.hlines`` calls. Applied uniformly to the quantile ticks,
        whisker marks, and box edges. Defaults to
        ``{'color': 'black', 'linewidth': 1.0}``; partial overrides
        merge on top of that default (e.g. passing ``{'linewidth': 2}``
        keeps lines black).
    box_props : dict, optional
        If given, a filled `~matplotlib.patches.Rectangle` is drawn
        behind the box as a background; the dict supplies its
        properties (facecolor, alpha, hatch, ...). It defaults to no
        edge, so it doesn't double the box outline. If None (the
        default), no background is drawn.
    ax : matplotlib Axes, optional
        Axes to draw on. Defaults to ``plt.gca()``.

    Returns
    -------
    dict
        Maps component name to the artist added to the axes:

        - ``"fill"``: the background `~matplotlib.patches.Rectangle`,
          or ``None`` if *box_props* was not given.
        - ``"ticks"``: the tick at each quantile.
        - ``"whiskers"``: the whisker marks at repeated values, or
          ``None`` if no whiskers were drawn.
        - ``"box"``: the two long edges of the box.

    Raises
    ------
    ValueError
        If *values* is empty, or if *orientation* is not 'vertical' or
        'horizontal'.

    See Also
    --------
    pavement_stats : Compute the values to pass in.
    plot : One-call convenience that combines stats and drawing.
    """
    if len(values) == 0:
        raise ValueError("values must be non-empty")
    if ax is None:
        ax = plt.gca()
    if orientation == 'vertical':
        perp, along = ax.hlines, ax.vlines
    elif orientation == 'horizontal':
        perp, along = ax.vlines, ax.hlines
    else:
        raise ValueError(
            f"orientation must be 'vertical' or 'horizontal', got {orientation!r}")
    props = {'color': 'black', 'linewidth': 1.0, **(line_props or {})}
    pos_lo, pos_hi = position - width/2, position + width/2
    artists: dict[str, Any] = {'fill': None}
    if box_props is not None:
        # Drawn first so it sits behind the lines. The value axis runs
        # along x for 'horizontal', along y for 'vertical'.
        if orientation == 'horizontal':
            xy = (values[0], pos_lo)
            w, h = values[-1] - values[0], pos_hi - pos_lo
        else:
            xy = (pos_lo, values[0])
            w, h = pos_hi - pos_lo, values[-1] - values[0]
        artists['fill'] = ax.add_patch(
            Rectangle(xy, w, h, **{'edgecolor': 'none', **box_props}))
    artists['ticks'] = perp(values, pos_lo, pos_hi, **props)
    artists['whiskers'] = None
    if show_whiskers:
        dupes = [x for x, n in Counter(values).items() if n > 1]
        if dupes:
            artists['whiskers'] = perp(
                dupes,
                pos_lo - whisker_extent, pos_hi + whisker_extent,
                **props)
    artists['box'] = along([pos_lo, pos_hi], values[0], values[-1], **props)
    return artists


def plot(
    data: Sequence[float] | Sequence[Iterable[float]],
    weights: Sequence[float] | Sequence[Sequence[float]] | None = None,
    positions: Sequence[float] | None = None,
    categories: Sequence[Hashable] | None = None,
    tick_labels: Sequence[Hashable] | None = None,
    bins: int | None | Sequence[int | None] = 4,
    widths: float | Sequence[float] = 0.6,
    whisker_extent: float = 0.1,
    show_whiskers: bool = True,
    orientation: Literal['vertical', 'horizontal'] = 'vertical',
    line_props: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    box_props: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    ax: Axes | None = None,
) -> list[dict[str, Any]]:
    """
    Draw one or more pavement rows.

    Accepts three input shapes:

    - A 1D sequence of values: a single row.
    - A sequence of 1D sequences: one row per dataset, at *positions*
      (matching matplotlib's ``boxplot``: ``data[0]`` at the smallest
      position).
    - A 1D sequence plus *categories*: tidy/long form. The data is
      split by category and rendered as in the wide form.

    Parameters
    ----------
    data : sequence of float, or sequence of iterables of float
        The values to plot. Shape determines which mode is used.
    weights : sequence, optional
        Positive weights. Must match the shape of *data*: flat for a
        single row or tidy form, nested for wide form.
    positions : sequence of float, optional
        Position of each row along the axis perpendicular to the
        value axis. Defaults to ``[1, 2, ..., N]``, matching
        matplotlib's ``boxplot``. Length must equal the number of
        rows.
    categories : sequence, optional
        Category label per entry in *data*, parallel to *data*. If
        given, *data* is treated as tidy/long form and split by
        category.
    tick_labels : sequence of str, optional
        Tick labels, one per row, in the same order as the rows. In
        tidy form, also selects which categories to include and their
        order. Ticks are only set when this is provided, on the x-axis
        for ``orientation='vertical'`` and the y-axis otherwise.
    bins : int, None, or sequence of (int or None), default: 4
        Number of equal-mass bins per row. A scalar applies to every
        row; a sequence sets each row's bin count individually and
        must have length equal to the number of rows. None shows all
        the data for that row instead of binning it (see
        `pavement_stats`); a sequence may mix None and integer entries.
    widths : float or sequence of float, default: 0.6
        Thickness of each row's box outline. A scalar applies to
        every row; a sequence sets each row's width individually and
        must have length equal to the number of rows.
    whisker_extent : float, default: 0.1
        How far the whisker marks extend beyond the box, perpendicular
        to the value axis. Unrelated to matplotlib's ``boxplot(whis=)``,
        which controls outlier cutoffs on the value axis.
    show_whiskers : bool, default: True
        If False, suppress whisker marks at repeated quantile values.
    orientation : {'vertical', 'horizontal'}, default: 'vertical'
        Direction of the value axis. 'vertical' puts values on the
        y-axis (matplotlib's boxplot default); 'horizontal' puts them
        on the x-axis.
    line_props : dict or sequence of dict, optional
        Per-row line styling. A single dict applies to every row; a
        sequence sets each row individually and must have length equal
        to the number of rows. See `draw_pavement` for the dict
        semantics.
    box_props : dict or sequence of dict, optional
        Per-row background fill. A single dict applies to every row; a
        sequence sets each row individually and must have length equal
        to the number of rows. See `draw_pavement` for the dict
        semantics.
    ax : matplotlib Axes, optional
        Axes to draw on. Defaults to ``plt.gca()``.

    Returns
    -------
    list of dict
        One artist dict per row, in the same order as the rows. Each
        dict has the shape returned by `draw_pavement`.

    Raises
    ------
    ValueError
        If *data* is empty; if *positions*, *bins*, *widths*,
        *line_props*, or *box_props* is given as a sequence with the
        wrong length; or for any reason raised by the underlying
        `pavement_stats` or `draw_pavement` calls (e.g. non-positive
        *bins* or invalid *orientation*).

    See Also
    --------
    pavement_stats : Compute quantile values for one dataset.
    draw_pavement : Render one row from precomputed values.
    """
    if categories is not None:
        if tick_labels is None:
            tick_labels = sorted(set(categories))
        data = [[d for d, c in zip(data, categories) if c == label]
                for label in tick_labels]
        if weights is not None:
            weights = [[w for w, c in zip(weights, categories) if c == label]
                       for label in tick_labels]
    if len(data) == 0:
        raise ValueError("data must be non-empty")
    if not hasattr(data[0], '__iter__'):
        data = [data]
        weights = [weights] if weights is not None else None
    n = len(data)
    if positions is None:
        positions = list(range(1, n + 1))
    elif len(positions) != n:
        raise ValueError(
            f"positions has length {len(positions)}, expected {n}")
    if bins is None or isinstance(bins, Integral):
        bins = [bins] * n
    elif len(bins) != n:
        raise ValueError(
            f"bins has length {len(bins)}, expected {n}")
    if isinstance(widths, Number):
        widths = [widths] * n
    elif len(widths) != n:
        raise ValueError(
            f"widths has length {len(widths)}, expected {n}")
    if line_props is None or isinstance(line_props, Mapping):
        line_props = [line_props] * n
    elif len(line_props) != n:
        raise ValueError(
            f"line_props has length {len(line_props)}, expected {n}")
    if box_props is None or isinstance(box_props, Mapping):
        box_props = [box_props] * n
    elif len(box_props) != n:
        raise ValueError(
            f"box_props has length {len(box_props)}, expected {n}")
    if ax is None:
        ax = plt.gca()
    weight_iter = weights if weights is not None else [None] * n
    artists = []
    for dataset, w, pos, b, width, props, bprops in zip(
            data, weight_iter, positions, bins, widths, line_props, box_props):
        values = pavement_stats(dataset, bins=b, weights=w)
        artists.append(draw_pavement(
            values, position=pos, width=width,
            whisker_extent=whisker_extent, show_whiskers=show_whiskers,
            orientation=orientation, line_props=props, box_props=bprops, ax=ax))
    if tick_labels is not None:
        set_ticks = ax.set_xticks if orientation == 'vertical' else ax.set_yticks
        set_ticks(list(positions), list(tick_labels))
    return artists


def margin(
    data: Iterable[float],
    axis: Literal['x', 'y'] = 'x',
    where: str | None = None,
    bins: int | None = 4,
    weights: Sequence[float] | None = None,
    pad: float = 0.03,
    size: float = 0.04,
    expand_margins: bool = True,
    show_whiskers: bool = True,
    line_props: Mapping[str, Any] | None = None,
    box_props: Mapping[str, Any] | None = None,
    clip_on: bool = False,
    ax: Axes | None = None,
) -> dict[str, Any]:
    """
    Draw a pavement plot in the margin of an existing plot.

    A marginal pavement is a richer drop-in for a rug plot: it shows
    the 1D distribution of one variable as a thin strip just outside
    the axes frame, aligned with the data on that axis.

    The strip is drawn with a blended transform, so it stays pinned
    to the edge at a fixed thickness — the same for x- and y-axis
    marginals — regardless of the data range on the other axis. By
    default it sits just *outside* the frame (*clip_on* is False) on
    the side opposite the tick labels — above the axes for
    ``axis='x'``, to the right for ``axis='y'``. The *where* argument
    moves it to any edge, inside or outside the frame.

    Call this after the main plot so the data-axis limits are
    already set; the marginal aligns to whatever limits the axes
    has when it is drawn. For ``axis='x'`` with ``where='top'``, if
    the axes already has a title, it is lifted clear of the marginal
    — so set the title before calling this.

    Parameters
    ----------
    data : iterable of float
        The values whose distribution to summarize.
    axis : {'x', 'y'}, default: 'x'
        Which axis the data belongs to. ``'x'`` draws a horizontal
        pavement; ``'y'`` draws a vertical one.
    where : str, optional
        Which side of the axes to place the strip on, optionally
        prefixed with 'inside' or 'outside' (e.g. 'bottom',
        'inside top', 'outside left'). The side is 'top' or 'bottom'
        for ``axis='x'`` and 'left' or 'right' for ``axis='y'``,
        defaulting to 'top'/'right'. The prefix defaults to
        'outside' — the strip sits beyond the frame, and beyond the
        tick labels on the label side — while 'inside' places it
        just within the frame, overlapping the data.
    bins : int or None, default: 4
        Number of equal-mass bins. None shows all the data instead of
        binning it (see `pavement_stats`), turning the marginal into a
        true rug.
    weights : sequence of float, optional
        Positive weights parallel to *data*.
    pad : float, default: 0.03
        Gap between the axes frame and the box, as a fraction of the
        axes height (aspect-scaled for y-axis marginals, like *size*).
    size : float, default: 0.04
        Thickness of the box, as a fraction of the axes height.
        y-axis marginals are scaled by the axes aspect ratio so they
        render at the same physical thickness as x-axis ones.
    expand_margins : bool, default: True
        For an 'inside' placement, expand the axes margins on the
        perpendicular axis so the strip does not overlap the data.
        No effect for 'outside' placements. Mirrors the argument of
        the same name on seaborn's ``rugplot``.
    show_whiskers : bool, default: True
        Whether to draw whisker marks at repeated quantile values.
    line_props : dict, optional
        Line2D properties for the box edges. Defaults to
        ``{'color': 'black', 'linewidth': 1.0}``.
    box_props : dict, optional
        If given, a background fill is drawn behind the strip. See
        `draw_pavement` for the dict semantics. If None (the
        default), no background is drawn.
    clip_on : bool, default: False
        Whether to clip the marginal to the axes box. False (the
        default) lets it render in the exterior margin.
    ax : matplotlib Axes, optional
        Axes to draw on. Defaults to ``plt.gca()``.

    Returns
    -------
    dict
        The artist dict from `draw_pavement`.

    Raises
    ------
    ValueError
        If *axis* is not 'x' or 'y', or *where* is not valid for
        the given *axis*.

    See Also
    --------
    plot : Draw a pavement in the main data area.
    draw_pavement : The underlying single-row renderer.
    """
    if ax is None:
        ax = plt.gca()
    sides = {'x': ('top', 'bottom'), 'y': ('right', 'left')}
    if axis not in sides:
        raise ValueError(f"axis must be 'x' or 'y', got {axis!r}")
    if where is None:
        placement, side = 'outside', sides[axis][0]
    else:
        parts = where.split()
        if len(parts) == 1:
            placement, side = 'outside', parts[0]
        elif len(parts) == 2:
            placement, side = parts
        else:
            raise ValueError(
                "where must be a side, optionally prefixed with "
                f"'inside' or 'outside'; got {where!r}")
        if placement not in ('inside', 'outside'):
            raise ValueError(
                f"where prefix must be 'inside' or 'outside', got {placement!r}")
        if side not in sides[axis]:
            raise ValueError(
                f"where side for axis={axis!r} must be one of "
                f"{sides[axis]}, got {side!r}")
    if axis == 'x':
        transform = blended_transform_factory(ax.transData, ax.transAxes)
        orientation: Literal['vertical', 'horizontal'] = 'horizontal'
        box_size, box_pad = size, pad
    else:
        transform = blended_transform_factory(ax.transAxes, ax.transData)
        orientation = 'vertical'
        # A y-axis strip's thickness is an axes-fraction of width, an
        # x-axis strip's of height. Scale by the axes aspect ratio so
        # both render at the same physical thickness.
        aspect = ax.bbox.height / ax.bbox.width
        box_size, box_pad = size * aspect, pad * aspect
    whisker_extent = 0.3 * box_size
    # Place the box. The far edge is the axes-fraction 1.0 side
    # (top/right); into_axes points from that edge toward the interior.
    far_edge = side in ('top', 'right')
    edge = 1.0 if far_edge else 0.0
    into_axes = -1.0 if far_edge else 1.0
    if placement == 'inside':
        position = edge + into_axes * (box_pad + box_size/2)
    else:  # outside; on the near edge, also clear the tick labels
        clearance = 0.0 if far_edge else _TICK_LABEL_CLEARANCE
        position = edge - into_axes * (clearance + box_pad + box_size/2)
    values = pavement_stats(data, bins=bins, weights=weights)
    props = {**(line_props or {}), 'transform': transform, 'clip_on': clip_on}
    bprops = None
    if box_props is not None:
        bprops = {**box_props, 'transform': transform, 'clip_on': clip_on}
    result = draw_pavement(
        values,
        position=position,
        width=box_size,
        whisker_extent=whisker_extent,
        show_whiskers=show_whiskers,
        orientation=orientation,
        line_props=props,
        box_props=bprops,
        ax=ax,
    )
    if placement == 'inside' and expand_margins:
        # Reserve room so the strip doesn't sit on top of the data:
        # the strip's own inward footprint (pad + box + whisker) plus
        # another pad of breathing room on the data side, matching the
        # strip's gap from the frame edge. ax.margins(m) leaves
        # m/(1+2m) of the view empty per side; invert that to cover it.
        footprint = min(2*box_pad + box_size + whisker_extent, 0.45)
        required = footprint / (1 - 2*footprint)
        mx, my = ax.margins()
        if axis == 'x':
            ax.margins(y=max(my, required))
        else:
            ax.margins(x=max(mx, required))
    if (axis == 'x' and side == 'top' and placement == 'outside'
            and ax.get_title()):
        # Lift the title above the marginal (box + whiskers) so they
        # don't overlap. Setting _autotitlepos stops matplotlib's
        # auto title positioning from clobbering this on the next draw.
        marginal_top = 1 + box_pad + box_size + whisker_extent
        ax.title.set_y(max(ax.title.get_position()[1], marginal_top + 0.04))
        ax._autotitlepos = False
    return result


def draw_pavement2d(
    stats: Mapping[str, Any],
    line_props: Mapping[str, Any] | None = None,
    box_props: Mapping[str, Any] | None = None,
    ax: Axes | None = None,
) -> dict[str, Any]:
    """
    Draw a 2D pavement from precomputed stats.

    Renders every box edge. Where adjacent columns (or rows, for
    ``first_split='y'``) share a boundary along the primary axis,
    the shared line is drawn once per side, which is invisible for
    line art but means each side's segment spans only its own
    column's (or row's) extent along the secondary axis.

    Parameters
    ----------
    stats : dict
        Output of `pavement_stats2d`.
    line_props : dict, optional
        Line2D properties passed through to ``Axes.vlines`` and
        ``Axes.hlines``. Defaults to ``{'color': 'black', 'linewidth': 1.0}``.
    box_props : dict, optional
        If given, a filled `~matplotlib.patches.Rectangle` is drawn
        behind every cell, with these properties (facecolor, alpha,
        ...) applied uniformly. Defaults to no edge. If None (the
        default), no fills are drawn.
    ax : matplotlib Axes, optional
        Axes to draw on. Defaults to ``plt.gca()``.

    Returns
    -------
    dict
        Maps component name to the artists added to the axes:

        - ``"fills"``: list of one background `Rectangle` per cell,
          or ``None`` if *box_props* was not given.
        - ``"verticals"``, ``"horizontals"``: the two LineCollection
          groups of box edges.

    See Also
    --------
    pavement_stats2d : Compute the stats dict to pass in.
    plot2d : One-call convenience that combines stats and drawing.
    """
    if ax is None:
        ax = plt.gca()
    props = {'color': 'black', 'linewidth': 1.0, **(line_props or {})}

    primary_edges = stats['primary_edges']
    secondary_edges_per_chunk = stats['secondary_edges_per_chunk']
    first_split = stats['first_split']

    fills = None if box_props is None else []
    rect_props = {'edgecolor': 'none', **(box_props or {})}
    primary_positions = []
    primary_perp_min = []
    primary_perp_max = []
    secondary_positions = []
    secondary_perp_min = []
    secondary_perp_max = []
    for k, sec_edges in enumerate(secondary_edges_per_chunk):
        p_lo, p_hi = primary_edges[k], primary_edges[k + 1]
        s_lo, s_hi = sec_edges[0], sec_edges[-1]
        for p_val in (p_lo, p_hi):
            primary_positions.append(p_val)
            primary_perp_min.append(s_lo)
            primary_perp_max.append(s_hi)
        for s_val in sec_edges:
            secondary_positions.append(s_val)
            secondary_perp_min.append(p_lo)
            secondary_perp_max.append(p_hi)
        if fills is not None:
            # One filled rectangle per cell in this chunk, drawn before
            # the lines so they sit behind them.
            for lo, hi in zip(sec_edges, sec_edges[1:]):
                if first_split == 'x':  # primary is x, secondary is y
                    xy, w, h = (p_lo, lo), p_hi - p_lo, hi - lo
                else:  # primary is y, secondary is x
                    xy, w, h = (lo, p_lo), hi - lo, p_hi - p_lo
                fills.append(ax.add_patch(Rectangle(xy, w, h, **rect_props)))

    if first_split == 'x':
        verticals = ax.vlines(
            primary_positions, primary_perp_min, primary_perp_max, **props)
        horizontals = ax.hlines(
            secondary_positions, secondary_perp_min, secondary_perp_max, **props)
    else:
        horizontals = ax.hlines(
            primary_positions, primary_perp_min, primary_perp_max, **props)
        verticals = ax.vlines(
            secondary_positions, secondary_perp_min, secondary_perp_max, **props)
    return {'fills': fills, 'verticals': verticals, 'horizontals': horizontals}


def plot2d(
    x: Iterable[float],
    y: Iterable[float],
    weights: Sequence[float] | None = None,
    bins: int = 4,
    x_bins: int | None = None,
    y_bins: int | None = None,
    first_split: Literal['x', 'y'] = 'x',
    line_props: Mapping[str, Any] | None = None,
    box_props: Mapping[str, Any] | None = None,
    ax: Axes | None = None,
) -> dict[str, Any]:
    """
    Draw a 2D pavement plot from paired data.

    Equivalent to ``draw_pavement2d(pavement_stats2d(...))``. Every
    cell of the resulting grid holds an equal share of the data.

    Parameters
    ----------
    x, y : iterable of float
        Paired coordinates. Must have the same length.
    weights : sequence of float, optional
        Positive weights, one per (x, y) pair.
    bins : int, default: 4
        Default number of bins along each axis.
    x_bins, y_bins : int, optional
        Override *bins* for the respective axis.
    first_split : {'x', 'y'}, default: 'x'
        Which axis to partition first.
    line_props : dict, optional
        Line2D properties for all box edges. Defaults to
        ``{'color': 'black', 'linewidth': 1.0}``.
    box_props : dict, optional
        If given, a background fill is drawn behind every cell, with
        these properties applied uniformly. See `draw_pavement2d`.
    ax : matplotlib Axes, optional
        Axes to draw on. Defaults to ``plt.gca()``.

    Returns
    -------
    dict
        The artist dict from `draw_pavement2d`.

    See Also
    --------
    pavement_stats2d : Compute the stats without drawing.
    draw_pavement2d : Render from a stats dict.
    plot : The 1D equivalent.
    """
    stats = pavement_stats2d(
        x, y,
        weights=weights,
        bins=bins, x_bins=x_bins, y_bins=y_bins,
        first_split=first_split,
    )
    return draw_pavement2d(stats, line_props=line_props, box_props=box_props,
                           ax=ax)
