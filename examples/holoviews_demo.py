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

    ``with_marginals`` adjoins the marginals (x on top, y on the right),
    splitting each by category and matching the scatter's colors — the
    use case that motivated implementing the plot once as a
    framework-native element. It handles the marginal orientation for us.

    The same layout is saved through both interactive backends to show
    it is genuinely backend-agnostic.
    """
    groups, xs, ys = make_clusters()

    def joint_plot():
        scatter = hv.NdOverlay(
            {g: hv.Scatter(
                [(x, y) for x, y, gg in zip(xs, ys, groups) if gg == g])
             for g in ["A", "B"]},
            kdims="group")
        return phv.with_marginals(scatter, x=xs, y=ys, categories=groups)

    for backend, scatter_opts in [
            ("bokeh", dict(width=500, height=400, size=6, tools=["hover"])),
            ("plotly", dict(width=500, height=400, size=8))]:
        hv.extension(backend)
        layout = joint_plot().opts(hv.opts.Scatter(**scatter_opts))
        name = f"holoviews_marginals_{backend}.html"
        hv.save(layout, name, backend=backend)
        print(f"wrote {name} — open it for hover/pan/zoom")


if __name__ == "__main__":
    static_pngs()
    interactive_html()
