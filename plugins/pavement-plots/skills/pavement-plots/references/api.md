# pavement API reference

Full parameter lists for every public function. Defaults shown. Read the section for the
function you're calling; the common `plot` parameters are shared across backends.

## Table of contents
- [`plot` (all backends)](#plot-all-backends)
- [matplotlib-only: `plot2d`, `margin`, `spark`](#matplotlib-only)
- [`pavement.svg`: `spark`, `tally`, `proportion`, `summary`](#pavementsvg)
- [`pavement.pandas`: the `.pave` accessor + `enable_repr`](#pavementpandas)
- [Interactive builders: `with_marginals`, `pavement_traces`/`glyphs`/`elements`, `add_pavement`](#interactive-builders)
- [Statistics (top level)](#statistics-top-level)

## `plot` (all backends)

Shared core parameters (present on matplotlib, plotly, bokeh, holoviews):

- `data` — one dataset, a wide list of datasets, or (with `categories`) one flat list.
- `weights=None` — weights mirroring the shape of `data` (weighted quantiles).
- `positions=None` — numeric position of each row.
- `categories=None` — tidy grouping: one row per distinct category of a flat `data`.
- `labels=None` — label per row.
- `bins=4` — int (equal-mass bins), `None` (rug), or a sequence for per-row control.
- `widths=0.6` — row thickness; scalar or per-row sequence.
- `whisker_extent=0.1`, `show_whiskers=True` — whisker length / visibility.
- `show_box=None` — resolved per row: defaults to box on for binned, off for `bins=None`
  rug. Pass `True`/`False` to override.
- `orientation="vertical"` — or `"horizontal"`.
- `color=None` — scalar or per-row.
- `fill_alpha=0.3`.

matplotlib `plot` also has: `value_label=None`, `line_props=None`, `box_props=None`,
`ax=None`. Returns a list of dicts (one per row) of the artists drawn.

Interactive backends (plotly/bokeh/holoviews) `plot` also accept `value_format=None`
(a `value -> str` callable for hover text; defaults to 3 sig figs) and backend-specific
styling. They return the native figure/element.

## matplotlib-only

```python
import pavement.matplotlib as pavement
```

### `plot2d(x, y, weights=None, bins=4, x_bins=None, y_bins=None, first_split="x", line_props=None, box_props=None, ax=None)`
A 2D pavement: a grid where every cell holds an equal share of the data. `first_split`
chooses whether the first equal-mass cut is along x or y; `x_bins`/`y_bins` override `bins`
per axis. Returns a dict of artists.

### `margin(data, axis="x", where=None, bins=4, weights=None, pad=0.03, size=0.04, expand_margins=True, show_whiskers=True, show_box=None, line_props=None, box_props=None, clip_on=False, ax=None)`
A single marginal pavement strip just inside or outside an edge of an existing plot — a
richer drop-in for a rug. `axis="x"|"y"`, `where` picks the edge (e.g. `"top"`,
`"bottom"`, `"left"`, `"right"`).

### `spark(data, weights=None, bins=4, orientation="horizontal", width=0.6, whisker_extent=0.1, show_whiskers=True, show_box=None, color=None, fill_alpha=0.3, line_props=None, box_props=None, figsize=None, dpi=200, pad=0.0, transparent=True, path=None)`
A borderless, word-sized raster image for inline use. Pass `path="spark.png"` to save;
returns the matplotlib `Figure`. (Web counterpart: `pavement.svg.spark`.)

## `pavement.svg`

```python
import pavement.svg as pavement
```
`spark`, `tally`, and `proportion` each return a self-contained `<svg>...</svg>` **string**
(no dependencies, no JS). Common kwargs: `orientation="horizontal"`, `height="1em"`,
`inline=True`, `hover=True`, `highlight=True`, `class_=...`, `path=None` (save to
`.svg`/`.html`). `summary` returns a `Summary` object (an HTML table that renders inline
in Jupyter), not a string.

### `spark(data, weights=None, bins=4, orientation="horizontal", width=0.6, whisker_extent=0.1, show_whiskers=True, show_box=None, color=None, fill_alpha=0.3, line_color=None, line_width=1.2, height="1em", inline=True, hover=True, value_format=None, tick_hover_limit=24, highlight=True, class_="pavement-spark", path=None)`
Numeric sparkline. Defaults to `currentColor`, scales with text. `value_format` formats
tooltip values (same callable as the interactive backends). `bins=None` makes a rug where
each value is hoverable when few, or a single summary when many (`tick_hover_limit`).

### `tally(data, orientation="horizontal", distinct_color=..., repeated_color=..., missing_color=..., line_color=None, line_width=1.0, min_box=3.0, height="1em", inline=True, hover=True, highlight=True, class_="pavement-tally", path=None)`
Categorical strip over raw values: distinct vs repeated vs missing. `data` is any iterable
of values (strings, etc.).

### `proportion(data, orientation="horizontal", colors=..., other_color=..., max_boxes=12, min_box=3.0, catchall_tolerance=0.1, value_crop=128, line_color=None, line_width=1.0, height="1em", inline=True, hover=True, highlight=True, class_="pavement-proportion", path=None)`
Proportion-of-each-category strip; the top `max_boxes` categories plus an "other" catch-all.

`tally` also takes `noun="entry"` — the singular noun for its tooltips/aria-label
(pluralized for display, e.g. `entry`→`entries`). It defaults to `"entry"`, not `"value"`,
because the count includes missing entries (which aren't values); `summary` passes `"row"`
for its whole-frame tally.

### `summary(data, color=..., height="1.6em", hover=True, highlight=True, class_="pavement-summary", path=None)`
A whole-dataframe / Series / sequence summary as one HTML `<table>`: a row per column
pairing its `tally` with its distribution — a `spark` for numeric columns, a `proportion`
for categorical. A dataframe adds a top row for the frame itself (its row count and a tally
over *whole rows*, where "missing" is an all-blank row). `data` may be a pandas
`DataFrame`/`Series`, a `dict` of column name → values, or a 1D sequence. Returns a
`Summary` that renders inline in Jupyter (`_repr_html_`); `str()` gives the HTML fragment,
`path="summary.html"` saves a standalone page. Also re-exported as top-level
`pavement.summary`. A numeric column's resolution auto-scales by distinct-value count: a
rug (≤24), then 4, 8 (>96), and 16 (>384) equal-mass bins. `color` tints the numeric sparks.

## `pavement.pandas`

```python
import pavement.pandas    # needs pandas; registers the .pave accessor on import
```

Importing the module registers a `.pave` accessor on pandas `DataFrame` and `Series` (via
pandas' `register_*_accessor`, so it's namespaced). Activates on this import only, never on
a bare `import pavement`.

- `df.pave(**kw)` and `df.pave.summary(**kw)` → `pavement.summary(df, **kw)` (a `Summary`).
- `df.pave.spark(col, **kw)` → a numeric column's `spark` (missing values dropped first).
- `df.pave.tally(col, **kw)` → a column's `tally`. `df.pave.proportion(col, **kw)` → its `proportion`.
- On a Series the helpers take no column: `s.pave()`, `s.pave.spark()`, `s.pave.tally()`, `s.pave.proportion()`.

The single-column helpers return the glyph's `<svg>` string wrapped in a `str` subclass, so
it renders inline in Jupyter yet still behaves as the plain string (embed/save) elsewhere.

### `enable_repr(series=True, **summary_kwargs)` / `disable_repr()`
Register/unregister an IPython HTML formatter so every `DataFrame` (and, unless
`series=False`, every `Series`) displays as its `pavement.summary` in the notebook —
**replacing** the normal data-table preview (opt-in). `summary_kwargs` (e.g. `height`,
`color`) are forwarded. Raises `RuntimeError` outside a running IPython/Jupyter session.

## Interactive builders

Each of plotly/bokeh/holoviews exposes, besides `plot`:

### `with_marginals(main, x=None, y=None, categories=None, ...)`
Adjoins pavement marginal strips to a scatter — x on top, y on the right — aligned and
color-matched to the scatter's per-category colors. `main` is the existing figure
(`go.Figure` / `bokeh figure` / holoviews scatter). Returns the composed figure/layout.

### Lower-level builders
- plotly: `pavement_traces(...)` -> traces; `add_pavement(fig, ...)` adds onto a figure.
- bokeh: `pavement_glyphs(...)`; `add_pavement(fig, ...)`.
- holoviews: `pavement_elements(...)`.

Use these to compose a pavement onto an existing figure/subplot rather than getting a
standalone one from `plot`.

## Statistics (top level)

```python
import pavement
pavement.quantiles(data, probs)            # quantiles at the given probabilities
pavement.pavement_stats(data, bins=4)      # equal-mass bin cut points / per-bin stats
pavement.pavement_stats2d(x, y, bins=4)    # 2D equal-mass grid stats
```
No plotting dependency. Use for the raw numbers or a custom renderer.
