"""
Demo: rug plots drop the box edges by default, on every backend.

A pavement normally frames its value ticks with two long box edges (the
borders parallel to the value axis). In rug mode (``bins=None``) those
edges are now dropped by default, so a rug reads like an ordinary rug plot
and the box becomes a quick visual cue for "these are quantiles, not raw
points". ``show_box=True`` keeps the box on a rug; ``show_box=False`` drops
it from a binned plot.

This script renders the before/after for matplotlib, SVG, Plotly, Bokeh,
and HoloViews into one self-contained HTML file and opens it in a browser.

Run it with the package importable, e.g. from the repo root:

    PYTHONPATH=src python examples/rug_borderless_demo.py
"""

from __future__ import annotations

import base64
import io
import webbrowser
from pathlib import Path

# A single dataset, used for every backend so the panels are comparable.
# Repeats and a gap give the rug some structure to look at.
DATA = [1, 2, 2, 3, 3, 3, 4, 5, 5, 7, 9, 12, 12, 13, 18]


# --- matplotlib (static PNGs, embedded as base64) -------------------------

def matplotlib_panels() -> list[tuple[str, str]]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    import pavement.matplotlib as pav

    def png(render) -> str:
        fig, ax = plt.subplots(figsize=(4.2, 1.6))
        render(ax)
        ax.set_yticks([])
        # Hide the Axes frame (spines) so it doesn't read as a box itself —
        # then the pavement's own box (or its absence, for a rug) is the
        # only rectangle on screen. Keep the bottom for the value axis.
        for side in ("top", "left", "right"):
            ax.spines[side].set_visible(False)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=130)
        plt.close(fig)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f'<img src="data:image/png;base64,{encoded}" alt="">'

    return [
        ("Binned (bins=4) — boxed, as always",
         png(lambda ax: pav.plot(DATA, bins=4, orientation="horizontal",
                                 ax=ax))),
        ("Rug (bins=None) — borderless by default",
         png(lambda ax: pav.plot(DATA, bins=None, orientation="horizontal",
                                 ax=ax))),
        ("Rug with show_box=True — box forced back on",
         png(lambda ax: pav.plot(DATA, bins=None, show_box=True,
                                 orientation="horizontal", ax=ax))),
    ]


# --- SVG (inline, self-contained) -----------------------------------------

def svg_panels() -> list[tuple[str, str]]:
    import pavement.svg as pav

    return [
        ("Binned (bins=4) — boxed",
         pav.spark(DATA, bins=4, height="2.2em")),
        ("Rug (bins=None) — borderless by default",
         pav.spark(DATA, bins=None, height="2.2em")),
        ("Rug with show_box=True — box forced back on",
         pav.spark(DATA, bins=None, show_box=True, height="2.2em")),
    ]


# --- Plotly (inline interactive) ------------------------------------------

def plotly_panels() -> list[tuple[str, str]]:
    import pavement.plotly as pav

    def html(**kw):
        fig = pav.plot(DATA, orientation="horizontal", **kw)
        fig.update_layout(height=180, margin=dict(l=10, r=10, t=10, b=30),
                          showlegend=False)
        fig.update_yaxes(visible=False)
        return fig.to_html(full_html=False, include_plotlyjs="cdn")

    return [
        ("Binned (bins=4) — boxed", html(bins=4)),
        ("Rug (bins=None) — borderless by default", html(bins=None)),
        ("Rug with show_box=True", html(bins=None, show_box=True)),
    ]


# --- Bokeh (inline interactive) -------------------------------------------

def bokeh_panels() -> list[tuple[str, str]]:
    from bokeh.embed import components

    import pavement.bokeh as pav

    def fig(**kw):
        f = pav.plot(DATA, orientation="horizontal", height=180, width=420,
                     toolbar_location=None, **kw)
        f.yaxis.visible = False
        return f

    scripts_divs = [
        ("Binned (bins=4) — boxed", fig(bins=4)),
        ("Rug (bins=None) — borderless by default", fig(bins=None)),
        ("Rug with show_box=True", fig(bins=None, show_box=True)),
    ]
    panels = []
    for title, f in scripts_divs:
        script, div = components(f)
        panels.append((title, script + div))
    return panels


# --- HoloViews (rendered through Bokeh, inline) ---------------------------

def holoviews_panels() -> list[tuple[str, str]]:
    import holoviews as hv
    from bokeh.embed import components

    import pavement.holoviews as pav
    hv.extension("bokeh")

    def fig(**kw):
        obj = pav.plot(DATA, orientation="horizontal", **kw)
        bokeh_fig = hv.render(obj, backend="bokeh")
        bokeh_fig.height, bokeh_fig.width = 180, 420
        bokeh_fig.toolbar_location = None
        bokeh_fig.yaxis.visible = False
        return bokeh_fig

    out = []
    for title, kw in [
        ("Binned (bins=4) — boxed", dict(bins=4)),
        ("Rug (bins=None) — borderless by default", dict(bins=None)),
        ("Rug with show_box=True", dict(bins=None, show_box=True)),
    ]:
        script, div = components(fig(**kw))
        out.append((title, script + div))
    return out


# --- Assemble the page ----------------------------------------------------

def _bokeh_cdn() -> str:
    from bokeh.resources import CDN
    return "\n".join(CDN.render_js().split("\n"))


def section(name: str, intro: str, panels: list[tuple[str, str]]) -> str:
    cards = "\n".join(
        f'<figure class="card"><figcaption>{title}</figcaption>'
        f'<div class="art">{body}</div></figure>'
        for title, body in panels)
    return (f'<section><h2>{name}</h2><p class="intro">{intro}</p>'
            f'<div class="row">{cards}</div></section>')


def build() -> str:
    sections = []
    errors = []

    def add(name, intro, fn):
        try:
            sections.append(section(name, intro, fn()))
        except Exception as exc:  # a missing optional backend shouldn't abort
            errors.append(f"{name}: {exc!r}")

    add("matplotlib", "Static artists. The rug's box edges are gone; the "
        "ticks remain.", matplotlib_panels)
    add("SVG sparkline", "Self-contained inline SVG. Hover a binned box or "
        "a rug tick for its tooltip.", svg_panels)
    add("Plotly", "Interactive — pan, zoom, hover.", plotly_panels)
    add("Bokeh", "Interactive — pan, zoom, hover.", bokeh_panels)
    add("HoloViews", "Rendered through the Bokeh backend.", holoviews_panels)

    note = ""
    if errors:
        note = ('<p class="errors">Skipped (not installed?): '
                + "; ".join(errors) + "</p>")

    return f"""<!doctype html>
<meta charset="utf-8">
<title>Pavement rug plots — borderless by default</title>
{_bokeh_cdn()}
<style>
  body {{ font: 16px/1.5 -apple-system, system-ui, sans-serif;
         margin: 0 auto; max-width: 1100px; padding: 2rem 1.5rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.7rem; margin-bottom: .2rem; }}
  .lede {{ color: #444; max-width: 70ch; }}
  .lede code {{ background: #f0f0f3; padding: .1em .35em; border-radius: 4px; }}
  section {{ margin-top: 2.5rem; border-top: 1px solid #e6e6ea; padding-top: 1rem; }}
  h2 {{ font-size: 1.25rem; margin-bottom: .1rem; }}
  .intro {{ color: #555; margin-top: .2rem; }}
  .row {{ display: flex; flex-wrap: wrap; gap: 1rem; align-items: stretch; }}
  .card {{ margin: 0; flex: 1 1 320px; border: 1px solid #e6e6ea; border-radius: 10px;
          padding: .8rem .9rem; background: #fcfcfd; }}
  figcaption {{ font-size: .82rem; color: #666; margin-bottom: .5rem; }}
  .art {{ display: flex; align-items: center; min-height: 64px; }}
  .art img {{ max-width: 100%; }}
  .errors {{ color: #b2182b; }}
</style>
<h1>Rug plots are borderless by default</h1>
<p class="lede">A pavement frames its value ticks with two long box edges. In
rug mode (<code>bins=None</code>) those edges are now dropped by default, so a
rug reads like an ordinary rug plot — and the box becomes a quick cue that
you're looking at quantiles, not raw points. <code>show_box=True</code> forces
the box back on; <code>show_box=False</code> drops it from a binned plot. Same
default on every backend.</p>
{note}
{''.join(sections)}
"""


def main() -> None:
    # Like the other demos, the output HTML lands in the current directory.
    out = Path("rug_borderless_demo.html").resolve()
    out.write_text(build(), encoding="utf-8")
    print(f"wrote {out} — open it to compare the backends")
    webbrowser.open(out.as_uri())


if __name__ == "__main__":
    main()
