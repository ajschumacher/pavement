"""
Demo of interactive pavement plots via ``pavement.holoviews``.

Renders the same plot definitions through three HoloViews backends:
static PNGs through matplotlib, and a standalone interactive HTML
(hover, pan, zoom, legend) through bokeh. Run it with the optional
dependency installed::

    pip install -e '.[holoviews]' bokeh
    python examples/holoviews_demo.py

Outputs land in the current directory.
"""

import random

import holoviews as hv

import pavement.holoviews as phv


def make_clusters(seed=1, n=60):
    """Two labelled 2D Gaussian clusters, returned as parallel lists."""
    rng = random.Random(seed)
    groups, xs, ys = [], [], []
    for label, (mx, my) in {"A": (0, 0), "B": (2, 1.5)}.items():
        for _ in range(n):
            groups.append(label)
            xs.append(rng.gauss(mx, 1))
            ys.append(rng.gauss(my, 1))
    return groups, xs, ys


def static_pngs():
    """Render a few pavements to PNG through the matplotlib backend."""
    hv.extension("matplotlib")

    single = phv.pavement([1, 2, 2, 3, 4, 5, 8, 13, 21])
    hv.save(single.opts(hv.opts.Rectangles(fig_size=160)),
            "holoviews_single.png")

    rug = phv.pavement([1, 2, 2, 3, 4, 5, 8, 13, 21], bins=None)
    hv.save(rug.opts(hv.opts.Rectangles(fig_size=160)),
            "holoviews_rug.png")

    categories = phv.pavement(
        [[1, 2, 3, 4, 5, 6, 7, 8], [3, 4, 5, 6, 7, 8, 9, 12],
         [2, 2, 3, 5, 8, 8, 9, 10]],
        labels=["cats", "dogs", "birds"])
    hv.save(categories, "holoviews_categories.png")

    print("wrote holoviews_single.png, holoviews_rug.png, "
          "holoviews_categories.png")


def interactive_html():
    """A scatter with category-split pavement marginals, saved as HTML.

    The marginals are adjoined with HoloViews' ``<<`` operator and split
    by category for free — the use case that motivated implementing the
    plot once as a framework-native element.

    Both marginals are built with ``orientation='horizontal'``: HoloViews
    orients each adjoined slot to share the main plot's axis (the top
    shares x, the right shares y), the same convention as ``.hist()``.
    """
    hv.extension("bokeh")
    groups, xs, ys = make_clusters()

    scatter = hv.NdOverlay(
        {g: hv.Scatter([(x, y) for x, y, gg in zip(xs, ys, groups) if gg == g])
         for g in ["A", "B"]},
        kdims="group")
    top = phv.pavement(xs, categories=groups, orientation="horizontal",
                       value_label="x")
    right = phv.pavement(ys, categories=groups, orientation="horizontal",
                         value_label="y")

    layout = (scatter << right << top).opts(
        hv.opts.Scatter(width=500, height=400, size=6, tools=["hover"]))
    hv.save(layout, "holoviews_marginals.html", backend="bokeh")
    print("wrote holoviews_marginals.html — open it for hover/pan/zoom")


if __name__ == "__main__":
    static_pngs()
    interactive_html()
