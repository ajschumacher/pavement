"""
Cross-backend demo of the expressive pavement box edges.

A pavement draws each bin's long top/bottom edges *only where one or more
values fall strictly inside that bin*, so the box closes where values are
spread out and opens into a gap where the mass clumps onto a value line. An
explicit ``show_box=True`` forces the complete box instead.

This script renders the **same data** through **every backend** — the inline
SVG spark, the matplotlib raster, and the interactive Plotly, Bokeh, and
HoloViews figures — and lays them out in one self-contained HTML page so you
can see they all open and close the box at exactly the same places.

The boxes are drawn outline-only (no fill), because the gap *is* the missing
top/bottom edge: a translucent fill would paper over it.

Run it with the plotting extras installed::

    python examples/box_edges_demo.py

It writes ``box_edges_demo.html`` to the current directory; open it and hover
the interactive plots.
"""

import base64
import io
import random
import warnings

warnings.filterwarnings("ignore")

import pavement.svg as psvg
import pavement.matplotlib as pmpl
import pavement.plotly as pp
import pavement.bokeh as pb
import pavement.holoviews as ph

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import holoviews as hv
hv.extension("bokeh")

from bokeh.embed import components
from bokeh.resources import CDN


# ---------------------------------------------------------------------------
# The classic iris sepal_width (cm), all 150 measurements. Rounded to 0.1 cm,
# so the values are discrete and heavily repeated: the most common ones (2.8,
# 2.9, 3.0, 3.1) land *on* the equal-mass bin edges, so those central bins
# hold no value strictly inside — and the box opens a gap right where the data
# is densest. The perfect thing to draw the eye to what the gap means.
# ---------------------------------------------------------------------------
sepal_width = [
    3.5, 3.0, 3.2, 3.1, 3.6, 3.9, 3.4, 3.4, 2.9, 3.1, 3.7, 3.4, 3.0,
    3.0, 4.0, 4.4, 3.9, 3.5, 3.8, 3.8, 3.4, 3.7, 3.6, 3.3, 3.4, 3.0,
    3.4, 3.5, 3.4, 3.2, 3.1, 3.4, 4.1, 4.2, 3.1, 3.2, 3.5, 3.6, 3.0,
    3.4, 3.5, 2.3, 3.2, 3.5, 3.8, 3.0, 3.8, 3.2, 3.7, 3.3, 3.2, 3.2,
    3.1, 2.3, 2.8, 2.8, 3.3, 2.4, 2.9, 2.7, 2.0, 3.0, 2.2, 2.9, 2.9,
    3.1, 3.0, 2.7, 2.2, 2.5, 3.2, 2.8, 2.5, 2.8, 2.9, 3.0, 2.8, 3.0,
    2.9, 2.6, 2.4, 2.4, 2.7, 2.7, 3.0, 3.4, 3.1, 2.3, 3.0, 2.5, 2.6,
    3.0, 2.6, 2.3, 2.7, 3.0, 2.9, 2.9, 2.5, 2.8, 3.3, 2.7, 3.0, 2.9,
    3.0, 3.0, 2.5, 2.9, 2.5, 3.6, 3.2, 2.7, 3.0, 2.5, 2.8, 3.2, 3.0,
    3.8, 2.6, 2.2, 3.2, 2.8, 2.8, 2.7, 3.3, 3.2, 2.8, 3.0, 2.8, 3.0,
    2.8, 3.8, 2.8, 2.8, 2.6, 3.0, 3.4, 3.1, 3.0, 3.1, 3.1, 3.1, 2.7,
    3.2, 3.3, 3.0, 2.5, 3.0, 3.4, 3.0,
]

# A smooth, spread distribution for contrast — every bin holds points strictly
# inside it, so the box never gaps.
_r = random.Random(1)
spread = [round(_r.uniform(0, 100), 1) for _ in range(400)]

# (title, data, extra-kwargs) — the kwargs every backend's plot/spark accepts.
CASES = [
    ("iris sepal_width, 8 bins — the box gaps in the dense middle, where "
     "2.8–3.1 cm are so common they all sit on bin edges",
     sepal_width, dict(bins=8)),
    ("Same data, <code>show_box=True</code> — the complete box, forced",
     sepal_width, dict(bins=8, show_box=True)),
    ("A spread distribution, 8 bins — every bin is populated, so the box "
     "stays closed end to end",
     spread, dict(bins=8)),
]

COLOR = "#2166ac"
LINE_W = 2
PLOT_W, PLOT_H = 560, 170


# ---------------------------------------------------------------------------
# Per-backend renderers (outline only — no fill — so the gaps read clearly),
# each returning an HTML fragment for one case.
# ---------------------------------------------------------------------------
def render_svg(data, kw):
    return psvg.spark(data, orientation="horizontal", line_color=COLOR,
                      line_width=LINE_W, height="3em", **kw)


def render_matplotlib(data, kw):
    fig, ax = plt.subplots(figsize=(PLOT_W / 100, PLOT_H / 100), dpi=110)
    pmpl.plot(data, orientation="horizontal", ax=ax,
              line_props={"linewidth": LINE_W, "color": COLOR}, **kw)
    ax.set_yticks([])
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.margins(x=0.02)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return (f'<img alt="matplotlib pavement" '
            f'style="max-width:100%;height:auto;" '
            f'src="data:image/png;base64,{b64}">')


def render_plotly(data, kw):
    fig = pp.plot(data, orientation="horizontal", color=COLOR, fill_alpha=0,
                  line_width=LINE_W, **kw)
    fig.update_layout(width=PLOT_W, height=PLOT_H,
                      margin=dict(l=30, r=10, t=10, b=30),
                      yaxis=dict(visible=False), showlegend=False,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": False})


# Bokeh and HoloViews both render to Bokeh figures; we collect them and emit a
# single shared <script> at the end, so BokehJS initializes once.
_bokeh_figs = {}


def _bokeh_figure(fig, key):
    fig.width, fig.height = PLOT_W, PLOT_H
    fig.toolbar_location = None
    fig.yaxis.visible = False
    fig.background_fill_alpha = 0
    fig.border_fill_alpha = 0
    _bokeh_figs[key] = fig
    return f"@@BOKEH:{key}@@"  # placeholder, swapped for its <div> at the end


def render_bokeh(data, kw, key):
    fig = pb.plot(data, orientation="horizontal", color=COLOR, fill_alpha=0,
                  line_width=LINE_W, **kw)
    return _bokeh_figure(fig, key)


def render_holoviews(data, kw, key):
    obj = ph.plot(data, orientation="horizontal", color=COLOR, fill_alpha=0, **kw)
    fig = hv.render(obj, backend="bokeh")
    return _bokeh_figure(fig, key)


BACKENDS = [
    ("SVG <code>spark</code>", "Inline, self-contained SVG — no JavaScript.",
     lambda data, kw, key: render_svg(data, kw)),
    ("matplotlib <code>plot</code>", "Static raster (PNG), for print.",
     lambda data, kw, key: render_matplotlib(data, kw)),
    ("Plotly <code>plot</code>", "Interactive — hover, pan, zoom.",
     lambda data, kw, key: render_plotly(data, kw)),
    ("Bokeh <code>plot</code>", "Interactive — hover, pan, zoom.",
     render_bokeh),
    ("HoloViews <code>plot</code>", "Backend-agnostic (rendered via Bokeh).",
     render_holoviews),
]


def build():
    sections = []
    for b_index, (title, blurb, renderer) in enumerate(BACKENDS):
        cards = []
        for c_index, (caption, data, kw) in enumerate(CASES):
            key = f"b{b_index}c{c_index}"
            fragment = renderer(data, kw, key)
            cards.append(
                f'<figure class="card">'
                f'<div class="plot">{fragment}</div>'
                f'<figcaption>{caption}</figcaption></figure>')
        sections.append(
            f'<section><h2>{title}</h2>'
            f'<p class="blurb">{blurb}</p>'
            f'<div class="grid">{"".join(cards)}</div></section>')

    # One shared Bokeh <script> for every Bokeh/HoloViews figure; swap each
    # placeholder for its rendered <div>.
    bokeh_script, bokeh_divs = components(_bokeh_figs)
    body = "".join(sections)
    for key, div in bokeh_divs.items():
        body = body.replace(f"@@BOKEH:{key}@@", div)

    return PAGE.format(body=body,
                       bokeh_resources=CDN.render(),
                       bokeh_script=bokeh_script)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>pavement — expressive box edges across every backend</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
{bokeh_resources}
<style>
  body {{ max-width: 70rem; margin: 2.5rem auto; padding: 0 1.5rem;
          font: 17px/1.6 Georgia, serif; color: #1a1a1a; background: #fbfaf7; }}
  h1 {{ font-size: 1.7rem; margin-bottom: 0.2rem; }}
  h2 {{ font-size: 1.15rem; margin: 0 0 0.2rem; }}
  .sub {{ color: #777; font-style: italic; margin-top: 0; }}
  .blurb {{ color: #666; font-size: 0.95rem; margin: 0 0 1rem; }}
  p {{ max-width: 54rem; }}
  code {{ font-family: Menlo, monospace; font-size: 0.85em;
          background: #f0eee8; padding: 0.05em 0.3em; border-radius: 3px; }}
  section {{ margin: 2.4rem 0; padding-top: 1.4rem;
             border-top: 1px solid rgba(128,128,128,.25); }}
  .grid {{ display: grid; grid-template-columns: repeat(3, 1fr);
           gap: 1rem 1.4rem; align-items: start; }}
  @media (max-width: 60rem) {{ .grid {{ grid-template-columns: 1fr; }} }}
  .card {{ margin: 0; min-width: 0; }}
  .plot {{ min-height: 60px; display: flex; align-items: center;
           overflow-x: auto; }}
  .plot img, .plot svg {{ display: block; }}
  figcaption {{ color: #555; font-size: 0.85rem; margin-top: 0.4rem; }}
  .legend {{ font-size: 0.95rem; color: #444; }}
</style></head><body>

<h1>Expressive box edges, every backend</h1>
<p class="sub">A pavement closes its box where values are spread out and opens
a gap where they clump onto a value line — identically across all five
backends.</p>

<p>Each bin draws its long top and bottom edges <em>only over itself, and only
when one or more values fall strictly inside it</em>. Below, every backend
renders the <strong>same three cases</strong> (boxes drawn outline-only, so the
gap — a missing stretch of top/bottom edge — reads clearly): iris
<code>sepal_width</code> binned into 8, which gaps in the dense middle; the
same data with <code>show_box=True</code> to force the complete box; and a
spread distribution, which stays closed. Compare a column down the page — every
backend opens and closes the box at the same places.</p>

{body}

<p class="legend">Drawn straight from
<code>pavement.svg</code>, <code>pavement.matplotlib</code>,
<code>pavement.plotly</code>, <code>pavement.bokeh</code>, and
<code>pavement.holoviews</code> — one shared geometry, one shared rule.</p>

{bokeh_script}
</body></html>
"""


def main():
    html = build()
    with open("box_edges_demo.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote box_edges_demo.html")


if __name__ == "__main__":
    main()
