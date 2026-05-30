"""
Demo of interactive pavement plots via ``pavement.plotly``.

Builds a few pavement figures and writes them as standalone interactive
HTML (hover, pan, zoom, legend). Run it with the optional dependency
installed::

    pip install -e '.[plotly]'
    python examples/plotly_demo.py

Outputs land in the current directory.
"""

import random

import plotly.graph_objects as go

import pavement.plotly as ppl


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


def standalone():
    """A single pavement, a rug, and a category-split pavement."""
    data = [1, 2, 2, 3, 4, 5, 8, 13, 21]

    single = ppl.plot(data)
    single.write_html("plotly_single.html")

    rug = ppl.plot(data, bins=None)
    rug.write_html("plotly_rug.html")

    categories = ppl.plot(
        [[1, 2, 3, 4, 5, 6, 7, 8], [3, 4, 5, 6, 7, 8, 9, 12],
         [2, 2, 3, 5, 8, 8, 9, 10]],
        labels=["cats", "dogs", "birds"])
    categories.write_html("plotly_categories.html")

    print("wrote plotly_single.html, plotly_rug.html, plotly_categories.html")


def joint_plot():
    """A colored scatter with category-split pavement marginals.

    The drop-in-for-rug-marginals use case: instead of plotly's
    ``marginal_x='rug'`` / ``marginal_y='rug'``, adjoin pavement strips
    that match the scatter's colors group for group. ``with_marginals``
    places x on top and y on the right and keeps them aligned with the
    scatter through pan and zoom.
    """
    groups, xs, ys = make_clusters()
    palette = {"A": "#636efa", "B": "#EF553B"}  # plotly's first two colors

    scatter = go.Figure()
    for g in ["A", "B"]:
        scatter.add_trace(go.Scatter(
            x=[x for x, gg in zip(xs, groups) if gg == g],
            y=[y for y, gg in zip(ys, groups) if gg == g],
            mode="markers", name=g, marker=dict(color=palette[g], size=7)))
    scatter.update_xaxes(title_text="x").update_yaxes(title_text="y")

    joint = ppl.with_marginals(scatter, x=xs, y=ys, categories=groups)
    joint.update_layout(width=640, height=520, title="pavement marginals")
    joint.write_html("plotly_marginals.html")
    print("wrote plotly_marginals.html — open it for hover/pan/zoom")


if __name__ == "__main__":
    standalone()
    joint_plot()
