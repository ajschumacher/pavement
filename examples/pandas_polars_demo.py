"""
Demo of the ``.pave`` accessor for pandas and polars.

Importing ``pavement.pandas`` (or ``pavement.polars``) registers a ``.pave``
accessor that turns any DataFrame or Series into a live summary or a single
sparkline strip — right from the dataframe, without calling ``pavement.summary``
by name.

Run it with no extra dependencies beyond pandas or polars::

    python examples/pandas_polars_demo.py

It writes ``pandas_polars_demo.html`` to the current directory; open it and
hover the strips.
"""

import html as _html
import random

import pavement

rng = random.Random(7)
N = 300

_CODE_STYLE = (
    "margin:.6rem 0 1rem;background:#1d1f23;color:#e8e6e1;"
    "padding:.9rem 1rem;border-radius:8px;font-size:.82rem;"
    "line-height:1.5;overflow-x:auto;"
)
_DETAILS_STYLE = "margin-bottom:1.2rem;"
_SUMMARY_STYLE = "cursor:pointer;color:#555;font-size:.9rem;"


def _code_block(code: str) -> str:
    return (
        f'<details style="{_DETAILS_STYLE}">'
        f'<summary style="{_SUMMARY_STYLE}">Show code</summary>'
        f'<pre style="{_CODE_STYLE}"><code>{_html.escape(code)}</code></pre>'
        f'</details>'
    )


def _subsection(title: str, code: str, body: str) -> str:
    return (
        f"<h3>{title}</h3>"
        + _code_block(code)
        + f'<div class="output">{body}</div>'
    )


def _people_dict():
    return {
        "user_id": list(range(100_000, 100_000 + N)),
        "plan": [rng.choice(["free", "free", "free", "pro", "pro", "team", None])
                 for _ in range(N)],
        "age": [None if rng.random() < 0.05 else round(rng.gauss(38, 11))
                for _ in range(N)],
        "purchases": [round(rng.expovariate(1 / 30), 1) for _ in range(N)],
    }


# ---------------------------------------------------------------------------
# Pandas section
# ---------------------------------------------------------------------------

pandas_section = ""
try:
    import pandas as pd
    import pavement.pandas  # registers .pave

    df = pd.DataFrame(_people_dict())
    age_series = df["age"]

    pandas_section = (
        "<h2>pandas</h2>"
        "<p>Import <code>pavement.pandas</code> once — that registers the "
        "<code>.pave</code> accessor on every pandas "
        "<code>DataFrame</code> and <code>Series</code>.</p>"

        + _subsection(
            "df.pave() — whole-frame summary",
            "import pavement.pandas       # registers .pave\n\ndf.pave()",
            str(df.pave()))

        + _subsection(
            "df.pave.spark(column) — one column's sparkline",
            'df.pave.spark("age")',
            str(df.pave.spark("age")))

        + _subsection(
            "df.pave.tally(column) — distinct / duplicate / missing",
            'df.pave.tally("plan")',
            str(df.pave.tally("plan")))

        + _subsection(
            "df.pave.proportion(column) — value-counts strip",
            'df.pave.proportion("plan")',
            str(df.pave.proportion("plan")))

        + _subsection(
            "Series.pave() — a single-row summary",
            "df['age'].pave()",
            str(age_series.pave()))

        + "<h3><code>enable_repr()</code> — make summary the default display</h3>"
        + _code_block(
            "import pavement.pandas\n\n"
            "pavement.pandas.enable_repr()\n"
            "# From this point on, displaying any DataFrame or Series in a\n"
            "# notebook cell shows pavement.summary instead of the default repr.\n\n"
            "pavement.pandas.disable_repr()  # restore the original display")
        + "<p>Call once at the top of a notebook to make "
        "<code>pavement.summary</code> every DataFrame's default cell preview. "
        "Strictly opt-in — a plain <code>import pavement.pandas</code> only adds "
        "the <code>.pave</code> accessor, nothing else.</p>"
    )
except ImportError:
    pandas_section = (
        "<h2>pandas</h2>"
        "<p><em>(Install pandas to see the <code>.pave</code> accessor "
        "examples.)</em></p>"
    )


# ---------------------------------------------------------------------------
# Polars section
# ---------------------------------------------------------------------------

polars_section = ""
try:
    import polars as pl
    import pavement.polars  # registers .pave namespace

    df_pl = pl.DataFrame(_people_dict())
    age_series_pl = df_pl["age"]

    polars_section = (
        "<h2>polars</h2>"
        "<p>The API is identical — import <code>pavement.polars</code> instead. "
        "Polars uses a plugin namespace rather than a pandas accessor, but the "
        "call shapes are the same.</p>"

        + _subsection(
            "df.pave() — whole-frame summary",
            "import pavement.polars       # registers .pave namespace\n\ndf.pave()",
            str(df_pl.pave()))

        + _subsection(
            "df.pave.spark(column) — one column's sparkline",
            'df.pave.spark("age")',
            str(df_pl.pave.spark("age")))

        + _subsection(
            "df.pave.tally(column) — distinct / duplicate / missing",
            'df.pave.tally("plan")',
            str(df_pl.pave.tally("plan")))

        + _subsection(
            "df.pave.proportion(column) — value-counts strip",
            'df.pave.proportion("plan")',
            str(df_pl.pave.proportion("plan")))

        + _subsection(
            "Series.pave() — a single-row summary",
            "df['age'].pave()",
            str(age_series_pl.pave()))
    )
except ImportError:
    polars_section = (
        "<h2>polars</h2>"
        "<p><em>(Install polars to see the <code>.pave</code> namespace "
        "examples.)</em></p>"
    )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

PAGE = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>pavement — .pave accessor for pandas and polars</title>
<style>
  body {{ max-width: 54rem; margin: 3rem auto; padding: 0 1.5rem;
          font: 17px/1.6 Georgia, serif; color: #1a1a1a; background: #fbfaf7; }}
  h1 {{ font-size: 1.7rem; margin-bottom: 0.2rem; }}
  h2 {{ font-size: 1.2rem; margin-top: 2.4rem; }}
  h3 {{ font-size: 1rem; margin: 1.8rem 0 0.4rem; color: #333; }}
  .sub {{ color: #777; font-style: italic; margin-top: 0; }}
  p {{ max-width: 50rem; }}
  code {{ font-family: Menlo, monospace; font-size: 0.85em;
          background: #f0eee8; padding: 0.05em 0.3em; border-radius: 3px; }}
  .output {{ margin-bottom: 0.6rem; font-size: 1.1em; }}
</style></head><body>

<h1>The <code>.pave</code> accessor</h1>
<p class="sub">One import, then <code>.pave</code> is available on every
DataFrame and Series — no need to call <code>pavement.summary</code> by name.</p>

{pandas_section}

{polars_section}

<h2>In a notebook</h2>
<p>In Jupyter, <code>df.pave()</code> at the end of a cell renders the summary
table inline automatically — the result has a <code>_repr_html_</code>. And
<code>enable_repr()</code> goes one step further: after calling it once,
<em>any</em> DataFrame displayed in a cell shows the pavement summary instead
of the default pandas/polars table.</p>

</body></html>
"""


def main() -> None:
    with open("pandas_polars_demo.html", "w", encoding="utf-8") as f:
        f.write(PAGE)
    print("wrote pandas_polars_demo.html — open it and hover the strips")


if __name__ == "__main__":
    main()
