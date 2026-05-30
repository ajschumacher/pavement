# Pavement plots

[![PyPI](https://img.shields.io/pypi/v/pavement.svg)](https://pypi.org/project/pavement/)
[![CI](https://github.com/ajschumacher/pavement/actions/workflows/ci.yml/badge.svg)](https://github.com/ajschumacher/pavement/actions/workflows/ci.yml)

Quantile-based pavement plots with matplotlib. Every box contains an
equal share of the data.

![plot of four data sets](https://raw.githubusercontent.com/ajschumacher/pavement/main/examples/four_sets.png)

See more in the [demo notebook](https://github.com/ajschumacher/pavement/blob/main/examples/demo.ipynb).


## Install

    pip install pavement


## Usage

    import pavement
    pavement.plot([1, 2, 3, 4, 5])


## Interactive plots (HoloViews)

For interactive, hoverable pavements that render through the bokeh or
plotly backends (as well as matplotlib), use the `pavement.holoviews`
module:

    import holoviews as hv
    import pavement.holoviews as phv

    hv.extension("bokeh")
    phv.pavement([1, 2, 3, 4, 5])

It mirrors `pavement.plot` (single, wide, or tidy `categories` input,
`bins=None` for a rug, per-row bins, orientation) and returns a plain
HoloViews object, so it composes with the framework. `with_marginals`
adjoins category-split pavement marginals to a scatter in one call:

    phv.with_marginals(scatter, x=xs, y=ys, categories=groups)

Install the optional dependency with `pip install pavement[holoviews]`
(plus `bokeh` and/or `plotly`). See `examples/holoviews_demo.py`.


## Interactive plots (Plotly)

To work directly in Plotly, use the `pavement.plotly` module. It builds
pavements from plain `plotly.graph_objects` traces (no figure-level
shapes), so a pavement carries its own hover and drops into any subplot
cell:

    import pavement.plotly as ppl

    ppl.pavement([1, 2, 3, 4, 5]).show()

It mirrors `pavement.plot` (single, wide, or tidy `categories` input,
`bins=None` for a rug, per-row bins, orientation) and returns a plain
`plotly.graph_objects.Figure`. A pavement is a drop-in for a rug plot,
including as a marginal: `with_marginals` adjoins pavement strips to a
scatter — x on top, y on the right — in the spirit of Plotly's own
[marginal plots](https://plotly.com/python/marginal-plots/), keeping
them aligned with the scatter and matching its per-category colors:

    import plotly.express as px

    df = px.data.iris()
    fig = px.scatter(df, x="sepal_width", y="sepal_length", color="species")
    ppl.with_marginals(fig, x=df.sepal_width, y=df.sepal_length,
                       categories=df.species).show()

Install the optional dependency with `pip install pavement[plotly]`. See
`examples/plotly_demo.py`.


## Interactive plots (Bokeh)

To work directly in Bokeh, use the `pavement.bokeh` module. It draws
pavements with plain Bokeh glyphs (filled `quad`s for the bins, `segment`s
for the ticks and box edges), so each row carries its own hover and drops
onto any figure:

    import pavement.bokeh as pbk
    from bokeh.plotting import show

    show(pbk.pavement([1, 2, 3, 4, 5]))

It mirrors `pavement.plot` (single, wide, or tidy `categories` input,
`bins=None` for a rug, per-row bins, orientation) and returns a plain
`bokeh.plotting.figure`, with a hover tool over the bins and ticks and a
clickable legend for multiple rows. A pavement is a drop-in for a rug plot,
including as a marginal: `with_marginals` arranges a scatter with pavement
strips — x on top, y on the right — with their ranges linked to the scatter
and matching its per-category colors:

    from bokeh.plotting import figure

    scatter = figure()
    for g in ["A", "B"]:
        scatter.scatter(xs[g], ys[g], color=palette[g], name=g)
    show(pbk.with_marginals(scatter, x=xs_all, y=ys_all, categories=groups))

Install the optional dependency with `pip install pavement[bokeh]`. See
`examples/bokeh_demo.py`.


## Development

    pip install -e '.[test]'
    pytest
