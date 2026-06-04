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
    spark,
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


def test_draw_pavement_show_box_false_drops_box():
    plt.figure()
    artists = draw_pavement([1, 2, 3, 4, 5], show_box=False)
    assert artists["box"] is None
    assert artists["ticks"] is not None  # ticks still drawn
    plt.close()


def test_plot_rug_omits_box_by_default():
    # A rug (bins=None) drops the box edges, so it reads like a plain rug; a
    # binned row with spread data keeps them. Per-row, so a mixed bins
    # sequence mixes too.
    plt.figure()
    rug, binned = plot([[1, 2, 2, 3, 5], list(range(9))], bins=[None, 4])
    assert rug["box"] is None
    assert binned["box"] is not None
    plt.close()


def test_plot_box_gaps_over_bins_without_interior():
    # Default (auto): a binned row draws each bin's edges only where it holds
    # a data point strictly inside it. Data spread through every bin keeps the
    # box; data sitting on its own bin edges leaves no box at all.
    plt.figure()
    spread, on_edges = plot([list(range(9)), [0, 1, 2, 3, 4]], bins=[4, 4])
    assert spread["box"] is not None
    assert on_edges["box"] is None
    plt.close()


def test_plot_show_box_true_forces_box_on_rug():
    plt.figure()
    (artists,) = plot([1, 2, 2, 3, 5], bins=None, show_box=True)
    assert artists["box"] is not None
    plt.close()


def test_draw_pavement_repeated_value_makes_a_tassel():
    plt.figure()
    # A repeated value reaches past the box as a tassel — one line per
    # distinct value, no separate tassels artist.
    artists = draw_pavement([1, 1, 2, 3], width=0.6)
    half = 0.6 / 2
    # Vertical ticks are horizontal segments [[xmin, y], [xmax, y]]; the
    # half-span is (xmax - xmin) / 2, which exceeds half for the tassel.
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
    # show_box=True so there is a box artist to inspect (the default auto box
    # gaps out for this on-the-edges data).
    plt.figure()
    artists = margin([1, 2, 3, 4, 5], show_box=True)
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
    art = margin([1, 2, 3, 4, 5], axis="x", where="inside bottom",
                 show_box=True, ax=ax)
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
    x_art = margin([1, 2, 3, 4, 5], axis="x", show_box=True, ax=ax)
    y_art = margin([1, 2, 3, 4, 5], axis="y", show_box=True, ax=ax)

    def frac_thickness(box, index):
        pts = [pt[index] for seg in box.get_segments() for pt in seg]
        return max(pts) - min(pts)

    # x-marginal thickness runs along y (index 1), as an axes-fraction
    # of height; the y-marginal along x (index 0), fraction of width.
    x_frac = frac_thickness(x_art["box"], 1)
    y_frac = frac_thickness(y_art["box"], 0)
    assert x_frac * ax.bbox.height == pytest.approx(y_frac * ax.bbox.width)
    plt.close(fig)


def test_spark_returns_figure():
    fig = spark([1, 2, 3, 4, 5])
    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_spark_axes_fills_figure_and_is_off():
    fig = spark([1, 2, 3, 4, 5])
    ax = fig.axes[0]
    assert tuple(ax.get_position().bounds) == (0, 0, 1, 1)
    assert not ax.axison
    plt.close(fig)


def test_spark_default_size_is_word_sized_horizontal():
    fig = spark([1, 2, 3, 4, 5])
    assert tuple(fig.get_size_inches()) == (1.4, 0.3)
    plt.close(fig)


def test_spark_vertical_transposes_default_size():
    fig = spark([1, 2, 3, 4, 5], orientation="vertical")
    assert tuple(fig.get_size_inches()) == (0.3, 1.4)
    plt.close(fig)


def test_spark_custom_figsize_and_dpi():
    fig = spark([1, 2, 3, 4, 5], figsize=(2, 0.5), dpi=300)
    assert tuple(fig.get_size_inches()) == (2, 0.5)
    assert fig.dpi == 300
    plt.close(fig)


def test_spark_limits_hug_value_extent():
    # Default pad=0: the value axis (x, for horizontal) hugs the data
    # range, expanded only by a sub-pixel half-stroke so the flush end
    # lines aren't clipped.
    fig = spark([0, 1, 2, 3, 4], bins=4)
    ax = fig.axes[0]
    lo, hi = ax.get_xlim()
    assert lo == pytest.approx(0, abs=0.05) and lo < 0
    assert hi == pytest.approx(4, abs=0.05) and hi > 4
    plt.close(fig)


def test_spark_pad_insets_the_pavement():
    # A positive pad adds breathing room as a fraction of the value
    # extent, beyond the flush (pad=0) limits.
    flush = spark([0, 1, 2, 3, 4], bins=4)
    padded = spark([0, 1, 2, 3, 4], bins=4, pad=0.1)
    assert padded.axes[0].get_xlim()[0] < flush.axes[0].get_xlim()[0]
    assert padded.axes[0].get_xlim()[1] > flush.axes[0].get_xlim()[1]
    plt.close(flush)
    plt.close(padded)


def test_spark_color_adds_fill():
    fig = spark([1, 2, 3, 4, 5], color="steelblue")
    ax = fig.axes[0]
    assert len(ax.patches) == 1  # translucent fill rectangle
    plt.close(fig)


def test_spark_bins_none_shows_all_data():
    fig = spark([1, 2, 3, 4, 5], bins=None)
    ax = fig.axes[0]
    ticks = next(c for c in ax.collections)
    assert len(ticks.get_segments()) == 5
    plt.close(fig)


def test_spark_saves_png(tmp_path):
    out = tmp_path / "spark.png"
    fig = spark([1, 2, 3, 4, 5], path=str(out))
    assert out.exists() and out.stat().st_size > 0
    plt.close(fig)


def test_spark_transparent_by_default(tmp_path):
    import matplotlib.image as mpimg

    out = tmp_path / "spark.png"
    fig = spark([1, 2, 3, 4, 5], path=str(out))
    assert fig.patch.get_alpha() == 0.0
    img = mpimg.imread(str(out))  # H x W x 4 (RGBA)
    assert img.shape[2] == 4
    assert (img[..., 3] == 0).any()  # some fully transparent pixels
    plt.close(fig)


def test_spark_ink_runs_flush_to_every_edge(tmp_path):
    import matplotlib.image as mpimg

    out = tmp_path / "spark.png"
    # Distinct values -> no tassels, so the box's four edges define the
    # bounding box; with default pad they reach all four image borders
    # (and the half-stroke margin keeps them from being clipped). show_box=True
    # forces the complete box (these values all sit on bin edges, so the auto
    # box would gap out).
    fig = spark([0, 1, 2, 3, 4, 5], bins=5, show_box=True, path=str(out))
    ink = mpimg.imread(str(out))[..., 3] > 0.05
    assert ink[0, :].any() and ink[-1, :].any()    # top and bottom edges
    assert ink[:, 0].any() and ink[:, -1].any()    # left and right edges
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
