import pytest

from pavement import quantiles


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
