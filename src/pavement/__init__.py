"""Quantile-based pavement plots with matplotlib."""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Iterable, Mapping, Sequence
from numbers import Integral, Number
from typing import Any, Literal

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.collections import LineCollection

__all__ = ["quantiles", "pavement_stats", "draw_pavement", "plot"]


def quantiles(
    data: Iterable[float],
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
    data : iterable of float
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
    data: Iterable[float],
    bins: int = 4,
    weights: Sequence[float] | None = None,
    presorted: bool = False,
) -> list[float]:
    """
    Compute the quantile values that define a single pavement plot.

    Wraps `quantiles` to turn a bin count into the corresponding
    evenly-spaced quantile levels (``0, 1/bins, ..., 1``).

    Parameters
    ----------
    data : iterable of float
        The values to summarize.
    bins : int, default: 4
        Number of equal-mass bins. Yields ``bins + 1`` quantile values:
        the two endpoints plus the ``bins - 1`` internal cut points.
    weights : sequence of float, optional
        Positive weights parallel to *data*. If None, each value
        contributes equally.
    presorted : bool, default: False
        Passed through to `quantiles`. If True, *data* (and *weights*)
        are assumed already sorted by *data* in ascending order.

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
    return quantiles(data, levels, weights, presorted=presorted)


def draw_pavement(
    values: Sequence[float],
    position: float = 1,
    width: float = 0.6,
    whisker: float = 0.1,
    show_whiskers: bool = True,
    orientation: Literal['vertical', 'horizontal'] = 'vertical',
    line_props: Mapping[str, Any] | None = None,
    ax: Axes | None = None,
) -> dict[str, LineCollection | None]:
    """
    Draw a single pavement row from precomputed quantile values.

    Renders a tick at each value perpendicular to the value axis, a
    box outline spanning ``values[0]`` to ``values[-1]``, and whisker
    marks at any value that occurs more than once (a sign that the
    data is concentrated there).

    Parameters
    ----------
    values : sequence of float
        Quantile values in ascending order, as returned by
        `pavement_stats`.
    position : float, default: 1
        Center of the row along the axis perpendicular to the value
        axis. For ``orientation='vertical'`` this is an x-coordinate;
        for ``orientation='horizontal'`` it is a y-coordinate. The
        default matches matplotlib's ``boxplot``, which places a
        single box at position 1.
    width : float, default: 0.6
        Total thickness of the box outline (perpendicular to the
        value axis).
    whisker : float, default: 0.1
        Extra extent of the whisker marks beyond the box.
    show_whiskers : bool, default: True
        If False, suppress the whisker marks even at repeated values.
    orientation : {'vertical', 'horizontal'}, default: 'vertical'
        Direction of the value axis. 'vertical' puts values on the
        y-axis (matplotlib's boxplot default); 'horizontal' puts them
        on the x-axis.
    line_props : dict, optional
        Line2D properties (color, linewidth, linestyle, alpha, ...)
        passed through to the underlying ``Axes.vlines`` /
        ``Axes.hlines`` calls. Applied uniformly to the quantile ticks,
        whisker marks, and box edges. Defaults to ``{'color': 'black'}``;
        partial overrides merge on top of that default (e.g. passing
        ``{'linewidth': 2}`` keeps lines black).
    ax : matplotlib Axes, optional
        Axes to draw on. Defaults to ``plt.gca()``.

    Returns
    -------
    dict
        Maps component name to the `~matplotlib.collections.LineCollection`
        artist that was added to the axes:

        - ``"ticks"``: vertical (or horizontal) tick at each quantile.
        - ``"whiskers"``: the whisker marks at repeated values, or
          ``None`` if no whiskers were drawn.
        - ``"box"``: the two long edges of the box.

    Raises
    ------
    ValueError
        If *orientation* is not 'vertical' or 'horizontal'.

    See Also
    --------
    pavement_stats : Compute the values to pass in.
    plot : One-call convenience that combines stats and drawing.
    """
    if ax is None:
        ax = plt.gca()
    if orientation == 'vertical':
        perp, along = ax.hlines, ax.vlines
    elif orientation == 'horizontal':
        perp, along = ax.vlines, ax.hlines
    else:
        raise ValueError(
            f"orientation must be 'vertical' or 'horizontal', got {orientation!r}")
    props = {'color': 'black', **(line_props or {})}
    pos_lo, pos_hi = position - width/2, position + width/2
    artists: dict[str, LineCollection | None] = {
        'ticks': perp(values, pos_lo, pos_hi, **props),
        'whiskers': None,
    }
    if show_whiskers:
        dupes = [x for x, n in Counter(values).items() if n > 1]
        if dupes:
            artists['whiskers'] = perp(
                dupes, pos_lo - whisker, pos_hi + whisker, **props)
    artists['box'] = along([pos_lo, pos_hi], values[0], values[-1], **props)
    return artists


def plot(
    data: Sequence[float] | Sequence[Iterable[float]],
    weights: Sequence[float] | Sequence[Sequence[float]] | None = None,
    positions: Sequence[float] | None = None,
    categories: Sequence[Hashable] | None = None,
    tick_labels: Sequence[Hashable] | None = None,
    bins: int | Sequence[int] = 4,
    widths: float | Sequence[float] = 0.6,
    whisker: float = 0.1,
    show_whiskers: bool = True,
    orientation: Literal['vertical', 'horizontal'] = 'vertical',
    line_props: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    ax: Axes | None = None,
) -> list[dict[str, LineCollection | None]]:
    """
    Draw one or more pavement rows.

    Accepts three input shapes:

    - A 1D sequence of values: a single row.
    - A sequence of 1D sequences: one row per dataset, at *positions*
      (matching matplotlib's ``boxplot``: ``data[0]`` at the smallest
      position).
    - A 1D sequence plus *categories*: tidy/long form. The data is
      split by category and rendered as in the wide form.

    Parameters
    ----------
    data : sequence of float, or sequence of iterables of float
        The values to plot. Shape determines which mode is used.
    weights : sequence, optional
        Positive weights. Must match the shape of *data*: flat for a
        single row or tidy form, nested for wide form.
    positions : sequence of float, optional
        Position of each row along the axis perpendicular to the
        value axis. Defaults to ``[1, 2, ..., N]``, matching
        matplotlib's ``boxplot``. Length must equal the number of
        rows.
    categories : sequence, optional
        Category label per entry in *data*, parallel to *data*. If
        given, *data* is treated as tidy/long form and split by
        category.
    tick_labels : sequence of str, optional
        Tick labels, one per row, in the same order as the rows. In
        tidy form, also selects which categories to include and their
        order. Ticks are only set when this is provided, on the x-axis
        for ``orientation='vertical'`` and the y-axis otherwise.
    bins : int or sequence of int, default: 4
        Number of equal-mass bins per row. A scalar applies to every
        row; a sequence sets each row's bin count individually and
        must have length equal to the number of rows.
    widths : float or sequence of float, default: 0.6
        Thickness of each row's box outline. A scalar applies to
        every row; a sequence sets each row's width individually and
        must have length equal to the number of rows.
    whisker : float, default: 0.1
        Extra extent of the whisker marks beyond the box.
    show_whiskers : bool, default: True
        If False, suppress whisker marks at repeated quantile values.
    orientation : {'vertical', 'horizontal'}, default: 'vertical'
        Direction of the value axis. 'vertical' puts values on the
        y-axis (matplotlib's boxplot default); 'horizontal' puts them
        on the x-axis.
    line_props : dict or sequence of dict, optional
        Per-row line styling. A single dict applies to every row; a
        sequence sets each row individually and must have length equal
        to the number of rows. See `draw_pavement` for the dict
        semantics.
    ax : matplotlib Axes, optional
        Axes to draw on. Defaults to ``plt.gca()``.

    Returns
    -------
    list of dict
        One artist dict per row, in the same order as the rows. Each
        dict has the shape returned by `draw_pavement`.

    Raises
    ------
    ValueError
        If *positions*, *bins*, *widths*, or *line_props* is given as
        a sequence and its length doesn't match the number of rows.

    See Also
    --------
    pavement_stats : Compute quantile values for one dataset.
    draw_pavement : Render one row from precomputed values.
    """
    if categories is not None:
        if tick_labels is None:
            tick_labels = sorted(set(categories))
        data = [[d for d, c in zip(data, categories) if c == label]
                for label in tick_labels]
        if weights is not None:
            weights = [[w for w, c in zip(weights, categories) if c == label]
                       for label in tick_labels]
    if not hasattr(data[0], '__iter__'):
        data = [data]
        weights = [weights] if weights is not None else None
    n = len(data)
    if positions is None:
        positions = list(range(1, n + 1))
    elif len(positions) != n:
        raise ValueError(
            f"positions has length {len(positions)}, expected {n}")
    if isinstance(bins, Integral):
        bins = [bins] * n
    elif len(bins) != n:
        raise ValueError(
            f"bins has length {len(bins)}, expected {n}")
    if isinstance(widths, Number):
        widths = [widths] * n
    elif len(widths) != n:
        raise ValueError(
            f"widths has length {len(widths)}, expected {n}")
    if line_props is None or isinstance(line_props, Mapping):
        line_props = [line_props] * n
    elif len(line_props) != n:
        raise ValueError(
            f"line_props has length {len(line_props)}, expected {n}")
    if ax is None:
        ax = plt.gca()
    weight_iter = weights if weights is not None else [None] * n
    artists = []
    for dataset, w, pos, b, width, props in zip(
            data, weight_iter, positions, bins, widths, line_props):
        values = pavement_stats(dataset, bins=b, weights=w)
        artists.append(draw_pavement(
            values, position=pos, width=width,
            whisker=whisker, show_whiskers=show_whiskers,
            orientation=orientation, line_props=props, ax=ax))
    if tick_labels is not None:
        set_ticks = ax.set_xticks if orientation == 'vertical' else ax.set_yticks
        set_ticks(list(positions), list(tick_labels))
    return artists
