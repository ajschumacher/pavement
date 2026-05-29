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


## Development

    pip install -e '.[test]'
    pytest
