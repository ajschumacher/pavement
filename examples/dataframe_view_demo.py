"""
Demo of a "smart header" DataFrame view: a table where each column
header stacks the column name, a tally strip (distinct / duplicate /
missing), and a distribution strip (pavement spark or proportion) —
an at-a-glance column profile right in the header, the way a SQL client
or BI tool might show when previewing a query result set.

Numeric and date columns get a pavement **spark** (frequency rug for
small or discrete columns; equal-mass bins for larger ones). Categorical
columns get a **proportion** strip. The ``notes`` column — 75 % missing —
shows what a data-quality flag looks like in the tally.

Run with no extra dependencies beyond the base install::

    python examples/dataframe_view_demo.py

It writes ``dataframe_view_demo.html`` to the current directory;
open it and hover the strips.
"""

import datetime
import html as _html
import random

from pavement.core import _is_missing
from pavement.svg import (
    _TALLY_DISTINCT,
    _distribution_strip,
    _tally_strip,
)

rng = random.Random(42)
N = 150

# ---------------------------------------------------------------------------
# Simulated SQL result set — a transactions table
# ---------------------------------------------------------------------------
_PRODUCTS = [
    ("Laptop Pro",                 "Electronics"),
    ("Mechanical Keyboard",        "Electronics"),
    ("Wireless Mouse",             "Electronics"),
    ("27-inch Monitor",            "Electronics"),
    ("Noise-Cancelling Headphones","Electronics"),
    ("USB-C Hub",                  "Electronics"),
    ("Webcam HD",                  "Electronics"),
    ("External SSD 1TB",           "Electronics"),
    ("Desk Lamp LED",              "Office"),
    ("Notebook A5",                "Office"),
    ("Pen Set 12pk",               "Office"),
    ("Stapler Heavy-Duty",         "Office"),
    ("Ergonomic Chair",            "Furniture"),
    ("Standing Desk Converter",    "Furniture"),
    ("Monitor Arm",                "Furniture"),
]
_STATUSES = (["completed"] * 7 + ["pending"] * 3
             + ["refunded"] * 2 + ["failed"] * 1)
_NOTES = [
    "Rush delivery",
    "Gift wrap requested",
    "Corporate account",
    "Return requested",
    "VIP customer",
    "Fragile items",
]

_chosen = [rng.choice(_PRODUCTS) for _ in range(N)]

data = {
    "transaction_id": list(range(10_001, 10_001 + N)),
    "customer_id":    [rng.randint(1, 50) for _ in range(N)],
    "product":        [p for p, _ in _chosen],
    "category":       [c for _, c in _chosen],
    "amount":         [round(rng.lognormvariate(3.5, 0.8), 2) for _ in range(N)],
    "quantity":       [rng.choices(range(1, 9),
                                   weights=[40, 22, 14, 9, 6, 4, 3, 2])[0]
                       for _ in range(N)],
    "date":           [datetime.date(2024, 1, 1)
                       + datetime.timedelta(days=rng.randint(0, 364))
                       for _ in range(N)],
    "status":         [rng.choice(_STATUSES) for _ in range(N)],
    "discount_pct":   [0.0 if rng.random() < 0.58
                       else float(rng.choice([5, 10, 15, 20, 25, 30]))
                       for _ in range(N)],
    "notes":          [None if rng.random() < 0.75
                       else rng.choice(_NOTES)
                       for _ in range(N)],
}

# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------
_TALLY_OPTS = {'height': '0.85em', 'hover': True, 'highlight': True}
_DIST_OPTS  = {'height': '1.8em',  'hover': True, 'highlight': True}


def _fill_width(svg: str) -> str:
    """Patch a strip SVG's CSS width from ``auto`` to ``100%``."""
    return svg.replace('width:auto;', 'width:100%;', 1)


def _col_header(name: str, values: list) -> str:
    """One <th> with the column name, tally, and distribution stacked."""
    present = [v for v in values if not _is_missing(v)]
    t_svg = _fill_width(_tally_strip(values, 'entry', _TALLY_OPTS))
    d_svg = _fill_width(
        _distribution_strip(values, present, _TALLY_DISTINCT, _DIST_OPTS))
    d_block = (f'<div style="margin-top:.15em;">{d_svg}</div>'
               if d_svg else '')
    return (
        f'<th class="dfv-th">'
        f'<div class="dfv-name">{_html.escape(str(name))}</div>'
        f'<div style="margin-top:.2em;">{t_svg}</div>'
        f'{d_block}'
        f'</th>'
    )


def _fmt(value) -> str:
    if _is_missing(value):
        return '<span class="dfv-null">—</span>'
    if isinstance(value, float):
        return f'{value:,.2f}'
    if isinstance(value, datetime.date):
        return value.isoformat()
    return _html.escape(str(value))


_names   = list(data.keys())
_columns = list(data.values())
_n_rows  = len(_columns[0])

_header = (
    '<thead><tr>'
    + ''.join(_col_header(n, c) for n, c in zip(_names, _columns))
    + '</tr></thead>'
)
_body = (
    '<tbody>'
    + ''.join(
        '<tr>'
        + ''.join(
            f'<td class="dfv-td{"0" if j == 0 else ""}">{_fmt(col[i])}</td>'
            for j, col in enumerate(_columns)
        )
        + '</tr>'
        for i in range(_n_rows)
    )
    + '</tbody>'
)

_TABLE = (
    '<div class="dfv-wrap">'
    '<table class="dfv">'
    f'{_header}{_body}'
    '</table></div>'
)

PAGE = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>DataFrame view — column profiles in the header</title>
<style>
  body {{
    max-width: 88rem;
    margin: 2.5rem auto;
    padding: 0 1.5rem;
    font: 17px/1.6 Georgia, serif;
    color: #1a1a1a;
    background: #fbfaf7;
  }}
  h1 {{ font-size: 1.7rem; margin-bottom: 0.2rem; }}
  .sub {{ color: #777; font-style: italic; margin-top: 0; }}
  p {{ max-width: 52rem; }}
  code {{
    font-family: Menlo, monospace;
    font-size: 0.85em;
    background: #f0eee8;
    padding: 0.05em 0.3em;
    border-radius: 3px;
  }}
  /* Scrollable table wrapper */
  .dfv-wrap {{
    overflow: auto;
    max-height: 68vh;
    border: 1px solid #d4d0c8;
    border-radius: 6px;
    margin-top: .8rem;
  }}

  .dfv {{
    border-collapse: collapse;
    font-family: inherit;
    width: max-content;
    min-width: 100%;
  }}

  /* Sticky column headers */
  .dfv-th {{
    position: sticky;
    top: 0;
    z-index: 2;
    background: #f0eee8;
    vertical-align: top;
    padding: .35em .5em .28em;
    min-width: 9em;
    border-bottom: 2px solid #ccc9bd;
    font-weight: normal;
    text-align: left;
    box-sizing: border-box;
  }}

  .dfv-name {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: .80em;
    font-weight: 600;
    color: #1a3a5a;
    margin-bottom: .1em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  /* Data cells */
  .dfv-td, .dfv-td0 {{
    padding: .26em .5em;
    font-size: .84em;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    border-bottom: 1px solid #ebe8e0;
    vertical-align: middle;
    white-space: nowrap;
    color: #222;
  }}
  .dfv-td0 {{ color: #bbb; }}

  /* Zebra striping and row hover */
  .dfv tbody tr:nth-child(even) td {{ background: #f7f5f1; }}
  .dfv tbody tr:hover td {{ background: #edf1f9 !important; }}

  .dfv-null {{ color: #ccc; user-select: none; }}
</style>
</head><body>

<h1>DataFrame view</h1>
<p class="sub">Each column header stacks the column name above a tally strip
and a distribution strip — an at-a-glance column profile right in the header,
as you might see in a SQL client or BI tool previewing a query result set.
Hover any strip for its share, value, and count.</p>

{_TABLE}

<p style="color:#888;font-size:.88rem;margin-top:.8rem;">
  {_n_rows:,}&thinsp;rows &middot; {len(_names):,}&thinsp;columns &mdash;
  <code>discount_pct</code> is 58&thinsp;% zeros (frequency rug) &middot;
  <code>notes</code> is 75&thinsp;% missing
</p>

</body></html>
"""


def main():
    with open("dataframe_view_demo.html", "w", encoding="utf-8") as f:
        f.write(PAGE)
    print("wrote dataframe_view_demo.html — open it and hover the strips")


if __name__ == "__main__":
    main()
