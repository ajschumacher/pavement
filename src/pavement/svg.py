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
from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Any, Literal
from xml.sax.saxutils import escape, quoteattr

from ._geometry import fmt, pct, resolve_show_box, row_spec, ValueFormat
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
    orientation: Literal['vertical', 'horizontal'] = 'horizontal',
    width: float = 0.6,
    whisker_extent: float = 0.1,
    show_whiskers: bool = False,
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
    orientation : {'vertical', 'horizontal'}, default: 'horizontal'
        Direction of the value axis. 'horizontal' runs values
        left-to-right, the natural fit for an inline strip.
    width : float, default: 0.6
        Box thickness across the row. As with `pavement.matplotlib.spark`
        only its ratio to *whisker_extent* matters — the geometry is
        stretched to fill the SVG.
    whisker_extent : float, default: 0.1
        How far whisker marks reach beyond the box at repeated values.
    show_whiskers : bool, default: False
        Whether to draw whisker marks at repeated quantile values.
    show_box : bool or None, default: None
        Whether to draw the two long box edges (the borders parallel to
        the value axis). None (the default) draws them when binned and
        omits them for a rug (``bins=None``), so a rug spark reads like a
        plain rug; True or False forces it.
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
    # Project an ordered non-float family (Decimal, date/datetime) onto a
    # numeric axis, taking its renderer as the default tooltip format. A
    # caller-supplied value_format still wins (and then receives the projected
    # value); real numbers pass through unchanged.
    data, projected_format = _project(data)
    value_format = value_format or projected_format
    values = pavement_stats(data, bins=bins, weights=weights)
    position = 1.0
    spec = row_spec(values, position, width, orientation,
                    whisker_extent, show_whiskers, value_format, data=data)
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
        # they double as hover targets — the value-range/percentile/count
        # tooltip and the CSS highlight both attach here.
        for b in spec.bins:
            x0, y0 = pt(position - half, b.low)
            x1, y1 = pt(position + half, b.high)
            bin_text = b.value_range + chr(10) + b.band + chr(10) + b.count
            title = f'<title>{escape(bin_text)}</title>' if hover else ''
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
    # The two long box edges (perpendicular to the ticks) are dropped for a
    # rug by default, so it reads like a plain rug rather than a one-row box.
    marks = [stroke_line(*pt(side, value_low), *pt(side, value_high))
             for side in (position - half, position + half)] \
        if resolve_show_box(show_box, bins) else []
    for t in spec.ticks:
        a = pt(position - t.reach, t.value)
        b = pt(position + t.reach, t.value)
        if per_tick_hover:
            # value first, then the percentile cut point (absent for a
            # single-value spark), then the count/share — the shared order.
            label = t.value_str
            if t.quantile:
                label += chr(10) + t.quantile
            label += chr(10) + t.count
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

    The three boxes always fill the strip edge to edge, since the counts
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
    lengths = _box_lengths([count for _, _, count in segments], span, min_box)
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

# Choosing a numeric column's pavement resolution from its total value count.
# While the column is small enough to read one value at a time, a rug shows
# them all — the limit matches `spark`'s tick_hover_limit, so every tick is
# individually hoverable — and past that an equal-mass binned pavement,
# doubling the bin count each time the total roughly quadruples, capped at 16
# (finer bins don't read at a sparkline's size).
_RUG_LIMIT = 24
_BIN_THRESHOLDS = ((97, 4), (257, 8))  # n < cut -> that many bins
_MAX_BINS = 16


def _choose_bins(n: int) -> int | None:
    """Bins for a numeric column's spark, from its total value count.

    None (a rug) up to ``_RUG_LIMIT``, then 4, 8, and a 16-bin cap — see the
    reasoning on the module constants above.
    """
    if n <= _RUG_LIMIT:
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


# Inline styles, so the table is self-contained: it leans on none of the host
# page's CSS and — unlike a <style> block — injects nothing global, which
# matters for a fragment dropped into a notebook cell (and rendered again and
# again). Each strip still carries its own scoped hover style inside its
# <svg>. The grays are mid-tone, legible on light and dark themes alike.
_TD = ('border:none;padding:.18em .8em .18em 0;text-align:left;'
       'vertical-align:middle;white-space:nowrap;')
_TD_TOTAL = _TD + 'border-bottom:1px solid rgba(128,128,128,.35);'
# Distribution column: no side padding — the extent cells handle the gaps.
_TD_DIST = 'border:none;padding:.18em 0 .18em 0;vertical-align:middle;white-space:nowrap;'
_TD_DIST_TOTAL = _TD_DIST + 'border-bottom:1px solid rgba(128,128,128,.35);'
# Min (left extent, right-aligned) and max (right extent, left-aligned) cells.
_TD_EXTL = ('border:none;padding:.18em .4em .18em .4em;text-align:right;'
            'vertical-align:middle;white-space:nowrap;')
_TD_EXTL_TOTAL = _TD_EXTL + 'border-bottom:1px solid rgba(128,128,128,.35);'
_TD_EXTR = ('border:none;padding:.18em .4em .18em .4em;text-align:left;'
            'vertical-align:middle;white-space:nowrap;')
_TD_EXTR_TOTAL = _TD_EXTR + 'border-bottom:1px solid rgba(128,128,128,.35);'
_COUNT_STYLE = 'color:#888;'  # muted, for a "1,234 rows" / "1,234 values" cell
_NAME_STYLE = ('font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'
               'monospace;font-size:.92em;')
_EXTENT_STYLE = ('color:#888;font-family:ui-monospace,SFMono-Regular,Menlo,'
                 'Consolas,monospace;font-size:.85em;')


def _count_label(n: int, noun: str) -> str:
    """A muted ``"1,234 rows"`` style count for a summary's label cell."""
    return f'<span style="{_COUNT_STYLE}">{n:,} {noun if n == 1 else _plural(noun)}</span>'


def _summary_row(label: str, tally_html: str, lo: str, dist_html: str, hi: str,
                 *, total: bool = False) -> str:
    """One table row: label, tally, min-extent, distribution, max-extent cells."""
    td = _TD_TOTAL if total else _TD
    td_dist = _TD_DIST_TOTAL if total else _TD_DIST
    td_extl = _TD_EXTL_TOTAL if total else _TD_EXTL
    td_extr = _TD_EXTR_TOTAL if total else _TD_EXTR
    lo_html = f'<span style="{_EXTENT_STYLE}">{escape(lo)}</span>' if lo else ''
    hi_html = f'<span style="{_EXTENT_STYLE}">{escape(hi)}</span>' if hi else ''
    return (f'<tr><td style="{td}">{label}</td>'
            f'<td style="{td}">{tally_html}</td>'
            f'<td style="{td_extl}">{lo_html}</td>'
            f'<td style="{td_dist}">{dist_html}</td>'
            f'<td style="{td_extr}">{hi_html}</td></tr>')


def _tally_strip(values: list[Any], noun: str, opts: dict[str, Any]) -> str:
    """A column's (or the whole frame's) tally strip — empty if there is
    nothing to count (a zero-length column)."""
    if not values:
        return ''
    return tally(values, noun=noun, **opts)


def _distribution_strip(values: list[Any], present: list[Any],
                        color: str, opts: dict[str, Any]) -> str:
    """A column's distribution strip: a pavement spark when its present values
    are an ordered family a pavement can draw (numbers, ``Decimal``, or
    ``date``/``datetime``), otherwise a proportion strip. Empty when the column
    has no present values — the tally already shows it is all missing (or
    empty), and there is no distribution to draw.
    """
    if not present:
        return ''
    if _pavement_column(present):
        return spark(present, bins=_choose_bins(len(present)),
                     color=color, **opts)
    return proportion(values, **opts)


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


_EXTENT_CROP = 16   # max display length for a categorical extent label


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
    data : DataFrame, dict, Series, or sequence
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
    opts = {'height': height, 'hover': hover, 'highlight': highlight}
    columns_data = _as_columns(data)
    rows: list[str] = []

    if columns_data is not None:
        names, columns = columns_data
        n_rows = len(columns[0]) if columns else 0
        # The frame as a whole: "N by M" shape label on the left, a tally
        # over whole rows in the middle, distribution cell empty.
        keys = [_row_key(row) for row in zip(*columns)] if columns else []
        n_cols = len(names)
        shape_label = (f'<span style="{_COUNT_STYLE}">'
                       f'{n_cols:,} by {n_rows:,}</span>')
        rows.append(_summary_row(
            shape_label,
            _tally_strip(keys, 'row', opts), '', '', '', total=True))
        for name, values in zip(names, columns):
            present = [v for v in values if not _is_missing(v)]
            lo, hi = _column_extent(values, present)
            rows.append(_summary_row(
                f'<span style="{_NAME_STYLE}">{escape(str(name))}</span>',
                _tally_strip(values, 'entry', opts),
                lo,
                _distribution_strip(values, present, color, opts),
                hi))
    else:
        values = list(data)
        present = [v for v in values if not _is_missing(v)]
        lo, hi = _column_extent(values, present)
        rows.append(_summary_row(
            _count_label(len(values), 'entry'),
            _tally_strip(values, 'entry', opts),
            lo,
            _distribution_strip(values, present, color, opts),
            hi))

    table = (f'<table class={quoteattr(class_)} '
             f'style="border-collapse:collapse;font-family:inherit;">'
             f'{"".join(rows)}</table>')

    if path is not None:
        document = table
        if path.endswith(('.html', '.htm')):
            document = ('<!doctype html><meta charset="utf-8">'
                        f'<body>{table}</body>')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(document)
    return Summary(table)
