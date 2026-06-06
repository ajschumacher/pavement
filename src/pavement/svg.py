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
  target carrying its value range, percentile band, and value share in a
  native ``<title>`` tooltip — the same hover text the Bokeh and Plotly
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

import datetime as _dt
import math
import numbers
import uuid
from collections import Counter
from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Any, Literal
from xml.sax.saxutils import escape, quoteattr

from ._geometry import box_edge_spans, fmt, hover_bins, pct, row_spec, ValueFormat
from .core import _is_missing, pavement_stats, proportion_stats, tally_stats

__all__ = ["spark", "tally", "proportion", "summary", "Summary"]

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

# Default proportion palette: value boxes alternate the tally's dark and
# light blue; the optional catch-all box (the lumped long tail) is a blue
# midway between them, so it reads as "the rest" without stealing attention.
_PROP_COLORS = ("#2166ac", "#92c5de")
_PROP_OTHER = "#5995c5"


def _num(value: float) -> str:
    """Format a coordinate compactly (no trailing zeros)."""
    return f"{value:.2f}".rstrip('0').rstrip('.')


def _plural(noun: str) -> str:
    """English plural of a count noun: a final consonant + ``y`` becomes
    ``ies`` (``entry`` -> ``entries``), otherwise just add ``s`` (``row`` ->
    ``rows``, ``value`` -> ``values``)."""
    if noun.endswith('y') and noun[-2:-1] not in 'aeiou':
        return noun[:-1] + 'ies'
    return noun + 's'


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


def _to_epoch(value: _dt.date) -> float:
    """A ``date`` or ``datetime`` as POSIX seconds — a monotonic float the
    pavement geometry can use and average."""
    if isinstance(value, _dt.datetime):
        return value.timestamp()
    return _dt.datetime(value.year, value.month, value.day).timestamp()


def _project(data: list[Any]) -> tuple[list[Any], ValueFormat | None]:
    """Map an ordered, non-float family onto a numeric axis for the pavement,
    with a default tooltip formatter that renders the values back.

    A pavement is a number line, but the SVG geometry needs plain floats and
    the Type-2 quantile midpoint needs values it can average — neither of which
    a ``datetime`` (you can't add two) or a ``Decimal`` (``Decimal * float``
    raises) supports directly. So:

    - real numbers (``int``/``float``/numpy scalars) pass through untouched;
    - ``Decimal`` becomes ``float``;
    - a ``date``/``datetime`` (including pandas ``Timestamp`` and polars
      temporals) becomes POSIX seconds, paired with a formatter that shows the
      quantile values as dates — or date-times, when any value carries a time
      of day;
    - a ``timedelta`` (including ``pandas.Timedelta`` and polars ``Duration``
      via ``.to_list()``) becomes total seconds, with a formatter showing
      ``"N days"`` for whole-day durations, ``"Nd HH:MM:SS"`` / ``"HH:MM:SS"``
      when any value has a non-zero second component, or ``"Nd HH:MM"`` /
      ``"HH:MM"`` when all values are whole minutes;
    - a numpy ``datetime64`` or ``timedelta64`` is cast to microsecond
      resolution via ``.astype('[us]')`` and then delegated to the
      appropriate branch above.

    Anything else is returned unchanged. *data* is assumed non-empty and of a
    single family (as `summary` guarantees via `_pavement_column`); the first
    element picks the branch. Returns ``(values, value_format_or_None)``.
    """
    sample = data[0]
    # numpy datetime64 / timedelta64: cast to microseconds then delegate.
    # Must come before the numbers.Real check because numpy timedelta64
    # registers as numbers.Real (its MRO includes signedinteger).
    if (hasattr(sample, 'item')
            and type(sample).__name__ in ('datetime64', 'timedelta64')):
        name = type(sample).__name__
        return _project([v.astype(f'{name}[us]').item() for v in data])
    if isinstance(sample, numbers.Real):       # int/float/bool/numpy reals
        return data, None
    if isinstance(sample, Decimal):
        return [float(v) for v in data], None
    if isinstance(sample, _dt.date):           # date or datetime (a subclass)
        seconds = [_to_epoch(v) for v in data]
        with_time = any(
            isinstance(v, _dt.datetime)
            and (v.hour or v.minute or v.second or v.microsecond) for v in data)
        if with_time:
            def show(s: float) -> str:
                return _dt.datetime.fromtimestamp(s).isoformat(
                    sep=' ', timespec='minutes')
        else:
            def show(s: float) -> str:
                return _dt.datetime.fromtimestamp(s).date().isoformat()
        return seconds, show
    if isinstance(sample, _dt.timedelta):      # timedelta, pandas Timedelta, polars Duration
        secs = [v.total_seconds() for v in data]
        whole_days = all(v.seconds == 0 and v.microseconds == 0 for v in data)
        if whole_days:
            def show(s: float) -> str:
                d = round(s / 86400)
                return f"{d} day" if abs(d) == 1 else f"{d} days"
        elif any(v.seconds % 60 != 0 or v.microseconds != 0 for v in data):
            def show(s: float) -> str:
                neg = s < 0
                abs_s = abs(s)
                d, rem = divmod(int(abs_s), 86400)
                h, rem = divmod(rem, 3600)
                m, sec = divmod(rem, 60)
                prefix = "-" if neg else ""
                if d:
                    return f"{prefix}{d}d {h:02d}:{m:02d}:{sec:02d}"
                return f"{prefix}{h:02d}:{m:02d}:{sec:02d}"
        else:
            def show(s: float) -> str:
                neg = s < 0
                abs_s = abs(s)
                d, rem = divmod(int(abs_s), 86400)
                h, rem = divmod(rem, 3600)
                m = rem // 60
                prefix = "-" if neg else ""
                if d:
                    return f"{prefix}{d}d {h:02d}:{m:02d}"
                return f"{prefix}{h:02d}:{m:02d}"
        return secs, show
    return data, None


def spark(
    data: Iterable[float],
    weights: Sequence[float] | None = None,
    bins: int | None = 4,
    domain: tuple[float, float] | None = None,
    orientation: Literal['vertical', 'horizontal'] = 'horizontal',
    width: float = 0.6,
    tassel_extent: float = 0.05,
    show_tassels: bool = False,
    proportional_representation: bool = False,
    min_representation: float = 0.05,
    show_box: bool | None = None,
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
        The values to summarize as a single pavement row. Besides plain
        numbers, an ordered non-float family is accepted and projected onto a
        numeric axis: ``Decimal``; ``date``/``datetime`` (including pandas
        ``Timestamp`` and polars temporals), shown as dates in the tooltips;
        ``timedelta`` (including ``pandas.Timedelta`` and polars ``Duration``),
        shown as durations; and numpy ``datetime64``/``timedelta64`` arrays
        (see *value_format* and `_project`).
    weights : sequence of float, optional
        Positive weights parallel to *data*.
    bins : int or None, default: 4
        Number of equal-mass bins. None shows all the data instead of
        binning it (see `pavement_stats`), turning the spark into a rug.
    domain : (float, float) or None, default: None
        Explicit ``(lo, hi)`` extent for the value axis, in projected
        coordinates (floats, after `_project` has converted dates etc.).
        When given, the ticks are positioned as if this were the full
        value range, so values outside the data's own range leave
        transparent empty space — useful for aligning multiple strips on
        a shared axis. When None the axis spans the data's own range.
    orientation : {'vertical', 'horizontal'}, default: 'horizontal'
        Direction of the value axis. 'horizontal' runs values
        left-to-right, the natural fit for an inline strip.
    width : float, default: 0.6
        Box thickness across the row. As with `pavement.matplotlib.spark`
        only its ratio to *tassel_extent* matters — the geometry is
        stretched to fill the SVG.
    tassel_extent : float, default: 0.05
        How far tassel marks reach beyond the box at repeated values.
    show_tassels : bool, default: False
        Whether to draw tassel marks at repeated quantile values.
    proportional_representation : bool, default: False
        Turn a rug into a *frequency rug*: scale each value line's length to
        how often that value occurs, so the most common value's line spans the
        full box and the rest reach proportionally less (a value seen half as
        often draws a line half as long). The lines sit on a shared baseline —
        the bottom edge for a horizontal rug, the left edge for a vertical one —
        and grow toward the far edge, like little bars. Only meaningful for a
        rug, so it
        requires ``bins=None`` and ``show_tassels=False`` (a tassel's reach
        and a frequency's reach would fight); a ``ValueError`` otherwise.
        Counts are unweighted — weights don't apply to a rug (see
        `pavement_stats`).
    min_representation : float, default: 0.05
        Floor on a value line's length under *proportional_representation*, as
        a fraction of the full box (so ``0.05`` keeps every line at least 5% of
        full length). Keeps a rare value's line from collapsing to an
        invisible point, the way *min_box* protects a tiny tally slice. Ignored
        unless *proportional_representation* is on.
    show_box : bool or None, default: None
        Whether (and how) to draw the long box edges (the borders parallel
        to the value axis). None (the default) draws them for a binned spark
        and omits them for a rug (``bins=None``), so a rug reads like a plain
        rug; when drawn, each bin contributes its pair of edges only where it
        holds one or more data points strictly inside it, so the outline
        closes around bins whose mass is spread out and gaps open where it
        clumps onto the value lines. ``True`` forces the *complete* box — the
        two edges unbroken across the whole value range, rug or binned — for
        when a solid outline is wanted regardless of where the mass falls.
        ``False`` omits the edges entirely.
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
        If True, add native ``<title>`` tooltips (no JavaScript): per bin,
        its value range, percentile band, and the share of values falling
        strictly inside it (``"1 to 2.5\\np0 to p25\\n15% (3 of 20
        values)"``); per tick, its value, percentile, and the share of
        values falling exactly on it (subject to *tick_hover_limit*). Every
        value is counted in exactly one bin or tick. When nothing finer is
        hoverable — a dense rug — a single whole-spark summary is used
        instead, so a spark is read value-by-value or summarised, never
        both. False turns all tooltips off.
    value_format : callable, optional
        Function mapping a value to its tooltip display string, e.g.
        ``lambda v: f"${v:,.2f}"``. Applies to the bin value ranges, the
        per-tick values, and the whole-spark summary; defaults to 3
        significant figures (or, for projected ``date``/``datetime`` data, to
        a date renderer). If given, it overrides that default and receives the
        *projected* numeric value for non-float input (POSIX seconds for
        dates, ``float`` for ``Decimal``).
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
    if proportional_representation and (bins is not None or show_tassels):
        raise ValueError(
            "proportional_representation requires a rug: bins=None and "
            "show_tassels=False")
    # Project an ordered non-float family (Decimal, date/datetime) onto a
    # numeric axis, taking its renderer as the default tooltip format. A
    # caller-supplied value_format still wins (and then receives the projected
    # value); real numbers pass through unchanged.
    data, projected_format = _project(data)
    value_format = value_format or projected_format
    values = pavement_stats(data, bins=bins, weights=weights)
    position = 1.0
    spec = row_spec(values, position, width, orientation,
                    tassel_extent, show_tassels, value_format, data=data)
    fmt_value = value_format or fmt
    reach = max(t.reach for t in spec.ticks)
    half = spec.half

    # A frequency rug scales each value line's *drawn* length to how common
    # that value is — the most common reaches the full box, the rest less, but
    # never below `min_representation` of full so a rare value stays visible.
    # The lines are anchored on a baseline edge below (see the tick loop), and
    # the box thickness `reach` is unchanged (every tick's geometric reach is
    # still `half`), so the viewBox isn't distorted. Without the flag, each line
    # is drawn at its full geometric reach, exactly as before.
    if proportional_representation:
        freq = Counter(data)
        top = max(freq.values())
        mark_reaches = [t.reach * max(freq[t.value] / top, min_representation)
                        for t in spec.ticks]
    else:
        mark_reaches = [t.reach for t in spec.ticks]

    value_low, value_high = spec.value_low, spec.value_high
    if domain is not None:
        value_low, value_high = domain
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

    # Whether each value line is individually hoverable. While the ticks
    # stay few enough to be worth hovering one by one (binned sparks
    # always are; a small rug is, a dense one isn't), each gets a
    # transparent wide hit-area and a value tooltip; a denser rug skips
    # this and leans on the whole-spark summary instead. Counting the
    # ticks (distinct values) rather than the raw data keeps repeats from
    # inflating the total. (Defined here because the rug's gap boxes below
    # appear under the same condition.)
    per_tick_hover = hover and (
        tick_hover_limit is None or len(spec.ticks) <= tick_hover_limit)

    # A rug, read value by value, also gets the boxes between its lines — the
    # gaps between consecutive distinct values — as hover targets, just like a
    # pavement's bins; a dense rug (ticks past the limit) keeps only its
    # whole-spark summary instead, to stay light.
    rug_gap_boxes = bins is None and per_tick_hover

    if bins is not None or rug_gap_boxes:
        # Equal-mass bins — or, for a rug, the boxes spanning the gaps between
        # distinct values: a translucent (or invisible) rect each, spanning the
        # box thickness. Drawn first so they sit behind the lines, and they
        # double as hover targets — the value-range/percentile/count tooltip
        # and the CSS highlight both attach here. A rug's gap boxes carry a
        # zero interior count (nothing falls strictly between two adjacent
        # values), but they make a wide stretch as easy to hover as a value
        # line is hard to hit; `hover_bins` drops the zero-width bins at a
        # rug's repeated values, which coincide with the tick lines.
        for b in hover_bins(spec, bins is None):
            x0, y0 = pt(position - half, b.low)
            x1, y1 = pt(position + half, b.high)
            # value range, then the percentile band, then the count — the
            # shared order; but an empty box (a rug gap, or a bin whose mass
            # sits on its edges) drops the band, which would otherwise read as
            # a misleading "pNN to pNN" over a stretch holding no data. Mirrors
            # the tick label's conditional percentile.
            lines = [b.value_range]
            if b.band and (b.inside or not b.count):
                lines.append(b.band)
            if b.count:
                lines.append(b.count)
            title = (f'<title>{escape(chr(10).join(lines))}</title>'
                     if hover else '')
            parts.append(rect(
                x0, y0, x1, y1, cls=' class="pvbin"',
                extra=f'fill="{fill_paint}" fill-opacity="{_num(rest_opacity)}" '
                      f'pointer-events="all"', child=title))
    elif color is not None:
        # A rug with no gap boxes (dense, or per-tick hover disabled) but a
        # requested color still fills the box as a single background.
        x0, y0 = pt(position - half, value_low)
        x1, y1 = pt(position + half, value_high)
        parts.append(rect(
            x0, y0, x1, y1,
            extra=f'fill="{fill_paint}" fill-opacity="{_num(fill_alpha)}" '
                  f'pointer-events="none"'))

    # All the value strokes share their styling, so it lives once on a
    # parent <g> and each line is just coordinates — keeps a dense rug
    # compact. The long box edges run along the value axis at each side;
    # then one tick per distinct value, reaching past the box as a tassel
    # where the value repeats (and closing the box ends at the extremes).
    # A hoverable tick pairs its visible mark with a transparent hit-area
    # inside a <g class="pvtick">, so CSS can thicken the mark on hover.
    #
    # `box_edge_spans` resolves where the long edges go (shared with every
    # other backend): by default each populated bin closes over itself and
    # gaps open where the mass clumps onto a value line; show_box=True forces
    # one unbroken span; show_box=False (and, by default, a rug) draws none.
    marks: list[str] = []
    for low, high in box_edge_spans(spec, show_box):
        marks += [stroke_line(*pt(side, low), *pt(side, high))
                  for side in (position - half, position + half)]
    # A frequency rug anchors its lines on one box edge (the *baseline*) and
    # grows them inward by their frequency-scaled length, so they read like
    # little bars rising from a shared line rather than floating symmetrically
    # across the value axis (which proved hard to read). The baseline is the
    # bottom edge for a horizontal rug and the left edge for a vertical one, and
    # a line grows the full box thickness (`2 * mark_reach`) toward the far
    # edge. In perpendicular coordinates the bottom is `position + half` (it
    # maps to the largest y) and the left is `position - half` (the smallest x),
    # so the two orientations anchor at opposite perp ends and grow opposite
    # ways. A plain rug or pavement keeps the symmetric, axis-centered marks.
    base_perp = position + half if horizontal else position - half
    grow = -1.0 if horizontal else 1.0
    for t, mark_reach in zip(spec.ticks, mark_reaches):
        # The visible mark uses the (possibly frequency-scaled) reach; the
        # transparent hit-area keeps the full reach so even a short line stays
        # easy to hover. They coincide unless proportional_representation is on.
        if proportional_representation:
            a = pt(base_perp, t.value)
            b = pt(base_perp + grow * 2 * mark_reach, t.value)
        else:
            a = pt(position - mark_reach, t.value)
            b = pt(position + mark_reach, t.value)
        if per_tick_hover:
            ha = pt(position - t.reach, t.value)
            hb = pt(position + t.reach, t.value)
            # value first, then the percentile cut point (absent for a
            # single-value spark), then the count/share — the shared order.
            label = t.value_str
            if t.quantile:
                label += chr(10) + t.quantile
            label += chr(10) + t.count
            marks.append(
                '<g class="pvtick">'
                + stroke_line(*a, *b, attrs=' class="pvmark"')
                + stroke_line(*ha, *hb, attrs=' class="pvhit" '
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


def _proportion_cutoff(counts: list[int], total: int, span: float,
                       min_box: float, max_boxes: int,
                       tolerance: float) -> int:
    """How many of the top values to show individually before a catch-all.

    *counts* is descending. Returns ``m``: the leading values get their own
    box and the rest (if any) are lumped into a single catch-all on the
    right. ``m`` is capped at *max_boxes*, but cut shorter as soon as the
    minimum-width inflation of the small boxes would distort the catch-all's
    width — versus its true proportion — by *tolerance* or more. That stops
    a long tail of tiny boxes from squeezing the catch-all into a misleading
    sliver; the remaining values go straight into the catch-all instead.
    """
    k = len(counts)
    if k <= max_boxes:
        return k  # every value fits; no catch-all needed
    chosen = 1
    for m in range(1, max_boxes + 1):
        remaining = total - sum(counts[:m])
        widths = _box_lengths(counts[:m] + [remaining], span, min_box)
        true_catch = span * remaining / total
        if true_catch > 0 and abs(widths[-1] - true_catch) / true_catch >= tolerance:
            break
        chosen = m
    return chosen


def proportion(
    data: Iterable[object],
    orientation: Literal['vertical', 'horizontal'] = 'horizontal',
    colors: Sequence[str] = _PROP_COLORS,
    other_color: str = _PROP_OTHER,
    max_boxes: int = 12,
    min_box: float = 3.0,
    catchall_tolerance: float = 0.1,
    value_crop: int | None = 128,
    line_color: str | None = None,
    line_width: float = 1.0,
    height: str = '1em',
    inline: bool = True,
    hover: bool = True,
    highlight: bool = True,
    class_: str = 'pavement-proportion',
    path: str | None = None,
) -> str:
    """
    Render a column's value counts as a self-contained inline SVG strip.

    A companion to `tally` in the same borderless form factor, visualizing a
    column's value distribution the way pandas ``value_counts()`` reports it.
    One box per value, left to right in descending frequency, each sized in
    proportion to how often that value occurs. It fills the gap a pavement
    spark leaves for categorical columns, which have no numeric distribution
    to draw. Missing values are dropped (see `proportion_stats`).

    High-cardinality columns are kept legible: at most *max_boxes* values get
    their own box, and the rest are lumped into a single catch-all box on the
    right. The cutoff comes sooner than *max_boxes* if a long tail of tiny
    boxes would otherwise squeeze the catch-all into a misleading width (see
    *catchall_tolerance*). Boxes never fall below *min_box*, so even a rare
    value stays visible and hoverable.

    Parameters
    ----------
    data : iterable
        The column's values, of any type (see `proportion_stats`).
    orientation : {'vertical', 'horizontal'}, default: 'horizontal'
        Box layout. 'horizontal' runs the boxes left-to-right (most common
        first); 'vertical' stacks them top-to-bottom in the same order.
    colors : sequence of str, default: a dark/light blue pair
        CSS colors cycled across the value boxes (so adjacent boxes differ).
    other_color : str
        CSS color of the catch-all box, when present.
    max_boxes : int, default: 12
        Most values to draw individually before lumping the rest into the
        catch-all.
    min_box : float, default: 3.0
        Smallest on-screen length of any box, in viewBox units (the strip is
        140 long). Keeps a rare value visible and hoverable; the shortfall is
        taken proportionally from the larger boxes (see `tally`).
    catchall_tolerance : float, default: 0.1
        How far the catch-all's drawn width may stray from its true
        proportion, as a fraction, before the individual-box cutoff is moved
        earlier (lumping more into the catch-all). Smaller is stricter.
    value_crop : int or None, default: 128
        Cap on a value's length in its tooltip; longer values are truncated
        with an ellipsis. None disables cropping.
    line_color : str or None, default: None
        Optional hairline outlining each box; None (the default) leaves the
        boxes borderless, separated by their fills, like `tally`.
    line_width : float, default: 1.0
        Outline stroke width in pixels (only when *line_color* is given).
    height : str, default: '1em'
        CSS height baked onto the root when *inline* is True.
    inline : bool, default: True
        If True, size the root so the strip drops into running text.
    hover : bool, default: True
        If True, give each box a ``<title>`` tooltip — its value, then its
        share and count, e.g. ``'dog\\n10% (10 of 100 values)'``. The
        catch-all reports the lumped share and how many distinct values it
        covers. False turns
        tooltips off.
    highlight : bool, default: True
        If True, add a scoped ``<style>`` that brightens the box under the
        cursor.
    class_ : str, default: 'pavement-proportion'
        CSS class on the root ``<svg>``.
    path : str, optional
        If given, also write the markup here (``.html``/``.htm`` wrapped in a
        minimal document; any other suffix as-is). The string is returned
        either way.

    Returns
    -------
    str
        The ``<svg>...</svg>`` markup.

    Raises
    ------
    ValueError
        If *data* has no non-missing values to summarize.

    See Also
    --------
    tally : The distinct/duplicate/missing companion strip.
    pavement.core.proportion_stats : The value counts it draws.
    """
    stats = proportion_stats(data)
    items = stats['counts']
    total = stats['total']
    if total == 0:
        raise ValueError("data has no non-missing values to summarize")

    horizontal = orientation == 'horizontal'
    view_w, view_h = _VIEWBOX[orientation]
    span = view_w if horizontal else view_h

    counts_only = [count for _, count in items]
    k = len(items)
    shown = _proportion_cutoff(counts_only, total, span, min_box,
                               max_boxes, catchall_tolerance)
    catch_count = total - sum(counts_only[:shown])  # 0 when all shown
    box_counts = counts_only[:shown] + ([catch_count] if catch_count else [])
    lengths = _box_lengths(box_counts, span, min_box)

    stroke = ''
    if line_color is not None:
        stroke = (f' stroke="{line_color}" stroke-width="{_num(line_width)}"'
                  f' vector-effect="non-scaling-stroke"')
    palette = list(colors) or list(_PROP_COLORS)
    noun = 'value' if total == 1 else 'values'

    parts: list[str] = []
    offset = 0.0
    for index, (count, length) in enumerate(zip(box_counts, lengths)):
        is_catch = bool(catch_count) and index == len(box_counts) - 1
        color = other_color if is_catch else palette[index % len(palette)]
        if horizontal:
            x, y, w, h = offset, 0.0, length, view_h
        else:
            x, y, w, h = 0.0, offset, view_w, length
        title = ''
        if hover:
            if is_catch:
                lumped = k - shown
                text = (f"other\n"
                        f"{pct(count, total)} ({count:,} of {total:,} {noun})\n"
                        f"(across {lumped:,} distinct values)")
            else:
                value = str(items[index][0])
                if value_crop is not None and len(value) > value_crop:
                    value = value[:value_crop] + "…"
                text = (f"{value}\n"
                        f"{pct(count, total)} ({count:,} of {total:,} {noun})")
            title = f'<title>{escape(text)}</title>'
        parts.append(
            f'<rect class="tvbox" x="{_num(x)}" y="{_num(y)}" '
            f'width="{_num(w)}" height="{_num(h)}" fill="{color}"{stroke} '
            f'pointer-events="all">{title}</rect>')
        offset += length

    style = ''
    if highlight:
        selector = '.' + '.'.join(class_.split())
        style = (
            f'<style>'
            f'{selector} .tvbox{{transition:filter .1s ease}}'
            f'{selector} .tvbox:hover{{filter:brightness(1.12)}}'
            f'</style>')

    root_style = 'overflow:visible;'
    if inline:
        root_style += f'height:{height};width:auto;vertical-align:-0.15em;'
    label = (f"value proportions of {total} {noun} across {k} distinct "
             f"value{'' if k == 1 else 's'}"
             + (f", top {shown} shown" if catch_count else ""))
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


def tally(
    data: Iterable[object],
    orientation: Literal['vertical', 'horizontal'] = 'horizontal',
    distinct_color: str = _TALLY_DISTINCT,
    repeated_color: str = _TALLY_REPEATED,
    missing_color: str = _TALLY_MISSING,
    line_color: str | None = None,
    line_width: float = 1.0,
    min_box: float = 3.0,
    fill_ratio: float = 1.0,
    height: str = '1em',
    inline: bool = True,
    hover: bool = True,
    highlight: bool = True,
    noun: str = 'entry',
    class_: str = 'pavement-tally',
    path: str | None = None,
) -> str:
    """
    Render a column's make-up as a self-contained inline SVG strip.

    A companion to `spark` with the same form factor and footprint, but a
    different question. Where a spark summarizes the *distribution* of a
    numeric column, a tally summarizes the *column itself*: three boxes,
    sized in proportion to how many of the column's values are distinct
    (leftmost), how many duplicate a value already seen (middle), and
    how many are missing (rightmost). It works on a column of any type, and
    surfaces exactly what a pavement plot can't — missing values and
    distinctness.

    By default the three boxes fill the strip edge to edge, since the counts
    sum to the total (see `pavement.core.tally_stats`); a category with no
    values draws no box. Each box carries a native ``<title>`` tooltip with
    its share and count — the lines between boxes do not. Returns an
    ``<svg>...</svg>`` string with no external dependencies; paste it into
    any HTML and it renders, scaling to the surrounding text.

    Parameters
    ----------
    data : iterable
        The column's values, of any type (see `tally_stats`).
    orientation : {'vertical', 'horizontal'}, default: 'horizontal'
        Box layout. 'horizontal' lays the boxes left-to-right
        (distinct, duplicate, missing); 'vertical' stacks them top-to-bottom
        in the same order.
    distinct_color, repeated_color, missing_color : str
        Any CSS color for each box (``repeated_color`` tints the
        ``duplicate`` box). Default to a dark blue, a light blue, and a
        muted dark red.
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
    fill_ratio : float, default: 1.0
        Fraction of the strip's span that the boxes occupy, in [0, 1]. At
        1.0 (default) the boxes fill edge to edge. Values below 1.0 leave
        the right (or bottom, when vertical) portion of the strip empty —
        transparent, with no box drawn. Used by `summary` to make each
        group's tally proportional to its row count relative to the largest
        group, so a smaller group appears visually narrower. Clamped to
        [0, 1]; the tooltips always report the true counts.
    height : str, default: '1em'
        CSS height baked onto the root when *inline* is True, so the strip
        tracks the font size; width follows the aspect.
    inline : bool, default: True
        If True, set ``height``/``width``/``vertical-align`` on the root so
        the strip drops into running text and sits on the baseline.
    hover : bool, default: True
        If True, give each box a ``<title>`` tooltip — its label, then its
        share and count, e.g. ``"distinct\\n60% (3 of 5 entries)"``. The
        distinct box adds a line for how many of those entries appear
        exactly once, e.g. ``"(2 appearing once)"``. False turns tooltips
        off.
    highlight : bool, default: True
        If True, add a scoped ``<style>`` that brightens the box under the
        cursor — a cue that the strip is interactive.
    noun : str, default: 'entry'
        Singular noun for what each entry is, used in the tooltips and the
        ``aria-label`` (e.g. ``"3 of 5 entries"``); pluralized for display
        (``entry`` -> ``entries``). The default is ``'entry'`` rather than
        ``'value'`` because the count includes missing entries, which aren't
        values. `summary` passes ``'row'`` for the whole-frame tally (entries
        are rows).
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
        ('duplicate', repeated_color, counts['repeated']),
        ('missing', missing_color, counts['missing']),
    ) if count > 0]  # a category with no values draws no box
    effective_span = span * max(0.0, min(1.0, fill_ratio))
    lengths = _box_lengths([count for _, _, count in segments], effective_span, min_box)
    word = noun if total == 1 else _plural(noun)

    parts: list[str] = []
    offset = 0.0
    for (label, color, count), length in zip(segments, lengths):
        if horizontal:
            x, y, w, h = offset, 0.0, length, view_h
        else:
            x, y, w, h = 0.0, offset, view_w, length
        title = ''
        if hover:
            text = f"{label}\n{pct(count, total)} ({count:,} of {total:,} {word})"
            if label == 'distinct':  # how many of the distinct values are singletons
                text += f"\n({counts['once']:,} appearing once)"
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
             f"{counts['repeated']} duplicate, {counts['missing']} missing "
             f"of {total} {word}")
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


# ---------------------------------------------------------------------------
# Dataframe / series summary
#
# One inline HTML table that puts the three strips above to work together: a
# row per column showing its `tally` (make-up) beside its distribution — a
# pavement `spark` for a numeric column, a `proportion` strip for a
# categorical one — topped, for a whole dataframe, by a row summarizing the
# frame itself. It is the natural thing to glance at when a dataframe first
# lands, and it renders inline in Jupyter through `Summary._repr_html_`.
# ---------------------------------------------------------------------------

# Choosing a numeric column's pavement resolution from its values. A rug shows
# every value individually (drawn as a frequency rug in the summary, so the
# line lengths carry the value counts); a binned pavement smears them into
# equal-mass bins. We rug when either:
#   - the column is small enough to read one value at a time (at most
#     ``_RUG_LIMIT`` values total — the limit matches `spark`'s
#     tick_hover_limit, so every tick stays individually hoverable), or
#   - it has few enough *distinct* values (at most ``_DISTINCT_RUG_LIMIT``) that
#     a frequency rug reads the distribution better than binning would — a
#     discrete rating, say, that is many values but only a handful of levels.
# Otherwise an equal-mass binned pavement, doubling the bin count each time the
# total roughly quadruples, capped at 16 (finer bins don't read at a
# sparkline's size).
_RUG_LIMIT = 24
_DISTINCT_RUG_LIMIT = 16  # a column with at most this many distinct values rugs
_BIN_THRESHOLDS = ((97, 4), (257, 8))  # n < cut -> that many bins
_MAX_BINS = 16


def _choose_bins(present: Sequence[Any]) -> int | None:
    """Bins for a numeric column's spark, from its *present* values.

    None (a rug) when the column has at most ``_RUG_LIMIT`` values *or* at most
    ``_DISTINCT_RUG_LIMIT`` distinct values; otherwise 4, 8, and a 16-bin cap —
    see the reasoning on the module constants above.
    """
    n = len(present)
    if n <= _RUG_LIMIT or len(set(present)) <= _DISTINCT_RUG_LIMIT:
        return None
    for cut, bins in _BIN_THRESHOLDS:
        if n < cut:
            return bins
    return _MAX_BINS


def _is_numeric(value: Any) -> bool:
    """Whether one value is numeric enough for a pavement plot.

    Real numbers only — ints, floats, ``Fraction``, and numpy's int/float
    scalars (which register as ``numbers.Real``) — and explicitly *not*
    booleans, which are technically ints but read as a two-level category,
    better shown as a proportion. Strings, complex numbers, datetimes, and the
    like are not numeric here and fall to a proportion plot.
    """
    return not isinstance(value, bool) and isinstance(value, numbers.Real)


def _pavement_column(present: list[Any]) -> bool:
    """Whether a column's *present* (non-missing) values are a single ordered
    family a pavement can draw — all real numbers, all ``Decimal``, all
    ``date``/``datetime``, all ``timedelta`` (durations), or all numpy
    ``datetime64``/``timedelta64`` — so it gets a `spark` (which projects the
    non-float families onto a number line, see `_project`) rather than a
    `proportion`.

    Requiring one family keeps the projection well-defined and sends mixed or
    un-orderable columns (and booleans, which read as a two-level category) to
    a proportion instead.
    """
    if not present:
        return False
    sample = present[0]
    return (all(_is_numeric(v) for v in present)
            or all(isinstance(v, Decimal) for v in present)
            or all(isinstance(v, _dt.date) for v in present)
            or all(isinstance(v, _dt.timedelta) for v in present)
            or (hasattr(sample, 'item')
                and type(sample).__name__ in ('datetime64', 'timedelta64')
                and all(type(v).__name__ == type(sample).__name__
                        for v in present)))


# A single canonical marker for a missing cell, so that two rows missing the
# *same* cells still compare equal (raw ``NaN`` never does), letting the
# whole-row tally count them as repeats. Identity-based equality/hashing makes
# it behave inside a row tuple.
_ROW_MISSING = object()


def _row_key(row: Iterable[Any]) -> Any:
    """A hashable key for one dataframe row, for the whole-row tally.

    Each missing cell collapses to one canonical marker, so two rows that
    match — including in *where* they are missing — count as repeats rather
    than distinct. A row whose cells are all missing returns ``None``, which
    the tally counts as a missing entity (an all-blank row).
    """
    cells = [_ROW_MISSING if _is_missing(v) else v for v in row]
    if all(c is _ROW_MISSING for c in cells):
        return None
    return tuple(cells)


def _as_columns(data: Any) -> tuple[list[Any], list[list[Any]]] | None:
    """Pull ``(names, columns)`` out of a dataframe-like input, else ``None``.

    Handles a plain ``dict`` of column name -> values, a pandas-style DataFrame
    (anything exposing both ``.columns`` and an ``.items()`` yielding
    name/column pairs), and a polars DataFrame (``.columns`` plus
    ``.get_columns()``). Returns ``None`` for everything else — a Series, list,
    array, or other 1D sequence — which `summary` treats as a single column.
    Each column is materialized as a list of its values.
    """
    if isinstance(data, dict):
        return list(data.keys()), [list(values) for values in data.values()]
    if hasattr(data, 'columns') and hasattr(data, 'items'):  # pandas DataFrame
        names: list[Any] = []
        columns: list[list[Any]] = []
        for name, column in data.items():
            names.append(name)
            columns.append(list(column))
        return names, columns
    if hasattr(data, 'columns') and hasattr(data, 'get_columns'):  # polars
        # get_columns() returns Series; to_list() maps nulls to None and a
        # float NaN to nan, both of which `_is_missing` already handles.
        return list(data.columns), [s.to_list() for s in data.get_columns()]
    return None


def _format_group_key(key: Any) -> str:
    """String label for a groupby key: join tuple keys with `` / ``."""
    if isinstance(key, tuple):
        return ' / '.join(str(k) for k in key)
    return str(key)


_GROUPBY_SERIES = 'series'
_GROUPBY_FRAME = 'frame'


def _detect_groupby(
        data: Any,
) -> tuple[str, Any, list[str], list[Any]] | None:
    """Classify *data* as a GroupBy if it iterates as ``(key, group)`` pairs.

    Handles both pandas GroupBy (detected via ``ngroups``) and polars
    ``GroupBy`` (detected via ``by`` + ``df``).

    Returns ``(kind, extra, keys, groups)`` or ``None``:

    - *kind* is ``'series'`` (SeriesGroupBy) or ``'frame'`` (DataFrameGroupBy).
    - *extra* is the Series name for ``'series'`` (may be ``None``), or the
      column count for ``'frame'``.
    - *keys* is the list of formatted group-key strings.
    - *groups* is the list of group objects (one per key).

    Detection is based on the groups themselves — a DataFrame group means a
    DataFrameGroupBy; anything else is treated as a SeriesGroupBy — so it
    is robust across different pandas versions and access patterns.

    The ``ngroups`` attribute gates the check: plain sequences, dicts, and
    DataFrames don't have it, so they fall through to other paths.
    """
    # pandas GroupBy has ``ngroups``; polars GroupBy has ``by`` and ``df``.
    if not (hasattr(data, 'ngroups')
            or (hasattr(data, 'by') and hasattr(data, 'df'))):
        return None
    keys: list[str] = []
    groups: list[Any] = []
    for key, group in data:
        keys.append(_format_group_key(key))
        groups.append(group)
    if not groups:
        # Empty GroupBy: fall back to the underlying object to determine kind.
        # pandas stores it as .obj; polars stores it as .df.
        obj = getattr(data, 'obj', None) or getattr(data, 'df', None)
        if obj is not None and hasattr(obj, 'columns'):
            n_cols = len(list(obj.columns))
            return _GROUPBY_FRAME, n_cols, [], []
        name = getattr(getattr(data, 'obj', None), 'name', None)
        return _GROUPBY_SERIES, name, [], []
    if hasattr(groups[0], 'columns'):
        n_cols = len(list(groups[0].columns))
        return _GROUPBY_FRAME, n_cols, keys, groups
    name = getattr(groups[0], 'name', None)
    return _GROUPBY_SERIES, name, keys, groups


# Inline styles, so the table is self-contained: it leans on none of the host
# page's CSS and — unlike a <style> block — injects nothing global, which
# matters for a fragment dropped into a notebook cell (and rendered again and
# again). Each strip still carries its own scoped hover style inside its
# <svg>. The grays are mid-tone, legible on light and dark themes alike.
_TD = ('border:none;padding:.18em 0;text-align:left;'
       'vertical-align:middle;white-space:nowrap;')
_TD_TOTAL = _TD + 'box-shadow:0 1px 0 0 rgba(128,128,128,.35);'
# Distribution column: no side padding — the extent cells handle the gaps.
_TD_DIST = 'border:none;padding:.18em 0 .18em 0;vertical-align:middle;white-space:nowrap;'
_TD_DIST_TOTAL = _TD_DIST + 'box-shadow:0 1px 0 0 rgba(128,128,128,.35);'
# Min (left extent, right-aligned) and max (right extent, left-aligned) cells.
_TD_EXTL = ('border:none;padding:.18em .4em .18em .4em;text-align:right;'
            'vertical-align:middle;white-space:nowrap;')
_TD_EXTL_TOTAL = _TD_EXTL + 'box-shadow:0 1px 0 0 rgba(128,128,128,.35);'
_TD_EXTR = ('border:none;padding:.18em .4em .18em .4em;text-align:left;'
            'vertical-align:middle;white-space:nowrap;')
_TD_EXTR_TOTAL = _TD_EXTR + 'box-shadow:0 1px 0 0 rgba(128,128,128,.35);'
_COUNT_STYLE = 'color:#888;'  # muted, for a "1,234 rows" / "1,234 values" cell
_NAME_STYLE = ('font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'
               'monospace;font-size:.92em;')
# Separate style for the name cell so it gets symmetric padding (0.4em each
# side), matching the extent cells.  _TD (used for the tally cell) keeps its
# original 0/0.8em padding so the tally SVG stays flush-left as before.
_TD_NAME = ('border:none;padding:.18em .4em .18em .4em;text-align:left;'
            'vertical-align:middle;white-space:nowrap;')
_TD_NAME_TOTAL = _TD_NAME + 'box-shadow:0 1px 0 0 rgba(128,128,128,.35);'
_EXTENT_STYLE = ('color:#888;font-family:ui-monospace,SFMono-Regular,Menlo,'
                 'Consolas,monospace;font-size:.85em;')

# Responsive layout constants for the summary wrapper and column widths.
# The wrapper caps the table at a comfortable "page of text" width and lets
# the text columns (name, extents) contract gracefully on smaller screens via
# clamp(), while always providing a horizontal-scroll fallback.
_SVG_ASPECT = 140.0 / 30.0   # horizontal strip viewBox width:height ratio
_TALLY_WIDTH_SCALE = 0.75    # tally strips: 75% of natural width (narrower)
_DIST_WIDTH_SCALE = 1.30     # distribution strips: 130% of natural width (wider)
_SUMMARY_MAX_WIDTH = 'min(100%, 54em)'
# Responsive width for all three text columns.  Using the same clamp() value
# for name, ext-left, and ext-right guarantees they are always exactly equal
# at any viewport width.  table-layout:fixed + calc() table width enforces this.
_TEXT_COL_CLAMP = 'clamp(5em, 20vw, 12em)'
# Scrollable wrapper inside each text cell. Width comes from the <col> element
# (via table-layout:fixed), so no explicit width is needed on the div itself.
_TEXT_WRAP = 'display:block;overflow-x:auto;white-space:nowrap;scrollbar-width:thin;'
# The drag handle for a draggable=True summary's column rows: a muted 6-dot
# grip pinned at the left of the name.  It is the *only* draggable element (so
# the rest of the row keeps its normal cursor and stays text-selectable), and
# starts hidden — `_drag_script` reveals it on load, so it appears only where
# the script actually runs (a browser) and not where it is stripped (notebooks,
# static renders), where dragging would not work anyway.
_HANDLE_STYLE = ('display:none;flex:none;cursor:grab;color:#bbb;font-size:1em;'
                 'line-height:1;user-select:none;-webkit-user-select:none;')


def _count_label(n: int, noun: str) -> str:
    """A muted ``"1,234 rows"`` style count for a summary's label cell."""
    return f'<span style="{_COUNT_STYLE}">{n:,} {noun if n == 1 else _plural(noun)}</span>'


def _summary_row(label: str, tally_html: str, lo: str, dist_html: str, hi: str,
                 *, total: bool = False, draggable: bool = False) -> str:
    """One table row: label, tally, min-extent, distribution, max-extent cells.

    With *draggable*, a (non-total) row carries a ``data-pave-row`` marker and a
    `_HANDLE_STYLE` grip (``.pavement-handle``) at the left of its name — the
    only draggable element, the hook the summary's reorder script
    (`_drag_script`) keys on. The total/header row gets neither, so it stays
    pinned at the top, and every row keeps its normal cursor and selectable text.
    """
    td_name = _TD_NAME_TOTAL if total else _TD_NAME
    td_tally = _TD_TOTAL if total else _TD
    td_dist = _TD_DIST_TOTAL if total else _TD_DIST
    td_extl = _TD_EXTL_TOTAL if total else _TD_EXTL
    td_extr = _TD_EXTR_TOTAL if total else _TD_EXTR
    lo_inner = f'<span style="{_EXTENT_STYLE}">{escape(lo)}</span>' if lo else ''
    hi_inner = f'<span style="{_EXTENT_STYLE}">{escape(hi)}</span>' if hi else ''
    lo_html = f'<div style="{_TEXT_WRAP}">{lo_inner}</div>' if lo else ''
    hi_html = f'<div style="{_TEXT_WRAP}">{hi_inner}</div>' if hi else ''
    if draggable and not total:
        tr = '<tr data-pave-row="">'
        handle = (f'<span class="pavement-handle" draggable="true" '
                  f'title="Drag to reorder" style="{_HANDLE_STYLE}">⠿</span>')
        name_cell = (f'<div style="display:flex;align-items:center;gap:.3em;">'
                     f'{handle}<div style="{_TEXT_WRAP}min-width:0;">{label}</div>'
                     f'</div>')
    else:
        tr = '<tr>'
        name_cell = f'<div style="{_TEXT_WRAP}">{label}</div>'
    return (f'{tr}<td style="{td_name}">{name_cell}</td>'
            f'<td style="{td_tally}">{tally_html}</td>'
            f'<td style="{td_extl}">{lo_html}</td>'
            f'<td style="{td_dist}">{dist_html}</td>'
            f'<td style="{td_extr}">{hi_html}</td></tr>')


def _drag_script(table_id: str) -> str:
    """A scoped, dependency-free reorder for the summary's column rows.

    Native HTML5 drag-and-drop, no library: grab a row's left-edge handle and
    the others slide to make room, so columns can be rearranged side by side.
    An IIFE keyed to the table's id (added nowhere else). On load it reveals the
    handles (hidden in the markup), so they appear only here, where dragging
    works — notebooks strip the ``<script>`` and just show the static table.
    Dragging starts only from a ``.pavement-handle``; rows are matched and moved
    by their ``data-pave-row`` marker, so the unmarked total row stays pinned.
    """
    return (
        # The body is wrapped in a CDATA section so the fragment stays
        # well-formed XML (the JS contains a bare "<"); the // guards make the
        # CDATA delimiters line comments to a browser's JS parser, so it runs
        # fine as HTML too — the classic XHTML-safe inline-script idiom.
        '<script>//<![CDATA[\n(function(){'
        f'var t=document.getElementById("{table_id}");if(!t)return;'
        # Reveal the handles: they ship hidden, so a stripped script leaves no
        # dangling grip on a table that cannot actually be dragged.
        'var hs=t.querySelectorAll(".pavement-handle"),i;'
        'for(i=0;i<hs.length;i++)hs[i].style.display="inline-block";'
        'var d=null;'
        't.addEventListener("dragstart",function(e){'
        'var h=e.target.closest(".pavement-handle");if(!h)return;'
        'd=h.closest("[data-pave-row]");if(!d)return;'
        'e.dataTransfer.effectAllowed="move";'
        # Drag the *whole row*, not just the grip: use the row as the drag
        # image, offset so the cursor holds it where the handle was grabbed.
        # Fade the original to a placeholder only after the image is captured
        # (a deferred tick), so the floating ghost stays solid; the guard skips
        # it if the drag was already cancelled.
        'var b=d.getBoundingClientRect();'
        'e.dataTransfer.setDragImage(d,e.clientX-b.left,e.clientY-b.top);'
        'setTimeout(function(){if(d)d.style.opacity="0.4";},0);});'
        't.addEventListener("dragend",function(){if(d)d.style.opacity="";d=null;});'
        # preventDefault on *every* dragover over the table keeps the drop
        # allowed — including when the cursor is over the dragged row itself
        # (where you usually release, since the row tracks under it). Without
        # that, the release lands on a "drop not allowed" spot and the browser
        # plays its snap-back animation of the drag image. Only the row-move is
        # conditional; the drop-accept is not.
        't.addEventListener("dragover",function(e){'
        'if(!d)return;e.preventDefault();e.dataTransfer.dropEffect="move";'
        'var r=e.target.closest("[data-pave-row]");if(!r||r===d)return;'
        'var b=r.getBoundingClientRect();'
        'd.parentNode.insertBefore(d,e.clientY-b.top<b.height/2?r:r.nextSibling);});'
        't.addEventListener("drop",function(e){e.preventDefault();});'
        '}());\n//]]></script>'
    )


def _set_strip_width(svg: str, width: str) -> str:
    """Patch an inline SVG strip's width from ``width:auto`` to *width*.

    All summary strips are rendered with ``width:auto`` (so they size
    naturally to their height × aspect ratio when used standalone). Inside
    the summary table we override this to an explicit em value so the tally
    and distribution columns can have different widths while keeping the same
    height.
    """
    return svg.replace('width:auto;', f'width:{width};', 1)


def _tally_strip(values: list[Any], noun: str, opts: dict[str, Any],
                 *, strip_width: str | None = None, fill_ratio: float = 1.0) -> str:
    """A column's (or the whole frame's) tally strip — empty if there is
    nothing to count (a zero-length column)."""
    if not values:
        return ''
    svg = tally(values, noun=noun, fill_ratio=fill_ratio, **opts)
    return _set_strip_width(svg, strip_width) if strip_width else svg


def _distribution_strip(values: list[Any], present: list[Any],
                        color: str, opts: dict[str, Any],
                        *, strip_width: str | None = None,
                        domain: tuple[float, float] | None = None) -> str:
    """A column's distribution strip: a pavement spark when its present values
    are an ordered family a pavement can draw (numbers, ``Decimal``, or
    ``date``/``datetime``), otherwise a proportion strip. Empty when the column
    has no present values — the tally already shows it is all missing (or
    empty), and there is no distribution to draw.
    """
    if not present:
        return ''
    if _pavement_column(present):
        bins = _choose_bins(present)
        # A summary rug is drawn as a frequency rug: the value lines carry the
        # value counts in their lengths, which is the whole point of rugging a
        # discrete column rather than binning it.
        svg = spark(present, bins=bins, color=color,
                    proportional_representation=bins is None,
                    domain=domain, **opts)
    else:
        svg = proportion(values, **opts)
    return _set_strip_width(svg, strip_width) if strip_width else svg


def _fmt_extent(value: float) -> str:
    """Format a number for an extent label: favour compact comma notation.

    Unlike the default `fmt` (which caps at 3 significant figures), this
    tries to show the value in a human-readable form within 16 characters:

    1. **Comma notation** — ``"100,000"`` for whole numbers, ``"1,234.5"``
       for fractional ones — when the result fits in 16 characters.
    2. **Scientific notation** with as many significant figures as fit in
       16 characters when comma notation is too long (e.g. ``"1.23456789e+20"``).

    Non-finite values (``inf``, ``nan``) fall back to `fmt`.
    """
    v = float(value)
    if not math.isfinite(v):
        return fmt(v)
    candidate = f"{int(v):,}" if v == int(v) else f"{v:,}"
    if len(candidate) <= 16:
        return candidate
    for sig in range(15, 0, -1):
        s = f"{v:.{sig}g}"
        if len(s) <= 16:
            return s
    return fmt(v)


_EXTENT_CROP = 128  # max display length for a categorical extent label (cell scrolls)


def _crop_value(v: Any) -> str:
    """Render *v* as a string for an extent label cell.

    Long values are truncated to ``_EXTENT_CROP`` characters (15 chars + ``…``).
    Values that would appear blank — empty strings, or whose stripped form is
    empty or non-printable (e.g. whitespace-only, control characters) — are
    wrapped in straight quotation marks (``”…”``) so the cell visibly
    conveys that a value is present.
    """
    s = str(v)
    cropped = s[:_EXTENT_CROP - 1] + '…' if len(s) > _EXTENT_CROP else s
    stripped = s.strip()
    if not stripped or not stripped.isprintable():
        return '"' + cropped + '"'
    return cropped


def _column_extent(values: list[Any], present: list[Any]) -> tuple[str, str]:
    """Axis-label strings for the extent cells flanking a distribution strip.

    - **Pavement columns**: formatted min and max, using the same projection
      and formatter as `spark` so the values match the hover tooltips.
    - **Proportion columns**: most common value on the left, least common on
      the right, each cropped to ``_EXTENT_CROP`` characters.

    Returns ``('', '')`` when *present* is empty.
    """
    if not present:
        return '', ''
    if _pavement_column(present):
        projected, vfmt = _project(list(present))
        fmt_v = vfmt or _fmt_extent
        return fmt_v(min(projected)), fmt_v(max(projected))
    # Categorical: most common first, least common last in proportion_stats.
    items = proportion_stats(values)['counts']
    if not items:
        return '', ''
    return _crop_value(items[0][0]), _crop_value(items[-1][0])


class Summary:
    """The result of `summary`: an HTML table that renders inline in Jupyter.

    Showing it in a notebook — or any tool honoring ``_repr_html_`` — displays
    the table; ``str()`` returns the same HTML fragment, for embedding
    elsewhere. (`summary`'s ``path=`` writes a standalone document to disk.)
    """

    def __init__(self, html: str) -> None:
        self.html = html

    def _repr_html_(self) -> str:
        return self.html

    def __str__(self) -> str:
        return self.html

    __repr__ = __str__


def summary(
    data: Any,
    color: str = _TALLY_DISTINCT,
    height: str = '1.6em',
    hover: bool = True,
    highlight: bool = True,
    draggable: bool = True,
    min_fill: float = 0.1,
    shared_bounds: bool | None = None,
    labels: Sequence[Any] | None = None,
    class_: str = 'pavement-summary',
    path: str | None = None,
) -> Summary:
    """
    Summarize a dataframe, Series, or sequence as one inline HTML table.

    The compact, at-a-glance view to reach for when data first lands. It pairs
    the column-summary strips of this module into a borderless, headerless
    table — one row per column, each showing its `tally` (how much of it is
    distinct, duplicate, or missing) beside its distribution. The distribution
    is a pavement `spark` for an ordered column — numbers, ``Decimal``, or
    ``date``/``datetime`` (a temporal column is projected onto a time axis, see
    `_project`) — and a `proportion` strip for a categorical one, so every
    column gets a distribution view where a pavement alone would leave the
    categorical ones blank. Every box is hoverable for its exact share, value,
    and count.

    The return value renders itself in Jupyter (via ``_repr_html_``), so
    ``pavement.summary(df)`` as the last line of a cell shows the table inline.

    What *data* may be:

    - **A dataframe** — a pandas or polars ``DataFrame``, or a plain ``dict``
      mapping column name to a sequence of values (handy with neither
      installed). Renders one row per column, under a top row summarizing the
      frame as a whole: its label is the shape (``"N by M"`` — columns by
      rows), its tally treats each *whole row* as the entity (so "duplicate"
      means a duplicated row and "missing" a row that is entirely blank), and
      its distribution cell is empty (a frame has no single distribution).
    - **A pandas DataFrameGroupBy** — e.g. ``df.groupby("team")``. Renders
      one row per group under a top row showing the group and column counts;
      each row's tally treats whole rows as the entity (same as the plain
      DataFrame header), so "duplicate" means a duplicated row within that
      group. Distribution cells are empty (no single column to show).
    - **A pandas SeriesGroupBy** — e.g. ``df["score"].groupby(df["team"])``.
      Renders one row per group, under a top row showing the series name and
      group count; the top row's tally and distribution cover all values
      across every group, giving a global view above the per-group breakdown.
      Multi-key groupby (grouped by several columns) labels each group with
      its key components joined by `` / ``.
    - **A Series or 1D sequence** — a pandas ``Series``, a list, a numpy
      array, etc. Renders a single row. A bare sequence has no accessible
      name, so where a column name would go it shows the entry count instead
      (e.g. ``"1,234 entries"`` — "entries", not "values", since the count
      includes any missing ones).

    A pavement column's resolution adapts to its total value count: a rug
    (every value shown, each hoverable) up to 24, then equal-mass bins — 4
    bins up to 96 values, 8 bins up to 256, then 16 — so a small column reads
    value-by-value and a large one as a smooth shape.

    Parameters
    ----------
    data : DataFrame, DataFrameGroupBy, SeriesGroupBy, dict, Series, or sequence
        The thing to summarize (see above).
    color : str, default: the tally's dark blue
        CSS color tinting the numeric distribution sparks, so they match the
        tally's "distinct" box. The categorical proportion strips keep their
        own alternating palette.
    height : str, default: '1.6em'
        CSS height of every strip. They share one aspect ratio, so a common
        height makes the tally and distribution columns line up.
    hover : bool, default: True
        Whether the strips carry their native ``<title>`` tooltips.
    highlight : bool, default: True
        Whether the strips brighten the box under the cursor (scoped CSS).
    draggable : bool, default: True
        If True, make the column rows drag-and-drop re-orderable, to rearrange
        them (e.g. to compare columns side by side). A small grip handle appears
        at the left of each column name and is the only draggable target, so the
        rest of each row keeps its normal cursor and stays text-selectable. Adds
        a small, self-contained ``<script>`` (the table's only JavaScript) scoped
        to this one table; the top/total row stays pinned. The script reveals the
        handles, so where it cannot run — notebooks strip it, static exports have
        no JS — they stay hidden and the plain static table shows, which is why
        this is harmless to leave on by default. Pass ``draggable=False`` for a
        guaranteed script-free fragment. Purely visual either way: the new order
        is not read back into Python. Has no effect unless there are two or more
        column rows to reorder — a single column, single group, or bare sequence
        gets no handle (nothing to rearrange).
    min_fill : float, default: 0.1
        When groups or columns have different row counts (a groupby or a dict
        with unequal-length values), each tally strip is scaled so its visible
        width is proportional to its row count relative to the largest group or
        column. *min_fill* is the floor: even the smallest tally strip uses at
        least this fraction of the full strip width, so it stays visible. ``0``
        makes the scaling fully proportional (a very small group's strip can
        shrink to nearly nothing); ``1`` makes every strip fill its full width
        (disables the proportional scaling). Has no effect when all groups or
        columns have the same length.
    shared_bounds : bool or None, default: None
        Whether to place all distribution strips on a single shared value
        axis, so their positions can be compared directly. When True, the
        global min and max across all groups (or all columns, for a dict)
        are used as the axis endpoints for every numeric distribution strip;
        a group whose values occupy only part of the global range shows data
        in the corresponding portion of the strip, with transparent empty
        space elsewhere. None (the default) auto-detects: True for groupby
        inputs (where comparing groups on a common axis is usually the
        point), False for plain DataFrames and dicts (where columns often
        have different units or scales). Has no effect on categorical
        proportion strips.
    labels : sequence, optional
        Which columns (or groups, for a groupby) to show and in what order,
        overriding the default order from the data. Each entry must match a
        column name (for a DataFrame or dict) or a group-key string (for a
        groupby). Raises ``ValueError`` if any name is not found. When
        ``None`` (the default), all columns or groups appear in their
        natural order.
    class_ : str, default: 'pavement-summary'
        CSS class on the ``<table>``, a hook for your own styling.
    path : str, optional
        If given, also write the markup here. A ``.html``/``.htm`` path is
        wrapped in a minimal standalone document; any other suffix is written
        as-is (the bare ``<table>`` fragment).

    Returns
    -------
    Summary
        An object that renders the table inline in Jupyter and whose ``str()``
        is the HTML fragment.

    See Also
    --------
    tally : The distinct/duplicate/missing strip in each row.
    proportion : The categorical distribution strip.
    spark : The numeric distribution sparkline.
    """
    # Compute all column widths from the base height.  All strips keep the same
    # height; tally is 75% as wide as the natural size, distribution 130%.
    # The three text columns get one shared width so the layout is uniform.
    # For non-em heights the widths fall back to width:auto on the SVGs.
    h_em: float | None = None
    if isinstance(height, str) and height.endswith('em'):
        try:
            h_em = float(height[:-2])
        except ValueError:
            pass
    if h_em is not None:
        natural_w = h_em * _SVG_ASPECT
        w_tally_svg = natural_w * _TALLY_WIDTH_SCALE
        w_dist_svg = natural_w * _DIST_WIDTH_SCALE
        w_tally = f'{w_tally_svg:.2f}em'    # for _set_strip_width
        w_dist = f'{w_dist_svg:.2f}em'      # for _set_strip_width
        # <col> widths for the two strip columns.  Text columns all use
        # _TEXT_COL_CLAMP — the same CSS value guarantees they are equal.
        w_tally_col = f'{w_tally_svg:.2f}em'   # tally cell: no horiz. padding
        w_dist_col = f'{w_dist_svg:.2f}em'    # dist cell: no horiz. padding
        # Table width = exact sum of column widths, expressed in CSS so the
        # browser never has leftover space to redistribute.  calc() lets us add
        # the responsive clamp() text columns to the fixed-em strip columns.
        w_total_css = (f'calc(3 * {_TEXT_COL_CLAMP} + {w_tally_col} + {w_dist_col})')
        fixed_layout = True
    else:
        w_tally = w_dist = None
        fixed_layout = False

    opts = {'height': height, 'hover': hover, 'highlight': highlight}
    groupby = _detect_groupby(data)
    columns_data = None if groupby is not None else _as_columns(data)

    # Resolve shared_bounds: None auto-detects (True for groupby, else False).
    if shared_bounds is None:
        shared_bounds = groupby is not None

    def _global_domain(present: list[Any]) -> tuple[float, float] | None:
        """Projected (lo, hi) axis domain from *present* values, or None."""
        if not present:
            return None
        proj, _ = _project(list(present))
        lo, hi = min(proj), max(proj)
        return (lo - 0.5, hi + 0.5) if lo == hi else (lo, hi)

    rows: list[str] = []
    # Dragging only earns its keep with two or more reorderable rows — a single
    # column, group, or bare sequence has nothing to rearrange, so it gets no
    # handles and no script. Each branch enables it once it knows its row count.
    enable_drag = False

    if groupby is not None and groupby[0] == _GROUPBY_FRAME:
        _, n_cols, group_keys, sub_dfs = groupby
        row_key_lists = []
        for sub_df in sub_dfs:
            col_lists = [list(sub_df[c]) for c in sub_df.columns]
            rks = [_row_key(row) for row in zip(*col_lists)] if col_lists else []
            row_key_lists.append(rks)
        if labels is not None:
            lab_str = [str(l) for l in labels]
            missing = [l for l in lab_str if l not in group_keys]
            if missing:
                raise ValueError(
                    f"labels not found in groupby keys: "
                    f"{', '.join(map(repr, missing))}")
            idx = {k: i for i, k in enumerate(group_keys)}
            order = [idx[l] for l in lab_str]
            group_keys = [group_keys[i] for i in order]
            row_key_lists = [row_key_lists[i] for i in order]
        n_groups = len(group_keys)
        enable_drag = draggable and n_groups >= 2
        all_row_keys = [rk for rks in row_key_lists for rk in rks]
        shape_label = (f'<span style="{_COUNT_STYLE}">'
                       f'{n_groups:,} {"group" if n_groups == 1 else "groups"}, '
                       f'{n_cols:,} {"column" if n_cols == 1 else "columns"}</span>')
        rows.append(_summary_row(
            shape_label,
            _tally_strip(all_row_keys, 'row', opts, strip_width=w_tally),
            '', '', '', total=True))
        group_sizes = [len(rks) for rks in row_key_lists]
        max_size = max(group_sizes, default=1)
        for key, row_keys, size in zip(group_keys, row_key_lists, group_sizes):
            fr = max(min_fill, size / max_size) if max_size else 1.0
            rows.append(_summary_row(
                f'<span style="{_NAME_STYLE}">{escape(key)}</span>',
                _tally_strip(row_keys, 'row', opts, strip_width=w_tally,
                             fill_ratio=fr),
                '', '', '', draggable=enable_drag))
    elif groupby is not None:  # _GROUPBY_SERIES
        _, series_name, group_keys, series_groups = groupby
        group_cols = [list(g) for g in series_groups]
        if labels is not None:
            lab_str = [str(l) for l in labels]
            missing = [l for l in lab_str if l not in group_keys]
            if missing:
                raise ValueError(
                    f"labels not found in groupby keys: "
                    f"{', '.join(map(repr, missing))}")
            idx = {k: i for i, k in enumerate(group_keys)}
            order = [idx[l] for l in lab_str]
            group_keys = [group_keys[i] for i in order]
            group_cols = [group_cols[i] for i in order]
        all_values = [v for col in group_cols for v in col]
        all_present = [v for v in all_values if not _is_missing(v)]
        n_groups = len(group_keys)
        enable_drag = draggable and n_groups >= 2
        count_part = _count_label(n_groups, 'group')
        if series_name is not None:
            header_label = (f'<span style="{_NAME_STYLE}">'
                            f'{escape(str(series_name))}</span> {count_part}')
        else:
            header_label = count_part
        global_lo, global_hi = _column_extent(all_values, all_present)
        global_domain = (_global_domain(all_present)
                         if shared_bounds and _pavement_column(all_present)
                         else None)
        rows.append(_summary_row(
            header_label,
            _tally_strip(all_values, 'entry', opts, strip_width=w_tally),
            global_lo,
            _distribution_strip(all_values, all_present, color, opts,
                                strip_width=w_dist),
            global_hi, total=True))
        group_sizes = [len(col) for col in group_cols]
        max_size = max(group_sizes, default=1)
        for key, values, size in zip(group_keys, group_cols, group_sizes):
            fr = max(min_fill, size / max_size) if max_size else 1.0
            present = [v for v in values if not _is_missing(v)]
            lo, hi = _column_extent(values, present)
            rows.append(_summary_row(
                f'<span style="{_NAME_STYLE}">{escape(key)}</span>',
                _tally_strip(values, 'entry', opts, strip_width=w_tally,
                             fill_ratio=fr),
                lo,
                _distribution_strip(values, present, color, opts,
                                    strip_width=w_dist,
                                    domain=global_domain),
                hi, draggable=enable_drag))
    elif columns_data is not None:
        names, col_values = columns_data
        if labels is not None:
            name_to_idx = {n: i for i, n in enumerate(names)}
            missing = [l for l in labels if l not in name_to_idx]
            if missing:
                raise ValueError(
                    f"labels not found in data: "
                    f"{', '.join(map(repr, missing))}")
            names = list(labels)
            col_values = [col_values[name_to_idx[l]] for l in labels]
        n_rows = len(col_values[0]) if col_values else 0
        # The frame as a whole: "N by M" shape label on the left, a tally
        # over whole rows in the middle, distribution cell empty.
        keys = [_row_key(row) for row in zip(*col_values)] if col_values else []
        n_cols = len(names)
        enable_drag = draggable and n_cols >= 2
        shape_label = (f'<span style="{_COUNT_STYLE}">'
                       f'{n_cols:,} by {n_rows:,}</span>')
        rows.append(_summary_row(
            shape_label,
            _tally_strip(keys, 'row', opts, strip_width=w_tally),
            '', '', '', total=True))
        col_sizes = [len(col) for col in col_values]
        max_size = max(col_sizes, default=1)
        all_col_present = [v for col in col_values for v in col if not _is_missing(v)]
        frame_global_domain = (_global_domain(all_col_present)
                               if shared_bounds and _pavement_column(all_col_present)
                               else None)
        for name, values, size in zip(names, col_values, col_sizes):
            fr = max(min_fill, size / max_size) if max_size else 1.0
            present = [v for v in values if not _is_missing(v)]
            lo, hi = _column_extent(values, present)
            rows.append(_summary_row(
                f'<span style="{_NAME_STYLE}">{escape(str(name))}</span>',
                _tally_strip(values, 'entry', opts, strip_width=w_tally,
                             fill_ratio=fr),
                lo,
                _distribution_strip(values, present, color, opts,
                                    strip_width=w_dist,
                                    domain=frame_global_domain),
                hi, draggable=enable_drag))
    else:
        values = list(data)
        present = [v for v in values if not _is_missing(v)]
        lo, hi = _column_extent(values, present)
        rows.append(_summary_row(
            _count_label(len(values), 'entry'),
            _tally_strip(values, 'entry', opts, strip_width=w_tally),
            lo,
            _distribution_strip(values, present, color, opts,
                                strip_width=w_dist),
            hi, draggable=enable_drag))

    if fixed_layout:
        # table-layout:fixed + explicit width ignores cell content entirely.
        # All three text <col> elements use the same clamp() value → guaranteed
        # equal.  The table width is the exact CSS sum of all column widths via
        # calc(), so the browser never has leftover space to redistribute.
        colgroup = (
            f'<colgroup>'
            f'<col style="width:{_TEXT_COL_CLAMP};"/>'
            f'<col style="width:{w_tally_col};"/>'
            f'<col style="width:{_TEXT_COL_CLAMP};"/>'
            f'<col style="width:{w_dist_col};"/>'
            f'<col style="width:{_TEXT_COL_CLAMP};"/>'
            f'</colgroup>'
        )
        table_style = (f'border-collapse:collapse;font-family:inherit;'
                       f'table-layout:fixed;width:{w_total_css};')
    else:
        colgroup = ''
        table_style = 'border-collapse:collapse;font-family:inherit;'

    if enable_drag:
        table_id = f'pavement-summary-{uuid.uuid4().hex[:8]}'
        id_attr = f' id={quoteattr(table_id)}'
        script = _drag_script(table_id)
    else:
        id_attr = script = ''
    table = (
        f'<div style="max-width:{_SUMMARY_MAX_WIDTH};overflow-x:auto;">'
        f'<table{id_attr} class={quoteattr(class_)} style={quoteattr(table_style)}>'
        f'{colgroup}{"".join(rows)}</table>{script}</div>'
    )

    if path is not None:
        document = table
        if path.endswith(('.html', '.htm')):
            document = ('<!doctype html><meta charset="utf-8">'
                        f'<body>{table}</body>')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(document)
    return Summary(table)
