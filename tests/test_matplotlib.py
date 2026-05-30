import pytest

pytest.importorskip("matplotlib")

import matplotlib.pyplot as plt  # noqa: E402
from pavement import pavement_stats2d  # noqa: E402
from pavement.matplotlib import (  # noqa: E402
    draw_pavement,
    draw_pavement2d,
    margin,
    plot,
    plot2d,
)


def test_plot_single():
    plt.figure()
    plot([1, 2, 3, 4, 5])
    plt.close()


def test_plot_wide():
    plt.figure()
    plot([[1, 2, 3], [4, 5, 6]], labels=["a", "b"])
    plt.close()


def test_plot_tidy():
    plt.figure()
    plot([1, 2, 3, 4, 5, 6], categories=["a", "a", "a", "b", "b", "b"])
    plt.close()


def test_plot_horizontal():
    plt.figure()
    plot([[1, 2, 3], [4, 5, 6]], labels=["a", "b"], orientation="horizontal")
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


def test_draw_pavement_box_props_adds_fill():
    plt.figure()
    artists = draw_pavement([1, 2, 3, 4, 5],
                            box_props={'facecolor': 'lightblue', 'alpha': 0.3})
    assert artists["fill"] is not None
    plt.close()


def test_draw_pavement_no_box_props_no_fill():
    plt.figure()
    artists = draw_pavement([1, 2, 3, 4, 5])
    assert artists["fill"] is None
    plt.close()


def test_plot_box_props_per_row():
    plt.figure()
    artists = plot([[1, 2, 3], [4, 5, 6]],
                   box_props=[{'facecolor': 'C0'}, {'facecolor': 'C1'}])
    assert all(d["fill"] is not None for d in artists)
    plt.close()


def test_plot_box_props_length_mismatch():
    with pytest.raises(ValueError, match="box_props"):
        plot([[1, 2, 3], [4, 5, 6]], box_props=[{'facecolor': 'C0'}])


def test_margin_box_props_adds_fill():
    plt.figure()
    artists = margin([1, 2, 3, 4, 5], box_props={'facecolor': 'gray',
                                                 'alpha': 0.2})
    assert artists["fill"] is not None
    plt.close()


def test_plot_bins_array():
    plt.figure()
    plot([[1, 2, 3, 4], [5, 6, 7, 8]], bins=[2, 4])
    plt.close()


def test_plot_bins_length_mismatch():
    with pytest.raises(ValueError, match="bins"):
        plot([[1, 2, 3], [4, 5, 6]], bins=[4])


def test_plot_bins_none_shows_all_data():
    plt.figure()
    # 5 distinct points -> a tick at each, so 5 segments in the ticks.
    artists = plot([1, 2, 3, 4, 5], bins=None)
    assert len(artists[0]["ticks"].get_segments()) == 5
    plt.close()


def test_plot_bins_mixed_none_and_int():
    plt.figure()
    artists = plot([[1, 2, 3, 4], [5, 6, 7, 8]], bins=[None, 2])
    assert len(artists[0]["ticks"].get_segments()) == 4  # all data
    assert len(artists[1]["ticks"].get_segments()) == 3  # 2 bins -> 3 edges
    plt.close()


def test_draw_pavement_returns_artist_dict():
    plt.figure()
    artists = draw_pavement([1, 2, 3, 4, 5])
    assert set(artists) == {"fill", "ticks", "box"}
    assert artists["ticks"] is not None
    assert artists["box"] is not None
    plt.close()


def test_draw_pavement_default_linewidth_is_one():
    plt.figure()
    artists = draw_pavement([1, 2, 3, 4, 5])
    assert artists["box"].get_linewidth()[0] == 1.0
    plt.close()


def test_draw_pavement_line_props_overrides_linewidth():
    plt.figure()
    artists = draw_pavement([1, 2, 3, 4, 5], line_props={"linewidth": 3})
    assert artists["box"].get_linewidth()[0] == 3.0
    plt.close()


def test_draw_pavement_repeated_value_makes_a_whisker():
    plt.figure()
    # A repeated value reaches past the box as a whisker — one line per
    # distinct value, no separate whiskers artist.
    artists = draw_pavement([1, 1, 2, 3], width=0.6)
    half = 0.6 / 2
    # Vertical ticks are horizontal segments [[xmin, y], [xmax, y]]; the
    # half-span is (xmax - xmin) / 2, which exceeds half for the whisker.
    reaches = [(seg[1][0] - seg[0][0]) / 2
               for seg in artists["ticks"].get_segments()]
    assert max(reaches) > half
    plt.close()


def test_plot_returns_list_of_artist_dicts():
    plt.figure()
    artists = plot([[1, 2, 3], [4, 5, 6]])
    assert isinstance(artists, list)
    assert len(artists) == 2
    assert all(set(d) == {"fill", "ticks", "box"} for d in artists)
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


def test_margin_smoke():
    plt.figure()
    artists = margin([1, 2, 3, 4, 5])
    assert set(artists) == {"fill", "ticks", "box"}
    plt.close()


def test_margin_axis_y():
    plt.figure()
    margin([1, 2, 3, 4, 5], axis="y")
    plt.close()


def test_margin_bins_none_shows_all_data():
    plt.figure()
    artists = margin([1, 2, 3, 4, 5], bins=None)
    assert len(artists["ticks"].get_segments()) == 5
    plt.close()


def test_margin_invalid_axis():
    with pytest.raises(ValueError, match="axis"):
        margin([1, 2, 3], axis="z")


def test_margin_clip_on_default_false():
    plt.figure()
    artists = margin([1, 2, 3, 4, 5])
    assert artists["box"].get_clip_on() is False
    plt.close()


def test_margin_respects_ax():
    fig, (ax1, ax2) = plt.subplots(1, 2)
    margin([1, 2, 3, 4, 5], ax=ax2)
    assert len(ax1.collections) == 0
    assert len(ax2.collections) > 0
    plt.close(fig)


def test_margin_x_lifts_title_clear():
    fig, ax = plt.subplots()
    ax.set_title("a title")
    margin([1, 2, 3, 4, 5], axis="x", ax=ax)
    assert ax.title.get_position()[1] > 1.0
    plt.close(fig)


def test_margin_y_leaves_title_alone():
    fig, ax = plt.subplots()
    ax.set_title("a title")
    margin([1, 2, 3, 4, 5], axis="y", ax=ax)
    assert ax.title.get_position()[1] == 1.0
    plt.close(fig)


def test_margin_where_bottom():
    plt.figure()
    margin([1, 2, 3, 4, 5], axis="x", where="bottom")
    plt.close()


def test_margin_where_left():
    plt.figure()
    margin([1, 2, 3, 4, 5], axis="y", where="left")
    plt.close()


def test_margin_where_invalid_for_axis():
    with pytest.raises(ValueError, match="where"):
        margin([1, 2, 3], axis="x", where="left")


def test_margin_where_bottom_leaves_title_alone():
    fig, ax = plt.subplots()
    ax.set_title("a title")
    margin([1, 2, 3, 4, 5], axis="x", where="bottom", ax=ax)
    assert ax.title.get_position()[1] == 1.0
    plt.close(fig)


def test_margin_inside_smoke():
    plt.figure()
    margin([1, 2, 3, 4, 5], axis="x", where="inside bottom")
    margin([1, 2, 3, 4, 5], axis="y", where="inside left")
    plt.close()


def test_margin_outside_prefix_explicit():
    plt.figure()
    margin([1, 2, 3, 4, 5], axis="x", where="outside top")
    plt.close()


def test_margin_invalid_placement():
    with pytest.raises(ValueError, match="inside.*outside"):
        margin([1, 2, 3], axis="x", where="upside top")


def test_margin_where_too_many_words():
    with pytest.raises(ValueError, match="where"):
        margin([1, 2, 3], axis="x", where="a b c")


def test_margin_inside_top_leaves_title_alone():
    fig, ax = plt.subplots()
    ax.set_title("a title")
    margin([1, 2, 3, 4, 5], axis="x", where="inside top", ax=ax)
    assert ax.title.get_position()[1] == 1.0
    plt.close(fig)


def test_margin_inside_stays_within_axes():
    fig, ax = plt.subplots()
    art = margin([1, 2, 3, 4, 5], axis="x", where="inside bottom", ax=ax)
    ys = [pt[1] for seg in art["box"].get_segments() for pt in seg]
    assert all(0 <= y <= 1 for y in ys)
    plt.close(fig)


def test_margin_inside_expands_margins():
    fig, ax = plt.subplots()
    margin([1, 2, 3, 4, 5], axis="x", where="inside bottom", ax=ax)
    assert ax.margins()[1] > 0.05  # y-margin grew past the default
    plt.close(fig)


def test_margin_inside_expand_false_keeps_margins():
    fig, ax = plt.subplots()
    margin([1, 2, 3, 4, 5], axis="x", where="inside bottom",
           expand_margins=False, ax=ax)
    assert ax.margins()[1] == 0.05
    plt.close(fig)


def test_margin_outside_does_not_expand():
    fig, ax = plt.subplots()
    margin([1, 2, 3, 4, 5], axis="x", where="outside top", ax=ax)
    assert ax.margins()[1] == 0.05
    plt.close(fig)


def test_margin_x_and_y_same_physical_thickness():
    fig, ax = plt.subplots(figsize=(8, 4))  # wide: width != height
    x_art = margin([1, 2, 3, 4, 5], axis="x", ax=ax)
    y_art = margin([1, 2, 3, 4, 5], axis="y", ax=ax)

    def frac_thickness(box, index):
        pts = [pt[index] for seg in box.get_segments() for pt in seg]
        return max(pts) - min(pts)

    # x-marginal thickness runs along y (index 1), as an axes-fraction
    # of height; the y-marginal along x (index 0), fraction of width.
    x_frac = frac_thickness(x_art["box"], 1)
    y_frac = frac_thickness(y_art["box"], 0)
    assert x_frac * ax.bbox.height == pytest.approx(y_frac * ax.bbox.width)
    plt.close(fig)


def test_plot2d_smoke():
    plt.figure()
    artists = plot2d(list(range(16)), list(range(16)))
    assert set(artists) == {"fills", "verticals", "horizontals"}
    assert artists["fills"] is None  # no box_props
    plt.close()


def test_plot2d_box_props_fills_every_cell():
    plt.figure()
    artists = plot2d(list(range(16)), list(range(16)), bins=2,
                     box_props={"facecolor": "C0", "alpha": 0.3})
    assert len(artists["fills"]) == 4  # 2 x_bins * 2 y_bins
    plt.close()


def test_plot2d_respects_ax():
    fig, (ax1, ax2) = plt.subplots(1, 2)
    plot2d(list(range(16)), list(range(16)), ax=ax2)
    assert len(ax1.collections) == 0
    assert len(ax2.collections) > 0
    plt.close(fig)


def test_draw_pavement2d_from_stats():
    plt.figure()
    stats = pavement_stats2d(list(range(16)), list(range(16)), bins=2)
    artists = draw_pavement2d(stats)
    assert set(artists) == {"fills", "verticals", "horizontals"}
    assert artists["fills"] is None  # no box_props
    plt.close()
