"""
Demo of inline pavement sparklines via ``pavement.svg``.

Builds a single self-contained HTML page with sparks set *inside* running
text and a table, the way Tufte uses sparklines. Each spark is an
``<svg>`` string embedded directly in the markup — no image files, no
JavaScript, no plotting dependency. ``pavement.svg`` ships with the base
install, so this just needs::

    python examples/svg_demo.py

The output ``svg_demo.html`` lands in the current directory; open it and
hover the sparks — the bin or value line under the cursor highlights and
shows a tooltip (a quantile band per bin, or each value's percentile on a
small rug).
"""

import random

import pavement.svg as psvg

rng = random.Random(7)

# A few distributions with different shapes, plus two that pile up on a
# value (so a whisker appears) and one rendered as a rug.
latency = [rng.expovariate(1 / 40) for _ in range(400)]            # skewed
cpu = [min(100, max(0, rng.gauss(38, 12))) for _ in range(400)]    # ~normal
scores = [min(100, max(0, rng.gauss(72, 11))) for _ in range(300)]
commute = ([rng.gauss(9, 0.4) for _ in range(180)] +              # bimodal
           [rng.gauss(18, 0.8) for _ in range(180)])
satisfaction = [rng.choice([1, 2, 3, 3, 4, 4, 4, 5, 5])           # whisker
                for _ in range(250)]
errors = [0.0] * 140 + [rng.expovariate(1 / 3) for _ in range(160)]  # whisker
normal = [rng.gauss(0, 1) for _ in range(500)]
# A small rug (at or below the default tick_hover_limit) so every value is
# individually hoverable — each shows its percentile and value.
build_min = [3.1, 3.4, 3.8, 4.0, 4.2, 4.5, 5.1, 5.9, 6.2, 7.0, 9.5, 12.0]

s = dict(
    latency=psvg.spark(latency, bins=8, color="#c0392b"),
    cpu=psvg.spark(cpu, bins=8, color="#2c7fb8"),
    scores=psvg.spark(scores, bins=10),
    commute=psvg.spark(commute, bins=8, color="#6a51a3"),
    satisfaction=psvg.spark(satisfaction, bins=5, color="#238b45"),
    errors=psvg.spark(errors, bins=6, color="#d95f0e"),
    rug=psvg.spark(normal, bins=None),
    binned=psvg.spark(normal, bins=6),
    small_rug=psvg.spark(build_min, bins=None, color="#2c7fb8"),
)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>pavement.svg — inline sparklines</title>
<style>
  body {{ max-width: 44rem; margin: 3rem auto; padding: 0 1.5rem;
          font: 18px/1.8 Georgia, serif; color: #1a1a1a; background: #fbfaf7; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 0.2rem; }}
  .sub {{ color: #777; font-style: italic; margin-top: 0; }}
  .pavement-spark {{ margin: 0 0.15em; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1.5rem;
           font-size: 0.95rem; }}
  th, td {{ text-align: left; padding: 0.4rem 0.6rem;
            border-bottom: 1px solid #e3e0d8; }}
  th {{ font-variant: small-caps; color: #555; font-weight: normal; }}
  td.num {{ font-variant-numeric: tabular-nums; color: #444; }}
  code {{ font-family: Menlo, monospace; font-size: 0.85em;
          background: #f0eee8; padding: 0.05em 0.3em; border-radius: 3px; }}
  .dark {{ background: #1d1f23; color: #e8e6e1; padding: 1.1rem 1.3rem;
           border-radius: 8px; }}
</style></head><body>

<h1>Distributions, mid-sentence</h1>
<p class="sub">Hover any spark — the bin or value line under the cursor
highlights (bins brighten, lines thicken) and shows a tooltip. Pure SVG —
no JavaScript, no image files.</p>

<p>Request latency kept a heavy tail {latency} while CPU stayed mid-range and
symmetric {cpu}; exam scores {scores} clustered above the pass mark. Commute
times split into two crowds {commute}. A pile-up raises a whisker: survey
satisfaction bunched on one answer {satisfaction}, and the error budget sat at
zero most days {errors}. With <code>bins=None</code> a spark becomes a rug
{rug}, versus the binned summary of the same data {binned}.</p>

<p>A rug adapts its hover to its size. A handful of build times {small_rug} is a
<em>small</em> rug — hover any value to read it and its percentile. The
500-point rug above {rug} is too dense for that, so it shows one whole-spark
summary instead; force per-value hover with <code>tick_hover_limit=None</code>,
or turn it off with <code>0</code>.</p>

<div class="dark">
<p style="margin:0">On a dark panel the sparks inherit the light text color
through <code>currentColor</code>: scores {scores}, latency {latency}, rug
{rug}.</p>
</div>

<table>
<thead><tr><th>endpoint</th><th>p50</th><th>p99</th><th>distribution</th></tr></thead>
<tbody>
  <tr><td>/search</td><td class="num">28</td><td class="num">210</td><td>{latency}</td></tr>
  <tr><td>/checkout</td><td class="num">41</td><td class="num">156</td><td>{cpu}</td></tr>
  <tr><td>/upload</td><td class="num">63</td><td class="num">540</td><td>{commute}</td></tr>
</tbody>
</table>

</body></html>
"""


def main():
    with open("svg_demo.html", "w", encoding="utf-8") as f:
        f.write(PAGE.format(**s))
    print("wrote svg_demo.html — open it and hover the sparks")


if __name__ == "__main__":
    main()
