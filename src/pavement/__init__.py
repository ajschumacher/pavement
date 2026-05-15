from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Sequence

import matplotlib.pyplot as plt


def quantiles(
    data: Sequence[float],
    levels: Sequence[float],
    weights: Sequence[float] | None = None,
    presorted: bool = False,
) -> list[float]:
    """
    Compute Type 2 quantiles, optionally weighted.

    Type 2 is the discontinuous quantile definition that averages two
    adjacent values when a level lands exactly on an order statistic.
    See https://robjhyndman.com/papers/sample_quantiles.pdf.

    Parameters
    ----------
    data : sequence of float
        The values to take quantiles of. Sorted internally unless
        *presorted* is True.
    levels : sequence of float
        Quantile levels in [0, 1], strictly increasing.
    weights : sequence of float, optional
        Positive weights parallel to *data*. If None, each value
        contributes equally.
    presorted : bool, default: False
        If True, *data* (and *weights*) are assumed already sorted by
        *data* in ascending order; the internal sort is skipped. A
        monotonicity check still runs and raises if the claim is false.

    Returns
    -------
    list of float
        One value per entry in *levels*, in the same order.

    Raises
    ------
    ValueError
        If *levels* is not strictly increasing in [0, 1], if *data* is
        not sorted when *presorted* is True, or if any weight is not
        positive.
    """
    if not all(0 <= a < b <= 1 for a, b in zip(levels, levels[1:])):
        raise ValueError("levels must be strictly increasing in [0, 1]")
    if not presorted:
        if weights is None:
            data = sorted(data)
        else:
            data, weights = zip(*sorted(zip(data, weights)))
    total = len(data) if weights is None else sum(weights)
    targets = [level * total for level in levels]
    level_index = 0
    value = float('-inf')
    cumulative = 0
    results = []
    for index in range(len(data)):
        if data[index] < value:
            raise ValueError("data must be sorted")
        value = data[index]
        weight = 1 if weights is None else weights[index]
        if weight <= 0:
            raise ValueError("weights must be positive")
        cumulative += weight
        while level_index < len(levels) and cumulative > targets[level_index]:
            results.append(value)
            level_index += 1
        if level_index < len(levels) and cumulative == targets[level_index]:
            next_value = data[index + 1] if index + 1 < len(data) else value
            results.append((value + next_value) / 2)
            level_index += 1
    return results


def pavement_stats(
    data: Sequence[float],
    bins: int = 4,
    weights: Sequence[float] | None = None,
) -> list[float]:
    """
    Compute the quantile values that define a single pavement plot.

    Wraps `quantiles` to turn a bin count into the corresponding
    evenly-spaced quantile levels (``0, 1/bins, ..., 1``).

    Parameters
    ----------
    data : sequence of float
        The values to summarize.
    bins : int, default: 4
        Number of equal-mass bins. Yields ``bins + 1`` quantile values:
        the two endpoints plus the ``bins - 1`` internal cut points.
    weights : sequence of float, optional
        Positive weights parallel to *data*. If None, each value
        contributes equally.

    Returns
    -------
    list of float
        ``bins + 1`` quantile values in ascending order.

    See Also
    --------
    quantiles : The underlying quantile computation.
    draw_pavement : Render these values as a pavement row.
    """
    levels = [x/bins for x in range(bins + 1)]
    return quantiles(data, levels, weights)


def draw_pavement(
    values: Sequence[float],
    ypos: float = 0,
    height: float = 0.6,
    whisker: float = 0.1,
    show_whiskers: bool = True,
) -> None:
    """
    Draw a single pavement row from precomputed quantile values.

    Renders a vertical tick at each value, a box outline spanning
    ``values[0]`` to ``values[-1]``, and whisker marks at any value
    that occurs more than once (a sign that the data is concentrated
    there).

    Parameters
    ----------
    values : sequence of float
        Quantile values in ascending order, as returned by
        `pavement_stats`.
    ypos : float, default: 0
        Vertical center of the row.
    height : float, default: 0.6
        Total height of the box outline.
    whisker : float, default: 0.1
        Extra vertical extent of the whisker marks beyond the box.
    show_whiskers : bool, default: True
        If False, suppress the whisker marks even at repeated values.

    See Also
    --------
    pavement_stats : Compute the values to pass in.
    plot : One-call convenience that combines stats and drawing.
    """
    plt.vlines(values,
               ymin=ypos - height/2, ymax=ypos + height/2,
               color='black')
    if show_whiskers:
        dupes = [x for x, n in Counter(values).items() if n > 1]
        if dupes:
            plt.vlines(dupes,
                       ymin=ypos - height/2 - whisker,
                       ymax=ypos + height/2 + whisker,
                       color='black')
    plt.hlines([ypos - height/2, ypos + height/2],
               xmin=values[0], xmax=values[-1],
               color='black')


def plot(
    data: Sequence[float] | Sequence[Sequence[float]],
    weights: Sequence[float] | Sequence[Sequence[float]] | None = None,
    categories: Sequence[Hashable] | None = None,
    labels: Sequence[Hashable] | None = None,
    bins: int = 4,
    ypos: float = 0,
    height: float = 0.6,
    whisker: float = 0.1,
    show_whiskers: bool = True,
) -> None:
    """
    Draw one or more pavement rows.

    Accepts three input shapes:

    - A 1D sequence of values: a single row at *ypos*.
    - A sequence of 1D sequences: one row per dataset, stacked
      top-to-bottom starting at ``ypos + len(data) - 1``.
    - A 1D sequence plus *categories*: tidy/long form. The data is
      split by category and rendered as in the wide form.

    Parameters
    ----------
    data : sequence of float, or sequence of sequences of float
        The values to plot. Shape determines which mode is used.
    weights : sequence, optional
        Positive weights. Must match the shape of *data*: flat for a
        single row or tidy form, nested for wide form.
    categories : sequence, optional
        Category label per entry in *data*, parallel to *data*. If
        given, *data* is treated as tidy/long form and split by
        category.
    labels : sequence of str, optional
        Y-tick labels, one per row, ordered top-to-bottom. In tidy
        form, also selects which categories to include and their
        order. Y-ticks are only set when this is provided.
    bins : int, default: 4
        Number of equal-mass bins per row.
    ypos : float, default: 0
        Vertical position of the bottom row. In single-row mode this
        is the row's center.
    height : float, default: 0.6
        Height of each row's box outline.
    whisker : float, default: 0.1
        Extra vertical extent of the whisker marks beyond the box.
    show_whiskers : bool, default: True
        If False, suppress whisker marks at repeated quantile values.

    See Also
    --------
    pavement_stats : Compute quantile values for one dataset.
    draw_pavement : Render one row from precomputed values.
    """
    if categories is not None:
        if labels is None:
            labels = sorted(set(categories))
        data = [[d for d, c in zip(data, categories) if c == label]
                for label in labels]
        if weights is not None:
            weights = [[w for w, c in zip(weights, categories) if c == label]
                       for label in labels]
    if not hasattr(data[0], '__iter__'):
        data = [data]
        weights = [weights] if weights is not None else None
    n = len(data)
    for index, dataset in enumerate(data):
        subweights = weights[index] if weights is not None else None
        values = pavement_stats(dataset, bins=bins, weights=subweights)
        draw_pavement(values, ypos=ypos + n - 1 - index, height=height,
                      whisker=whisker, show_whiskers=show_whiskers)
    if labels is not None:
        plt.gca().set_yticks(range(ypos, ypos + n), list(reversed(labels)))
