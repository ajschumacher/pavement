import pytest

go = pytest.importorskip("plotly.graph_objects")

from pavement.plotly import (  # noqa: E402
    pavement_traces,
    add_pavement,
    plot,
    with_marginals,
)


def _fill_traces(fig):
    return [t for t in fig.data if t.fill == "toself"]


def _line_traces(fig):
    return [t for t in fig.data
            if t.mode == "lines" and t.fill != "toself"]


def _line_trace(traces):
    return next(t for t in traces
                if t.mode == "lines" and t.fill != "toself")


def _tick_trace(traces):
    return next(t for t in traces if t.mode == "markers")


def test_traces_are_fills_line_ticks():
    # Four bins -> four fill traces, then the visible line trace, then the
    # invisible tick-marker hover layer.
    traces = pavement_traces([1, 2, 3, 4, 5], bins=4)
    fills = [t for t in traces if t.fill == "toself"]
    lines = [t for t in traces if t.mode == "lines" and t.fill != "toself"]
    ticks = [t for t in traces if t.mode == "markers"]
    assert (len(fills), len(lines), len(ticks)) == (4, 1, 1)
    # Each box hovers anywhere inside; the tick layer is invisible.
    assert all(t.hoveron == "fills" for t in fills)
    assert ticks[0].marker.opacity == 0


def test_traces_drop_fill_when_alpha_zero():
    traces = pavement_traces([1, 2, 3, 4, 5], fill_alpha=0)
    assert all(t.fill != "toself" for t in traces)
    # Just the line trace (carrying the legend role) and the tick hover.
    assert len(traces) == 2


def test_traces_drop_hover_when_disabled():
    traces = pavement_traces([1, 2, 3, 4, 5], hover=False)
    assert [t for t in traces if t.hovertemplate] == []
    assert all(t.mode != "markers" for t in traces)  # no tick-hover layer


def _line_segment_count(trace):
    # The line trace lays each segment out as [a, b, None]; count the None
    # pen-lifts to count segments (ticks plus, when drawn, two box edges).
    return sum(1 for v in trace.x if v is None)


def test_traces_rug_drops_box_edges_by_default():
    # A rug (bins=None) keeps the value ticks but drops the two box edges,
    # so the line trace has exactly one segment per distinct value.
    rug = _line_trace(pavement_traces([1, 2, 2, 3, 5], bins=None))
    assert _line_segment_count(rug) == 4  # 4 distinct values, no box edges


def test_traces_show_box_true_keeps_box_on_rug():
    forced = _line_trace(
        pavement_traces([1, 2, 2, 3, 5], bins=None, show_box=True))
    assert _line_segment_count(forced) == 4 + 2  # ticks plus two box edges


def test_one_fill_trace_per_bin():
    # Four bins -> four fill traces, each a single closed rectangle.
    fills = [t for t in pavement_traces([1, 2, 3, 4, 5], bins=4)
             if t.fill == "toself"]
    assert len(fills) == 4
    assert all(None not in t.x for t in fills)


def test_box_hover_is_band_and_range():
    fills = [t for t in pavement_traces([1, 2, 3, 4, 5], bins=4)
             if t.fill == "toself"]
    # Each box hovers (anywhere inside) its value range, percentile band, and
    # the share of values falling strictly inside it — the same layout as the
    # other backends. With one value per quantile, every value is on a tick,
    # so the boxes hold none.
    assert fills[0].text == "1 to 2<br>p0 to p25<br>0% (0 of 5 values)"
    assert fills[-1].text == "4 to 5<br>p75 to p100<br>0% (0 of 5 values)"
    assert fills[0].hoveron == "fills"
    assert fills[0].hovertemplate == "%{text}<extra></extra>"


def test_tick_hover_is_single_quantile_and_value():
    ticks = _tick_trace(pavement_traces([1, 2, 3, 4, 5], bins=4))
    # A tick hovers its value, percentile, and the share of values falling on
    # it — the rug-style read.
    assert list(ticks.text) == [
        "1<br>p0<br>20% (1 of 5 values)", "2<br>p25<br>20% (1 of 5 values)",
        "3<br>p50<br>20% (1 of 5 values)", "4<br>p75<br>20% (1 of 5 values)",
        "5<br>p100<br>20% (1 of 5 values)"]
    assert ticks.hovertemplate == "%{text}<extra></extra>"


def test_named_hover_leads_with_name():
    traces = pavement_traces([1, 2, 3, 4, 5], name="cats")
    fill = next(t for t in traces if t.fill == "toself")
    ticks = _tick_trace(traces)
    assert fill.text.startswith("cats<br>")
    assert list(ticks.text)[0].startswith("cats<br>")


def test_value_format_customizes_value_strings():
    # A custom value_format reformats the value strings in both hover
    # layers (box ranges and tick values); the percentiles are unchanged.
    traces = pavement_traces([1, 2, 3, 4, 5], bins=4,
                             value_format=lambda v: f"${v:.2f}")
    fill = next(t for t in traces if t.fill == "toself")
    ticks = _tick_trace(traces)
    assert fill.text == "$1.00 to $2.00<br>p0 to p25<br>0% (0 of 5 values)"
    assert list(ticks.text)[0] == "$1.00<br>p0<br>20% (1 of 5 values)"


def test_value_format_threads_through_plot():
    fig = plot([1, 2, 3, 4, 5], bins=4, value_format=lambda v: f"${v:.2f}")
    fills = _fill_traces(fig)
    assert fills[0].text == "$1.00 to $2.00<br>p0 to p25<br>0% (0 of 5 values)"


def test_horizontal_swaps_axes():
    vert = next(t for t in pavement_traces([1, 2, 3, 4, 5],
                orientation="vertical") if t.fill == "toself")
    horiz = next(t for t in pavement_traces([1, 2, 3, 4, 5],
                 orientation="horizontal") if t.fill == "toself")
    # The value range lands on y for vertical, on x for horizontal.
    assert list(vert.y) == list(horiz.x)
    assert list(vert.x) == list(horiz.y)


def test_repeated_value_makes_a_whisker():
    # Heavy repetition piles several quantile edges onto one value, whose
    # tick then reaches past the box as a whisker.
    line = _line_trace(pavement_traces([0, 0, 0, 0, 1, 2, 3], bins=4,
                                       width=0.6))
    half = 0.6 / 2
    # Tick segments are the x-spans before the box edges; the widest one
    # exceeds the box width.
    reaches = []
    xs = list(line.x)
    for i in range(0, len(xs) - 1, 3):
        if xs[i] is not None and xs[i + 1] is not None:
            reaches.append(abs(xs[i + 1] - xs[i]) / 2)
    assert max(reaches) > half


def test_bins_none_is_a_rug():
    traces = pavement_traces([1, 2, 3, 4, 5], bins=None)
    fills = [t for t in traces if t.fill == "toself"]
    ticks = _tick_trace(traces)
    assert len(fills) == 4              # one band between each pair of points
    assert len(list(ticks.text)) == 5  # a tick hover at every data point


def test_pavement_single_returns_figure():
    fig = plot([1, 2, 3, 4, 5])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 6  # 4 bin fills + line + tick hover
    assert fig.layout.showlegend is False  # anonymous single row


def test_pavement_multiple_gets_legend_per_row():
    fig = plot([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
    assert fig.layout.showlegend is True
    legend_names = [t.name for t in fig.data if t.showlegend]
    assert legend_names == ["a", "b"]


def test_pavement_tidy_splits_by_category():
    fig = plot([1, 2, 3, 4, 5, 6],
                   categories=["x", "x", "x", "y", "y", "y"])
    names = sorted({t.name for t in fig.data if t.name})
    assert names == ["x", "y"]


def test_pavement_per_row_bins_mix_none_and_int():
    fig = plot([[1, 2, 3, 4], [5, 6, 7, 8]], bins=[None, 2],
                   labels=["a", "b"])
    fills = _fill_traces(fig)
    assert sum(1 for t in fills if t.name == "a") == 3  # all data: 3 bands
    assert sum(1 for t in fills if t.name == "b") == 2  # 2 bins


def test_pavement_labels_tick_the_position_axis():
    fig = plot([[1, 2], [3, 4]], labels=["a", "b"])
    assert list(fig.layout.xaxis.ticktext) == ["a", "b"]
    assert list(fig.layout.xaxis.tickvals) == [1, 2]


def test_pavement_anonymous_row_has_no_position_ticks():
    fig = plot([1, 2, 3, 4, 5])
    assert fig.layout.xaxis.showticklabels is False


def test_pavement_horizontal_labels_value_axis_on_x():
    fig = plot([1, 2, 3, 4, 5], orientation="horizontal",
                   value_label="height")
    assert fig.layout.xaxis.title.text == "height"


def test_pavement_default_colors_match_plotly_cycle():
    from plotly.colors import qualitative
    fig = plot([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
    line_colors = [t.line.color for t in _line_traces(fig)]
    assert line_colors[:2] == list(qualitative.Plotly[:2])


def test_add_pavement_targets_subplot_cell():
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=1, cols=2)
    add_pavement(fig, [1, 2, 3, 4, 5], row=1, col=2)
    # Traces in cell (1,2) reference the second x-axis.
    assert all(t.xaxis == "x2" for t in fig.data)


def _main_axes(fig):
    """The (xaxis, yaxis) of the central scatter (the visible markers)."""
    t = next(t for t in fig.data
             if t.mode == "markers" and t.marker.opacity != 0)
    return t.xaxis, t.yaxis


def _shares(fig, trace_axis, main_axis):
    """Whether *trace_axis* is, or is matched to, *main_axis*."""
    if trace_axis == main_axis:
        return True
    key = trace_axis.replace("x", "xaxis").replace("y", "yaxis")
    return fig.layout[key].matches == main_axis


def _has_x_marginal(fig, main_x, main_y):
    # A marginal trace in the same column as the main cell (shares its x)
    # but in a different row (its y differs) — the strip on top.
    return any(_shares(fig, t.xaxis, main_x) and t.yaxis != main_y
               for t in fig.data)


def _has_y_marginal(fig, main_x, main_y):
    return any(_shares(fig, t.yaxis, main_y) and t.xaxis != main_x
               for t in fig.data)


def test_with_marginals_places_top_and_right():
    main = go.Figure(go.Scatter(x=[0, 1, 2], y=[0, 1, 2], mode="markers"))
    fig = with_marginals(main, x=[0, 1, 2], y=[0, 1, 2])
    main_x, main_y = _main_axes(fig)
    assert _has_x_marginal(fig, main_x, main_y)  # x-marginal shares main x
    assert _has_y_marginal(fig, main_x, main_y)  # y-marginal shares main y


def test_with_marginals_x_only_skips_right():
    main = go.Figure(go.Scatter(x=[0, 1], y=[0, 1], mode="markers"))
    fig = with_marginals(main, x=[0, 1, 2])
    main_x, main_y = _main_axes(fig)
    assert _has_x_marginal(fig, main_x, main_y)
    assert not _has_y_marginal(fig, main_x, main_y)


def test_with_marginals_y_only_skips_top():
    main = go.Figure(go.Scatter(x=[0, 1], y=[0, 1], mode="markers"))
    fig = with_marginals(main, y=[0, 1, 2])
    main_x, main_y = _main_axes(fig)
    assert _has_y_marginal(fig, main_x, main_y)
    assert not _has_x_marginal(fig, main_x, main_y)


def test_with_marginals_matches_main_colors():
    # The marginal of a category is colored like the main trace of the
    # same name, so a colored scatter and its marginals match.
    main = go.Figure([
        go.Scatter(x=[0], y=[0], mode="markers", name="a",
                   marker=dict(color="#112233")),
        go.Scatter(x=[1], y=[1], mode="markers", name="b",
                   marker=dict(color="#445566")),
    ])
    fig = with_marginals(main, y=[0, 1, 2, 3],
                         categories=["a", "a", "b", "b"])
    # The fill is the scatter's color at fill_alpha opacity (the zero-width
    # line lets trace opacity dim the fill alone), so the marginals match
    # the scatter group for group without baking an alpha into the color.
    fills = {t.name: (t.fillcolor, t.opacity) for t in _fill_traces(fig)}
    assert fills["a"] == ("#112233", 0.3)
    assert fills["b"] == ("#445566", 0.3)


def test_with_marginals_carries_axis_titles():
    main = go.Figure(go.Scatter(x=[0, 1], y=[0, 1], mode="markers"))
    main.update_xaxes(title_text="width").update_yaxes(title_text="height")
    fig = with_marginals(main, x=[0, 1], y=[0, 1])
    main_x = next(t for t in fig.data if t.mode == "markers"
                  and t.marker.opacity != 0).xaxis
    assert fig.layout[main_x.replace("x", "xaxis")].title.text == "width"


def test_with_marginals_requires_some_data():
    with pytest.raises(ValueError, match="x and/or y"):
        with_marginals(go.Figure())


def test_with_marginals_rejects_managed_kwargs():
    for kw in ("orientation", "color", "show_legend"):
        with pytest.raises(ValueError, match=kw):
            with_marginals(go.Figure(), x=[1, 2, 3], **{kw: object()})


def test_pavement_renders_to_html():
    fig = plot([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
    assert len(fig.to_html()) > 0


def test_with_marginals_renders_to_html():
    main = go.Figure(go.Scatter(x=[0, 1, 2], y=[0, 1, 2], mode="markers"))
    fig = with_marginals(main, x=[0, 1, 2], y=[0, 1, 2])
    assert len(fig.to_html()) > 0


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
