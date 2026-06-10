# API Reference

Every rendering backend exposes the same `plot`, so switching canvases is a
one-line import change. The backend-agnostic statistics and the column
summaries live at the top level with no plotting dependency.

!!! tip "One API, many canvases"
    ```python
    import pavement.matplotlib as pavement   # or .bokeh / .plotly / .holoviews
    pavement.plot([1, 2, 3, 4, 5])
    ```

    `pavement.svg` is the one exception: it draws single-row sparklines
    (`spark`), not multi-row `plot`s.

## Top-level package (`pavement`)

The package root re-exports the pure-Python statistics and the headline
`summary` entry point — no backend required.

::: pavement.core
    options:
      members:
        - quantiles
        - pavement_stats
        - pavement_stats2d
        - tally_stats
        - proportion_stats

## Static plots (`pavement.matplotlib`)

::: pavement.matplotlib

## Inline SVG sparklines (`pavement.svg`)

Self-contained `<svg>` strings — no plotting library, no JavaScript. This is
where `summary`, `spark`, `tally`, and `proportion` live.

::: pavement.svg

## Interactive — Plotly (`pavement.plotly`)

::: pavement.plotly

## Interactive — Bokeh (`pavement.bokeh`)

::: pavement.bokeh

## Interactive — HoloViews (`pavement.holoviews`)

::: pavement.holoviews

## pandas integration (`pavement.pandas`)

Importing this module registers the `.pave` accessor on pandas `DataFrame`
and `Series`.

::: pavement.pandas

## polars integration (`pavement.polars`)

Importing this module registers the `.pave` namespace on polars `DataFrame`
and `Series`.

::: pavement.polars
