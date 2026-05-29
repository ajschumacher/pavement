import pytest

hv = pytest.importorskip("holoviews")

from pavement.holoviews import (  # noqa: E402
    pavement,
    pavement_elements,
    with_marginals,
)


@pytest.fixture(autouse=True)
def _bokeh_backend():
    # A backend must be active for .opts() to resolve option names.
    hv.extension("bokeh")


def test_elements_returns_fill_ticks_box():
    els = pavement_elements([1, 2, 3, 4, 5])
    assert set(els) == {"fill", "ticks", "box"}
    assert isinstance(els["fill"], hv.Rectangles)
    assert isinstance(els["ticks"], hv.Segments)
    assert isinstance(els["box"], hv.Segments)
    assert len(els["fill"]) == 4   # 4 bins -> 4 rectangles
    assert len(els["ticks"]) == 5  # one per distinct quantile value
    assert len(els["box"]) == 2    # two long edges


def test_elements_one_tick_per_distinct_value_with_whisker():
    # Heavy repetition collapses several quantile edges onto one value.
    els = pavement_elements([0, 0, 0, 0, 1, 2, 3], bins=4)
    ticks = els["ticks"]
    # 5 quantile edges but 0 repeats -> fewer than 5 distinct ticks, each
    # drawn once (no separate whisker element stacked on a bin border).
    assert len(ticks) < 5
    half = 0.6 / 2
    # The repeated value's tick reaches past the box width (a whisker).
    reaches = [abs(x1 - x0) / 2 for x0, x1 in
               zip(ticks.dimension_values("x0"), ticks.dimension_values("x1"))]
    assert max(reaches) > half


def test_elements_band_vdim_reports_quantile_span():
    els = pavement_elements([1, 2, 3, 4, 5], bins=4)
    assert list(els["fill"].dimension_values("band")) == [
        "0%–25%", "25%–50%", "50%–75%", "75%–100%"]


def test_elements_tick_level_vdim_reports_cumulative_quantile():
    els = pavement_elements([1, 2, 3, 4, 5], bins=4)
    assert list(els["ticks"].dimension_values("level")) == [
        "0%", "25%", "50%", "75%", "100%"]


def test_elements_horizontal_swaps_axes():
    vert = pavement_elements([1, 2, 3, 4, 5], orientation="vertical")
    horiz = pavement_elements([1, 2, 3, 4, 5], orientation="horizontal")
    # The value range lands on y for vertical, on x for horizontal.
    assert list(vert["fill"].dimension_values("y0")) == list(
        horiz["fill"].dimension_values("x0"))


def test_elements_bins_none_is_a_rug():
    els = pavement_elements([1, 2, 3, 4, 5], bins=None)
    assert len(els["fill"]) == 4   # one band between each pair of points
    assert len(els["ticks"]) == 5  # a tick at every data point


def test_pavement_single_returns_overlay():
    result = pavement([1, 2, 3, 4, 5])
    assert isinstance(result, hv.Overlay)


def test_pavement_multiple_returns_ndoverlay_keyed_by_label():
    result = pavement([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
    assert isinstance(result, hv.NdOverlay)
    assert list(result.keys()) == ["a", "b"]


def test_pavement_tidy_splits_by_category():
    result = pavement([1, 2, 3, 4, 5, 6],
                      categories=["x", "x", "x", "y", "y", "y"])
    assert isinstance(result, hv.NdOverlay)
    assert list(result.keys()) == ["x", "y"]


def test_pavement_per_row_bins_mix_none_and_int():
    result = pavement([[1, 2, 3, 4], [5, 6, 7, 8]], bins=[None, 2],
                      labels=["a", "b"])
    assert len(result["a"].Rectangles.I) == 3  # all data: 3 bands
    assert len(result["b"].Rectangles.I) == 2  # 2 bins


def test_pavement_renders_across_backends():
    # The same definition renders through every backend; styling resolves
    # against whichever backend is active when the plot is built (the
    # usual HoloViews pattern of choosing the backend up front).
    for backend in ("bokeh", "matplotlib", "plotly"):
        hv.extension(backend)
        obj = pavement([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
        # Should not raise; returns a backend-native figure object.
        assert hv.render(obj, backend=backend) is not None


def test_pavement_bokeh_has_hover_with_clean_tooltips():
    obj = pavement([1, 2, 3, 4, 5])
    fig = hv.render(obj, backend="bokeh")
    hovers = [t for t in fig.toolbar.tools if type(t).__name__ == "HoverTool"]
    fieldsets = [[name for name, _ in h.tooltips] for h in hovers]
    # The fills hover the band/range; the ticks hover the value/level.
    # Neither dumps the raw x0/y0/x1/y1 corners.
    assert ["band", "low", "high"] in fieldsets
    assert ["value", "level"] in fieldsets
    assert not any("x0" in fields for fields in fieldsets)


def test_pavement_default_colors_match_holoviews_cycle():
    # Default group colors are HoloViews' own cycle, so a category-split
    # pavement matches a default-colored main plot (e.g. a Scatter
    # NdOverlay) group-for-group, in the same key order.
    cycle = hv.Cycle().values
    obj = pavement([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
    fig = hv.render(obj, backend="bokeh")
    fills = [r.glyph.fill_color for r in fig.renderers
             if getattr(r, "glyph", None) is not None
             and getattr(r.glyph, "fill_color", None)]
    assert fills[:2] == cycle[:2]


def test_with_marginals_places_top_and_right():
    main = hv.Scatter([(0, 0), (1, 1), (2, 2)])
    layout = with_marginals(main, x=[0, 1, 2], y=[0, 1, 2])
    assert isinstance(layout, hv.AdjointLayout)
    assert layout.main is main
    assert isinstance(layout.right, hv.Overlay)  # y-marginal
    assert isinstance(layout.top, hv.Overlay)    # x-marginal


def test_with_marginals_x_only_uses_top_slot():
    main = hv.Scatter([(0, 0), (1, 1)])
    layout = with_marginals(main, x=[0, 1, 2])
    assert isinstance(layout.top, hv.Overlay)     # x lands on top
    assert isinstance(layout.right, hv.Empty)     # right held open, not used


def test_with_marginals_y_only_uses_right_slot():
    main = hv.Scatter([(0, 0), (1, 1)])
    layout = with_marginals(main, y=[0, 1, 2])
    assert isinstance(layout.right, hv.Overlay)
    assert layout.top is None


def test_with_marginals_builds_horizontal_marginals():
    # Both slots are built horizontal (value on the x kdim) — the
    # orientation that makes HoloViews' adjoint align each marginal with
    # the main plot's shared axis instead of squishing it.
    main = hv.Scatter([(0, 0), (1, 5), (2, 10)])
    layout = with_marginals(main, x=[0, 1, 2], y=[0, 5, 10])
    right_x = (list(layout.right.Rectangles.I.dimension_values("x0"))
               + list(layout.right.Rectangles.I.dimension_values("x1")))
    top_x = (list(layout.top.Rectangles.I.dimension_values("x0"))
             + list(layout.top.Rectangles.I.dimension_values("x1")))
    assert (min(right_x), max(right_x)) == (0, 10)  # y-data spans the x kdim
    assert (min(top_x), max(top_x)) == (0, 2)       # x-data spans the x kdim


def test_with_marginals_renders_across_backends():
    main = hv.Scatter([(0, 0), (1, 1), (2, 2)])
    for backend in ("bokeh", "matplotlib", "plotly"):
        hv.extension(backend)
        layout = with_marginals(main, x=[0, 1, 2], y=[0, 1, 2])
        assert hv.render(layout, backend=backend) is not None


def test_with_marginals_requires_some_data():
    with pytest.raises(ValueError, match="x and/or y"):
        with_marginals(hv.Scatter([(0, 0)]))


def test_with_marginals_rejects_orientation_kwarg():
    with pytest.raises(ValueError, match="orientation"):
        with_marginals(hv.Scatter([(0, 0)]), x=[1, 2, 3], orientation="vertical")


def test_pavement_empty_data():
    with pytest.raises(ValueError, match="empty"):
        pavement([])


def test_pavement_positions_length_mismatch():
    with pytest.raises(ValueError, match="positions"):
        pavement([[1, 2], [3, 4]], positions=[1])


def test_pavement_bins_length_mismatch():
    with pytest.raises(ValueError, match="bins"):
        pavement([[1, 2], [3, 4]], bins=[4])


def test_pavement_color_length_mismatch():
    with pytest.raises(ValueError, match="color"):
        pavement([[1, 2], [3, 4]], color=["red"])


def test_pavement_labels_length_mismatch():
    with pytest.raises(ValueError, match="labels"):
        pavement([[1, 2], [3, 4]], labels=["only-one"])
