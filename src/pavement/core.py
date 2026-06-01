"""
Backend-agnostic pavement statistics.

The pure-math core of the package: quantile computation and the
quantile values that define 1D and 2D pavement plots. Nothing here
imports a plotting library, so it is the shared foundation every
backend (`pavement.matplotlib`, `pavement.holoviews`, `pavement.plotly`,
`pavement.bokeh`) builds on. The top-level ``pavement`` package
re-exports these three functions.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Literal

__all__ = [
    "quantiles",
    "pavement_stats",
    "pavement_stats2d",
]


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
        If *levels* is not strictly increasing in [0, 1]; if *weights*
        is given and its length doesn't match *data*; if *data* is not
        sorted when *presorted* is True; or if any weight is not
        positive.
    """
    if not (all(0 <= a < b <= 1 for a, b in zip(levels, levels[1:]))
            and all(0 <= level <= 1 for level in levels)):
        raise ValueError("levels must be strictly increasing in [0, 1]")
    data = list(data)
    if weights is not None and len(weights) != len(data):
        raise ValueError(
            f"weights has length {len(weights)}, expected {len(data)}")
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
    bins: int | None = 4,
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
    bins : int or None, default: 4
        Number of equal-mass bins. Yields ``bins + 1`` quantile values:
        the two endpoints plus the ``bins - 1`` internal cut points. If
        None, no binning is done and every data point is returned
        (sorted), so the pavement shows all the data — useful for small
        datasets, like a rug plot.
    weights : sequence of float, optional
        Positive weights parallel to *data*. If None, each value
        contributes equally. Ignored when *bins* is None, since every
        point is shown regardless of weight.
    presorted : bool, default: False
        Passed through to `quantiles`. If True, *data* (and *weights*)
        are assumed already sorted by *data* in ascending order.

    Returns
    -------
    list of float
        ``bins + 1`` quantile values in ascending order, or every data
        point (sorted) when *bins* is None.

    Raises
    ------
    ValueError
        If *bins* is less than 1; if *data* is not sorted when
        *presorted* is True; or for any reason raised by `quantiles`.

    See Also
    --------
    quantiles : The underlying quantile computation.
    """
    if bins is None:
        data = list(data)
        if not presorted:
            return sorted(data)
        if any(later < earlier for earlier, later in zip(data, data[1:])):
            raise ValueError("data must be sorted")
        return data
    if bins < 1:
        raise ValueError(f"bins must be a positive integer, got {bins}")
    levels = [x/bins for x in range(bins + 1)]
    return quantiles(data, levels, weights, presorted=presorted)


def pavement_stats2d(
    x: Iterable[float],
    y: Iterable[float],
    weights: Sequence[float] | None = None,
    bins: int = 4,
    x_bins: int | None = None,
    y_bins: int | None = None,
    first_split: Literal['x', 'y'] = 'x',
) -> dict[str, Any]:
    """
    Compute the box edges for a 2D pavement plot.

    Sort the data along the *first_split* axis and partition it into
    *primary_bins* chunks of equal weight. Within each chunk, sort
    along the other axis and compute *secondary_bins* equal-weight
    quantiles. Every cell of the resulting grid holds the same
    fraction of the data, ``1 / (x_bins * y_bins)``.

    Parameters
    ----------
    x, y : iterable of float
        Paired coordinates. Must have the same length.
    weights : sequence of float, optional
        Positive weights, one per (x, y) pair. Used for both the
        partition step and the inner quantile step.
    bins : int, default: 4
        Default number of bins along each axis.
    x_bins, y_bins : int, optional
        Override *bins* for the respective axis.
    first_split : {'x', 'y'}, default: 'x'
        Which axis to partition first. ``'x'`` produces columns split
        further into y-bands; ``'y'`` produces rows split further into
        x-bands. The two orderings generally give different grids.

    Returns
    -------
    dict
        ``{'first_split': 'x' | 'y',
           'primary_edges': list[float] of length primary_bins+1,
           'secondary_edges_per_chunk':
               list of primary_bins lists, each of length
               secondary_bins+1}``

        When *first_split* is ``'x'``, primary edges are x-edges and
        secondary edges (per chunk) are y-edges; when ``'y'``, vice
        versa.

    Raises
    ------
    ValueError
        If *x* and *y* have different lengths or are empty; if
        *weights* has a length that doesn't match; if *x_bins* or
        *y_bins* is less than 1; if there are fewer data points than
        the primary-axis bin count; or if a chunk ends up empty
        (which can happen with heavily skewed weights).

    See Also
    --------
    quantiles : The underlying 1D quantile computation.
    """
    if first_split not in ('x', 'y'):
        raise ValueError(
            f"first_split must be 'x' or 'y', got {first_split!r}")
    if x_bins is None:
        x_bins = bins
    if y_bins is None:
        y_bins = bins
    if x_bins < 1:
        raise ValueError(f"x_bins must be a positive integer, got {x_bins}")
    if y_bins < 1:
        raise ValueError(f"y_bins must be a positive integer, got {y_bins}")

    x = list(x)
    y = list(y)
    n = len(x)
    if n != len(y):
        raise ValueError(
            f"x and y must have the same length, got {n} and {len(y)}")
    if n == 0:
        raise ValueError("x and y must be non-empty")
    if weights is not None and len(weights) != n:
        raise ValueError(
            f"weights has length {len(weights)}, expected {n}")

    if first_split == 'x':
        primary, secondary = x, y
        primary_bins, secondary_bins = x_bins, y_bins
    else:
        primary, secondary = y, x
        primary_bins, secondary_bins = y_bins, x_bins

    if n < primary_bins:
        axis = first_split
        raise ValueError(
            f"need at least {axis}_bins ({primary_bins}) data points "
            f"to split along {axis!r}, got {n}")

    indices = sorted(range(n), key=lambda i: primary[i])
    p_sorted = [primary[i] for i in indices]
    s_sorted = [secondary[i] for i in indices]
    w_sorted = [weights[i] for i in indices] if weights is not None else None

    # The drawn column edges and the chunk membership are computed by two
    # independent passes: primary_edges from Type-2 quantiles (which average
    # at an exact order statistic), and the chunks below from a greedy
    # cumulative-weight partition. For a point sitting right on a boundary
    # the two can disagree by one point, so a column's drawn extent and the
    # exact set of points feeding its secondary quantiles aren't guaranteed
    # identical. The difference is at most one boundary point and invisible
    # on typical data; equal weights and distinct values make them agree.
    p_levels = [k/primary_bins for k in range(primary_bins + 1)]
    primary_edges = quantiles(p_sorted, p_levels, w_sorted, presorted=True)

    weights_for_partition = w_sorted if w_sorted is not None else [1] * n
    total = sum(weights_for_partition)
    targets = [k * total / primary_bins for k in range(1, primary_bins + 1)]

    chunks: list[list[int]] = [[] for _ in range(primary_bins)]
    current = 0
    cumulative: float = 0.0
    for i, w in enumerate(weights_for_partition):
        chunks[current].append(i)
        cumulative += w
        while current < primary_bins - 1 and cumulative >= targets[current]:
            current += 1

    if any(len(c) == 0 for c in chunks):
        raise ValueError(
            "some chunks are empty (typically caused by heavily skewed "
            "weights); reduce bins or rebalance weights")

    s_levels = [k/secondary_bins for k in range(secondary_bins + 1)]
    secondary_edges_per_chunk = []
    for chunk_idx in chunks:
        s_chunk = [s_sorted[i] for i in chunk_idx]
        w_chunk = [w_sorted[i] for i in chunk_idx] if w_sorted is not None else None
        secondary_edges_per_chunk.append(quantiles(s_chunk, s_levels, w_chunk))

    return {
        'first_split': first_split,
        'primary_edges': primary_edges,
        'secondary_edges_per_chunk': secondary_edges_per_chunk,
    }
