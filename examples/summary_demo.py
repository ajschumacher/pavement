"""
Demo of ``pavement.summary`` — a one-call, at-a-glance summary of a
dataframe, Series, or sequence as an inline HTML table.

In a Jupyter notebook this is the whole story::

    import pavement
    pavement.summary(df)        # renders the table inline in the cell

``summary`` returns an object with a ``_repr_html_``, so a notebook displays
it automatically. Outside a notebook (as here) ``str(summary(...))`` gives the
same self-contained HTML fragment, which this script drops into a page.

Each row pairs a column's **tally** (how much is distinct / duplicate /
missing) with its **distribution** — a pavement **spark** for a numeric
column, a **proportion** strip for a categorical one. A dataframe gets a top
row summarizing the frame itself: the row count, and a tally that treats each
*whole row* as the entity (so "duplicate" means a duplicated row and "missing"
a row that is entirely blank).

Run it with no dependencies beyond the base install::

    python examples/summary_demo.py

It writes ``summary_demo.html`` to the current directory; open it and hover
the strips — each box shows its share, value, and count.
"""

import datetime
import math
import random

import pavement
import pavement.svg as psvg

rng = random.Random(7)
NA = float("nan")  # stand-in for a missing value
N = 500


def _missing(value):
    return value is None or (isinstance(value, float) and math.isnan(value))


# ---------------------------------------------------------------------------
# A made-up "dataframe" as a plain dict of columns (no pandas needed). The mix
# is the point: numeric and not, clean and not, and — among the numeric ones —
# a spread of total value counts, so the summary's auto-resolution shows rugs
# for small columns and 4, 8, or 16 equal-mass bins as the columns get larger.
# ---------------------------------------------------------------------------
people = {
    # A unique key: every row distinct, nothing missing.
    "user_id": list(range(100_000, 100_000 + N)),
    # Few levels, lots of repeats, a little missing -> a proportion strip.
    "plan": [rng.choice(["free", "free", "free", "pro", "pro", "team", None])
             for _ in range(N)],
    # ~450 values present (10% missing) -> 16 equal-mass bins.
    "rating": [rng.choice([1, 2, 3, 4, 5]) if rng.random() > 0.1 else NA
               for _ in range(N)],
    # ~475 values present (5% missing) -> 16 equal-mass bins.
    "age": [NA if rng.random() < 0.05 else round(rng.gauss(38, 11))
            for _ in range(N)],
    # A date column -> a pavement laid out on a time axis (dates in the
    # tooltips), skewed toward recent signups.
    "signup_date": [datetime.date(2023, 1, 1)
                    + datetime.timedelta(days=round(730 * rng.random() ** 2))
                    for _ in range(N)],
    # A timedelta column -> a pavement on a duration axis (e.g. "1d 03:45").
    "session_duration": [datetime.timedelta(
                             seconds=max(30, round(rng.expovariate(1 / 1800))))
                         for _ in range(N)],
    # Heavily skewed, 500 values -> 16 bins shows the long right tail.
    "purchases": [round(rng.expovariate(1 / 30), 1) for _ in range(N)],
    # Continuous, 500 values -> the full 16-bin pavement.
    "latency_ms": [round(rng.lognormvariate(3, 0.6), 2) for _ in range(N)],
    # Free-text-ish, high cardinality, a chunk missing -> proportion catch-all.
    "referrer": [None if rng.random() < 0.2 else
                 ("" if rng.random() < 0.08 else f"ref-{rng.randrange(10**6)}")
                 for _ in range(N)],
    # A column gone almost entirely missing — a data-quality red flag. Its
    # tally is nearly all red and it has no distribution to draw.
    "legacy_field": [rng.randrange(5) if rng.random() < 0.03 else None
                     for _ in range(N)],
}

# A few duplicate whole rows and a couple of all-blank rows, so the top
# "rows" tally has some repeats and missing to show (otherwise every row is
# unique thanks to user_id).
for src in (3, 17, 42):                      # duplicate a few existing rows…
    for col in people.values():
        col.append(col[src])
for _ in range(4):                           # …and add some all-missing rows
    for col in people.values():
        col.append(NA)


# A single numeric Series-like (a bare list): the label becomes the value
# count, since a list has no name to show.
daily_signups = [max(0, round(rng.gauss(120, 35))) for _ in range(N)]

# A single categorical Series-like.
survey = (["strongly agree"] * 30 + ["agree"] * 55 + ["neutral"] * 22
          + ["disagree"] * 12 + ["strongly disagree"] * 6)


# ---------------------------------------------------------------------------
# Three distributions to show off the expressive box edges. A bin draws its
# long top/bottom edge only where data falls *strictly inside* it, so the
# outline closes around bins whose mass is spread out and opens into a gap
# where the mass clumps onto a value line. The three below span the range:
# everywhere-spread (a fully closed box), a central clump (closed flanks
# around an open gap), and all-on-a-few-values (no closed edge at all).
# ---------------------------------------------------------------------------
_r = random.Random(1)
spread_values = [round(_r.uniform(0, 100), 1) for _ in range(400)]
_r = random.Random(3)
clumped_middle = ([round(_r.uniform(0, 30), 1) for _ in range(120)]
                  + [50] * 160
                  + [round(_r.uniform(70, 100), 1) for _ in range(120)])
_r = random.Random(5)
few_values = [_r.choice([10, 10, 10, 25, 25, 60, 90]) for _ in range(400)]

# Bigger than the inline strips above, with whiskers on, so the closed edges
# and the gaps (and the whisker at a clumped value) read clearly.
_BOX_OPTS = dict(bins=8, show_whiskers=True, height="2.6em")


def _box_figure(title: str, note: str, values: list) -> str:
    """One labeled spark for the box-edge gallery."""
    return (
        '<figure style="margin:1.4rem 0;">'
        f'<div style="color:#1a3a5a;">{psvg.spark(values, **_BOX_OPTS)}</div>'
        f'<figcaption style="color:#555;font-size:0.95rem;margin-top:0.5rem;">'
        f'<strong>{title}.</strong> {note}</figcaption></figure>')


box_section = f"""
<h2>Expressive box edges</h2>
<p>Each bin draws its long top and bottom edges <em>only over itself, and only
when one or more values fall strictly inside it</em>. So the box closes around
the bins where values are spread out, and opens into a gap wherever the bin's
mass sits on a value line instead — letting spread and clumping read straight
off the outline. All three below are 8-bin pavements; hover any bin or line for
its value range, percentile, and count.</p>
{_box_figure("Spread throughout",
             "Continuous values fill every bin, so the box stays fully closed "
             "end to end.", spread_values)}
{_box_figure("A clump in the middle",
             "A heavy spike of one repeated value gives the central bins no "
             "interior: the box opens into a gap there (with a whisker at the "
             "repeated value) while the spread-out flanks stay closed.",
             clumped_middle)}
{_box_figure("Only a few values",
             "When every value lands on a bin edge, no bin has an interior at "
             "all — the box never closes, leaving just the value lines.",
             few_values)}
"""


# Optionally show the real pandas path too, if pandas is installed — the call
# is identical, `pavement.summary(df)`.
pandas_section = ""
try:
    import pandas as pd

    iris_like = pd.DataFrame({
        "sepal_length": [round(rng.gauss(5.8, 0.8), 1) for _ in range(150)],
        "sepal_width": [round(rng.gauss(3.0, 0.4), 1) for _ in range(150)],
        "species": (["setosa"] * 50 + ["versicolor"] * 50
                    + ["virginica"] * 50),
        "measured": [rng.random() > 0.07 for _ in range(150)],
    })
    pandas_section = f"""
<h2>A pandas DataFrame</h2>
<p>The call is the same — <code>pavement.summary(df)</code> — for a real
<code>DataFrame</code>. Numeric columns become sparks, the species and the
boolean flag become proportion strips.</p>
{pavement.summary(iris_like)}
"""
except ImportError:
    pandas_section = """
<h2>A pandas DataFrame</h2>
<p><em>(Install pandas to see the identical <code>pavement.summary(df)</code>
call on a real <code>DataFrame</code>.)</em></p>
"""


# Optionally show numpy datetime64 / timedelta64 arrays directly (no pandas
# needed), if numpy is installed.
numpy_section = ""
try:
    import numpy as np

    events = {
        "event_time": [
            np.datetime64("2024-01-01", "s") + np.timedelta64(i * 3600, "s")
            for i in range(N)
        ],
        "response_delay": [
            np.timedelta64(max(1, round(rng.expovariate(1 / 60))), "s")
            for _ in range(N)
        ],
    }
    numpy_section = f"""
<h2>Numpy <code>datetime64</code> and <code>timedelta64</code> arrays</h2>
<p>Raw numpy arrays work too — no pandas or polars needed.
<code>datetime64</code> columns land on a time axis; <code>timedelta64</code>
columns show durations (e.g. <em>00:01</em> for one minute).</p>
{pavement.summary(events)}
"""
except ImportError:
    numpy_section = """
<h2>Numpy arrays</h2>
<p><em>(Install numpy to see <code>datetime64</code> and
<code>timedelta64</code> arrays as pavement sparks.)</em></p>
"""


PAGE = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>pavement.summary — inline dataframe summaries</title>
<style>
  body {{ max-width: 54rem; margin: 3rem auto; padding: 0 1.5rem;
          font: 18px/1.6 Georgia, serif; color: #1a1a1a; background: #fbfaf7; }}
  h1 {{ font-size: 1.7rem; margin-bottom: 0.2rem; }}
  h2 {{ font-size: 1.2rem; margin-top: 2.4rem; }}
  .sub {{ color: #777; font-style: italic; margin-top: 0; }}
  p {{ max-width: 50rem; }}
  code {{ font-family: Menlo, monospace; font-size: 0.85em;
          background: #f0eee8; padding: 0.05em 0.3em; border-radius: 3px; }}
  .legend {{ font-size: 0.95rem; color: #444; }}
  .swatch {{ display: inline-block; width: 0.8em; height: 0.8em;
             border-radius: 2px; vertical-align: -0.05em; margin-right: 0.3em; }}
</style></head><body>

<h1><code>pavement.summary</code></h1>
<p class="sub">One call, an at-a-glance picture of a dataframe, Series, or
sequence — a tally beside a distribution for every column. Pure SVG, no
JavaScript. Hover any strip for its share, value, and count.</p>

<p class="legend">tally:
  <span class="swatch" style="background:#2166ac"></span>distinct &nbsp;
  <span class="swatch" style="background:#92c5de"></span>duplicate &nbsp;
  <span class="swatch" style="background:#b2182b"></span>missing</p>

<h2>A dataframe</h2>
<p>One row per column, under a top row for the frame as a whole: its
<strong>{len(next(iter(people.values())))} rows</strong>, and a tally that
treats each <em>whole row</em> as the entity. Numeric columns get a pavement
<strong>spark</strong> whose resolution adapts to how many values are present —
a rug for 24 or fewer, then 4, 8, or 16 equal-mass bins for larger columns.
Dates work too: <code>signup_date</code> is laid out on a time axis (hover for
the dates). Durations too: <code>session_duration</code> shows timedeltas on a
duration axis (e.g. <em>1d 02:00</em>). Categorical columns get a
<strong>proportion</strong> strip, and <code>legacy_field</code> shows what an
almost-all-missing column looks like.</p>
{pavement.summary(people)}

<h2>A single Series</h2>
<p>Pass one sequence and you get a single row. A bare list has no name, so the
label shows the value count instead. Numeric values give a spark:</p>
{pavement.summary(daily_signups)}
<p>…and categorical values give a proportion strip:</p>
{pavement.summary(survey)}
{pandas_section}{numpy_section}{box_section}
<h2>In a notebook</h2>
<p>Everything above is just <code>str(pavement.summary(...))</code> dropped
into this page. In Jupyter you skip the <code>str()</code> — the last line of
a cell, <code>pavement.summary(df)</code>, renders the table inline on its
own. And for pandas or polars, <code>import pavement.pandas</code> (or
<code>import pavement.polars</code>) adds a <code>.pave</code> accessor:
<code>df.pave()</code>, <code>df.pave.spark("age")</code>,
<code>df.pave.tally("plan")</code> — or
<code>pavement.pandas.enable_repr()</code> to make the summary every
DataFrame's default preview.</p>

</body></html>
"""


def main():
    with open("summary_demo.html", "w", encoding="utf-8") as f:
        f.write(PAGE)
    print("wrote summary_demo.html — open it and hover the strips")


if __name__ == "__main__":
    main()
