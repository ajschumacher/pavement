# Examples

These are the **actual outputs** of the scripts in
[`examples/`](https://github.com/ajschumacher/pavement/tree/main/examples),
embedded live. The interactive plots are fully interactive — hover for the
quantile tooltips, pan, zoom, and toggle legends right on the page.

!!! info "Self-contained"
    Each frame is a standalone HTML file. The inline-SVG and summary examples
    use no JavaScript and no plotting dependency at all.

## Inline SVG sparklines — `pavement.svg`

Dependency-free `<svg>` sparks that inherit the surrounding text color and carry
their quantile tooltips with pure CSS — no JavaScript. Hover the bins. This page
also shows the `tally` and `proportion` column strips.

[:octicons-file-code-16: svg_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/svg_demo.py)
· [:octicons-link-external-16: view standalone](examples/assets/svg_demo.html)

<iframe class="example-frame" src="assets/svg_demo.html" style="height: 620px;"></iframe>

## Whole-dataframe summary — `pavement.summary`

One glanceable table over a mixed dataframe: a tally (distinct / duplicate /
missing) paired with a distribution per column.

[:octicons-file-code-16: summary_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/summary_demo.py)
· [:octicons-link-external-16: view standalone](examples/assets/summary_demo.html)

<iframe class="example-frame" src="assets/summary_demo.html" style="height: 720px;"></iframe>

## DataFrame view — column profiles in the header

A table where each column header stacks the column name, a tally strip, and a
distribution strip — a SQL-client–style preview of a result set with column
statistics built right into the header. Numeric and date columns get a pavement
spark; categorical columns get a proportion strip.

[:octicons-file-code-16: dataframe_view_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/dataframe_view_demo.py)
· [:octicons-link-external-16: view standalone](examples/assets/dataframe_view_demo.html)

<iframe class="example-frame" src="assets/dataframe_view_demo.html" style="height: 620px;"></iframe>

## The `.pave` accessor — pandas & polars

Importing `pavement.pandas` / `pavement.polars` registers a `.pave` accessor, so
the summary and the column strips are a method away on any frame or series.

[:octicons-file-code-16: pandas_polars_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/pandas_polars_demo.py)
· [:octicons-link-external-16: view standalone](examples/assets/pandas_polars_demo.html)

<iframe class="example-frame" src="assets/pandas_polars_demo.html" style="height: 700px;"></iframe>

## Value formatting & box edges

How `value_format` controls hover text across backends, and how box edges read on
binned plots versus rugs.

[:octicons-file-code-16: value_format_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/value_format_demo.py)
· [:octicons-link-external-16: view standalone](examples/assets/value_format_demo.html)

<iframe class="example-frame" src="assets/value_format_demo.html" style="height: 620px;"></iframe>

[:octicons-file-code-16: box_edges_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/box_edges_demo.py)
· [:octicons-link-external-16: view standalone](examples/assets/box_edges_demo.html)

<iframe class="example-frame" src="assets/box_edges_demo.html" style="height: 620px;"></iframe>

## Interactive — Plotly, Bokeh & HoloViews

The same pavements across every interactive backend: single rows, rugs,
category-split rows, and scatters with pavement marginals. Hover for the quantile
tooltips, pan, zoom, and toggle the legends.

[:octicons-file-code-16: interactive_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/interactive_demo.py)
· [:octicons-link-external-16: view standalone](examples/assets/interactive_demo.html)

<iframe class="example-frame" src="assets/interactive_demo.html" style="height: 900px;"></iframe>
