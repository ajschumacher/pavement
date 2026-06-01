"""
Demo of the ``value_format`` hover hook across the interactive backends.

Every interactive pavement backend — Plotly, Bokeh, HoloViews, and the
dependency-free ``pavement.svg`` sparkline — shows the binned values on
hover. By default a value is rendered to three significant figures; pass
``value_format`` (a function from a value to its display string) to render
it however you like. The same one-argument callable works on every
backend, so ``lambda v: f"${v:,.0f}"`` turns ``1200.0`` into ``$1,200``
in every hover, consistently.

This script builds a single self-contained ``value_format_demo.html`` that
shows, for each backend, the call that makes the plot and the live result
beside it — hover the boxes (and the ticks) to see the formatted values.
Run it with the interactive extras installed::

    pip install -e '.[plotly,bokeh,holoviews]'
    python examples/value_format_demo.py

The page lands in the current directory.
"""

import html

import plotly.graph_objects as go
import plotly.io as pio
from bokeh.embed import components
from bokeh.resources import CDN

import holoviews as hv

import pavement.bokeh as pbk
import pavement.plotly as ppl
import pavement.holoviews as phv
import pavement.svg as psvg

# HoloViews renders one definition through either interactive backend, so
# load both and confirm the hover formats correctly on each.
hv.extension("bokeh", "plotly")

# Daily revenue (in dollars) for three storefronts — the kind of data
# where a bare "1.23e+03" hover helps nobody and "$1,230" helps everyone.
REVENUE = {
    "kiosk": [320, 410, 455, 690, 720, 980, 1180, 1320, 1850, 2400],
    "outlet": [880, 1020, 1140, 1290, 1460, 1700, 1980, 2310, 2820, 3600],
    "flagship": [1500, 1900, 2250, 2700, 3100, 3800, 4400, 5200, 6100, 8200],
}

# One formatter, used unchanged on every backend below.
def money(v):
    return f"${v:,.0f}"


# Each section: a title, the source line(s) to display, and the rendered
# HTML fragment. The code strings are written out verbatim so the page
# documents exactly the call that produced the plot beside it.

def plotly_fragment():
    code = (
        'import pavement.plotly as ppl\n'
        '\n'
        'ppl.plot(revenue, labels=stores, orientation="horizontal",\n'
        '         value_label="daily revenue",\n'
        '         value_format=lambda v: f"${v:,.0f}")\n'
    )
    fig = ppl.plot(
        list(REVENUE.values()), labels=list(REVENUE),
        orientation="horizontal", value_label="daily revenue",
        value_format=money)
    fig.update_layout(height=320, margin=dict(l=70, r=20, t=20, b=40))
    body = pio.to_html(fig, full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": False})
    return "Plotly", code, body


def bokeh_fragment():
    code = (
        'import pavement.bokeh as pbk\n'
        '\n'
        'pbk.plot(revenue, labels=stores, orientation="horizontal",\n'
        '         value_label="daily revenue",\n'
        '         value_format=lambda v: f"${v:,.0f}")\n'
    )
    fig = pbk.plot(
        list(REVENUE.values()), labels=list(REVENUE),
        orientation="horizontal", value_label="daily revenue",
        value_format=money, height=320, width=560)
    script, div = components(fig)
    return "Bokeh", code, script + div


def holoviews_fragment():
    code = (
        'import holoviews as hv\n'
        'import pavement.holoviews as phv\n'
        '\n'
        'hv.extension("bokeh")\n'
        'phv.plot(revenue, labels=stores, orientation="horizontal",\n'
        '         value_label="daily revenue",\n'
        '         value_format=lambda v: f"${v:,.0f}")\n'
    )
    hv.Store.set_current_backend("bokeh")
    el = phv.plot(
        list(REVENUE.values()), labels=list(REVENUE),
        orientation="horizontal", value_label="daily revenue",
        value_format=money)
    el = el.opts(width=560, height=320)
    fig = hv.render(el, backend="bokeh")
    return "HoloViews (bokeh backend)", code, "".join(components(fig))


def holoviews_plotly_fragment():
    code = (
        'import holoviews as hv\n'
        'import pavement.holoviews as phv\n'
        '\n'
        'hv.extension("plotly")        # only this line changes\n'
        'phv.plot(revenue, labels=stores, orientation="horizontal",\n'
        '         value_label="daily revenue",\n'
        '         value_format=lambda v: f"${v:,.0f}")\n'
    )
    # Build with plotly current so plot() adds plotly's hover layer (its
    # shapes can't hover, so an invisible marker line carries the text).
    hv.Store.set_current_backend("plotly")
    el = phv.plot(
        list(REVENUE.values()), labels=list(REVENUE),
        orientation="horizontal", value_label="daily revenue",
        value_format=money)
    # hv.render returns a plotly figure spec (a dict); rebuild it to embed.
    fig = go.Figure(hv.render(el, backend="plotly"))
    fig.update_layout(height=340, margin=dict(l=70, r=20, t=20, b=40),
                      hovermode="closest")
    body = pio.to_html(fig, full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": False})
    hint = ('<p class="hint">The same pavement, rendered through '
            "HoloViews' <em>plotly</em> backend instead of bokeh — hover "
            "still reads the formatted dollars.</p>")
    return "HoloViews (plotly backend)", code, hint + body


def svg_fragment():
    code = (
        'import pavement.svg as psvg\n'
        '\n'
        'psvg.spark(revenue, color="#2c7fb8",\n'
        '           value_format=lambda v: f"${v:,.0f}")\n'
    )
    # A row of sparks, one per store, each hovering formatted dollars.
    rows = []
    for store, values in REVENUE.items():
        spark = psvg.spark(values, color="#2c7fb8", value_format=money)
        rows.append(
            f'<tr><td>{store}</td>'
            f'<td style="font-size:2.2em;line-height:1">{spark}</td></tr>')
    body = (
        '<p class="hint">Each spark is a bare <code>&lt;svg&gt;</code> '
        'string — no JavaScript. Hover a bin to read its dollar range.</p>'
        '<table class="sparks"><tbody>' + "".join(rows) + '</tbody></table>')
    return "Inline SVG (pavement.svg)", code, body


SECTIONS = [plotly_fragment, bokeh_fragment, holoviews_fragment,
            holoviews_plotly_fragment, svg_fragment]


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>pavement — value_format hover hook</title>
{plotly_js}
{bokeh_js}
<style>
  body {{ max-width: 60rem; margin: 3rem auto; padding: 0 1.5rem;
          font: 16px/1.6 -apple-system, Segoe UI, Roboto, sans-serif;
          color: #1a1a1a; background: #fbfaf7; }}
  h1 {{ font-size: 1.7rem; margin-bottom: 0.2rem; }}
  .sub {{ color: #666; margin-top: 0; max-width: 44rem; }}
  .sub code {{ background: #f0eee8; padding: 0.05em 0.3em; border-radius: 3px; }}
  section {{ margin: 2.5rem 0; padding-top: 1.5rem;
             border-top: 1px solid #e3e0d8; }}
  h2 {{ font-size: 1.2rem; margin: 0 0 1rem; }}
  pre {{ margin: 0 0 1.2rem; background: #1d1f23; color: #e8e6e1;
         padding: 1rem 1.1rem; border-radius: 8px; overflow-x: auto;
         font-size: 0.82rem; line-height: 1.5; max-width: 40rem; }}
  pre .kw {{ color: #c792ea; }}
  .result {{ min-width: 0; }}
  .hint {{ color: #666; font-size: 0.9rem; margin: 0 0 0.6rem; }}
  code {{ font-family: Menlo, monospace; }}
  table.sparks td {{ padding: 0.35rem 0.9rem 0.35rem 0;
                     border-bottom: 1px solid #eceae3; color: #444; }}
  table.sparks td:first-child {{ font-variant: small-caps; color: #666; }}
</style></head><body>

<h1>One hover formatter, every backend</h1>
<p class="sub">Every interactive pavement shows its binned values on hover.
Pass <code>value_format</code> — a function from a value to its display
string — and the same one-argument callable formats the hover on every
backend. Here it is <code>lambda v: f"${{v:,.0f}}"</code> throughout, so
<code>1200.0</code> reads as <code>$1,200</code> everywhere. Hover the
boxes (and the ticks) to see it.</p>

{sections}

</body></html>
"""


def _highlight(code):
    """Minimal escaping for the code block (no real syntax highlighting)."""
    return html.escape(code)


def main():
    sections_html = []
    for build in SECTIONS:
        title, code, body = build()
        sections_html.append(
            f'<section><h2>{html.escape(title)}</h2>'
            f'<pre><code>{_highlight(code)}</code></pre>'
            f'<div class="result">{body}</div>'
            f'</section>')

    page = PAGE.format(
        plotly_js='<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" '
                  'charset="utf-8"></script>',
        bokeh_js=CDN.render(),
        sections="\n".join(sections_html))
    with open("value_format_demo.html", "w", encoding="utf-8") as f:
        f.write(page)
    print("wrote value_format_demo.html — open it and hover the pavements")


if __name__ == "__main__":
    main()
