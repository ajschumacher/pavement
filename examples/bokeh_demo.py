"""
Demo of interactive pavement plots via ``pavement.bokeh``.

Builds a few pavement figures and writes them as standalone interactive
HTML (hover, pan, zoom, clickable legend). Run it with the optional
dependency installed::

    pip install -e '.[bokeh]'
    python examples/bokeh_demo.py

Outputs land in the current directory.
"""

import random

from bokeh.plotting import figure, save, output_file

import pavement.bokeh as pbk


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


def _write(obj, filename):
    output_file(filename)
    save(obj)


def standalone():
    """A single pavement, a rug, and a category-split pavement."""
    data = [1, 2, 2, 3, 4, 5, 8, 13, 21]

    single = pbk.pavement(data, value_label="value", height=200)
    _write(single, "bokeh_single.html")

    rug = pbk.pavement(data, bins=None, value_label="value", height=200)
    _write(rug, "bokeh_rug.html")

    categories = pbk.pavement(
        [[1, 2, 3, 4, 5, 6, 7, 8], [3, 4, 5, 6, 7, 8, 9, 12],
         [2, 2, 3, 5, 8, 8, 9, 10]],
        labels=["cats", "dogs", "birds"], value_label="value")
    _write(categories, "bokeh_categories.html")

    print("wrote bokeh_single.html, bokeh_rug.html, bokeh_categories.html")


def joint_plot():
    """A colored scatter with category-split pavement marginals.

    The drop-in-for-rug-marginals use case: ``with_marginals`` places a
    pavement strip on the top (for x) and the right (for y), links their
    ranges to the scatter's, and matches the scatter's colors group for
    group (read off the named scatter renderers).
    """
    groups, xs, ys = make_clusters()
    palette = {"A": "#1f77b4", "B": "#ff7f0e"}  # Category10's first two

    scatter = figure(width=500, height=400, x_axis_label="x", y_axis_label="y")
    for g in ["A", "B"]:
        scatter.scatter(
            [x for x, gg in zip(xs, groups) if gg == g],
            [y for y, gg in zip(ys, groups) if gg == g],
            size=7, color=palette[g], legend_label=g, name=g)
    scatter.legend.location = "top_left"

    joint = pbk.with_marginals(scatter, x=xs, y=ys, categories=groups)
    _write(joint, "bokeh_marginals.html")
    print("wrote bokeh_marginals.html — open it for hover/pan/zoom")


if __name__ == "__main__":
    standalone()
    joint_plot()
