"""
Demo of the experimental column "tally" strip via ``pavement.svg.tally``.

A tally is a companion to the ``spark`` sparkline with the same form factor,
but a different question. A spark summarizes the *distribution* of a numeric
column; a tally summarizes the *column itself* — how many of its values are
distinct (dark blue), how many merely repeat a value already seen (light
blue), and how many are missing (dark red). It works on a column of any
type, and surfaces exactly what a pavement plot can't: missing values and
distinctness.

Run it with no dependencies beyond the base install::

    python examples/tally_demo.py

The output ``tally_demo.html`` lands in the current directory; open it and
hover the strips — each box brightens and shows its share and count. The
centerpiece is a "dataframe summary": one row per column, with the column's
tally beside its pavement spark (numeric columns only).

"tally" is a working title — see the README/PR for candidate names.
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
    """One HTML table row per column: name, tally, and pavement spark."""
    rows = []
    for name, values in columns.items():
        tally = psvg.tally(values, height="1.6em")
        if is_numeric(values):
            clean = [v for v in values if not _missing(v)]
            spark = psvg.spark(clean, bins=8, color="#2166ac", height="1.6em")
        else:
            # Pavement plots need numbers; a non-numeric column has no
            # distribution to draw — the tally carries the whole story.
            spark = '<span class="na">—</span>'
        rows.append(f"<tr><td><code>{name}</code></td>"
                    f"<td>{tally}</td><td>{spark}</td></tr>")
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


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>pavement.svg — column tally (working title)</title>
<style>
  body {{ max-width: 50rem; margin: 3rem auto; padding: 0 1.5rem;
          font: 18px/1.7 Georgia, serif; color: #1a1a1a; background: #fbfaf7; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 0.2rem; }}
  h2 {{ font-size: 1.2rem; margin-top: 2.2rem; }}
  .sub {{ color: #777; font-style: italic; margin-top: 0; }}
  .pavement-tally, .pavement-spark {{ margin: 0 0.15em; }}
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

<h1>Column tally <span class="sub">(working title)</span></h1>
<p class="sub">A glance at a column's make-up: how much is distinct, repeated,
or missing. Hover any strip — each box brightens and shows its share and
count. Pure SVG, no JavaScript, no image files.</p>

<p class="legend">
  <span class="swatch" style="background:#2166ac"></span>distinct &nbsp;
  <span class="swatch" style="background:#92c5de"></span>repeated &nbsp;
  <span class="swatch" style="background:#b2182b"></span>missing
</p>

<h2>A dataframe summary</h2>
<p>One row per column: the <strong>tally</strong> works on every column,
numeric or not; the <strong>pavement spark</strong> needs numbers, so a
categorical or text column shows a dash. Together they answer two different
questions about each column.</p>

<table class="summary">
<thead><tr><th>column</th><th>tally</th><th>pavement</th></tr></thead>
<tbody>
{summary}
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
        user_id=psvg.tally(columns["user_id"]),
        plan=psvg.tally(columns["plan"]),
        legacy_field=psvg.tally(columns["legacy_field"]),
    )
    with open("tally_demo.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote tally_demo.html — open it and hover the strips")


if __name__ == "__main__":
    main()
