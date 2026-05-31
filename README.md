# Pavement plots

[![PyPI](https://img.shields.io/pypi/v/pavement.svg)](https://pypi.org/project/pavement/)
[![CI](https://github.com/ajschumacher/pavement/actions/workflows/ci.yml/badge.svg)](https://github.com/ajschumacher/pavement/actions/workflows/ci.yml)

Quantile-based pavement plots: every box contains an equal share of the
data. One plot, four drawing backends — matplotlib, Bokeh, Plotly, and
HoloViews — behind a single shared API.

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


## Interactive plots (Plotly)

`pavement.plotly` targets Plotly directly. It builds pavements from plain
`plotly.graph_objects` traces (no figure-level shapes), so a pavement
carries its own hover and drops into any subplot cell:

    import pavement.plotly as pavement
    pavement.plot([1, 2, 3, 4, 5]).show()

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


## Development

    pip install -e '.[test]'              # core only
    pip install -e '.[test,matplotlib]'   # + matplotlib
    pip install -e '.[test,all]'          # + every backend
    pytest
