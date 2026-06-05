# Examples

These are the **actual outputs** of the scripts in
[`examples/`](https://github.com/ajschumacher/pavement/tree/main/examples),
embedded live. The interactive plots below are fully interactive — hover for the
quantile tooltips, pan, zoom, and toggle legends right on the page.

!!! info "Self-contained"
    Each frame is a standalone HTML file. The inline-SVG and summary examples
    use no JavaScript and no plotting dependency at all.

## Inline SVG sparklines — `pavement.svg`

Dependency-free `<svg>` sparks that inherit the surrounding text color and carry
their quantile tooltips with pure CSS — no JavaScript. Hover the bins.

[:octicons-file-code-16: svg_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/svg_demo.py)

<iframe class="example-frame" src="assets/svg_demo.html" style="height: 620px;"></iframe>

## Whole-dataframe summary — `pavement.summary`

One glanceable table over a mixed dataframe: a tally (distinct / duplicate /
missing) paired with a distribution per column.

[:octicons-file-code-16: summary_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/summary_demo.py)

<iframe class="example-frame" src="assets/summary_demo.html" style="height: 720px;"></iframe>

## Column-summary strips — `tally` & `proportion`

The two borderless column strips that compose into `summary`.

[:octicons-file-code-16: column_summary_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/column_summary_demo.py)

<iframe class="example-frame" src="assets/column_summary_demo.html" style="height: 620px;"></iframe>

## Value formatting & box edges

How `value_format` controls hover text across backends, and how box edges read on
binned plots versus rugs.

[:octicons-file-code-16: value_format_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/value_format_demo.py)
· [:octicons-file-code-16: box_edges_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/box_edges_demo.py)

<iframe class="example-frame" src="assets/value_format_demo.html" style="height: 620px;"></iframe>

<iframe class="example-frame" src="assets/box_edges_demo.html" style="height: 620px;"></iframe>

## Interactive — Plotly

[:octicons-file-code-16: plotly_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/plotly_demo.py)

A single pavement, a rug, category-split rows, and a scatter with pavement
marginals:

<iframe class="example-frame" src="assets/plotly_single.html" style="height: 420px;"></iframe>

<iframe class="example-frame" src="assets/plotly_rug.html" style="height: 420px;"></iframe>

<iframe class="example-frame" src="assets/plotly_categories.html" style="height: 460px;"></iframe>

<iframe class="example-frame" src="assets/plotly_marginals.html" style="height: 560px;"></iframe>

## Interactive — Bokeh

[:octicons-file-code-16: bokeh_demo.py](https://github.com/ajschumacher/pavement/blob/main/examples/bokeh_demo.py)

The same shapes drawn with native Bokeh glyphs, hover tool and clickable legend
included:

<iframe class="example-frame" src="assets/bokeh_single.html" style="height: 420px;"></iframe>

<iframe class="example-frame" src="assets/bokeh_rug.html" style="height: 420px;"></iframe>

<iframe class="example-frame" src="assets/bokeh_categories.html" style="height: 460px;"></iframe>

<iframe class="example-frame" src="assets/bokeh_marginals.html" style="height: 620px;"></iframe>
