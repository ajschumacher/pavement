import matplotlib.pyplot as plt
import pytest

from pavement import (
    draw_pavement,
    draw_pavement2d,
    pavement_stats,
    pavement_stats2d,
    plot,
    plot2d,
    quantiles,
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


def test_pavement_stats_default_bins():
    assert pavement_stats([1, 2, 3, 4, 5]) == [1, 2, 3, 4, 5]


def test_pavement_stats_presorted_rejects_unsorted():
    with pytest.raises(ValueError, match="sorted"):
        pavement_stats([3, 1, 2], presorted=True)


def test_pavement_stats_invalid_bins():
    with pytest.raises(ValueError, match="bins"):
        pavement_stats([1, 2, 3, 4, 5], bins=0)


def test_plot_single():
    plt.figure()
    plot([1, 2, 3, 4, 5])
    plt.close()


def test_plot_wide():
    plt.figure()
    plot([[1, 2, 3], [4, 5, 6]], tick_labels=["a", "b"])
    plt.close()


def test_plot_tidy():
    plt.figure()
    plot([1, 2, 3, 4, 5, 6], categories=["a", "a", "a", "b", "b", "b"])
    plt.close()


def test_plot_horizontal():
    plt.figure()
    plot([[1, 2, 3], [4, 5, 6]], tick_labels=["a", "b"], orientation="horizontal")
    plt.close()


def test_plot_invalid_orientation():
    with pytest.raises(ValueError, match="orientation"):
        plot([1, 2, 3], orientation="sideways")


def test_plot_positions_length_mismatch():
    with pytest.raises(ValueError, match="positions"):
        plot([[1, 2, 3], [4, 5, 6]], positions=[0])


def test_plot_custom_positions():
    plt.figure()
    plot([[1, 2, 3], [4, 5, 6]], positions=[0, 10])
    plt.close()


def test_plot_widths_array():
    plt.figure()
    plot([[1, 2, 3], [4, 5, 6]], widths=[0.3, 0.8])
    plt.close()


def test_plot_widths_length_mismatch():
    with pytest.raises(ValueError, match="widths"):
        plot([[1, 2, 3], [4, 5, 6]], widths=[0.3])


def test_plot_line_props_dict():
    plt.figure()
    plot([[1, 2, 3], [4, 5, 6]], line_props={'color': 'red', 'linewidth': 2})
    plt.close()


def test_plot_line_props_per_row():
    plt.figure()
    plot([[1, 2, 3], [4, 5, 6]],
         line_props=[{'color': 'red'}, {'color': 'blue'}])
    plt.close()


def test_plot_line_props_length_mismatch():
    with pytest.raises(ValueError, match="line_props"):
        plot([[1, 2, 3], [4, 5, 6]], line_props=[{'color': 'red'}])


def test_plot_bins_array():
    plt.figure()
    plot([[1, 2, 3, 4], [5, 6, 7, 8]], bins=[2, 4])
    plt.close()


def test_plot_bins_length_mismatch():
    with pytest.raises(ValueError, match="bins"):
        plot([[1, 2, 3], [4, 5, 6]], bins=[4])


def test_draw_pavement_returns_artist_dict():
    plt.figure()
    artists = draw_pavement([1, 2, 3, 4, 5])
    assert set(artists) == {"ticks", "whiskers", "box"}
    assert artists["ticks"] is not None
    assert artists["box"] is not None
    assert artists["whiskers"] is None  # no repeated values
    plt.close()


def test_draw_pavement_returns_whiskers_when_dupes():
    plt.figure()
    artists = draw_pavement([1, 1, 2, 3])  # 1 repeats -> whisker mark
    assert artists["whiskers"] is not None
    plt.close()


def test_plot_returns_list_of_artist_dicts():
    plt.figure()
    artists = plot([[1, 2, 3], [4, 5, 6]])
    assert isinstance(artists, list)
    assert len(artists) == 2
    assert all(set(d) == {"ticks", "whiskers", "box"} for d in artists)
    plt.close()


def test_plot_respects_ax_argument():
    fig, (ax1, ax2) = plt.subplots(1, 2)
    plot([1, 2, 3], ax=ax2)
    assert len(ax1.collections) == 0
    assert len(ax2.collections) > 0
    plt.close(fig)


def test_draw_pavement_empty_values():
    plt.figure()
    with pytest.raises(ValueError, match="empty"):
        draw_pavement([])
    plt.close()


def test_plot_empty_data():
    with pytest.raises(ValueError, match="empty"):
        plot([])


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


def test_pavement_stats2d_xweights_length_mismatch():
    with pytest.raises(ValueError, match="x_weights"):
        pavement_stats2d([1, 2, 3], [1, 2, 3], x_weights=[1, 1])


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


def test_plot2d_smoke():
    plt.figure()
    artists = plot2d(list(range(16)), list(range(16)))
    assert set(artists) == {"verticals", "horizontals"}
    plt.close()


def test_plot2d_respects_ax():
    fig, (ax1, ax2) = plt.subplots(1, 2)
    plot2d(list(range(16)), list(range(16)), ax=ax2)
    assert len(ax1.collections) == 0
    assert len(ax2.collections) > 0
    plt.close(fig)
