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
  backends show — and each quantile tick carries its single value. An
  inline ``<style>`` adds a CSS ``:hover`` highlight. Both are optional.

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

from ._geometry import row_spec
from .core import pavement_stats

__all__ = ["spark"]

# Internal coordinate box. The numbers only set coordinate resolution;
# their ratio is the spark's default shape — a wide, word-like strip,
# matching the matplotlib spark's 1.4:0.3in default. The geometry is
# stretched to fill this box (like matplotlib's axes filling the figure),
# so the data range never distorts the outline's footprint.
_VIEWBOX = {'horizontal': (140.0, 30.0), 'vertical': (30.0, 140.0)}
# Width of a tick's transparent hover hit-area, in px (non-scaling), wide
# enough to grab with mouse or touch.
_HIT_WIDTH = 8.0


def _num(value: float) -> str:
    """Format a coordinate compactly (no trailing zeros)."""
    return f"{value:.2f}".rstrip('0').rstrip('.')


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
        If True, add native ``<title>`` tooltips: a quantile band and
        value range per bin, and a single value per tick. No JavaScript.
    highlight : bool, default: True
        If True, add a scoped ``<style>`` so the bin under the cursor
        highlights on hover (pure CSS).
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
                    whisker_extent, show_whiskers)
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
                    child: str = '') -> str:
        coords = (f'<line x1="{_num(x0)}" y1="{_num(y0)}" '
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

    # All the strokes share their styling, so it lives once on a parent
    # <g> and each line is just coordinates — keeps a dense rug compact.
    # The two long box edges span the value axis at each side; then one
    # tick per distinct value, reaching past the box as a whisker where
    # the value repeats (and closing the box ends at the extremes).
    strokes = [stroke_line(*pt(side, value_low), *pt(side, value_high))
               for side in (position - half, position + half)]
    strokes += [stroke_line(*pt(position - t.reach, t.value),
                            *pt(position + t.reach, t.value))
                for t in spec.ticks]
    parts.append(
        f'<g stroke="{line_paint}" stroke-width="{_num(line_width)}" '
        f'fill="none" vector-effect="non-scaling-stroke" '
        f'pointer-events="none">{"".join(strokes)}</g>')

    # Transparent wide hit-areas over each tick, on top, carrying the
    # single-value tooltip — like the other backends' tick markers. Only
    # for binned sparks: a rug's ticks are the data points themselves, so
    # one hover target each would be both unhelpful and heavy.
    if hover and bins is not None:
        hits = []
        for t in spec.ticks:
            label = (t.quantile + chr(10) + t.value_str) if t.quantile \
                else t.value_str
            hits.append(stroke_line(
                *pt(position - t.reach, t.value),
                *pt(position + t.reach, t.value),
                child=f'<title>{escape(label)}</title>'))
        parts.append(
            f'<g stroke="transparent" stroke-width="{_num(_HIT_WIDTH)}" '
            f'vector-effect="non-scaling-stroke" pointer-events="all">'
            f'{"".join(hits)}</g>')

    style = ''
    if highlight:
        selector = '.' + '.'.join(class_.split())
        hover_opacity = min(1.0, fill_alpha + 0.2) if color is not None else 0.13
        style = (f'<style>{selector} .pvbin{{transition:fill-opacity .08s ease}}'
                 f'{selector} .pvbin:hover{{fill-opacity:{_num(hover_opacity)}}}'
                 f'</style>')

    root_style = 'overflow:visible;'  # let flush edges show their full stroke
    if inline:
        root_style += f'height:{height};width:auto;vertical-align:-0.15em;'
    label = f"pavement sparkline of {n} value{'' if n == 1 else 's'}"
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_num(view_w)} {_num(view_h)}" '
        f'preserveAspectRatio="none" class={quoteattr(class_)} '
        f'role="img" aria-label={quoteattr(label)} '
        f'style={quoteattr(root_style)}>'
        f'{style}<desc>{escape(label)}</desc>'
        f'{"".join(parts)}</svg>')

    if path is not None:
        document = svg
        if path.endswith(('.html', '.htm')):
            document = ('<!doctype html><meta charset="utf-8">'
                        f'<body>{svg}</body>')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(document)
    return svg
