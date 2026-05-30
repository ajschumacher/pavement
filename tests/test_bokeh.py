import pytest

pytest.importorskip("bokeh")

from bokeh.plotting import figure  # noqa: E402
from bokeh.models import HoverTool, Legend, GridPlot  # noqa: E402
from bokeh.embed import file_html  # noqa: E402
from bokeh.resources import CDN  # noqa: E402

from pavement.bokeh import (  # noqa: E402
    pavement_glyphs,
    add_pavement,
    pavement,
    with_marginals,
)


def _quads(fig):
    return [r for r in fig.renderers if type(r.glyph).__name__ == "Quad"]


def _segments(fig):
    return [r for r in fig.renderers if type(r.glyph).__name__ == "Segment"]


def _tick_segments(fig):
    # Tick segments carry hover columns; the box edges don't.
    return [r for r in _segments(fig) if "quantiles" in r.data_source.data]


def _box_segments(fig):
    return [r for r in _segments(fig) if "quantiles" not in r.data_source.data]


def test_glyphs_are_fills_ticks_box():
    # One row -> one quad renderer (its bins), one tick segment, one box
    # segment.
    fig = figure()
    rends = pavement_glyphs(fig, [1, 2, 3, 4, 5], bins=4)
    assert type(rends["fills"].glyph).__name__ == "Quad"
    assert type(rends["ticks"].glyph).__name__ == "Segment"
    assert type(rends["box"].glyph).__name__ == "Segment"
    # Four bins land in the fill source as four quads.
    assert len(rends["fills"].data_source.data["left"]) == 4


def test_glyphs_drop_fill_when_alpha_zero():
    fig = figure()
    rends = pavement_glyphs(fig, [1, 2, 3, 4, 5], fill_alpha=0)
    assert rends["fills"] is None
    assert _quads(fig) == []


def test_fill_hover_is_band_and_range():
    fig = figure()
    rends = pavement_glyphs(fig, [1, 2, 3, 4, 5], bins=4)
    data = rends["fills"].data_source.data
    # Each box carries its quantile band and value range, the same layout as
    # the other backends.
    assert data["quantiles"][0] == "0% to 25%"
    assert data["values"][0] == "1 to 2"
    assert data["quantiles"][-1] == "75% to 100%"
    assert data["values"][-1] == "4 to 5"


def test_tick_hover_is_single_quantile_and_value():
    fig = figure()
    rends = pavement_glyphs(fig, [1, 2, 3, 4, 5], bins=4)
    data = rends["ticks"].data_source.data
    assert list(data["quantiles"]) == ["0%", "25%", "50%", "75%", "100%"]
    assert list(data["values"]) == ["1", "2", "3", "4", "5"]


def test_named_glyphs_carry_group():
    fig = figure()
    rends = pavement_glyphs(fig, [1, 2, 3, 4, 5], name="cats")
    assert rends["fills"].data_source.data["group"][0] == "cats"
    assert rends["ticks"].data_source.data["group"][0] == "cats"
    assert rends["fills"].name == "cats"


def test_horizontal_swaps_axes():
    vfig, hfig = figure(), figure()
    vert = pavement_glyphs(vfig, [1, 2, 3, 4, 5], orientation="vertical")
    horiz = pavement_glyphs(hfig, [1, 2, 3, 4, 5], orientation="horizontal")
    v, h = vert["fills"].data_source.data, horiz["fills"].data_source.data
    # The value range lands on bottom/top (y) for vertical, left/right (x)
    # for horizontal; the position lands on the other pair.
    assert list(v["bottom"]) == list(h["left"])
    assert list(v["top"]) == list(h["right"])
    assert list(v["left"]) == list(h["bottom"])


def test_repeated_value_makes_a_whisker():
    # Heavy repetition piles several quantile edges onto one value, whose
    # tick reaches past the box as a whisker.
    fig = figure()
    rends = pavement_glyphs(fig, [0, 0, 0, 0, 1, 2, 3], bins=4, width=0.6)
    data = rends["ticks"].data_source.data
    half = 0.6 / 2
    # Vertical ticks are horizontal segments; their half-span is x1 - center.
    reaches = [(x1 - x0) / 2 for x0, x1 in zip(data["x0"], data["x1"])]
    assert max(reaches) > half


def test_bins_none_is_a_rug():
    fig = figure()
    rends = pavement_glyphs(fig, [1, 2, 3, 4, 5], bins=None)
    # One band between each pair of points; a tick at every data point.
    assert len(rends["fills"].data_source.data["left"]) == 4
    assert len(rends["ticks"].data_source.data["x0"]) == 5


def test_pavement_single_returns_figure():
    fig = pavement([1, 2, 3, 4, 5])
    assert isinstance(fig, figure)
    assert len(_quads(fig)) == 1            # one row's bins
    assert len(_tick_segments(fig)) == 1
    assert fig.select(Legend) == []         # anonymous single row, no legend


def test_pavement_has_hover_by_default():
    fig = pavement([1, 2, 3, 4, 5])
    hovers = fig.select(HoverTool)
    assert len(hovers) == 1
    assert hovers[0].tooltips == "@quantiles<br>@values"


def test_pavement_hover_can_be_disabled():
    fig = pavement([1, 2, 3, 4, 5], hover=False)
    assert fig.select(HoverTool) == []


def test_pavement_multiple_gets_legend_per_row():
    fig = pavement([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
    legend = fig.select(Legend)[0]
    assert [item.label.value for item in legend.items] == ["a", "b"]
    assert legend.click_policy == "hide"


def test_pavement_legend_toggles_whole_row():
    # Each legend entry hides the row's fill, ticks, and box together.
    fig = pavement([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
    legend = fig.select(Legend)[0]
    kinds = sorted(type(r.glyph).__name__ for r in legend.items[0].renderers)
    assert kinds == ["Quad", "Segment", "Segment"]


def test_pavement_named_hover_leads_with_group():
    fig = pavement([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
    assert fig.select(HoverTool)[0].tooltips == "@group<br>@quantiles<br>@values"


def test_pavement_tidy_splits_by_category():
    fig = pavement([1, 2, 3, 4, 5, 6],
                   categories=["x", "x", "x", "y", "y", "y"])
    names = sorted({q.name for q in _quads(fig)})
    assert names == ["x", "y"]


def test_pavement_per_row_bins_mix_none_and_int():
    fig = pavement([[1, 2, 3, 4], [5, 6, 7, 8]], bins=[None, 2],
                   labels=["a", "b"])
    by_name = {q.name: q.data_source.data["left"] for q in _quads(fig)}
    assert len(by_name["a"]) == 3   # all data: 3 bands
    assert len(by_name["b"]) == 2   # 2 bins


def test_pavement_labels_tick_the_position_axis():
    fig = pavement([[1, 2], [3, 4]], labels=["a", "b"])
    assert fig.xaxis[0].major_label_overrides == {1: "a", 2: "b"}
    assert list(fig.xaxis[0].ticker.ticks) == [1, 2]


def test_pavement_anonymous_row_has_no_position_ticks():
    fig = pavement([1, 2, 3, 4, 5])
    assert list(fig.xaxis[0].ticker.ticks) == []


def test_pavement_horizontal_labels_value_axis_on_x():
    fig = pavement([1, 2, 3, 4, 5], orientation="horizontal",
                   value_label="height")
    assert fig.xaxis[0].axis_label == "height"


def test_pavement_vertical_labels_value_axis_on_y():
    fig = pavement([1, 2, 3, 4, 5], value_label="height")
    assert fig.yaxis[0].axis_label == "height"


def test_pavement_default_colors_match_category10():
    from bokeh.palettes import Category10
    fig = pavement([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
    colors = [q.glyph.fill_color for q in _quads(fig)]
    assert colors[:2] == list(Category10[10][:2])


def test_pavement_forwards_figure_kwargs():
    fig = pavement([1, 2, 3, 4, 5], width=321, height=234)
    assert (fig.width, fig.height) == (321, 234)


def test_add_pavement_draws_onto_given_figure():
    fig = figure()
    add_pavement(fig, [1, 2, 3, 4, 5])
    assert len(_quads(fig)) == 1


def _grid_figures(layout):
    return [child for child, _, _ in layout.children
            if isinstance(child, figure)]


def test_with_marginals_returns_gridplot():
    main = figure(width=300, height=300)
    main.scatter([0, 1, 2], [0, 1, 2])
    layout = with_marginals(main, x=[0, 1, 2], y=[0, 1, 2])
    assert isinstance(layout, GridPlot)


def test_with_marginals_places_top_and_right():
    main = figure(width=300, height=300)
    main.scatter([0, 1, 2], [0, 1, 2])
    layout = with_marginals(main, x=[0, 1, 2], y=[0, 1, 2])
    figs = _grid_figures(layout)
    # The top strip shares the scatter's x range; the right strip its y range.
    assert any(f is not main and f.x_range is main.x_range for f in figs)
    assert any(f is not main and f.y_range is main.y_range for f in figs)


def test_with_marginals_x_only_skips_right():
    main = figure(width=300, height=300)
    main.scatter([0, 1], [0, 1])
    layout = with_marginals(main, x=[0, 1, 2])
    figs = [f for f in _grid_figures(layout) if f is not main]
    assert len(figs) == 1
    assert figs[0].x_range is main.x_range


def test_with_marginals_y_only_skips_top():
    main = figure(width=300, height=300)
    main.scatter([0, 1], [0, 1])
    layout = with_marginals(main, y=[0, 1, 2])
    figs = [f for f in _grid_figures(layout) if f is not main]
    assert len(figs) == 1
    assert figs[0].y_range is main.y_range


def test_with_marginals_matches_main_colors():
    # The marginal of a category is colored like the main renderer of the
    # same name, so a colored scatter and its marginals match.
    main = figure(width=300, height=300)
    main.scatter([0], [0], name="a", fill_color="#112233")
    main.scatter([1], [1], name="b", fill_color="#445566")
    layout = with_marginals(main, y=[0, 1, 2, 3],
                            categories=["a", "a", "b", "b"])
    right = next(f for f in _grid_figures(layout)
                 if f is not main and f.y_range is main.y_range)
    colors = {q.name: q.glyph.fill_color for q in _quads(right)}
    assert colors == {"a": "#112233", "b": "#445566"}


def test_with_marginals_requires_some_data():
    with pytest.raises(ValueError, match="x and/or y"):
        with_marginals(figure())


def test_with_marginals_rejects_managed_kwargs():
    for kw in ("orientation", "color", "show_legend"):
        with pytest.raises(ValueError, match=kw):
            with_marginals(figure(), x=[1, 2, 3], **{kw: object()})


def test_pavement_renders_to_html():
    fig = pavement([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
    assert len(file_html(fig, CDN)) > 0


def test_with_marginals_renders_to_html():
    main = figure(width=300, height=300)
    main.scatter([0, 1, 2], [0, 1, 2])
    layout = with_marginals(main, x=[0, 1, 2], y=[0, 1, 2])
    assert len(file_html(layout, CDN)) > 0


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
