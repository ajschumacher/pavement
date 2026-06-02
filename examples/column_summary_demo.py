"""
Demo of the experimental column-summary strips in ``pavement.svg``: the
``tally`` and the ``proportion`` plot.

Both are companions to the ``spark`` sparkline, in the same borderless form
factor, answering questions a pavement plot can't:

- A **tally** summarizes a column's make-up — how many values are distinct
  (dark blue), repeated (light blue), or missing (dark red) — for a column
  of any type.
- A **proportion** plot summarizes a column's value counts (à la pandas
  ``value_counts``): one box per value, widest first, with a catch-all for
  the long tail of a high-cardinality column. It fills the gap a pavement
  spark leaves for categorical columns.

Run it with no dependencies beyond the base install::

    python examples/column_summary_demo.py

The output ``column_summary_demo.html`` lands in the current directory; open it and
hover the strips — each box brightens and shows its share and count. The
centerpiece is a "dataframe summary": one row per column with its tally and
its distribution (a pavement spark for numeric columns, a proportion plot
for categorical ones).
"""

import math
import random

import pavement.svg as psvg

rng = random.Random(11)
NA = float("nan")  # stand-in for a missing value

# ---------------------------------------------------------------------------
# A made-up "dataframe": each column is just a list of values. The mix is the
# point — numeric and not, clean and not, distinct and repetitive — so the
# tally has something to say about every one, while the pavement spark only
# applies to the numeric columns.
# ---------------------------------------------------------------------------
N = 200

columns = {
    # A unique key: every value distinct, nothing missing.
    "user_id": list(range(1000, 1000 + N)),
    # A category with a handful of levels: lots of repeats, a few missing.
    "plan": [rng.choice(["free", "free", "free", "pro", "pro", "team", None])
             for _ in range(N)],
    # Numeric, roughly normal, a sprinkle of missing (NaN).
    "age": [NA if rng.random() < 0.06 else round(rng.gauss(38, 11))
            for _ in range(N)],
    # Numeric and heavily skewed, no missing, many repeats at the low end.
    "purchases": [int(rng.expovariate(1 / 2.5)) for _ in range(N)],
    # A boolean flag: only two distinct values, so almost all "repeated".
    "is_active": [rng.random() < 0.7 for _ in range(N)],
    # Free-text-ish: mostly distinct, a chunk missing (None / empty string).
    "referrer": [None if rng.random() < 0.25 else
                 ("" if rng.random() < 0.1 else f"ref-{rng.randrange(10**6)}")
                 for _ in range(N)],
    # Numeric score with real repeats (a 1-5 rating) and some missing.
    "rating": [None if rng.random() < 0.15 else
               rng.choice([1, 2, 3, 3, 4, 4, 4, 5, 5]) for _ in range(N)],
    # A column gone almost entirely missing — a data-quality red flag.
    "legacy_field": [rng.randrange(5) if rng.random() < 0.04 else None
                     for _ in range(N)],
}


def is_numeric(values):
    """Whether a column is numeric (ignoring missing) — bools don't count."""
    present = [v for v in values if not _missing(v)]
    return bool(present) and all(
        isinstance(v, (int, float)) and not isinstance(v, bool)
        for v in present)


def _missing(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


def summary_rows():
    """One HTML table row per column: name, tally, and distribution.

    The distribution is a pavement spark for numeric columns and a
    proportion plot for the rest — so every column gets a distribution
    view, where a pavement spark alone would leave the categorical ones
    blank.
    """
    rows = []
    for name, values in columns.items():
        tally = psvg.tally(values, height="1.6em")
        if is_numeric(values):
            clean = [v for v in values if not _missing(v)]
            dist = psvg.spark(clean, bins=8, color="#2166ac", height="1.6em")
        else:
            dist = psvg.proportion(values, height="1.6em")
        rows.append(f"<tr><td><code>{name}</code></td>"
                    f"<td>{tally}</td><td>{dist}</td></tr>")
    return "\n".join(rows)


# A small gallery of hand-built columns showing the extremes.
gallery = {
    "all distinct": psvg.tally(list(range(40)), height="1.6em"),
    "all one value": psvg.tally(["yes"] * 40, height="1.6em"),
    "half missing": psvg.tally([rng.randrange(8) for _ in range(20)]
                               + [None] * 20, height="1.6em"),
    "all missing": psvg.tally([None] * 40, height="1.6em"),
    "balanced": psvg.tally([1, 1, 2, 2, 3] + [None] * 2, height="1.6em"),
}
gallery_rows = "\n".join(
    f"<tr><td>{label}</td><td>{strip}</td></tr>"
    for label, strip in gallery.items())


# A gallery of proportion plots, from low to high cardinality.
survey = (["strongly agree"] * 30 + ["agree"] * 55 + ["neutral"] * 22
          + ["disagree"] * 12 + ["strongly disagree"] * 6)
fruit = ["apple"] * 48 + ["banana"] * 26 + ["cherry"] * 14 + ["date"] * 8
# A long tail: a few common cities, then hundreds of one-offs.
cities = (["Springfield"] * 40 + ["Riverton"] * 25 + ["Fairview"] * 15
          + [f"town-{i}" for i in range(400)])
ids = [f"order-{rng.randrange(10**6)}" for _ in range(300)]  # essentially all unique

proportion_gallery = {
    "survey answers (5 levels)": psvg.proportion(survey, height="1.6em"),
    "fruit picked (4 kinds)": psvg.proportion(fruit, height="1.6em"),
    "home city (long tail)": psvg.proportion(cities, height="1.6em"),
    "order id (all unique)": psvg.proportion(ids, height="1.6em"),
}
proportion_gallery_rows = "\n".join(
    f"<tr><td>{label}</td><td>{strip}</td></tr>"
    for label, strip in proportion_gallery.items())


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>pavement.svg — column tally &amp; proportion strips</title>
<style>
  body {{ max-width: 50rem; margin: 3rem auto; padding: 0 1.5rem;
          font: 18px/1.7 Georgia, serif; color: #1a1a1a; background: #fbfaf7; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 0.2rem; }}
  h2 {{ font-size: 1.2rem; margin-top: 2.2rem; }}
  .sub {{ color: #777; font-style: italic; margin-top: 0; }}
  .pavement-tally, .pavement-spark, .pavement-proportion {{ margin: 0 0.15em; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1rem;
           font-size: 0.95rem; }}
  th, td {{ text-align: left; padding: 0.45rem 0.6rem;
            border-bottom: 1px solid #e3e0d8; vertical-align: middle; }}
  th {{ font-variant: small-caps; color: #555; font-weight: normal; }}
  code {{ font-family: Menlo, monospace; font-size: 0.85em; }}
  .na {{ color: #bbb; }}
  .legend {{ font-size: 0.95rem; color: #444; }}
  .swatch {{ display: inline-block; width: 0.8em; height: 0.8em;
             border-radius: 2px; vertical-align: -0.05em; margin-right: 0.3em; }}
  .summary td:nth-child(2), .summary td:nth-child(3) {{ width: 12rem; }}
</style></head><body>

<h1>Column tally</h1>
<p class="sub">A glance at a column's make-up: how much is distinct, repeated,
or missing. Hover any strip — each box brightens and shows its share and
count, and the distinct box also notes how many values appear exactly once.
Pure SVG, no JavaScript, no image files.</p>

<p class="legend">
  <span class="swatch" style="background:#2166ac"></span>distinct &nbsp;
  <span class="swatch" style="background:#92c5de"></span>repeated &nbsp;
  <span class="swatch" style="background:#b2182b"></span>missing
</p>

<h2>A dataframe summary</h2>
<p>One row per column: a <strong>tally</strong> of its make-up beside its
<strong>distribution</strong>. The distribution is a <strong>pavement
spark</strong> for numeric columns and a <strong>proportion plot</strong> for
categorical ones — so every column gets a distribution view, where a pavement
spark alone would leave the categorical rows blank.</p>

<table class="summary">
<thead><tr><th>column</th><th>tally</th><th>distribution</th></tr></thead>
<tbody>
{summary}
</tbody>
</table>

<h2>Proportion plots</h2>
<p>A proportion plot is a column's <code>value_counts()</code>: one box per
value, widest (most common) first, in alternating blues. Hover a box for its
value, share, and count. For a high-cardinality column only the top values
get a box; the rest are lumped into a final <span class="swatch"
style="background:#5995c5"></span>catch-all box (a blue in between), whose
tooltip says how many distinct values it covers. Boxes never shrink below a
visible minimum, and the catch-all kicks in early rather than let a long tail
of slivers misrepresent it.</p>

<table>
<thead><tr><th>column</th><th>proportion</th></tr></thead>
<tbody>
{proportion_gallery}
</tbody>
</table>

<h2>The extremes</h2>
<p>The three boxes always fill the strip and a missing category draws no box,
so the shape alone tells you a lot at a glance.</p>

<table>
<thead><tr><th>column</th><th>tally</th></tr></thead>
<tbody>
{gallery}
</tbody>
</table>

<h2>Inline, mid-sentence</h2>
<p>Like a spark, a tally sits in running text: the user table is almost all
unique ids {user_id}, the plan column is a few repeated levels {plan}, and a
legacy field has quietly gone almost all-missing {legacy_field} — a red flag
worth chasing.</p>

</body></html>
"""


def main():
    html = PAGE.format(
        summary=summary_rows(),
        gallery=gallery_rows,
        proportion_gallery=proportion_gallery_rows,
        user_id=psvg.tally(columns["user_id"]),
        plan=psvg.tally(columns["plan"]),
        legacy_field=psvg.tally(columns["legacy_field"]),
    )
    with open("column_summary_demo.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote column_summary_demo.html — open it and hover the strips")


if __name__ == "__main__":
    main()
