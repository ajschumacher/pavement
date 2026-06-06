"""
Interactive pavement plots across every backend.

Builds a single self-contained ``interactive_demo.html`` that covers all three
interactive backends — Plotly, Bokeh, and HoloViews — in separate sections.
Each section shows the same things: a single-row pavement, a multi-category
comparison, and a joint scatter with pavement marginals. The code that produced
each output is shown in a collapsible block just above it.

Run it with the optional extras installed::

    pip install -e '.[plotly,bokeh,holoviews]'
    python examples/interactive_demo.py

Missing backends are skipped with a note; the page still writes.
"""

from __future__ import annotations

import html
import random

# Shared data -----------------------------------------------------------------

def make_clusters(seed: int = 1, n: int = 60):
    """Two labelled 2D Gaussian clusters, returned as parallel lists."""
    rng = random.Random(seed)
    groups, xs, ys = [], [], []
    for label, (mx, my) in {"A": (0, 0), "B": (2, 1.5)}.items():
        for _ in range(n):
            groups.append(label)
            xs.append(rng.gauss(mx, 1))
            ys.append(rng.gauss(my, 1))
    return groups, xs, ys


SINGLE = [1, 2, 2, 3, 4, 5, 8, 13, 21]
CATEGORIES = [
    [1, 2, 3, 4, 5, 6, 7, 8],
    [3, 4, 5, 6, 7, 8, 9, 12],
    [2, 2, 3, 5, 8, 8, 9, 10],
]
CAT_LABELS = ["cats", "dogs", "birds"]


# Code-above-output helper ----------------------------------------------------

_CODE_STYLE = (
    "margin:.6rem 0 1rem;background:#1d1f23;color:#e8e6e1;"
    "padding:.9rem 1rem;border-radius:8px;font-size:.82rem;"
    "line-height:1.5;overflow-x:auto;"
)
_DETAILS_STYLE = "margin-bottom:1.2rem;"
_SUMMARY_STYLE = "cursor:pointer;color:#555;font-size:.9rem;"


def _code_block(code: str) -> str:
    return (
        f'<details style="{_DETAILS_STYLE}">'
        f'<summary style="{_SUMMARY_STYLE}">Show code</summary>'
        f'<pre style="{_CODE_STYLE}"><code>{html.escape(code)}</code></pre>'
        f'</details>'
    )


def _subsection(title: str, code: str, body: str) -> str:
    return (
        f"<h3>{title}</h3>"
        + _code_block(code)
        + f'<div class="output">{body}</div>'
    )


# Plotly ----------------------------------------------------------------------

def plotly_section() -> str:
    import plotly.graph_objects as go
    import plotly.io as pio
    import pavement.plotly as ppl

    def fig_html(fig, height: int = 280) -> str:
        fig.update_layout(
            height=height,
            margin=dict(l=60, r=20, t=20, b=40),
            showlegend=True,
        )
        return pio.to_html(
            fig, full_html=False, include_plotlyjs=False,
            config={"displayModeBar": False})

    groups, xs, ys = make_clusters()
    palette = {"A": "#636efa", "B": "#EF553B"}

    scatter = go.Figure()
    for g in ["A", "B"]:
        scatter.add_trace(go.Scatter(
            x=[x for x, gg in zip(xs, groups) if gg == g],
            y=[y for y, gg in zip(ys, groups) if gg == g],
            mode="markers", name=g, marker=dict(color=palette[g], size=7)))
    scatter.update_xaxes(title_text="x").update_yaxes(title_text="y")
    joint = ppl.with_marginals(scatter, x=xs, y=ys, categories=groups)
    joint.update_layout(width=640, height=500)

    return (
        _subsection(
            "Single pavement",
            "import pavement.plotly as ppl\n\nppl.plot([1, 2, 2, 3, 4, 5, 8, 13, 21])",
            fig_html(ppl.plot(SINGLE, value_label="value")))
        + _subsection(
            "Multiple categories",
            "ppl.plot(\n"
            "    [[1,2,3,4,5,6,7,8], [3,4,5,6,7,8,9,12], [2,2,3,5,8,8,9,10]],\n"
            '    labels=["cats", "dogs", "birds"])',
            fig_html(ppl.plot(CATEGORIES, labels=CAT_LABELS,
                              value_label="value"), height=340))
        + _subsection(
            "Scatter with pavement marginals",
            "import plotly.graph_objects as go\nimport pavement.plotly as ppl\n\n"
            "scatter = go.Figure()\n"
            "for g in groups:\n"
            "    scatter.add_trace(go.Scatter(x=xs[g], y=ys[g], name=g, ...))\n"
            "ppl.with_marginals(scatter, x=xs, y=ys, categories=groups)",
            fig_html(joint, height=500))
    )


# Bokeh -----------------------------------------------------------------------

_bokeh_figs: dict = {}


def bokeh_section() -> str:
    from bokeh.embed import components
    import pavement.bokeh as pbk

    def placeholder(fig, key: str) -> str:
        fig.toolbar_location = None
        _bokeh_figs[key] = fig
        return f"@@BOKEH:{key}@@"

    groups, xs, ys = make_clusters()
    palette = {"A": "#1f77b4", "B": "#ff7f0e"}

    from bokeh.plotting import figure as bk_figure
    scatter = bk_figure(width=500, height=380, x_axis_label="x", y_axis_label="y")
    for g in ["A", "B"]:
        scatter.scatter(
            [x for x, gg in zip(xs, groups) if gg == g],
            [y for y, gg in zip(ys, groups) if gg == g],
            size=7, color=palette[g], legend_label=g, name=g)
    scatter.legend.location = "top_left"
    joint = pbk.with_marginals(scatter, x=xs, y=ys, categories=groups)

    return (
        _subsection(
            "Single pavement",
            "import pavement.bokeh as pbk\nfrom bokeh.plotting import show\n\n"
            "show(pbk.plot([1, 2, 2, 3, 4, 5, 8, 13, 21], value_label='value'))",
            placeholder(pbk.plot(SINGLE, value_label="value", height=240, width=520),
                        "bk_single"))
        + _subsection(
            "Multiple categories",
            "pbk.plot(\n"
            "    [[1,2,3,4,5,6,7,8], [3,4,5,6,7,8,9,12], [2,2,3,5,8,8,9,10]],\n"
            '    labels=["cats", "dogs", "birds"])',
            placeholder(pbk.plot(CATEGORIES, labels=CAT_LABELS,
                                 value_label="value", height=320, width=520),
                        "bk_cats"))
        + _subsection(
            "Scatter with pavement marginals",
            "from bokeh.plotting import figure\nimport pavement.bokeh as pbk\n\n"
            "scatter = figure()\n"
            "for g in groups:\n"
            "    scatter.scatter(xs[g], ys[g], color=palette[g], name=g)\n"
            "pbk.with_marginals(scatter, x=xs_all, y=ys_all, categories=groups)",
            placeholder(joint, "bk_joint"))
    )


def bokeh_resolve(body: str) -> tuple[str, str]:
    """Swap @@BOKEH:key@@ placeholders for rendered divs; return (body, script)."""
    from bokeh.embed import components
    script, divs = components(_bokeh_figs)
    for key, div in divs.items():
        body = body.replace(f"@@BOKEH:{key}@@", div)
    return body, script


# HoloViews -------------------------------------------------------------------

def holoviews_section() -> str:
    import holoviews as hv
    from bokeh.embed import components
    import pavement.holoviews as phv

    hv.extension("bokeh")

    def hv_placeholder(obj, key: str, width: int = 520, height: int = 260) -> str:
        fig = hv.render(obj.opts(width=width, height=height), backend="bokeh")
        fig.toolbar_location = None
        _bokeh_figs[key] = fig
        return f"@@BOKEH:{key}@@"

    groups, xs, ys = make_clusters()

    scatter = hv.NdOverlay(
        {g: hv.Scatter([(x, y) for x, y, gg in zip(xs, ys, groups) if gg == g])
         for g in ["A", "B"]},
        kdims="group")
    joint = phv.with_marginals(scatter, x=xs, y=ys, categories=groups)

    return (
        _subsection(
            "Single pavement",
            "import holoviews as hv\nimport pavement.holoviews as phv\n\n"
            "hv.extension('bokeh')\nphv.plot([1, 2, 2, 3, 4, 5, 8, 13, 21])",
            hv_placeholder(phv.plot(SINGLE), "hv_single"))
        + _subsection(
            "Multiple categories",
            "phv.plot(\n"
            "    [[1,2,3,4,5,6,7,8], [3,4,5,6,7,8,9,12], [2,2,3,5,8,8,9,10]],\n"
            '    labels=["cats", "dogs", "birds"])',
            hv_placeholder(phv.plot(CATEGORIES, labels=CAT_LABELS), "hv_cats",
                           height=340))
        + _subsection(
            "Scatter with pavement marginals",
            "import holoviews as hv\nimport pavement.holoviews as phv\n\n"
            "scatter = hv.NdOverlay({g: hv.Scatter([...]) for g in groups})\n"
            "phv.with_marginals(scatter, x=xs, y=ys, categories=groups)",
            hv_placeholder(joint.opts(
                hv.opts.Scatter(width=480, height=360, size=6, tools=["hover"])),
                "hv_joint", width=640, height=500))
    )


# Page assembly ---------------------------------------------------------------

def build() -> str:
    sections_html = []
    errors = []
    bokeh_script = ""

    def add(name: str, blurb: str, fn):
        try:
            sections_html.append(
                f'<section>'
                f'<h2>{name}</h2>'
                f'<p class="blurb">{blurb}</p>'
                + fn() +
                f'</section>')
        except Exception as exc:
            errors.append(f"<li><strong>{html.escape(name)}</strong>: "
                          f"{html.escape(str(exc))}</li>")

    add("Plotly",
        "Interactive hover, pan, and zoom. Returns a plain "
        "<code>plotly.graph_objects.Figure</code>.",
        plotly_section)
    add("Bokeh",
        "Interactive hover, pan, and zoom. Returns a plain "
        "<code>bokeh.plotting.figure</code> with glyphs and a hover tool.",
        bokeh_section)
    add("HoloViews",
        "Backend-agnostic: the same definition renders through Bokeh or Plotly. "
        "Here rendered via Bokeh.",
        holoviews_section)

    body = "".join(sections_html)

    if _bokeh_figs:
        body, bokeh_script = bokeh_resolve(body)

    errors_html = ""
    if errors:
        errors_html = (
            '<p class="errors">Skipped (not installed?):<ul>'
            + "".join(errors) + "</ul></p>")

    try:
        from bokeh.resources import CDN
        bokeh_resources = CDN.render()
    except ImportError:
        bokeh_resources = ""

    try:
        plotly_js = ('<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" '
                     'charset="utf-8"></script>')
    except Exception:
        plotly_js = ""

    return PAGE.format(
        plotly_js=plotly_js,
        bokeh_resources=bokeh_resources,
        errors=errors_html,
        body=body,
        bokeh_script=bokeh_script,
    )


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>pavement — interactive backends</title>
{plotly_js}
{bokeh_resources}
<style>
  body {{ max-width: 60rem; margin: 3rem auto; padding: 0 1.5rem;
          font: 17px/1.6 Georgia, serif; color: #1a1a1a; background: #fbfaf7; }}
  h1 {{ font-size: 1.7rem; margin-bottom: 0.2rem; }}
  h2 {{ font-size: 1.25rem; margin: 0; }}
  h3 {{ font-size: 1rem; margin: 1.8rem 0 0.4rem; color: #333; }}
  .sub {{ color: #777; font-style: italic; margin-top: 0; }}
  .blurb {{ color: #555; font-size: 0.95rem; margin: 0.3rem 0 1.2rem; }}
  p {{ max-width: 54rem; }}
  code {{ font-family: Menlo, monospace; font-size: 0.85em;
          background: #f0eee8; padding: 0.05em 0.3em; border-radius: 3px; }}
  /* Code blocks supply their own dark background; don't let the inline-code
     beige box paint over the light-on-dark text inside them. */
  pre code {{ background: none; padding: 0; border-radius: 0;
              font-size: inherit; color: inherit; }}
  section {{ margin: 2.6rem 0; padding-top: 1.4rem;
             border-top: 1px solid rgba(128,128,128,.22); }}
  .output {{ margin-bottom: 0.6rem; }}
  .errors {{ color: #b2182b; }}
</style></head><body>

<h1>Interactive pavement plots</h1>
<p class="sub">The same API — <code>plot(data)</code> and
<code>with_marginals(scatter, x, y, categories)</code> — on every interactive
backend. Pick one by importing its submodule.</p>

{errors}

{body}

{bokeh_script}
</body></html>
"""


def main() -> None:
    with open("interactive_demo.html", "w", encoding="utf-8") as f:
        f.write(build())
    print("wrote interactive_demo.html — open it and hover the pavements")


if __name__ == "__main__":
    main()
