---
name: pavement-plots
description: >-
  Use this skill whenever you write Python that uses the `pavement` library (the
  `pavement` PyPI package) — quantile-based "pavement" plots where every box holds an
  equal share of the data, a boxplot alternative that shows the whole distribution.
  Trigger it for any request to make a pavement plot, a quantile/equal-mass distribution
  plot, an inline SVG or raster sparkline, a 2D pavement, or a rug/marginal strip, across
  the matplotlib, Bokeh, Plotly, HoloViews, or dependency-free SVG backends. Use it even
  when the user just says "pavement plot", imports `pavement.matplotlib`/`.bokeh`/
  `.plotly`/`.holoviews`/`.svg`, or asks for `spark`, `plot2d`, `margin`, `with_marginals`,
  `tally`, `proportion`, `summary` (an inline dataframe summary), or the pandas `.pave`
  accessor — these are pavement-specific APIs that are easy to get subtly wrong from
  memory, so consult this skill rather than guessing the call shape.
---

# pavement plots

`pavement` draws **quantile-based pavement plots**: a box is cut into bins where
**every bin holds an equal share of the data**, so a bin is wide where data is sparse
and narrow where it's dense. It's a boxplot alternative that shows the whole shape of a
distribution. The core statistics are pure Python; each rendering backend is an optional
dependency.

## The one thing to know first

**You pick a backend by importing its submodule, and they all expose the same `plot`.**
The import line is the only thing that changes between backends:

```python
import pavement.matplotlib as pavement   # or .bokeh / .plotly / .holoviews
pavement.plot([1, 2, 3, 4, 5])
```

So the idiomatic pattern is `import pavement.<backend> as pavement`, then call
`pavement.plot(...)`. Don't reach for a top-level `pavement.plot` — the top level only
holds the backend-agnostic statistics (see [Statistics only](#statistics-without-plotting)).

## Choosing a backend

Match the backend to where the plot will live. When unsure, ask; otherwise default to
matplotlib for scripts/notebooks and `pavement.svg` for anything going into HTML/Markdown.

| Backend | Import | Use for | Install |
|---|---|---|---|
| matplotlib | `pavement.matplotlib` | static figures, papers, notebooks; also `plot2d`, `margin`, raster `spark` | `pavement[matplotlib]` |
| Plotly | `pavement.plotly` | interactive web plots (hover/zoom), Dash | `pavement[plotly]` |
| Bokeh | `pavement.bokeh` | interactive web plots, Bokeh apps | `pavement[bokeh]` |
| HoloViews | `pavement.holoviews` | backend-agnostic elements that render through bokeh/plotly/matplotlib | `pavement[holoviews]` |
| SVG | `pavement.svg` | **inline sparklines in HTML/Markdown — no dependencies, always installed** | (none) |

`plot` returns that framework's native object — matplotlib artists (a list of dicts),
a `bokeh.plotting.figure`, a `plotly.graph_objects.Figure`, or a HoloViews element — so
the result drops straight into the rest of that framework's workflow (e.g. `.show()` on
Plotly, `bokeh.plotting.show(...)` on Bokeh).

## The three input shapes for `plot`

`plot` accepts the same three shapes on every backend. This is the most common thing to
get wrong, so match the user's data to one of these:

```python
# 1. One dataset -> one pavement row
pavement.plot([1, 2, 3, 4, 5])

# 2. A "wide" list of datasets -> one row each
pavement.plot([[1, 2, 3], [4, 5, 6, 7], [2, 2, 9]])

# 3. Tidy data: one flat list of values + matching categories
pavement.plot(values, categories=groups)   # one row per distinct category
```

Shape 3 (`categories=`) is the right choice for a DataFrame column split by a grouping
column — pass `df["value"]` and `categories=df["group"]`, not a manual groupby.

## Idioms and gotchas

These are the things worth getting right; they're shared across backends.

- **`bins` controls the cut.** Default `bins=4` (quartiles). More bins = finer detail.
  `bins=None` makes a **rug** (individual value ticks, no equal-mass binning). `bins` may
  also be a sequence to set it per row.
- **`bins=None` drops the long box edges by default**, so it reads like an ordinary rug.
  The box's presence is the visual cue that you're looking at quantiles. `show_box` flips
  per row: pass `show_box=True` to keep the box on a rug, `show_box=False` to drop it from
  a binned plot.
- **`orientation="horizontal"`** lays rows out horizontally (default `"vertical"`).
- **`weights`** mirrors the shape of `data` for weighted quantiles.
- **`positions`, `widths`, `labels`** place, size, and name the rows.
- **`value_format`** (interactive backends + svg) formats hover/tooltip values — one
  callable `value -> str` that works unchanged on Plotly, Bokeh, HoloViews, and svg:
  `value_format=lambda v: f"${v:,.2f}"`. Defaults to three significant figures.

For the full parameter list of any function, read
[references/api.md](references/api.md) rather than guessing.

## Backend-specific extras

Only some backends add functions beyond `plot`. Don't assume a helper exists on a backend
that doesn't have it (e.g. there is no `plot2d` on Plotly).

**matplotlib** adds three:
```python
import pavement.matplotlib as pavement
pavement.plot2d(x, y, bins=4)               # 2D grid; every cell = equal share of data
pavement.margin(values, axis="x", where="top")  # a marginal strip on an existing Axes
pavement.spark(values, path="spark.png")    # word-sized borderless raster image
```

**`pavement.svg`** is for HTML/Markdown and adds string-returning glyphs (no files, no JS):
```python
import pavement.svg as pavement
html = pavement.spark([1, 2, 3, 4, 5])      # returns an "<svg>...</svg>" string
html = pavement.tally(["a", "a", "b", None]) # distinct/duplicate/missing strip
html = pavement.proportion(category_labels)  # value-counts strip (à la value_counts)
pavement.summary(df)                          # whole-dataframe summary table
```
`spark` defaults to `currentColor` (inherits text color, dark-mode friendly) and
`height="1em"` (scales with text). Each equal-mass bin is a hover target with a native
`<title>` tooltip. Pass `path="spark.svg"`/`"spark.html"` to save.

`summary(data)` is the headline data-summary call (also re-exported as top-level
`pavement.summary`): it returns a one-row-per-column HTML table pairing each column's
`tally` with its distribution (a `spark` for numeric columns, a `proportion` for
categorical), plus a top row summarizing the whole frame (row count + a whole-row tally).
It accepts a pandas `DataFrame`/`Series`, a `dict` of columns, or a 1D sequence, and
renders inline in Jupyter (it returns a `Summary` with `_repr_html_`; `str()` is the HTML).

For pandas or polars, prefer the accessor: `import pavement.pandas` (or
`import pavement.polars`) registers `.pave` on `DataFrame`/`Series`, so `df.pave()` is the
summary, `df.pave.summary()` the same, and `df.pave.spark("col")` / `.tally("col")` /
`.proportion("col")` give a single column's strip (a Series' helpers take no column name).
`pavement.pandas.enable_repr()` / `disable_repr()` make the summary a frame's default
inline display (opt-in; it replaces the data table). The accessor activates on its own
import (`pavement.pandas` / `pavement.polars`), like `import hvplot.pandas` — never on a
bare `import pavement`. `pavement.summary(df)` itself also takes a pandas or polars frame
directly.

**Plotly, Bokeh, HoloViews** each add `with_marginals(...)`, which adjoins pavement
strips to a scatter (x on top, y on the right) — a richer rug, color-matched to the
scatter's categories:
```python
import pavement.plotly as pavement
pavement.with_marginals(fig, x=df.sepal_width, y=df.sepal_length, categories=df.species)
```
They also expose lower-level builders (`pavement_traces`/`pavement_glyphs`/
`pavement_elements` and `add_pavement`) for composing onto an existing figure.

## Statistics without plotting

The top-level package has the backend-agnostic numbers with **no plotting dependency**:

```python
import pavement
pavement.pavement_stats([1, 2, 3, 4, 5], bins=4)   # the quantile cut points / bin stats
pavement.quantiles([1, 2, 3, 4, 5], [0.25, 0.5, 0.75])
pavement.pavement_stats2d(x, y, bins=4)            # 2D version
```

Use these when the user wants the underlying quantile numbers, or to build a custom
renderer — not a chart.

## Install

The core is dependency-free (`pip install pavement`). Each backend is an extra:
`pip install pavement[matplotlib]` (or `bokeh`, `plotly`, `holoviews`, or `all`).
`pavement.svg` needs nothing extra. If a user's import fails, the missing extra is
almost always the cause.
