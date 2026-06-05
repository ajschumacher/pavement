"""
Regenerate the images embedded at the top of ``README.md``.

Three assets, all written into ``examples/``:

* ``title_spark.svg`` — a bimodal 16-bin pavement spark for the title line.
  Pure SVG (``pavement.svg``), embedded as an ``<img>`` so it renders on
  GitHub and PyPI; an explicit color keeps it visible in light and dark.
* ``four_sets.png`` — the matplotlib hero: four classic distribution shapes
  as filled, colored pavements (``pavement.matplotlib``).
* ``summary.png`` — a screenshot of ``pavement.summary`` over a small mixed
  dataframe, showing the tally-plus-distribution table.

Run it from the repo root::

    python examples/readme_assets.py

The SVG and the matplotlib PNG need only the base install plus matplotlib.
The summary screenshot additionally needs pandas and a headless Chrome
(via selenium); if those are missing it is skipped with a note.
"""

import datetime
import math
import os
import random

import pavement
import pavement.svg as psvg

HERE = os.path.dirname(os.path.abspath(__file__))
ACCENT = "#4c6ef5"  # the indigo used across all three assets


# ---------------------------------------------------------------------------
# 1. Title spark — a clearly bimodal distribution in 16 equal-mass bins.
# ---------------------------------------------------------------------------
def make_title_spark() -> None:
    rng = random.Random(11)
    values = ([rng.gauss(-1.0, 0.30) for _ in range(500)]
              + [rng.gauss(1.0, 0.30) for _ in range(500)])
    psvg.spark(
        values,
        bins=16,
        color=ACCENT,
        inline=False,   # a clean, scalable file; sizing comes from the <img>
        hover=False,    # decorative here — embedded as an image
        path=os.path.join(HERE, "title_spark.svg"),
    )
    print("wrote examples/title_spark.svg")


# ---------------------------------------------------------------------------
# 2. Hero figure — four distribution shapes as filled, colored pavements.
#    The data echoes Wickham & Stryjewski's boxplot examples (Figure 4 of
#    https://vita.had.co.nz/papers/boxplots.pdf).
# ---------------------------------------------------------------------------
def make_four_sets() -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    import pavement.matplotlib as pmpl

    rng = np.random.default_rng(42)
    n = 1000

    normal = rng.standard_normal(n)
    skewed = rng.lognormal(0, 0.5, n) - 1.0
    heavy = rng.standard_t(df=4, size=n) * 0.5
    bimodal = np.concatenate([rng.normal(-1, 0.35, n // 2),
                              rng.normal(1, 0.35, n // 2)])
    rng.shuffle(bimodal)

    # Bottom-to-top, so the most striking shape (bimodal) sits at the bottom
    # and the familiar normal at the top.
    datasets = [bimodal, heavy, skewed, normal]
    labels = ["bimodal", "leptokurtic", "right-skewed", "normal"]
    colors = ["#4c6ef5", "#0ea5a4", "#f59f00", "#e8590c"]

    fig, ax = plt.subplots(figsize=(8, 4.2))
    pmpl.plot(datasets, labels=labels, bins=16, orientation="horizontal",
              color=colors, fill_alpha=0.28, ax=ax)
    ax.set_title("Pavement plots: Every box has an equal share of the data",
                 fontsize=13, pad=12)
    ax.tick_params(length=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#bbb")
    ax.margins(x=0.02)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "four_sets.png"), dpi=200,
                facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print("wrote examples/four_sets.png")


# ---------------------------------------------------------------------------
# 3. Summary screenshot — a small mixed dataframe through pavement.summary,
#    showing off tally + distribution for every column kind at once.
# ---------------------------------------------------------------------------
def _build_people() -> "dict":
    rng = random.Random(7)
    NA = float("nan")
    N = 500
    people = {
        # A unique key: every row distinct, nothing missing.
        "user_id": list(range(100_000, 100_000 + N)),
        # A few levels with a little missing -> a proportion strip.
        "plan": [rng.choice(["free", "free", "free", "pro", "pro", "team",
                             None]) for _ in range(N)],
        # Five discrete levels -> a frequency rug.
        "rating": [rng.choice([1, 2, 3, 4, 5]) if rng.random() > 0.1 else NA
                   for _ in range(N)],
        # ~Normal, continuous -> a 16-bin spark.
        "age": [NA if rng.random() < 0.05 else round(rng.gauss(38, 11))
                for _ in range(N)],
        # A date column -> a pavement on a time axis.
        "signup_date": [datetime.date(2023, 1, 1)
                        + datetime.timedelta(days=round(730 * rng.random()**2))
                        for _ in range(N)],
        # A duration column -> a pavement on a duration axis.
        "session": [datetime.timedelta(
                        seconds=max(30, round(rng.expovariate(1 / 1800))))
                    for _ in range(N)],
        # Heavily skewed -> 16 bins show the long right tail.
        "purchases": [round(rng.expovariate(1 / 30), 1) for _ in range(N)],
        # Almost entirely missing -> a near-all-red tally, no distribution.
        "legacy_field": [rng.randrange(5) if rng.random() < 0.03 else None
                         for _ in range(N)],
    }
    # A few duplicate whole rows and a couple of all-blank rows, so the top
    # "rows" tally has repeats and missing to show.
    for src in (3, 17, 42):
        for col in people.values():
            col.append(col[src])
    for _ in range(4):
        for col in people.values():
            col.append(NA)
    return people


SUMMARY_PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
  body {{ margin: 0; background: #ffffff; }}
  #card {{ display: inline-block; padding: 24px 30px 22px;
           font: 17px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI",
                 Roboto, Helvetica, Arial, sans-serif; color: #1a1a1a; }}
</style></head><body>
<div id="card">
  {table}
</div></body></html>"""


def make_summary_png() -> None:
    try:
        import pandas as pd
    except ImportError:
        print("skipped examples/summary.png (needs pandas)")
        return

    df = pd.DataFrame(_build_people())
    html = SUMMARY_PAGE.format(table=str(pavement.summary(df)))
    html_path = os.path.join(HERE, "summary.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        print("wrote examples/summary.html "
              "(install selenium + Chrome to render summary.png)")
        return

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--force-device-scale-factor=2")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--window-size=1100,900")
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as exc:  # noqa: BLE001 - report and skip, don't crash
        print(f"wrote examples/summary.html "
              f"(could not start headless Chrome: {exc})")
        return
    try:
        driver.get("file://" + html_path)
        card = driver.find_element("id", "card")
        card.screenshot(os.path.join(HERE, "summary.png"))
    finally:
        driver.quit()
    os.remove(html_path)
    print("wrote examples/summary.png")


def main() -> None:
    make_title_spark()
    make_four_sets()
    make_summary_png()


if __name__ == "__main__":
    main()
