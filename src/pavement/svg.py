"""
Inline, interactive pavement sparklines as self-contained SVG.

Where `pavement.matplotlib.spark` renders a borderless pavement to a
raster image for print, this backend emits the same idea as a string of
SVG you can drop straight into HTML, Markdown, or an email — no plotting
library, no JavaScript bundle, no CDN. The returned ``<svg>`` *is* the
artifact.

That makes it the natural fit for an inline sparkline:

- **Vector and themeable.** Lines default to ``currentColor``, so the
  spark inherits the surrounding text color (dark mode included), and it
  stays crisp at any size. ``vector-effect="non-scaling-stroke"`` keeps
  the box outline a constant width however small the spark is scaled.
- **Sizes with the text.** By default the root carries
  ``height: 1em; width: auto``, so ``spark(values)`` drops into a
  sentence and tracks the font size like a word.
- **Interactive with zero JavaScript.** Every equal-mass bin is a hover
  target carrying its quantile band and value range in a native
  ``<title>`` tooltip — the same hover text the Bokeh and Plotly
  backends show — and each quantile tick carries its single value. A
  small rug (``bins=None``) makes every value hoverable; a dense one
  falls back to a single whole-spark summary instead (see
  ``tick_hover_limit``) — a spark is read value-by-value or summarised,
  never both. An inline ``<style>`` adds CSS hover feedback: the bin or
  value line under the cursor highlights, signalling the interactivity.
  Both optional.

Only `spark` is exposed; richer multi-row or marginal pavements belong to
the matplotlib and interactive backends. The shared geometry comes from
`pavement._geometry`, so an SVG spark lines up box-for-box with the other
backends.

Examples
--------
>>> import pavement.svg as psvg
>>> markup = psvg.spark([1, 2, 3, 4, 5])          # an <svg>...</svg> string
>>> psvg.spark(values, color="steelblue", path="spark.svg")  # doctest: +SKIP
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Literal
from xml.sax.saxutils import escape, quoteattr

from ._geometry import fmt, row_spec, ValueFormat
from .core import pavement_stats, tally_stats

__all__ = ["spark", "tally"]

# Internal coordinate box. The numbers only set coordinate resolution;
# their ratio is the spark's default shape — a wide, word-like strip,
# matching the matplotlib spark's 1.4:0.3in default. The geometry is
# stretched to fill this box (like matplotlib's axes filling the figure),
# so the data range never distorts the outline's footprint.
_VIEWBOX = {'horizontal': (140.0, 30.0), 'vertical': (30.0, 140.0)}
# Width of a tick's transparent hover hit-area, in px (non-scaling), wide
# enough to grab with mouse or touch.
_HIT_WIDTH = 8.0

# Default tally palette: a dark blue for distinct values, a light blue for
# repeats of them, and a muted dark red for missing. Picked from a
# ColorBrewer diverging ramp — easy on the eyes for regular use, with the
# red reading clearly as "something's off" without being alarmingly bright.
_TALLY_DISTINCT = "#2166ac"
_TALLY_REPEATED = "#92c5de"
_TALLY_MISSING = "#b2182b"


def _num(value: float) -> str:
    """Format a coordinate compactly (no trailing zeros)."""
    return f"{value:.2f}".rstrip('0').rstrip('.')


def _pct(count: int, total: int) -> str:
    """Format a share as a whole-percent string for a tally tooltip.

    A nonzero share that would round down to ``0%`` shows ``<1%`` instead,
    so a real-but-tiny slice (a stray missing value among thousands) never
    reads as nothing.
    """
    frac = count / total
    if 0 < frac < 0.005:
        return "<1%"
    return f"{frac:.0%}"


def _box_lengths(counts: list[int], span: float, min_box: float) -> list[float]:
    """Lengths for a tally's boxes along *span*, proportional to *counts*.

    No box for a nonzero category is shorter than *min_box*, so a tiny
    slice stays visible and hoverable rather than collapsing to a hairline;
    the shortfall is taken proportionally from the boxes still above the
    minimum (a water-filling pass, repeated until it settles). The minimum
    is honored only while it fits the span; with ``min_box <= 0`` (or when
    it can't fit) the layout is purely proportional. *counts* should already
    exclude empty categories, which draw no box at all.
    """
    k = len(counts)
    total = sum(counts)
    if total <= 0:
        return [0.0] * k
    if min_box <= 0 or k * min_box >= span:
        return [span * c / total for c in counts]
    fixed = [False] * k
    while True:
        free = [i for i in range(k) if not fixed[i]]
        free_count = sum(counts[i] for i in free)
        free_span = span - min_box * (k - len(free))
        newly = [i for i in free
                 if free_count and free_span * counts[i] / free_count < min_box]
        if not newly:
            break
        for i in newly:
            fixed[i] = True
    free_count = sum(counts[i] for i in range(k) if not fixed[i])
    free_span = span - min_box * sum(fixed)
    return [min_box if fixed[i]
            else (free_span * counts[i] / free_count if free_count else 0.0)
            for i in range(k)]


def spark(
    data: Iterable[float],
    weights: Sequence[float] | None = None,
    bins: int | None = 4,
    orientation: Literal['vertical', 'horizontal'] = 'horizontal',
    width: float = 0.6,
    whisker_extent: float = 0.1,
    show_whiskers: bool = True,
    color: str | None = None,
    fill_alpha: float = 0.3,
    line_color: str | None = None,
    line_width: float = 1.2,
    height: str = '1em',
    inline: bool = True,
    hover: bool = True,
    value_format: ValueFormat | None = None,
    tick_hover_limit: int | None = 24,
    highlight: bool = True,
    class_: str = 'pavement-spark',
    path: str | None = None,
) -> str:
    """
    Render a single pavement as a self-contained inline SVG sparkline.

    Returns an ``<svg>...</svg>`` string with no external dependencies —
    paste it into any HTML and it renders, scaling to the surrounding
    text. Like `pavement.matplotlib.spark` it draws exactly one
    distribution (a 1D sequence of values) edge to edge with no axes, and
    defaults to ``'horizontal'`` so the value axis runs left-to-right.

    Parameters
    ----------
    data : iterable of float
        The values to summarize as a single pavement row.
    weights : sequence of float, optional
        Positive weights parallel to *data*.
    bins : int or None, default: 4
        Number of equal-mass bins. None shows all the data instead of
        binning it (see `pavement_stats`), turning the spark into a rug.
    orientation : {'vertical', 'horizontal'}, default: 'horizontal'
        Direction of the value axis. 'horizontal' runs values
        left-to-right, the natural fit for an inline strip.
    width : float, default: 0.6
        Box thickness across the row. As with `pavement.matplotlib.spark`
        only its ratio to *whisker_extent* matters — the geometry is
        stretched to fill the SVG.
    whisker_extent : float, default: 0.1
        How far whisker marks reach beyond the box at repeated values.
    show_whiskers : bool, default: True
        Whether to draw whisker marks at repeated quantile values.
    color : str, optional
        Any CSS color. Tints the lines and fills each bin translucently
        (see *fill_alpha*). Defaults to no fill and ``currentColor``
        lines, so the spark inherits the text color.
    fill_alpha : float, default: 0.3
        Opacity of the per-bin fill drawn when *color* is given.
    line_color : str, optional
        Color for the box and ticks. Overrides *color* for the lines;
        defaults to *color* if given, else ``currentColor``.
    line_width : float, default: 1.2
        Stroke width in pixels. Held constant as the spark scales
        (``non-scaling-stroke``), so lines stay crisp when shrunk.
    height : str, default: '1em'
        CSS height baked onto the root when *inline* is True. ``'1em'``
        makes the spark track the font size; width follows the aspect.
    inline : bool, default: True
        If True, set ``height``/``width``/``vertical-align`` on the root
        so the spark drops into running text and sits on the baseline.
        If False, omit sizing and leave it to your own CSS.
    hover : bool, default: True
        If True, add native ``<title>`` tooltips (no JavaScript): a
        quantile band and value range per bin, and a single value per
        tick (subject to *tick_hover_limit*). When nothing finer is
        hoverable — a dense rug — a single whole-spark summary is used
        instead, so a spark is read value-by-value or summarised, never
        both. False turns all tooltips off.
    value_format : callable, optional
        Function mapping a value to its tooltip display string, e.g.
        ``lambda v: f"${v:,.2f}"``. Applies to the bin value ranges, the
        per-tick values, and the whole-spark summary; defaults to 3
        significant figures.
    tick_hover_limit : int or None, default: 24
        Cap on how many ticks (distinct values) get their own per-value
        tooltip. At or below it, each tick is individually hoverable; a
        denser spark — typically a large rug — falls back to just the
        summary tooltip, since hundreds of overlapping hit-areas are both
        unhelpful and heavy. None lifts the cap (hover every value,
        however many); 0 disables per-tick hover entirely. Binned sparks
        have only ``bins + 1`` ticks, so the default rarely affects them.
    highlight : bool, default: True
        If True, add a scoped ``<style>`` with pure-CSS hover feedback:
        the bin under the cursor brightens and a hovered value line
        thickens — visible cues that the spark is interactive.
    class_ : str, default: 'pavement-spark'
        CSS class on the root ``<svg>``, a hook for your own styling.
    path : str, optional
        If given, also write the markup here. A ``.html``/``.htm`` path
        is wrapped in a minimal standalone document; any other suffix
        (e.g. ``.svg``) is written as-is. The string is returned either
        way.

    Returns
    -------
    str
        The ``<svg>...</svg>`` markup.

    See Also
    --------
    pavement.matplotlib.spark : The raster (PNG) counterpart, for print.
    pavement_stats : Compute the quantile values a spark draws.
    """
    data = list(data)
    n = len(data)
    if n == 0:
        raise ValueError("data must be non-empty")
    values = pavement_stats(data, bins=bins, weights=weights)
    position = 1.0
    spec = row_spec(values, position, width, orientation,
                    whisker_extent, show_whiskers, value_format)
    fmt_value = value_format or fmt
    reach = max(t.reach for t in spec.ticks)
    half = spec.half

    value_low, value_high = spec.value_low, spec.value_high
    if value_high == value_low:  # constant data: give the box a little span
        value_low, value_high = value_low - 0.5, value_high + 0.5
    value_range = value_high - value_low
    perp_low, perp_high = position - reach, position + reach
    perp_range = perp_high - perp_low

    horizontal = orientation == 'horizontal'
    view_w, view_h = _VIEWBOX[orientation]

    def pt(perp: float, value: float) -> tuple[float, float]:
        """Map (perpendicular, value) geometry onto SVG (x, y), filling
        the viewBox. SVG y grows downward, so the value axis is flipped
        for a vertical spark to keep larger values toward the top."""
        fv = (value - value_low) / value_range
        fp = (perp - perp_low) / perp_range
        if horizontal:
            return fv * view_w, fp * view_h
        return fp * view_w, (1.0 - fv) * view_h

    line_paint = line_color or color or 'currentColor'
    fill_paint = color or 'currentColor'
    rest_opacity = fill_alpha if color is not None else 0.0

    def stroke_line(x0: float, y0: float, x1: float, y1: float, *,
                    attrs: str = '', child: str = '') -> str:
        coords = (f'<line{attrs} x1="{_num(x0)}" y1="{_num(y0)}" '
                  f'x2="{_num(x1)}" y2="{_num(y1)}"')
        return f'{coords}>{child}</line>' if child else f'{coords}/>'

    parts: list[str] = []

    def rect(x0: float, y0: float, x1: float, y1: float, *,
             cls: str = '', extra: str = '', child: str = '') -> str:
        x, y = min(x0, x1), min(y0, y1)
        return (f'<rect{cls} x="{_num(x)}" y="{_num(y)}" '
                f'width="{_num(abs(x1 - x0))}" height="{_num(abs(y1 - y0))}" '
                f'{extra}>{child}</rect>')

    if bins is not None:
        # Equal-mass bins: a translucent (or invisible) rect each, spanning
        # the box thickness. Drawn first so they sit behind the lines, and
        # they double as hover targets — the band/range tooltip and the CSS
        # highlight both attach here.
        for b in spec.bins:
            x0, y0 = pt(position - half, b.low)
            x1, y1 = pt(position + half, b.high)
            title = (f'<title>{escape(b.band + chr(10) + b.value_range)}</title>'
                     if hover else '')
            parts.append(rect(
                x0, y0, x1, y1, cls=' class="pvbin"',
                extra=f'fill="{fill_paint}" fill-opacity="{_num(rest_opacity)}" '
                      f'pointer-events="all"', child=title))
    elif color is not None:
        # A rug (one tick per point) has no meaningful bins to hover, but
        # a requested color still fills the box as a single background.
        x0, y0 = pt(position - half, value_low)
        x1, y1 = pt(position + half, value_high)
        parts.append(rect(
            x0, y0, x1, y1,
            extra=f'fill="{fill_paint}" fill-opacity="{_num(fill_alpha)}" '
                  f'pointer-events="none"'))

    # Whether each value line is individually hoverable. While the ticks
    # stay few enough to be worth hovering one by one (binned sparks
    # always are; a small rug is, a dense one isn't), each gets a
    # transparent wide hit-area and a value tooltip; a denser rug skips
    # this and leans on the whole-spark summary instead. Counting the
    # ticks (distinct values) rather than the raw data keeps repeats from
    # inflating the total.
    per_tick_hover = hover and (
        tick_hover_limit is None or len(spec.ticks) <= tick_hover_limit)

    # All the value strokes share their styling, so it lives once on a
    # parent <g> and each line is just coordinates — keeps a dense rug
    # compact. The two long box edges span the value axis at each side;
    # then one tick per distinct value, reaching past the box as a whisker
    # where the value repeats (and closing the box ends at the extremes).
    # A hoverable tick pairs its visible mark with a transparent hit-area
    # inside a <g class="pvtick">, so CSS can thicken the mark on hover.
    marks = [stroke_line(*pt(side, value_low), *pt(side, value_high))
             for side in (position - half, position + half)]
    for t in spec.ticks:
        a = pt(position - t.reach, t.value)
        b = pt(position + t.reach, t.value)
        if per_tick_hover:
            label = (t.quantile + chr(10) + t.value_str) if t.quantile \
                else t.value_str
            marks.append(
                '<g class="pvtick">'
                + stroke_line(*a, *b, attrs=' class="pvmark"')
                + stroke_line(*a, *b, attrs=' class="pvhit" '
                              'stroke="transparent" '
                              f'stroke-width="{_num(_HIT_WIDTH)}" '
                              'pointer-events="all"',
                              child=f'<title>{escape(label)}</title>')
                + '</g>')
        else:
            marks.append(stroke_line(*a, *b))
    parts.append(
        f'<g stroke="{line_paint}" stroke-width="{_num(line_width)}" '
        f'fill="none" vector-effect="non-scaling-stroke" '
        f'pointer-events="none">{"".join(marks)}</g>')

    # CSS hover feedback (pure, scoped): the bin under the cursor brightens
    # its fill, and a hovered value line thickens — both signalling that
    # the spark is interactive. Harmless when an element isn't present.
    style = ''
    if highlight:
        selector = '.' + '.'.join(class_.split())
        hover_opacity = min(1.0, fill_alpha + 0.2) if color is not None else 0.13
        thick = _num(line_width * 2)
        style = (
            f'<style>'
            f'{selector} .pvbin{{transition:fill-opacity .1s ease}}'
            f'{selector} .pvbin:hover{{fill-opacity:{_num(hover_opacity)}}}'
            f'{selector} .pvmark{{transition:stroke-width .1s ease}}'
            f'{selector} .pvtick:hover .pvmark{{stroke-width:{thick}}}'
            f'</style>')

    root_style = 'overflow:visible;'  # let flush edges show their full stroke
    if inline:
        root_style += f'height:{height};width:auto;vertical-align:-0.15em;'
    label = f"pavement sparkline of {n} value{'' if n == 1 else 's'}"
    # A whole-spark summary tooltip — but only when nothing finer is
    # hoverable, so a spark is either summarised as a whole or read value
    # by value, never both. That means a dense rug (no bins, ticks past
    # the limit); a binned or small-rug spark relies on its own per-bin /
    # per-value tooltips instead.
    root_title = ''
    if hover and bins is None and not per_tick_hover:
        summary = (f"{n} value{'' if n == 1 else 's'}, "
                   f"{fmt_value(spec.value_low)} to {fmt_value(spec.value_high)}")
        root_title = f'<title>{escape(summary)}</title>'
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_num(view_w)} {_num(view_h)}" '
        f'preserveAspectRatio="none" class={quoteattr(class_)} '
        f'role="img" aria-label={quoteattr(label)} '
        f'style={quoteattr(root_style)}>'
        f'{root_title}<desc>{escape(label)}</desc>{style}'
        f'{"".join(parts)}</svg>')

    if path is not None:
        document = svg
        if path.endswith(('.html', '.htm')):
            document = ('<!doctype html><meta charset="utf-8">'
                        f'<body>{svg}</body>')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(document)
    return svg


def tally(
    data: Iterable[object],
    orientation: Literal['vertical', 'horizontal'] = 'horizontal',
    distinct_color: str = _TALLY_DISTINCT,
    repeated_color: str = _TALLY_REPEATED,
    missing_color: str = _TALLY_MISSING,
    line_color: str | None = None,
    line_width: float = 1.0,
    min_box: float = 3.0,
    height: str = '1em',
    inline: bool = True,
    hover: bool = True,
    highlight: bool = True,
    class_: str = 'pavement-tally',
    path: str | None = None,
) -> str:
    """
    Render a column's make-up as a self-contained inline SVG strip.

    A companion to `spark` with the same form factor and footprint, but a
    different question. Where a spark summarizes the *distribution* of a
    numeric column, a tally summarizes the *column itself*: three boxes,
    sized in proportion to how many of the column's values are distinct
    (leftmost), how many merely repeat a value already seen (middle), and
    how many are missing (rightmost). It works on a column of any type, and
    surfaces exactly what a pavement plot can't — missing values and
    distinctness.

    The three boxes always fill the strip edge to edge, since the counts
    sum to the total (see `pavement.core.tally_stats`); a category with no
    values draws no box. Each box carries a native ``<title>`` tooltip with
    its share and count — the lines between boxes do not. Returns an
    ``<svg>...</svg>`` string with no external dependencies; paste it into
    any HTML and it renders, scaling to the surrounding text.

    This is an experimental feature; its home in the package may change.

    Parameters
    ----------
    data : iterable
        The column's values, of any type (see `tally_stats`).
    orientation : {'vertical', 'horizontal'}, default: 'horizontal'
        Box layout. 'horizontal' lays the boxes left-to-right
        (distinct, repeated, missing); 'vertical' stacks them top-to-bottom
        in the same order.
    distinct_color, repeated_color, missing_color : str
        Any CSS color for each box. Default to a dark blue, a light blue,
        and a muted dark red.
    line_color : str or None, default: None
        Color of an optional hairline outlining each box (and so separating
        adjacent boxes). The default, None, leaves the boxes borderless,
        separated by their fills alone. When given, the outline is held at a
        constant width as the strip scales (``non-scaling-stroke``).
    line_width : float, default: 1.0
        Outline stroke width in pixels (only when *line_color* is given).
    min_box : float, default: 3.0
        Smallest on-screen length a box may have for a category that has
        *any* values, in viewBox units (the strip is 140 long, so the
        default is ~2% of it). Keeps a tiny-but-nonzero slice — a stray
        missing value among thousands — visible and hoverable instead of
        collapsing to a hairline; the shortfall is taken proportionally
        from the larger boxes, and the tooltip still reports the true share
        and count. 0 makes the boxes purely proportional. A category with no
        values still draws no box.
    height : str, default: '1em'
        CSS height baked onto the root when *inline* is True, so the strip
        tracks the font size; width follows the aspect.
    inline : bool, default: True
        If True, set ``height``/``width``/``vertical-align`` on the root so
        the strip drops into running text and sits on the baseline.
    hover : bool, default: True
        If True, give each box a ``<title>`` tooltip — its share and count,
        e.g. ``"60% distinct\\n3 of 5 values"``. False turns tooltips off.
    highlight : bool, default: True
        If True, add a scoped ``<style>`` that brightens the box under the
        cursor — a cue that the strip is interactive.
    class_ : str, default: 'pavement-tally'
        CSS class on the root ``<svg>``, a hook for your own styling.
    path : str, optional
        If given, also write the markup here. A ``.html``/``.htm`` path is
        wrapped in a minimal standalone document; any other suffix is
        written as-is. The string is returned either way.

    Returns
    -------
    str
        The ``<svg>...</svg>`` markup.

    Raises
    ------
    ValueError
        If *data* is empty (no values to summarize).

    See Also
    --------
    spark : The distribution sparkline this strip accompanies.
    pavement.core.tally_stats : The backend-agnostic counts it draws.
    """
    counts = tally_stats(data)
    total = counts['total']
    if total == 0:
        raise ValueError("data must be non-empty")

    horizontal = orientation == 'horizontal'
    view_w, view_h = _VIEWBOX[orientation]
    span = view_w if horizontal else view_h  # axis the boxes lay out along

    stroke = ''
    if line_color is not None:
        stroke = (f' stroke="{line_color}" stroke-width="{_num(line_width)}"'
                  f' vector-effect="non-scaling-stroke"')

    segments = [(label, color, count) for label, color, count in (
        ('distinct', distinct_color, counts['distinct']),
        ('repeated', repeated_color, counts['repeated']),
        ('missing', missing_color, counts['missing']),
    ) if count > 0]  # a category with no values draws no box
    lengths = _box_lengths([count for _, _, count in segments], span, min_box)
    noun = 'value' if total == 1 else 'values'

    parts: list[str] = []
    offset = 0.0
    for (label, color, count), length in zip(segments, lengths):
        if horizontal:
            x, y, w, h = offset, 0.0, length, view_h
        else:
            x, y, w, h = 0.0, offset, view_w, length
        title = ''
        if hover:
            text = f"{_pct(count, total)} {label}\n{count:,} of {total:,} {noun}"
            title = f'<title>{escape(text)}</title>'
        parts.append(
            f'<rect class="tvbox" x="{_num(x)}" y="{_num(y)}" '
            f'width="{_num(w)}" height="{_num(h)}" fill="{color}"{stroke} '
            f'pointer-events="all">{title}</rect>')
        offset += length

    # CSS hover feedback (pure, scoped): the box under the cursor brightens,
    # signalling that the strip is interactive. The fills are opaque, so a
    # brightness filter reads more clearly here than an opacity change.
    style = ''
    if highlight:
        selector = '.' + '.'.join(class_.split())
        style = (
            f'<style>'
            f'{selector} .tvbox{{transition:filter .1s ease}}'
            f'{selector} .tvbox:hover{{filter:brightness(1.12)}}'
            f'</style>')

    root_style = 'overflow:visible;'  # let the flush outline show its stroke
    if inline:
        root_style += f'height:{height};width:auto;vertical-align:-0.15em;'
    label = (f"column tally: {counts['distinct']} distinct, "
             f"{counts['repeated']} repeated, {counts['missing']} missing "
             f"of {total} {noun}")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_num(view_w)} {_num(view_h)}" '
        f'preserveAspectRatio="none" class={quoteattr(class_)} '
        f'role="img" aria-label={quoteattr(label)} '
        f'style={quoteattr(root_style)}>'
        f'<desc>{escape(label)}</desc>{style}'
        f'{"".join(parts)}</svg>')

    if path is not None:
        document = svg
        if path.endswith(('.html', '.htm')):
            document = ('<!doctype html><meta charset="utf-8">'
                        f'<body>{svg}</body>')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(document)
    return svg
