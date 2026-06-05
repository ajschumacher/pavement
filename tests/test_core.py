from math import nan

import pytest

import pavement
from pavement import (
    pavement_stats,
    pavement_stats2d,
    proportion_stats,
    quantiles,
    tally_stats,
)


def test_quantiles_median_odd():
    assert quantiles([1, 2, 3], [0.5]) == [2]


def test_quantiles_median_even():
    assert quantiles([1, 2], [0.5]) == [1.5]


def test_quantiles_weighted():
    assert quantiles([1, 2], [0.5, 0.8], [4, 1]) == [1, 1.5]


def test_quantiles_max():
    assert quantiles([1, 2, 3, 4, 5], [1]) == [5]


def test_quantiles_median_and_max():
    assert quantiles([1, 2, 3, 4, 5], [0.5, 1]) == [3, 5]


def test_quantiles_sorts_unsorted_input():
    assert quantiles([3, 1, 2], [0.5]) == [2]


def test_quantiles_presorted_rejects_unsorted():
    with pytest.raises(ValueError, match="sorted"):
        quantiles([3, 1, 2], [0.5], presorted=True)


def test_quantiles_weights_length_mismatch():
    with pytest.raises(ValueError, match="weights"):
        quantiles([1, 2, 3], [0.5], weights=[0.5])


def test_quantiles_single_level_out_of_range():
    # A one-element levels list must still be validated against [0, 1];
    # the pairwise increasing check alone skips it.
    with pytest.raises(ValueError, match="increasing in"):
        quantiles([1, 2, 3], [-0.5])
    with pytest.raises(ValueError, match="increasing in"):
        quantiles([1, 2, 3], [2.0])


def test_quantiles_drops_missing():
    # NaN and None are dropped before any math, so they neither corrupt the
    # quantiles nor trip the sort check; the result is as if they were absent.
    assert quantiles([1, 2, nan, 3], [0.5]) == [2]
    assert quantiles([1, None, 2, 3], [0.5]) == [2]


def test_quantiles_drops_missing_with_weights():
    # A dropped value takes its weight with it: the NaN's weight of 99 must
    # not pull the median, which stays the unweighted median of 1, 2, 3.
    assert quantiles([1, 2, nan, 3], [0.5], weights=[1, 1, 99, 1]) == [2]


def test_quantiles_rejects_empty():
    with pytest.raises(ValueError, match="non-empty"):
        quantiles([], [0.5])


def test_quantiles_rejects_all_missing():
    with pytest.raises(ValueError, match="non-empty"):
        quantiles([nan, None], [0.5])


def test_pavement_stats_default_bins():
    assert pavement_stats([1, 2, 3, 4, 5]) == [1, 2, 3, 4, 5]


def test_pavement_stats_presorted_rejects_unsorted():
    with pytest.raises(ValueError, match="sorted"):
        pavement_stats([3, 1, 2], presorted=True)


def test_pavement_stats_invalid_bins():
    with pytest.raises(ValueError, match="bins"):
        pavement_stats([1, 2, 3, 4, 5], bins=0)


def test_pavement_stats_bins_none_returns_all_data():
    assert pavement_stats([3, 1, 2, 5, 4], bins=None) == [1, 2, 3, 4, 5]


def test_pavement_stats_bins_none_keeps_duplicates():
    assert pavement_stats([2, 1, 2], bins=None) == [1, 2, 2]


def test_pavement_stats_bins_none_presorted_rejects_unsorted():
    with pytest.raises(ValueError, match="sorted"):
        pavement_stats([3, 1, 2], bins=None, presorted=True)


def test_pavement_stats_drops_missing():
    assert pavement_stats([1, 2, nan, 3, 4, None, 5], bins=2) == [1, 3, 5]


def test_pavement_stats_bins_none_drops_missing():
    assert pavement_stats([3, nan, 1, 2, None], bins=None) == [1, 2, 3]


def test_pavement_stats_rejects_empty():
    with pytest.raises(ValueError, match="non-empty"):
        pavement_stats([], bins=4)


def test_pavement_stats_bins_none_rejects_empty():
    with pytest.raises(ValueError, match="non-empty"):
        pavement_stats([], bins=None)


def test_pavement_stats2d_shape():
    stats = pavement_stats2d([1, 2, 3, 4], [1, 2, 3, 4], bins=2)
    assert stats["first_split"] == "x"
    assert len(stats["primary_edges"]) == 3  # x_bins + 1
    assert len(stats["secondary_edges_per_chunk"]) == 2  # x_bins
    assert all(len(e) == 3 for e in stats["secondary_edges_per_chunk"])


def test_pavement_stats2d_first_split_y():
    stats = pavement_stats2d(
        [1, 2, 3, 4], [4, 3, 2, 1], bins=2, first_split="y")
    assert stats["first_split"] == "y"
    assert len(stats["primary_edges"]) == 3  # y_bins + 1
    assert len(stats["secondary_edges_per_chunk"]) == 2  # y_bins


def test_pavement_stats2d_different_bins_per_axis():
    stats = pavement_stats2d(
        list(range(20)), list(range(20)), x_bins=2, y_bins=5)
    assert len(stats["primary_edges"]) == 3
    assert all(len(e) == 6 for e in stats["secondary_edges_per_chunk"])


def test_pavement_stats2d_xy_length_mismatch():
    with pytest.raises(ValueError, match="same length"):
        pavement_stats2d([1, 2, 3], [1, 2])


def test_pavement_stats2d_weights_length_mismatch():
    with pytest.raises(ValueError, match="weights"):
        pavement_stats2d([1, 2, 3], [1, 2, 3], weights=[1, 1])


def test_pavement_stats2d_invalid_first_split():
    with pytest.raises(ValueError, match="first_split"):
        pavement_stats2d([1, 2], [1, 2], first_split="diagonal")


def test_pavement_stats2d_invalid_bins():
    with pytest.raises(ValueError, match="x_bins"):
        pavement_stats2d([1, 2, 3, 4], [1, 2, 3, 4], x_bins=0)


def test_pavement_stats2d_empty():
    with pytest.raises(ValueError, match="non-empty"):
        pavement_stats2d([], [])


def test_pavement_stats2d_too_few_points():
    with pytest.raises(ValueError, match="data points"):
        pavement_stats2d([1, 2], [1, 2], bins=4)


def test_column_summaries_reexported_at_top_level():
    # The column summaries are part of the backend-agnostic public surface,
    # reachable from the package root like the pavement statistics.
    assert pavement.tally_stats is tally_stats
    assert pavement.proportion_stats is proportion_stats
    for name in ("tally_stats", "proportion_stats"):
        assert name in pavement.__all__
    assert tally_stats([1, 1, 2])["distinct"] == 2
    assert proportion_stats([1, 1, 2])["counts"][0] == (1, 2)
