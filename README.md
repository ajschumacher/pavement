# Pavement plots

[![PyPI](https://img.shields.io/pypi/v/pavement.svg)](https://pypi.org/project/pavement/)
[![CI](https://github.com/ajschumacher/pavement/actions/workflows/ci.yml/badge.svg)](https://github.com/ajschumacher/pavement/actions/workflows/ci.yml)

Quantile-based pavement plots: every box contains an equal share of the
data. One plot, four drawing backends — matplotlib, Bokeh, Plotly, and
HoloViews — behind a single shared API, plus a dependency-free
`pavement.svg` for interactive inline sparklines.

![plot of four data sets](https://raw.githubusercontent.com/ajschumacher/pavement/main/examples/four_sets.png)

See more in the [demo notebook](https://github.com/ajschumacher/pavement/blob/main/examples/demo.ipynb).


## Install

The core (the quantile statistics) is pure Python with no dependencies:

    pip install pavement

Each rendering backend — matplotlib included — is an optional extra, so
you only install what you'll use. Install the one(s) you want:

    pip install pavement[matplotlib]
    pip install pavement[bokeh]
    pip install pavement[plotly]
    pip install pavement[holoviews]
    pip install pavement[all]          # all four

The `pavement.svg` sparkline backend needs no extra — it has no
dependencies and is always available with the base install.


## Usage

Pick a backend by importing its submodule. Every backend exposes the same
`plot`, so the import line is the only thing you change to switch:

    import pavement.matplotlib as pavement   # or .bokeh / .plotly / .holoviews
    pavement.plot([1, 2, 3, 4, 5])

`plot` accepts the same three input shapes on every backend — a single
dataset, a wide list of datasets, or tidy data plus `categories` — along
with `bins` (use `bins=None` for a rug), `weights`, `positions`,
`widths`, `labels`, and `orientation`. It returns that framework's native
object (matplotlib artists, a `bokeh.plotting.figure`, a
`plotly.graph_objects.Figure`, or a HoloViews element), so the result
drops straight into the rest of your workflow.

A rug (`bins=None`) drops the two long box edges by default, leaving just
the value ticks — so it reads like an ordinary rug plot, and the presence
of the box is a quick visual cue that you're looking at quantiles rather
than raw points. Pass `show_box=True` to keep the box on a rug (or
`show_box=False` to drop it from a binned plot); it is resolved per row,
so a mixed `bins` sequence gets the right default for each.

The backend-agnostic statistics live at the top level, with no plotting
dependency of their own:

    import pavement
    pavement.pavement_stats([1, 2, 3, 4, 5], bins=4)   # quantile cut points
    pavement.quantiles([1, 2, 3, 4, 5], [0.25, 0.5, 0.75])


## matplotlib (`pavement.matplotlib`)

The static backend draws pavements as matplotlib artists on an `Axes`:

    import pavement.matplotlib as pavement
    pavement.plot([1, 2, 3, 4, 5])

It also has three things specific to matplotlib: `plot2d` for 2D
pavements (a grid where every cell holds an equal share of the data),
`margin` for a single marginal strip — a richer drop-in for a rug plot —
placed just inside or outside any edge of an existing plot, and `spark`
for a borderless, word-sized image that drops inline into text:

    pavement.spark(values, path="spark.png")  # ![](spark.png) in your prose


## Inline sparklines (`pavement.svg`)

For sparklines on the web, `pavement.svg` emits a self-contained
`<svg>` string you can drop straight into HTML — no plotting library, no
JavaScript, no image files. It has no dependencies, so it ships with the
base install.

    import pavement.svg as pavement
    html = pavement.spark([1, 2, 3, 4, 5])      # an <svg>...</svg> string

The result is built for running text. Lines default to `currentColor`,
so a spark inherits the surrounding font color (dark mode included), and
it scales with the text (`height: 1em` by default) while staying crisp at
any size. Every equal-mass bin is a hover target carrying its quantile
band and value range as a native `<title>` tooltip — the same hover the
Bokeh and Plotly backends show — with a CSS `:hover` highlight, all
without a line of JavaScript. The bin or value line under the cursor
also highlights, so the interactivity is discoverable. A `bins=None` rug
makes each value hoverable when there are few of them, or shows a single
whole-spark summary when there are many (tunable with `tick_hover_limit`).
The tooltip values format through `value_format` like the other backends
(e.g. `value_format=lambda v: f"${v:,.2f}"`). Pass `color`, `orientation`,
or `path="spark.svg"` / `path="spark.html"` to save.

This is the web counterpart of `pavement.matplotlib.spark`, which renders
the same idea to a raster image for print.

Alongside `spark`, `pavement.svg` has two column-summary strips in the same
borderless form factor: `tally`, which shows how much of a column is
distinct, repeated, or missing, and `proportion`, which shows its value
counts (à la pandas `value_counts`) with a catch-all for a long tail. Both
take a column of any type and return an `<svg>` string like `spark` does.


## Dataframe summaries (`pavement.summary`)

`pavement.summary` turns a whole dataframe, Series, or sequence into one
inline HTML table — the thing to glance at when data first lands. Each
column becomes a row pairing its **tally** (how much is distinct, repeated, or
missing) with its **distribution**: a pavement spark for numeric columns and a
proportion strip for categorical ones, so every column gets a distribution
view where a pavement alone would leave the categorical rows blank. A
dataframe is topped by a row summarizing the frame itself — its row count and
a tally that treats each *whole row* as the entity, so "repeated" means a
duplicated row and "missing" a row that is entirely blank.

    import pavement
    pavement.summary(df)        # renders inline in a Jupyter cell

The result renders itself in Jupyter (via `_repr_html_`), so it appears on its
own when it's the last line of a cell. `summary` accepts a pandas `DataFrame`
or `Series`, a plain `dict` of columns (no pandas required), or any 1D
sequence. A numeric column's resolution adapts to its number of distinct
values — a rug when few, then 4, 8, or 16 equal-mass bins as it grows — so a
small column reads value-by-value and a large one as a smooth shape. Like the
rest of `pavement.svg` it is pure SVG with no dependencies and no JavaScript;
`str()` gives the HTML fragment and `path="summary.html"` saves a standalone
page. See `examples/summary_demo.py`.


## Interactive plots (Plotly)

`pavement.plotly` targets Plotly directly. It builds pavements from plain
`plotly.graph_objects` traces (no figure-level shapes), so a pavement
carries its own hover and drops into any subplot cell:

    import pavement.plotly as pavement
    pavement.plot([1, 2, 3, 4, 5]).show()

Every interactive backend formats the values it shows on hover the same
way: pass `value_format`, a function from a value to its display string,
and the hover renders through it. The one callable works unchanged on
Plotly, Bokeh, HoloViews, and `pavement.svg`, so `lambda v: f"${v:,.2f}"`
reads `1200.0` as `$1,200.00` everywhere (it defaults to three
significant figures). See `examples/value_format_demo.py`.

    pavement.plot(prices, value_format=lambda v: f"${v:,.2f}").show()

A pavement is a drop-in for a rug plot, including as a marginal:
`with_marginals` adjoins pavement strips to a scatter — x on top, y on
the right — in the spirit of Plotly's own
[marginal plots](https://plotly.com/python/marginal-plots/), keeping them
aligned with the scatter and matching its per-category colors:

    import plotly.express as px
    import pavement.plotly as pavement

    df = px.data.iris()
    fig = px.scatter(df, x="sepal_width", y="sepal_length", color="species")
    pavement.with_marginals(fig, x=df.sepal_width, y=df.sepal_length,
                            categories=df.species).show()

Install with `pip install pavement[plotly]`. See `examples/plotly_demo.py`.


## Interactive plots (Bokeh)

`pavement.bokeh` draws pavements with plain Bokeh glyphs (filled `quad`s
for the bins, `segment`s for the ticks and box edges), so each row
carries its own hover and drops onto any figure:

    import pavement.bokeh as pavement
    from bokeh.plotting import show

    show(pavement.plot([1, 2, 3, 4, 5]))

It returns a plain `bokeh.plotting.figure`, with a hover tool over the
bins and ticks and a clickable legend for multiple rows. As with the
other backends, `with_marginals` arranges a scatter with pavement strips
— x on top, y on the right — with their ranges linked to the scatter and
matching its per-category colors:

    from bokeh.plotting import figure
    import pavement.bokeh as pavement

    scatter = figure()
    for g in ["A", "B"]:
        scatter.scatter(xs[g], ys[g], color=palette[g], name=g)
    show(pavement.with_marginals(scatter, x=xs_all, y=ys_all, categories=groups))

Install with `pip install pavement[bokeh]`. See `examples/bokeh_demo.py`.


## Interactive plots (HoloViews)

`pavement.holoviews` builds the same pavement geometry as HoloViews
elements, so one definition renders through any HoloViews backend
(`bokeh` or `plotly` for interactivity, `matplotlib` for a static image).
Select the backend with `hv.extension(...)` first, as usual:

    import holoviews as hv
    import pavement.holoviews as pavement

    hv.extension("bokeh")
    pavement.plot([1, 2, 3, 4, 5])

It returns a plain HoloViews object, so it composes with the framework.
`with_marginals` adjoins category-split pavement marginals to a scatter
in one call:

    pavement.with_marginals(scatter, x=xs, y=ys, categories=groups)

Install with `pip install pavement[holoviews]` (plus `bokeh` and/or
`plotly`). See `examples/holoviews_demo.py`.


## Using pavement with Claude

This repo ships a [Claude Code](https://code.claude.com/docs) plugin that
teaches Claude to use pavement correctly — which backend to import, the
three `plot` input shapes, and the idioms that are easy to get wrong from
memory (`bins=None` rugs, the per-row `show_box` default, `value_format`).

Add this repo as a plugin marketplace and install it:

    /plugin marketplace add ajschumacher/pavement
    /plugin install pavement-plots@pavement

Once installed, Claude consults the skill automatically whenever you ask
it to make a pavement plot or sparkline. To try it without installing —
or when working in a clone of this repo — load it directly for one
session:

    claude --plugin-dir ./plugins/pavement-plots

The skill itself is plain Markdown at
`plugins/pavement-plots/skills/pavement-plots/`, so you can read or adapt
it without Claude Code.


## Development

    pip install -e '.[test]'              # core only
    pip install -e '.[test,matplotlib]'   # + matplotlib
    pip install -e '.[test,all]'          # + every backend
    pytest
