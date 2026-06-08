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
each bin's value range, percentile band, and value share), and two `holoviews.Segments`
— the quantile ticks and the box edges. Keeping the lines separate from
the fill means the ticks and box share one consistent style; a repeated
quantile value (data piled up) simply extends its own tick into a
tassel, so every line is drawn exactly once. The ticks carry their own
hover, like a rug plot's.

The headline function is `plot`, which mirrors the matplotlib backend's
`pavement.matplotlib.plot`: it accepts a single dataset, a wide list of
datasets, or tidy data plus *categories*, and returns a HoloViews
object. Because
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
>>> phv.plot([1, 2, 3, 4, 5])                   # doctest: +SKIP
>>> phv.plot(values, categories=labels)         # doctest: +SKIP
"""

from __future__ import annotations

import base64
from collections.abc import Hashable, Iterable, Sequence
from numbers import Integral, Number
from typing import Any, Literal

import holoviews as hv
import numpy as np

from .core import pavement_stats
from ._geometry import (
    bin_corners,
    broadcast,
    hover_bins,
    hover_html,
    long_box_edges,
    normalize_rows,
    resolve_colors,
    row_spec,
    tick_segment,
    ValueFormat,
)

__all__ = ["pavement_elements", "plot", "with_marginals"]

# Hover dimensions. Each fill and tick carries a single ``hover`` string (the
# row name, value, percentile, and count, line-break separated with the empty
# lines dropped — see `hover_html`), the one field every backend's tooltip
# reads. Fills also keep numeric low/high for the plotly hover geometry (which
# samples the value axis to label each point; not shown).
_FILL_VDIMS = ["low", "high", "hover"]
_TICK_VDIMS = ["hover"]


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


def _default_colors(n: int) -> list[str]:
    """HoloViews' own default color cycle, *n* entries.

    HoloViews auto-cycles this for the elements that support it (Scatter,
    Curve, ...) but not for Rectangles, so we apply it ourselves. Sharing
    the exact cycle means a default-colored pavement's groups match a
    default-colored main plot's groups, in the same key order — on every
    backend, since this cycle is backend-independent.
    """
    palette = list(hv.Cycle().values)
    if not palette:
        # hv.Cycle() is empty until a backend is loaded. Without this guard
        # the modulo below raises an opaque ZeroDivisionError for any input.
        raise RuntimeError(
            "no active HoloViews extension; call hv.extension('bokeh') "
            "(or 'plotly'/'matplotlib') before building a pavement plot"
        )
    return [palette[i % len(palette)] for i in range(n)]


def _row_geometry(
    values: Sequence[float],
    position: float,
    width: float,
    orientation: Literal["vertical", "horizontal"],
    tassel_extent: float,
    show_tassels: bool,
    show_box: bool | None,
    group: Hashable | None,
    value_format: ValueFormat | None,
    data: Sequence[float] | None = None,
    rug: bool = False,
) -> tuple[list[tuple], list[tuple], list[tuple]]:
    """Build the (fill, tick, box-edge) tuples for one row.

    Returns ``(fills, ticks, edges)``. A fill is
    ``(x0, y0, x1, y1, low, high, hover)``; a tick is
    ``(x0, y0, x1, y1, hover)``; an edge is ``(x0, y0, x1, y1)``. *hover* is the
    composed tooltip string (the row name, value, percentile, and count, with
    empty lines dropped — see `hover_html`), shown verbatim by every backend;
    *low*/*high* stay numeric for the plotly hover geometry. The shared
    `row_spec` does the binning, the one-tick-per-distinct-value (tassel)
    logic, and (from *data*) the per-bin/per-tick value counts.
    """
    spec = row_spec(values, position, width, orientation,
                    tassel_extent, show_tassels, value_format, data=data)
    name = None if group is None else str(group)

    # Fills: one borderless rectangle per equal-mass bin, a hover target
    # reading as a value range, a percentile band, and a value share. A rug
    # instead hovers the gaps between its distinct values (`hover_bins` drops
    # the zero-width bins at repeated points), so it gets the same easy hover
    # targets between its lines. An empty box (a rug gap, or a bin whose mass
    # sits on its edges) drops the band, which would otherwise read as a
    # misleading "pNN to pNN" over a stretch holding no data; low/high stay for
    # the plotly hover geometry.
    fills: list[tuple] = []
    for b in hover_bins(spec, rug):
        (x0, y0), (x1, y1) = bin_corners(b.low, b.high, position, spec.half,
                                         orientation)
        band = b.band if (b.inside or not b.count) else ""
        hover = hover_html(name, b.value_range, band, b.count)
        fills.append((x0, y0, x1, y1, b.low, b.high, hover))

    # Ticks: one per distinct value, reaching past the box as a tassel
    # where it repeats. A line hover reads as a single quantile and value.
    ticks: list[tuple] = []
    for t in spec.ticks:
        seg = tick_segment(position, t.reach, t.value, orientation)
        ticks.append((*seg, hover_html(name, t.value_str, t.quantile, t.count)))

    # Box edges: each populated bin closes over itself and a gap opens where
    # the mass clumps onto a value line; show_box True forces one unbroken
    # span, False (and, by default, a rug) draws none. Shared with every
    # backend via `box_edge_spans`.
    edges = long_box_edges(spec, show_box)
    return fills, ticks, edges


def pavement_elements(
    data: Iterable[float],
    bins: int | None = 4,
    weights: Sequence[float] | None = None,
    position: float = 1,
    width: float = 0.6,
    tassel_extent: float = 0.05,
    show_tassels: bool = False,
    show_box: bool | None = None,
    orientation: Literal["vertical", "horizontal"] = "vertical",
    group: Hashable | None = None,
    value_format: ValueFormat | None = None,
) -> dict[str, Any]:
    """
    Build the raw HoloViews elements for a single pavement row.

    The lower-level companion to `plot`: it computes one row's quantile
    values and returns the unstyled component elements, leaving styling,
    overlaying, and axis labelling to the caller. `plot` wraps this.

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
    tassel_extent : float, default: 0.05
        How far tassel marks extend beyond the box at repeated values.
    show_tassels : bool, default: False
        Whether to draw tassel marks at repeated quantile values.
    show_box : bool or None, default: None
        Whether to draw the two long box edges. None (the default) draws
        them when binned and omits them for a rug (``bins=None``), so a rug
        reads like a plain rug plot; True or False forces it. When omitted,
        the ``"box"`` element is an empty `holoviews.Segments`.
    orientation : {'vertical', 'horizontal'}, default: 'vertical'
        Direction of the value axis. 'vertical' puts values on the
        y-axis; 'horizontal' puts them on the x-axis.
    group : hashable, optional
        If given, the row name; it leads each fill's and tick's composed
        ``hover`` string.
    value_format : callable, optional
        Function mapping a value to its hover display string, e.g.
        ``lambda v: f"${v:,.2f}"``. Applies to the bin value ranges and
        tick values; defaults to 3 significant figures.

    Returns
    -------
    dict
        Maps component name to the unstyled HoloViews element:

        - ``"fill"``: a `holoviews.Rectangles` of the equal-mass bins,
          with value dimensions ``low``, ``high``, and ``hover`` (the
          composed tooltip string). Meant to be drawn borderless, as a
          hover target behind the lines.
        - ``"ticks"``: a `holoviews.Segments`, one tick per distinct
          quantile value (extended into a tassel where the value
          repeats), with value dimension ``hover``.
        - ``"box"``: a `holoviews.Segments` of the two long box edges.

    See Also
    --------
    plot : The headline, multi-row function built on this.
    pavement.pavement_stats : The underlying quantile computation.
    """
    data = list(data)
    values = pavement_stats(data, bins=bins, weights=weights)
    fills, ticks, edges = _row_geometry(
        values, position, width, orientation,
        tassel_extent, show_tassels, show_box,
        group, value_format, data=data, rug=bins is None)
    return {
        "fill": hv.Rectangles(fills, vdims=_FILL_VDIMS),
        "ticks": hv.Segments(ticks, vdims=_TICK_VDIMS),
        "box": hv.Segments(edges),
    }


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
    else:  # "ticks" or "box": Segments lines, styled identically
        if backend in _SEG_LINE_COLOR:
            opts[_SEG_LINE_COLOR[backend]] = color
    # Hover is interactive-backend only; matplotlib silently has none.
    # plotly gets its hover from a separate marker layer (shapes can't
    # hover), so only bokeh's glyphs are wired up here. ``hover_tooltips``
    # sets the template; binding it to every row's fill and ticks (not
    # just one) is finished by `_bokeh_hover_hook` at render time.
    if hover and backend == "bokeh" and role in ("fill", "ticks"):
        # The composed ``hover`` field, rendered as raw HTML so its line breaks
        # show (and so empty lines, already dropped, leave no blank row).
        opts["hover_tooltips"] = "@hover{safe}"
    return element.opts(**opts)


def _bokeh_hover_hook(plot: Any, element: Any) -> None:
    """Bind the bokeh hover tool to every fill and tick glyph.

    HoloViews' ``hover_tooltips`` builds a HoverTool with the right
    template, but across an overlay the rendered tool ends up bound to a
    single glyph — so only one row, and only its bin fills, would hover.
    Overlaid elements merge their (identical) hover tools into one, and
    the merge keeps just one renderer.

    Run as a finalize hook on the assembled plot, this rebinds that one
    tool to every glyph carrying the hover columns — each row's bin fills
    (`~holoviews.Rectangles`) and quantile ticks (`~holoviews.Segments`),
    so the whole pavement hovers, boxes and value lines alike. The box
    edges carry no ``hover`` column, so they stay non-hovering, matching
    the other backends. Any duplicate hover tools the merge left are
    dropped. Idempotent, so it is safe if the hook runs more than once.
    """
    from bokeh.models import GlyphRenderer, HoverTool
    fig = plot.state
    hovers = [t for t in fig.tools if isinstance(t, HoverTool)]
    if not hovers:
        return
    targets = [r for r in fig.renderers
               if isinstance(r, GlyphRenderer)
               and "hover" in getattr(r.data_source, "data", {})]
    hovers[0].renderers = targets
    for extra in hovers[1:]:
        fig.tools.remove(extra)


def _decode_plotly_array(arr: Any) -> np.ndarray:
    """Decode a plotly trace coordinate array, binary-encoded or plain."""
    if isinstance(arr, dict) and "bdata" in arr:
        return np.frombuffer(base64.b64decode(arr["bdata"]), dtype=arr["dtype"])
    return np.asarray(arr, dtype=float) if arr is not None else np.empty(0)


# How many invisible hover points to spread along a row's value axis. A
# dense line (rather than one point per bin) means hovering anywhere
# along a bin shows its tooltip, instead of only near the bin's center.
_HOVER_SAMPLES = 80


def _plotly_hover_layer(
    fill: Any,
    orientation: str,
) -> Any:
    """An invisible Scatter line carrying per-bin hover text, for plotly.

    HoloViews renders the fills and lines as plotly *shapes*, which can't
    hold hover, and its plotly Scatter exposes no tooltip control. So for
    plotly we overlay a dense line of invisible markers down the row's
    value axis (the bins stack along it at one position) and use a render
    hook to inject a hovertemplate and each marker's bin's composed hover
    text (value range, percentile band, value share — empties dropped) as
    per-point ``text``, the same display string bokeh's glyph hover shows.

    The hook finds its own trace by matching the markers' value-axis
    coordinates (distinctive per row) against either trace axis —
    "either" because a side marginal is transposed by the adjoint, moving
    those coordinates from x to y. This separates rows reliably as long as
    their sampled value ranges differ; two groups sharing the same min and
    max would produce identical samples and could match each other's trace
    — unusual, but the reason the match keys on the full coordinate array
    rather than just the endpoints.
    """
    low = fill.dimension_values("low")
    high = fill.dimension_values("high")
    texts = fill.dimension_values("hover")
    if len(low) == 0:
        return hv.Scatter([])
    # The bins stack along the value axis at a single position; sample
    # that axis densely and label each sample by the bin containing it.
    if orientation == "horizontal":
        position = (fill.dimension_values("y0")[0]
                    + fill.dimension_values("y1")[0]) / 2
    else:
        position = (fill.dimension_values("x0")[0]
                    + fill.dimension_values("x1")[0]) / 2
    samples = np.linspace(float(low.min()), float(high.max()), _HOVER_SAMPLES)
    edges = np.append(low, high[-1])  # contiguous bin edges
    which = np.clip(np.searchsorted(edges, samples, side="right") - 1,
                    0, len(low) - 1)
    # Each sample carries its bin's already-composed hover text verbatim (name,
    # value, percentile, count — empties dropped), shown the same way the
    # dedicated plotly backend does it: per-point text, so an empty box's
    # missing band leaves no blank line.
    text = [texts[i] for i in which]
    template = "%{text}<extra></extra>"
    constant = np.full(_HOVER_SAMPLES, position)
    points = (samples, constant) if orientation == "horizontal" \
        else (constant, samples)

    def matches(coords: np.ndarray) -> bool:
        return len(coords) == len(samples) and bool(np.allclose(coords, samples))

    def hook(plot: Any, element: Any) -> None:
        for trace in plot.state.get("data", []):
            if trace.get("type") != "scatter":
                continue
            if matches(_decode_plotly_array(trace.get("x"))) or \
                    matches(_decode_plotly_array(trace.get("y"))):
                trace["text"] = text
                trace["hovertemplate"] = template
                trace["hoverinfo"] = "text"
                trace["showlegend"] = False
                trace.setdefault("marker", {})["opacity"] = 0  # invisible
                return

    return hv.Scatter(points).opts(hooks=[hook])


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
    orientation: Literal["vertical", "horizontal"] = "vertical",
    value_label: str | None = None,
    value_format: ValueFormat | None = None,
    color: str | Sequence[str] | None = None,
    fill_alpha: float = 0.3,
    hover: bool = True,
    show_legend: bool = False,
    transpose_labels: bool = False,
) -> Any:
    """
    Build an interactive pavement plot as a HoloViews object.

    The HoloViews counterpart of `pavement.matplotlib.plot`. Accepts the
    same three input shapes — a single 1D dataset, a wide sequence of
    datasets, or tidy data plus *categories* — and returns a HoloViews
    object that renders through any backend.

    A single dataset returns a `holoviews.Overlay` (the bins, plus any
    tassels). Multiple rows return a `holoviews.NdOverlay` keyed by
    *labels*, which gives a legend and a consistent per-row color cycle;
    in tidy form this is the "split by category" case. Either result is
    a plain HoloViews object, so it composes with the framework: overlay
    it with ``*``, adjoin it as a marginal with ``<<``, or restyle it
    with ``.opts``.

    Parameters
    ----------
    data : sequence of float, or sequence of iterables of float
        The values to plot. Shape determines the mode, as in
        `pavement.matplotlib.plot`.
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
    tassel_extent : float, default: 0.05
        How far tassel marks extend beyond the box.
    show_tassels : bool, default: False
        Whether to draw tassel marks at repeated quantile values.
    show_box : bool or None, default: None
        Whether to draw each row's two long box edges. None (the default)
        draws them for a binned row and omits them for a rug
        (``bins=None``), so a rug reads like a plain rug plot; True or
        False forces it. Resolved per row, so a mixed *bins* sequence gets
        the right default for each.
    orientation : {'vertical', 'horizontal'}, default: 'vertical'
        Direction of the value axis.
    value_label : str, optional
        If given, label the value axis (x for horizontal, y otherwise).
        Defaults to ``None`` (unlabelled), as the ``matplotlib`` backend
        does; pass a string to label the axis.
    value_format : callable, optional
        Function mapping a value to its hover display string, e.g.
        ``lambda v: f"${v:,.2f}"``. Applies to the bin value ranges and
        tick values; defaults to 3 significant figures.
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
    show_legend : bool, default: False
        Whether to show the category legend (only relevant with multiple
        rows). Off by default; pass True to label the rows with a legend.
        Has no effect on matplotlib, which can't build a legend handle for
        the bin glyphs. `with_marginals` turns this off for marginals,
        whose legend duplicates the main plot's.
    transpose_labels : bool, default: False
        Place the value-axis label and the position ticks on the
        *opposite* axes from *orientation*. Use this only when the plot
        will be rendered transposed — as HoloViews' adjoint does for a
        right/left marginal, where it swaps the axes but not the tick
        labels. `with_marginals` sets this for the right marginal so its
        category ticks land on the (horizontal) position axis rather
        than the shared value axis. Leave it False for a standalone plot.

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
    pavement.matplotlib.plot : The matplotlib equivalent.
    pavement_elements : The single-row element builder this wraps.

    Examples
    --------
    >>> import holoviews as hv
    >>> import pavement.holoviews as phv
    >>> hv.extension('bokeh')                              # doctest: +SKIP
    >>> phv.plot([1, 2, 3, 4, 5])                          # doctest: +SKIP

    Split tidy data by category, then adjoin it as a top marginal::

        main = hv.Scatter((x, y))
        top = phv.plot(x, categories=group, orientation='horizontal')
        layout = main << top                               # doctest: +SKIP
    """
    # labelled: whether to tick the position axis with per-row labels —
    # only when the rows mean something nameable (categories or explicit
    # labels), not for an anonymous single row at position 1.
    data, weight_rows, labels, labelled = normalize_rows(
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

    rows = {}
    for label, dataset, w, pos, b, width, col in zip(
            labels, data, weight_rows, positions, bins, widths, colors):
        group = label if n > 1 else None
        els = pavement_elements(
            dataset, bins=b, weights=w, position=pos, width=width,
            tassel_extent=tassel_extent, show_tassels=show_tassels,
            show_box=show_box, orientation=orientation, group=group,
            value_format=value_format)
        # Fill behind (hover target), then the box edges, then the ticks.
        parts = [_style(els[role], role, col, fill_alpha, hover)
                 for role in ("fill", "box", "ticks")]
        # bokeh hovers the glyphs directly; plotly draws them as
        # non-hoverable shapes, so add an invisible marker layer there.
        if hover and hv.Store.current_backend == "plotly":
            parts.append(_plotly_hover_layer(els["fill"], orientation))
        rows[label] = hv.Overlay(parts)

    if n == 1:
        result = rows[labels[0]]
    else:
        result = hv.NdOverlay(rows, kdims="group")

    # Label the value axis; the perpendicular (position) axis carries
    # the row labels as ticks when the rows are nameable, else nothing —
    # its bare "x0"/"y0" dimension name is never meaningful here. When
    # the plot will be displayed transposed (transpose_labels), put the
    # labels and ticks on the swapped axes so they still match the data.
    value_axis = "x" if orientation == "horizontal" else "y"
    pos_axis = "y" if orientation == "horizontal" else "x"
    if transpose_labels:
        value_axis, pos_axis = pos_axis, value_axis
    # An unlabelled value axis (the default) is blanked, not left to fall
    # back to the bare "x0"/"y0" dimension name HoloViews would otherwise show.
    value_text = "" if value_label is None else value_label
    opts: dict[str, Any] = {f"{value_axis}label": value_text, f"{pos_axis}label": ""}
    if labelled:
        opts[f"{pos_axis}ticks"] = [
            (pos, str(label)) for pos, label in zip(positions, labels)]
    if n > 1:
        # matplotlib can't build a legend handle for Rectangles glyphs;
        # the legend is otherwise an interactive-backend feature.
        opts["show_legend"] = show_legend and hv.Store.current_backend != "matplotlib"
    # bokeh merges the per-element hover tools into one bound to a single
    # glyph; a finalize hook rebinds it to every row's fills and ticks.
    if hover and hv.Store.current_backend == "bokeh":
        opts["hooks"] = [_bokeh_hover_hook]
    return result.opts(**opts)


def with_marginals(
    main: Any,
    x: Sequence[float] | None = None,
    y: Sequence[float] | None = None,
    categories: Sequence[Hashable] | None = None,
    x_label: str = "x",
    y_label: str = "y",
    size: int | None = None,
    **kwargs: Any,
) -> Any:
    """
    Adjoin pavement marginals to a plot — x on top, y on the right.

    A one-call joint-plot helper that hides the things you would
    otherwise have to know to adjoin a pavement with HoloViews' ``<<``
    operator: that each marginal must be built with
    ``orientation='horizontal'`` (HoloViews orients each adjoined slot to
    share the main plot's axis), that ``<<`` fills the right slot before
    the top, and how to keep the marginal strips thin. Pass the marginal
    data and it places them correctly.

    The marginals are drawn as thin strips with their (redundant)
    category legends turned off, so they don't crowd the main plot. With
    *categories*, each is split by category; leaving *color* at its
    default (see `plot`) makes the groups match a default-colored
    *main* plot, so a colored scatter and its marginals share one color
    scheme for free.

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
        marginal by category, as in `plot`.
    x_label, y_label : str, default: 'x', 'y'
        Value-axis labels for the top and right marginals.
    size : int, optional
        Thickness of each marginal strip in pixels (bokeh/plotly; the
        matplotlib adjoint sizes its own). Defaults to roughly 40px per
        category, so multi-group marginals stay legible. Pass a larger
        value to give crowded categories more room.
    **kwargs
        Forwarded to `plot` for both marginals (e.g. *bins*,
        *color*, *fill_alpha*, *show_tassels*, *show_legend*,
        *value_format*).
        *orientation* is set automatically and must not be passed;
        *show_legend* defaults to False here but may be overridden.

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
    plot : Builds each marginal; call it directly for finer control.

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
            "call plot directly if you need to set it")
    if "transpose_labels" in kwargs:
        raise ValueError(
            "transpose_labels is set per slot by with_marginals; "
            "call plot directly if you need to control it")
    kwargs.setdefault("show_legend", False)

    if size is None:
        n_groups = len(set(categories)) if categories is not None else 1
        size = 40 * n_groups + 30

    def strip(data: Sequence[float], label: str, dim: str,
              transpose: bool) -> Any:
        pav = plot(data, categories=categories, orientation="horizontal",
                       value_label=label, transpose_labels=transpose, **kwargs)
        return _thin(pav, dim, size)

    layout = main
    # `<<` fills the right slot first, then the top. Add y (right) before
    # x (top); for an x-only marginal, hold the right slot open with an
    # Empty so x still lands on top rather than the right. The right slot
    # is rendered transposed, so its strip is thinned in width (not
    # height) and its labels are transposed to keep the axes sensible.
    if y is not None:
        layout = layout << strip(y, y_label, "width", transpose=True)
    elif x is not None:
        layout = layout << hv.Empty()
    if x is not None:
        layout = layout << strip(x, x_label, "height", transpose=False)
    return layout


# The option that sets a fixed pixel extent along one dimension, per
# backend. bokeh uses inner-frame dimensions; plotly uses overall figure
# dimensions. matplotlib has no per-element pixel size (it sizes its own
# adjoint slots), so it is absent and left alone.
_THIN_OPT = {
    "bokeh": {"width": "frame_width", "height": "frame_height"},
    "plotly": {"width": "width", "height": "height"},
}


def _thin(strip: Any, dim: str, size: int) -> Any:
    """Constrain a marginal strip's short dimension to *size* pixels.

    *dim* is ``"height"`` (top strip) or ``"width"`` (right strip).
    Without this, bokeh and plotly oversize their adjoint marginals;
    matplotlib sizes its own and is left alone.
    """
    names = _THIN_OPT.get(hv.Store.current_backend)
    if names is None:
        return strip
    opt = names[dim]
    return strip.opts(hv.opts.Rectangles(**{opt: size}),
                      hv.opts.Segments(**{opt: size}))
