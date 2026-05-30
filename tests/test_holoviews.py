import pytest

hv = pytest.importorskip("holoviews")

from pavement.holoviews import (  # noqa: E402
    pavement_elements,
    plot,
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


def test_elements_box_hover_strings():
    els = pavement_elements([1, 2, 3, 4, 5], bins=4)
    # A box reads as a quantile band and a value range, "X to Y" (no dash).
    assert list(els["fill"].dimension_values("quantiles")) == [
        "0% to 25%", "25% to 50%", "50% to 75%", "75% to 100%"]
    assert list(els["fill"].dimension_values("values")) == [
        "1 to 2", "2 to 3", "3 to 4", "4 to 5"]


def test_elements_line_hover_strings():
    els = pavement_elements([1, 2, 3, 4, 5], bins=4)
    # A line (tick) reads as a single quantile and a single value.
    assert list(els["ticks"].dimension_values("quantiles")) == [
        "0%", "25%", "50%", "75%", "100%"]
    assert list(els["ticks"].dimension_values("values")) == [
        "1", "2", "3", "4", "5"]


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
    result = plot([1, 2, 3, 4, 5])
    assert isinstance(result, hv.Overlay)


def test_pavement_multiple_returns_ndoverlay_keyed_by_label():
    result = plot([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
    assert isinstance(result, hv.NdOverlay)
    assert list(result.keys()) == ["a", "b"]


def test_pavement_tidy_splits_by_category():
    result = plot([1, 2, 3, 4, 5, 6],
                      categories=["x", "x", "x", "y", "y", "y"])
    assert isinstance(result, hv.NdOverlay)
    assert list(result.keys()) == ["x", "y"]


def test_pavement_per_row_bins_mix_none_and_int():
    result = plot([[1, 2, 3, 4], [5, 6, 7, 8]], bins=[None, 2],
                      labels=["a", "b"])
    assert len(result["a"].Rectangles.I) == 3  # all data: 3 bands
    assert len(result["b"].Rectangles.I) == 2  # 2 bins


def test_pavement_renders_across_backends():
    # The same definition renders through every backend; styling resolves
    # against whichever backend is active when the plot is built (the
    # usual HoloViews pattern of choosing the backend up front).
    for backend in ("bokeh", "matplotlib", "plotly"):
        hv.extension(backend)
        obj = plot([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
        # Should not raise; returns a backend-native figure object.
        assert hv.render(obj, backend=backend) is not None


def test_pavement_bokeh_hover_is_clean_quantile_value_template():
    obj = plot([1, 2, 3, 4, 5])
    fig = hv.render(obj, backend="bokeh")
    hovers = [t for t in fig.toolbar.tools if type(t).__name__ == "HoverTool"]
    templates = {h.tooltips for h in hovers}
    # Both fills and ticks hover the same quantile/value layout, stacked
    # by line break, with no raw x0/y0/x1/y1 corners. (bokeh normalizes
    # @field to @{field}.)
    assert templates == {"@{quantiles}<br>@{values}"}


def test_pavement_bokeh_group_hover_leads_with_group():
    obj = plot([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
    fig = hv.render(obj, backend="bokeh")
    hovers = [t for t in fig.toolbar.tools if type(t).__name__ == "HoverTool"]
    # With a group, it is the first hover line.
    assert all(h.tooltips == "@{group}<br>@{quantiles}<br>@{values}"
               for h in hovers)


def test_pavement_default_colors_match_holoviews_cycle():
    # Default group colors are HoloViews' own cycle, so a category-split
    # pavement matches a default-colored main plot (e.g. a Scatter
    # NdOverlay) group-for-group, in the same key order.
    cycle = hv.Cycle().values
    obj = plot([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
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


def test_pavement_show_legend_false_empties_legend():
    fig_on = hv.render(plot([[1, 2], [3, 4]], labels=["a", "b"]),
                       backend="bokeh")
    fig_off = hv.render(
        plot([[1, 2], [3, 4]], labels=["a", "b"], show_legend=False),
        backend="bokeh")
    assert [len(le.items) for le in fig_on.legend] == [2]
    assert [len(le.items) for le in fig_off.legend] == [0]


def test_with_marginals_thins_strips_in_bokeh():
    main = hv.Scatter([(0, 0), (1, 1), (2, 2)])
    grid = hv.render(with_marginals(main, x=[0, 1, 2], y=[0, 1, 2], size=70),
                     backend="bokeh")
    figs = [c[0] for c in grid.children if c[0].__class__.__name__ == "figure"]
    # Each marginal has a 70px short dimension; the main has neither set.
    short = [min(f.frame_width or 9999, f.frame_height or 9999) for f in figs]
    assert short.count(70) == 2


def test_with_marginals_hides_marginal_legend_by_default():
    main = hv.NdOverlay({"a": hv.Scatter([(0, 0)]), "b": hv.Scatter([(1, 1)])},
                        kdims="group")
    grid = hv.render(
        with_marginals(main, y=[0, 1, 2, 3], categories=["a", "a", "b", "b"],
                       size=80),
        backend="bokeh")
    figs = [c[0] for c in grid.children if c[0].__class__.__name__ == "figure"]
    items = {(f.frame_width, f.frame_height): [len(le.items) for le in f.legend]
             for f in figs}
    assert items[(80, None)] == [0]      # marginal: no legend
    assert items[(None, None)] == [2]    # main: keeps its legend


def test_with_marginals_show_legend_override():
    main = hv.NdOverlay({"a": hv.Scatter([(0, 0)]), "b": hv.Scatter([(1, 1)])},
                        kdims="group")
    grid = hv.render(
        with_marginals(main, y=[0, 1, 2, 3], categories=["a", "a", "b", "b"],
                       size=80, show_legend=True),
        backend="bokeh")
    figs = [c[0] for c in grid.children if c[0].__class__.__name__ == "figure"]
    marg = next(f for f in figs if f.frame_width == 80)
    assert [len(le.items) for le in marg.legend] == [2]  # override re-adds it


def _axis_label_values(axis):
    overrides = getattr(axis, "major_label_overrides", None)
    if isinstance(overrides, list):
        overrides = overrides[0] if overrides else {}
    return set(dict(overrides).values()) if overrides else set()


def test_pavement_transpose_labels_swaps_tick_axis():
    # Horizontal places category ticks on y; transpose_labels moves them
    # to x (to survive a transposed display, e.g. a right marginal).
    plain = hv.render(
        plot([[1, 2], [3, 4]], labels=["a", "b"], orientation="horizontal"),
        backend="bokeh")
    swapped = hv.render(
        plot([[1, 2], [3, 4]], labels=["a", "b"], orientation="horizontal",
                 transpose_labels=True),
        backend="bokeh")
    assert _axis_label_values(plain.yaxis) == {"a", "b"}
    assert _axis_label_values(plain.xaxis) == set()
    assert _axis_label_values(swapped.xaxis) == {"a", "b"}
    assert _axis_label_values(swapped.yaxis) == set()


def test_with_marginals_right_marginal_axes_make_sense():
    # The adjoint transposes the right slot; its category ticks must end
    # up on the (horizontal) position axis, never on the shared value axis.
    main = hv.NdOverlay({"a": hv.Scatter([(0, 0)]), "b": hv.Scatter([(1, 1)])},
                        kdims="group")
    grid = hv.render(
        with_marginals(main, y=[0, 1, 2, 3], categories=["a", "a", "b", "b"],
                       size=80),
        backend="bokeh")
    right = next(c[0] for c in grid.children
                 if c[0].__class__.__name__ == "figure" and c[0].frame_width == 80)
    assert _axis_label_values(right.xaxis) == {"a", "b"}  # on position axis
    assert _axis_label_values(right.yaxis) == set()       # not on value axis


def test_with_marginals_rejects_transpose_labels_kwarg():
    with pytest.raises(ValueError, match="transpose_labels"):
        with_marginals(hv.Scatter([(0, 0)]), x=[1, 2, 3], transpose_labels=True)


def test_with_marginals_requires_some_data():
    with pytest.raises(ValueError, match="x and/or y"):
        with_marginals(hv.Scatter([(0, 0)]))


def test_with_marginals_rejects_orientation_kwarg():
    with pytest.raises(ValueError, match="orientation"):
        with_marginals(hv.Scatter([(0, 0)]), x=[1, 2, 3], orientation="vertical")


def test_pavement_plotly_adds_invisible_hover_layer():
    # plotly draws the bins/lines as non-hoverable shapes, so a hidden
    # marker layer carries the hover. It is invisible and tooltip-rich.
    hv.extension("plotly")
    try:
        fig = hv.render(plot([1, 2, 3, 4, 5, 6, 7, 8]), backend="plotly")
    finally:
        hv.extension("bokeh")
    hover = [t for t in fig["data"] if t.get("hovertemplate")]
    assert len(hover) == 1
    assert (hover[0].get("marker") or {}).get("opacity") == 0
    # Same two-line quantile/value layout as bokeh, via customdata.
    assert hover[0]["hovertemplate"] == (
        "%{customdata[0]}<br>%{customdata[1]}<extra></extra>")
    # The customdata carries the same display strings bokeh shows: the
    # first sample falls in the first bin (0% to 25%, a value range).
    assert hover[0]["customdata"][0][0] == "0% to 25%"
    assert " to " in hover[0]["customdata"][0][1]
    # A dense line of points (not one per bin) so hovering anywhere along
    # a bin works, each labelled by the bin it falls in.
    assert len(hover[0]["customdata"]) > 8


def test_with_marginals_plotly_hovers_marginals_not_scatter():
    # Each marginal (top + right) of each category gets its own hover
    # layer; the main scatter traces are left untouched.
    hv.extension("plotly")
    try:
        main = hv.NdOverlay(
            {"a": hv.Scatter([(0, 0), (1, 1)]),
             "b": hv.Scatter([(2, 2), (3, 3)])}, kdims="group")
        fig = hv.render(
            with_marginals(main, x=[0, 1, 2, 3], y=[0, 1, 2, 3],
                           categories=["a", "a", "b", "b"]),
            backend="plotly")
    finally:
        hv.extension("bokeh")
    hovered = [t for t in fig["data"] if t.get("hovertemplate")]
    plain = [t for t in fig["data"] if not t.get("hovertemplate")]
    assert len(hovered) == 4  # 2 categories x (top + right)
    assert len(plain) == 2    # the two scatter traces
    assert all((t.get("marker") or {}).get("opacity") == 0 for t in hovered)


def test_pavement_empty_data():
    with pytest.raises(ValueError, match="empty"):
        plot([])


def test_pavement_positions_length_mismatch():
    with pytest.raises(ValueError, match="positions"):
        plot([[1, 2], [3, 4]], positions=[1])


def test_pavement_bins_length_mismatch():
    with pytest.raises(ValueError, match="bins"):
        plot([[1, 2], [3, 4]], bins=[4])


def test_pavement_color_length_mismatch():
    with pytest.raises(ValueError, match="color"):
        plot([[1, 2], [3, 4]], color=["red"])


def test_pavement_labels_length_mismatch():
    with pytest.raises(ValueError, match="labels"):
        plot([[1, 2], [3, 4]], labels=["only-one"])
