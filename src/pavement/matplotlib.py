"""
Static pavement plots with matplotlib.

The matplotlib backend draws pavements as matplotlib artists on an Axes.
Beyond the shared ``plot`` API (single, wide, or tidy data; a rug with
``bins=None``; orientation), this backend adds three things the
interactive backends don't have: 2D pavements (`plot2d`), a single-strip
marginal (`margin`) with rich inside/outside placement, and a borderless,
word-sized inline image (`spark`).

The backend-agnostic statistics live in `pavement.core`; the shared row
geometry in `pavement._geometry`.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping, Sequence
from numbers import Integral, Number
from typing import Any, Literal

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.patches import Rectangle
from matplotlib.transforms import blended_transform_factory

from matplotlib.figure import Figure

from ._geometry import box_edge_spans, broadcast, normalize_rows, row_spec
from .core import pavement_stats, pavement_stats2d

__all__ = [
    "draw_pavement",
    "plot",
    "spark",
    "margin",
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
    tassel_extent: float = 0.05,
    show_tassels: bool = False,
    show_box: bool | None = True,
    orientation: Literal['vertical', 'horizontal'] = 'vertical',
    line_props: Mapping[str, Any] | None = None,
    box_props: Mapping[str, Any] | None = None,
    data: Sequence[float] | None = None,
    ax: Axes | None = None,
) -> dict[str, Any]:
    """
    Draw a single pavement row from precomputed quantile values.

    Renders one tick per distinct value perpendicular to the value
    axis and a box outline spanning ``values[0]`` to ``values[-1]``. A
    value that repeats (a sign the data is concentrated there) reaches
    past the box as a tassel, so every line is drawn exactly once.

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
    tassel_extent : float, default: 0.05
        How far the tassel marks extend beyond the box, perpendicular
        to the value axis. Unrelated to matplotlib's ``boxplot(whis=)``,
        which controls outlier cutoffs on the value axis.
    show_tassels : bool, default: False
        If False, suppress the tassel marks even at repeated values.
    show_box : bool or None, default: True
        How to draw the long box edges (the borders parallel to the value
        axis, perpendicular to the value ticks). ``True`` (the default here)
        draws the complete box — both edges unbroken across the value range.
        ``False`` drops them, leaving only the ticks (a plain rug). ``None``
        is the auto mode: each bin contributes its edges only where it holds
        a data point strictly inside it, so the box closes where values are
        spread and gaps open where the mass clumps onto a value line — which
        needs *data* to be given (without it the auto box is empty). The
        higher-level `plot` passes ``None`` by default, so a binned pavement
        gaps and a rug shows no box.
    orientation : {'vertical', 'horizontal'}, default: 'vertical'
        Direction of the value axis. 'vertical' puts values on the
        y-axis (matplotlib's boxplot default); 'horizontal' puts them
        on the x-axis.
    line_props : dict, optional
        Line2D properties (color, linewidth, linestyle, alpha, ...)
        passed through to the underlying ``Axes.vlines`` /
        ``Axes.hlines`` calls. Applied uniformly to the quantile ticks
        (tassels included) and box edges. Defaults to
        ``{'color': 'black', 'linewidth': 1.0}``; partial overrides
        merge on top of that default (e.g. passing ``{'linewidth': 2}``
        keeps lines black).
    box_props : dict, optional
        If given, a filled `~matplotlib.patches.Rectangle` is drawn
        behind the box as a background; the dict supplies its
        properties (facecolor, alpha, hatch, ...). It defaults to no
        edge, so it doesn't double the box outline. If None (the
        default), no background is drawn.
    data : sequence of float, optional
        The raw values *values* was computed from. Only the auto box
        (``show_box=None``) uses it — to count how many points fall strictly
        inside each bin and so decide which bin edges to draw. Without it the
        auto box is empty; ``show_box`` True/False ignore it.
    ax : matplotlib Axes, optional
        Axes to draw on. Defaults to ``plt.gca()``.

    Returns
    -------
    dict
        Maps component name to the artist added to the axes:

        - ``"fill"``: the background `~matplotlib.patches.Rectangle`,
          or ``None`` if *box_props* was not given.
        - ``"ticks"``: one tick per distinct quantile value, extended
          into a tassel where the value repeats.
        - ``"box"``: the long box edges (one `~matplotlib.collections.LineCollection`
          of every drawn edge segment), or ``None`` when no edge is drawn —
          ``show_box`` False, or the auto box finds no bin with interior data.

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
    if orientation not in ('vertical', 'horizontal'):
        raise ValueError(
            f"orientation must be 'vertical' or 'horizontal', got {orientation!r}")
    if ax is None:
        ax = plt.gca()
    spec = row_spec(values, position, width, orientation,
                    tassel_extent, show_tassels, data=data)
    # 'perp' draws the ticks (across the row); 'along' the box edges (down
    # the value axis). They swap roles with orientation.
    perp, along = (ax.hlines, ax.vlines) if orientation == 'vertical' \
        else (ax.vlines, ax.hlines)
    props = {'color': 'black', 'linewidth': 1.0, **(line_props or {})}
    pos_lo, pos_hi = position - spec.half, position + spec.half
    artists: dict[str, Any] = {'fill': None}
    if box_props is not None:
        # Drawn first so it sits behind the lines. The value axis runs
        # along x for 'horizontal', along y for 'vertical'.
        if orientation == 'horizontal':
            xy = (spec.value_low, pos_lo)
            w, h = spec.value_high - spec.value_low, pos_hi - pos_lo
        else:
            xy = (pos_lo, spec.value_low)
            w, h = pos_hi - pos_lo, spec.value_high - spec.value_low
        artists['fill'] = ax.add_patch(
            Rectangle(xy, w, h, **{'edgecolor': 'none', **box_props}))
    # One tick per distinct value, reaching `reach` to either side of the
    # row center — past the box (a tassel) where the value repeats, so
    # every line is drawn exactly once.
    artists['ticks'] = perp(
        [t.value for t in spec.ticks],
        [position - t.reach for t in spec.ticks],
        [position + t.reach for t in spec.ticks],
        **props)
    # The long box edges run along the value axis (perpendicular to the
    # ticks). `box_edge_spans` decides where: the auto box (show_box None,
    # with data) closes each populated bin and gaps open where the mass
    # clumps onto a value line; True forces one unbroken span; False (and a
    # rug, whose bins have no interior) draws none — leaving a plain rug. Each
    # span draws both sides, gathered into one LineCollection.
    spans = box_edge_spans(spec, show_box)
    if spans:
        sides, lows, highs = [], [], []
        for low, high in spans:
            for side in (pos_lo, pos_hi):
                sides.append(side)
                lows.append(low)
                highs.append(high)
        artists['box'] = along(sides, lows, highs, **props)
    else:
        artists['box'] = None
    return artists


def plot(
    data: Sequence[float] | Sequence[Iterable[float]],
    weights: Sequence[float] | Sequence[Sequence[float]] | None = None,
    positions: Sequence[float] | None = None,
    categories: Sequence[Hashable] | None = None,
    labels: Sequence[Hashable] | None = None,
    bins: int | None | Sequence[int | None] = 4,
    widths: float | Sequence[float] = 0.6,
    tassel_extent: float = 0.05,
    show_tassels: bool = False,
    show_box: bool | None = None,
    orientation: Literal['vertical', 'horizontal'] = 'vertical',
    value_label: str | None = None,
    color: str | Sequence[str] | None = None,
    fill_alpha: float = 0.3,
    line_props: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    box_props: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    ax: Axes | None = None,
) -> list[dict[str, Any]]:
    """
    Draw one or more pavement rows.

    The matplotlib backend's headline function — the counterpart of
    `pavement.bokeh.plot`, `pavement.plotly.plot`, and
    `pavement.holoviews.plot`. Accepts the same three input shapes:

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
    labels : sequence, optional
        One label per row, in row order. In tidy form, also selects
        which categories to include and their order. When given (or in
        tidy form), the rows are ticked on the position axis — the
        x-axis for ``orientation='vertical'``, the y-axis otherwise.
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
    tassel_extent : float, default: 0.05
        How far the tassel marks extend beyond the box, perpendicular
        to the value axis. Unrelated to matplotlib's ``boxplot(whis=)``,
        which controls outlier cutoffs on the value axis.
    show_tassels : bool, default: False
        If False, suppress tassel marks at repeated quantile values.
    show_box : bool or None, default: None
        Whether to draw each row's two long box edges (the borders
        parallel to the value axis). None (the default) draws them for a
        binned row and omits them for a rug (``bins=None``), so a rug
        reads like a plain rug plot while a binned pavement keeps its box;
        True or False forces the choice for every row. Resolved per row,
        so a mixed *bins* sequence gets the right default for each.
    orientation : {'vertical', 'horizontal'}, default: 'vertical'
        Direction of the value axis. 'vertical' puts values on the
        y-axis (matplotlib's boxplot default); 'horizontal' puts them
        on the x-axis.
    value_label : str, optional
        If given, label the value axis (y for vertical, x otherwise).
        The shared name for this across backends; matplotlib leaves the
        axis unlabelled by default (``None``), where the interactive
        backends default to ``'value'``. There is no ``value_format``
        counterpart here: this static backend draws no hover tooltips, so
        values are never formatted for display the way they are in the
        ``bokeh``/``plotly``/``holoviews`` backends.
    color : str or sequence of str, optional
        Per-row color convenience. A single color applies to every row;
        a sequence sets each row and must match the number of rows. It
        tints the lines and, unless *box_props* is given for that row,
        draws a translucent fill of the same color (see *fill_alpha*).
        Defaults to None: black lines and no fill, unless *line_props* /
        *box_props* say otherwise. For full control use those instead;
        a per-row *line_props* color overrides *color*.
    fill_alpha : float, default: 0.3
        Opacity of the fill drawn for a row that has a *color* but no
        explicit *box_props*. Ignored when no such fill is drawn.
    line_props : dict or sequence of dict, optional
        Per-row line styling. A single dict applies to every row; a
        sequence sets each row individually and must have length equal
        to the number of rows. See `draw_pavement` for the dict
        semantics.
    box_props : dict or sequence of dict, optional
        Per-row background fill. A single dict applies to every row; a
        sequence sets each row individually and must have length equal
        to the number of rows. Takes precedence over *color* for the
        fill. See `draw_pavement` for the dict semantics.
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
        If *data* is empty; if *positions*, *bins*, *widths*, *color*,
        *labels*, *line_props*, or *box_props* is given as a sequence
        with the wrong length; or for any reason raised by the
        underlying `pavement_stats` or `draw_pavement` calls (e.g.
        non-positive *bins* or invalid *orientation*).

    See Also
    --------
    pavement_stats : Compute quantile values for one dataset.
    draw_pavement : Render one row from precomputed values.
    pavement.bokeh.plot : The Bokeh equivalent.
    """
    data, weight_rows, labels, labelled = normalize_rows(
        data, weights, categories, labels)
    n = len(data)
    if positions is None:
        positions = list(range(1, n + 1))
    elif len(positions) != n:
        raise ValueError(
            f"positions has length {len(positions)}, expected {n}")
    bins = broadcast(bins, n, "bins",
                     lambda v: v is None or isinstance(v, Integral))
    widths = broadcast(widths, n, "widths", lambda v: isinstance(v, Number))
    if color is None:
        colors: list[Any] = [None] * n
    else:
        colors = broadcast(color, n, "color", lambda v: isinstance(v, str))
    line_props = broadcast(line_props, n, "line_props",
                           lambda v: v is None or isinstance(v, Mapping))
    box_props = broadcast(box_props, n, "box_props",
                          lambda v: v is None or isinstance(v, Mapping))
    if ax is None:
        ax = plt.gca()
    artists = []
    for dataset, w, pos, b, width, col, lp, bp in zip(
            data, weight_rows, positions, bins, widths, colors,
            line_props, box_props):
        # color is a convenience: tint the lines, and (unless box_props is
        # given for this row) draw a translucent fill of the same color. A
        # per-row line_props color wins over color.
        row_line = {**({'color': col} if col is not None else {}), **(lp or {})}
        if bp is None and col is not None:
            bp = {'facecolor': col, 'alpha': fill_alpha}
        values = pavement_stats(dataset, bins=b, weights=w)
        artists.append(draw_pavement(
            values, position=pos, width=width,
            tassel_extent=tassel_extent, show_tassels=show_tassels,
            show_box=show_box,
            orientation=orientation, line_props=row_line or None,
            box_props=bp, data=dataset, ax=ax))
    if labelled:
        set_ticks = ax.set_xticks if orientation == 'vertical' else ax.set_yticks
        set_ticks(list(positions), [str(label) for label in labels])
    if value_label is not None:
        if orientation == 'vertical':
            ax.set_ylabel(value_label)
        else:
            ax.set_xlabel(value_label)
    return artists


def spark(
    data: Sequence[float],
    weights: Sequence[float] | None = None,
    bins: int | None = 4,
    orientation: Literal['vertical', 'horizontal'] = 'horizontal',
    width: float = 0.6,
    tassel_extent: float = 0.05,
    show_tassels: bool = False,
    show_box: bool | None = None,
    color: str | None = None,
    fill_alpha: float = 0.3,
    line_props: Mapping[str, Any] | None = None,
    box_props: Mapping[str, Any] | None = None,
    figsize: tuple[float, float] | None = None,
    dpi: float = 200,
    pad: float = 0.0,
    transparent: bool = True,
    path: str | None = None,
) -> Figure:
    """
    Render a single pavement as a borderless inline "sparkline" image.

    A spark is a pavement stripped to its ink: one row drawn on its own
    figure, with no axes, ticks, labels, or surrounding whitespace, so
    the box and tassels run right to the edges of the image. The main
    use is to save a small PNG and drop it inline in text, sized to sit
    among words like one of Tufte's sparklines.

    Unlike `plot`, this draws exactly one distribution (a 1D sequence of
    values) and owns its figure — it creates one rather than drawing on
    a shared `~matplotlib.axes.Axes`. It defaults to ``'horizontal'`` so
    the value axis runs left-to-right like the surrounding text.

    Parameters
    ----------
    data : sequence of float
        The values to summarize as a single pavement row.
    weights : sequence of float, optional
        Positive weights parallel to *data*.
    bins : int or None, default: 4
        Number of equal-mass bins. None shows all the data instead of
        binning it (see `pavement_stats`).
    orientation : {'vertical', 'horizontal'}, default: 'horizontal'
        Direction of the value axis. 'horizontal' (the default here,
        unlike `plot`) runs values left-to-right, the natural fit for an
        inline strip; 'vertical' runs them bottom-to-top.
    width : float, default: 0.6
        Thickness of the box outline, perpendicular to the value axis.
        Only its ratio to *tassel_extent* matters — the figure is
        scaled to fit whatever is drawn.
    tassel_extent : float, default: 0.05
        How far tassel marks extend beyond the box at repeated values.
    show_tassels : bool, default: False
        Whether to draw tassel marks at repeated quantile values.
    show_box : bool or None, default: None
        Whether to draw the two long box edges. None (the default) draws
        them when binned and omits them for a rug (``bins=None``), so a
        rug spark reads like a plain rug; True or False forces it.
    color : str, optional
        Tints the lines and, unless *box_props* is given, draws a
        translucent fill of the same color (see *fill_alpha*). Defaults
        to black lines and no fill.
    fill_alpha : float, default: 0.3
        Opacity of the fill drawn when *color* is given without an
        explicit *box_props*.
    line_props : dict, optional
        Line2D properties for the ticks and box edges. See
        `draw_pavement`. A color here overrides *color*.
    box_props : dict, optional
        Background fill properties; takes precedence over *color* for
        the fill. See `draw_pavement`.
    figsize : (float, float), optional
        Figure size in inches. Defaults to a word-sized strip —
        ``(1.4, 0.3)`` for horizontal, transposed for vertical.
    dpi : float, default: 200
        Dots per inch, high enough that the small image stays crisp in
        print. With the default *figsize* a horizontal spark is about
        280x60 pixels.
    pad : float, default: 0.0
        Extra breathing room around the drawn geometry, as a fraction of
        its extent on each axis. Defaults to none: the box runs flush to
        the image edge (the half-stroke needed to keep the outermost
        lines from being clipped is always added on top of this, so a
        flush edge still shows its full thickness). Raise it to inset the
        pavement within the image.
    transparent : bool, default: True
        Draw on a transparent background (and save with transparency),
        so the strip blends into whatever it's placed on.
    path : str, optional
        If given, the figure is saved here (e.g. a ``.png``) at *dpi*
        with no extra border. The `~matplotlib.figure.Figure` is
        returned either way.

    Returns
    -------
    matplotlib.figure.Figure
        The figure holding the spark. The caller is responsible for
        closing it (e.g. ``plt.close(fig)``) when done.

    See Also
    --------
    plot : Draw one or more pavement rows on a shared Axes.
    draw_pavement : The underlying single-row renderer.
    """
    if figsize is None:
        figsize = (1.4, 0.3) if orientation == 'horizontal' else (0.3, 1.4)
    values = pavement_stats(data, bins=bins, weights=weights)
    fig = plt.figure(figsize=figsize, dpi=dpi)
    # An axes filling the whole figure: the pavement is the entire image.
    ax = fig.add_axes((0, 0, 1, 1))
    # color is a convenience, mirroring plot(): tint the lines and, unless
    # box_props is given, fill with a translucent version of the same color.
    row_line = {**({'color': color} if color is not None else {}),
                **(line_props or {})}
    if box_props is None and color is not None:
        box_props = {'facecolor': color, 'alpha': fill_alpha}
    line_width = row_line.get('linewidth', row_line.get('lw', 1.0))
    position = 1.0
    draw_pavement(
        values, position=position, width=width,
        tassel_extent=tassel_extent, show_tassels=show_tassels,
        show_box=show_box,
        orientation=orientation, line_props=row_line or None,
        box_props=box_props, data=data, ax=ax)
    # Fit the view tightly to the drawn geometry. The perpendicular extent
    # is the largest tick reach (a tassel, where present, else the box
    # half-width); the value extent is the box span.
    spec = row_spec(values, position, width, orientation,
                    tassel_extent, show_tassels)
    reach = max(t.reach for t in spec.ticks)
    value_extent = (spec.value_high - spec.value_low) or 1.0
    pos_extent = 2 * reach
    # A box edge sitting on the image boundary would otherwise lose half
    # its stroke to clipping. Expand each limit by the half-stroke width
    # in data units so flush edges show full thickness: a point is 1/72
    # inch, the axes fills the figure, so data-per-inch is extent/inches
    # (the dpi cancels). Any *pad* is extra breathing room on top.
    value_inches, pos_inches = (figsize if orientation == 'horizontal'
                                else (figsize[1], figsize[0]))
    value_margin = line_width * value_extent / (144 * value_inches) \
        + pad * value_extent
    pos_margin = line_width * pos_extent / (144 * pos_inches) \
        + pad * pos_extent
    value_lim = (spec.value_low - value_margin, spec.value_high + value_margin)
    pos_lim = (position - reach - pos_margin, position + reach + pos_margin)
    if orientation == 'horizontal':
        ax.set_xlim(value_lim)
        ax.set_ylim(pos_lim)
    else:
        ax.set_ylim(value_lim)
        ax.set_xlim(pos_lim)
    ax.set_axis_off()
    if transparent:
        fig.patch.set_alpha(0.0)
    if path is not None:
        fig.savefig(path, dpi=dpi, transparent=transparent, pad_inches=0)
    return fig


def margin(
    data: Iterable[float],
    axis: Literal['x', 'y'] = 'x',
    where: str | None = None,
    bins: int | None = 4,
    weights: Sequence[float] | None = None,
    pad: float = 0.03,
    size: float = 0.04,
    expand_margins: bool = True,
    show_tassels: bool = False,
    show_box: bool | None = None,
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
    show_tassels : bool, default: False
        Whether to draw tassel marks at repeated quantile values.
    show_box : bool or None, default: None
        Whether to draw the two long box edges. None (the default) draws
        them when binned and omits them for a rug (``bins=None``), so a
        rug marginal reads like an ordinary rug plot; True or False forces
        it.
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
    # Match the package-wide tassel proportion: the spark defaults reach
    # tassel_extent past the box *half*-width, a ratio of 0.05/(0.6/2) = 1/6.
    # Here the box thickness is box_size (its half is box_size/2), so
    # box_size/12 gives that same 1/6-of-the-half reach.
    tassel_extent = box_size / 12
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
        tassel_extent=tassel_extent,
        show_tassels=show_tassels,
        show_box=show_box,
        orientation=orientation,
        line_props=props,
        box_props=bprops,
        data=data,
        ax=ax,
    )
    if placement == 'inside' and expand_margins:
        # Reserve room so the strip doesn't sit on top of the data:
        # the strip's own inward footprint (pad + box + tassel) plus
        # another pad of breathing room on the data side, matching the
        # strip's gap from the frame edge. ax.margins(m) leaves
        # m/(1+2m) of the view empty per side; invert that to cover it.
        footprint = min(2*box_pad + box_size + tassel_extent, 0.45)
        required = footprint / (1 - 2*footprint)
        mx, my = ax.margins()
        if axis == 'x':
            ax.margins(y=max(my, required))
        else:
            ax.margins(x=max(mx, required))
    if (axis == 'x' and side == 'top' and placement == 'outside'
            and ax.get_title()):
        # Lift the title above the marginal (box + tassels) so they
        # don't overlap. Setting _autotitlepos stops matplotlib's
        # auto title positioning from clobbering this on the next draw.
        marginal_top = 1 + box_pad + box_size + tassel_extent
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
