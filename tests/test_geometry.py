import pytest

from pavement.core import pavement_stats
from pavement._geometry import (
    bin_corners,
    bin_polygon,
    box_edge_spans,
    box_edges,
    broadcast,
    complete_color_map,
    fmt,
    hover_bins,
    hover_html,
    long_box_edges,
    normalize_rows,
    pct,
    place,
    resolve_colors,
    row_spec,
    tick_segment,
)


def _palette(n):
    return [f"c{i}" for i in range(n)]


def test_fmt_three_sig_figs():
    assert fmt(1) == "1"
    assert fmt(1234) == "1.23e+03"
    assert fmt(0.012345) == "0.0123"


def test_pct_whole_percent_and_tiny_floor():
    assert pct(1, 4) == "25%"
    assert pct(0, 8) == "0%"          # a real zero stays 0%
    assert pct(1, 1000) == "<1%"      # nonzero-but-tiny never reads as 0%


# --- row_spec -------------------------------------------------------------

def test_row_spec_bins_ticks_and_extent():
    spec = row_spec([1, 2, 3, 4, 5])  # 4 equal-mass bins, all distinct
    assert len(spec.bins) == 4
    assert len(spec.ticks) == 5
    assert (spec.value_low, spec.value_high) == (1, 5)
    assert [b.band for b in spec.bins] == [
        "p0 to p25", "p25 to p50", "p50 to p75", "p75 to p100"]
    assert [b.value_range for b in spec.bins] == [
        "1 to 2", "2 to 3", "3 to 4", "4 to 5"]
    assert [t.quantile for t in spec.ticks] == [
        "p0", "p25", "p50", "p75", "p100"]
    assert [t.value_str for t in spec.ticks] == ["1", "2", "3", "4", "5"]


def test_row_spec_value_format_formats_values_not_quantiles():
    # A custom value_format reformats the value strings (bin ranges and
    # tick values) but leaves the percentile strings untouched.
    spec = row_spec([1, 2, 3, 4, 5], value_format=lambda v: f"${v:.2f}")
    assert [b.value_range for b in spec.bins] == [
        "$1.00 to $2.00", "$2.00 to $3.00",
        "$3.00 to $4.00", "$4.00 to $5.00"]
    assert [t.value_str for t in spec.ticks] == [
        "$1.00", "$2.00", "$3.00", "$4.00", "$5.00"]
    # Percentile bands are not values, so they don't change.
    assert [b.band for b in spec.bins] == [
        "p0 to p25", "p25 to p50", "p50 to p75", "p75 to p100"]


def test_row_spec_value_format_defaults_to_fmt():
    # None (the default) is the 3-sig-fig fmt — same as omitting it.
    assert (row_spec([1, 2, 3, 4, 5], value_format=None).bins[0].value_range
            == row_spec([1, 2, 3, 4, 5]).bins[0].value_range == "1 to 2")


def test_row_spec_counts_empty_without_data():
    # No data passed -> no "X of Y values" line (the historical behavior).
    spec = row_spec([1, 2, 3, 4, 5])
    assert [b.count for b in spec.bins] == ["", "", "", ""]
    assert [t.count for t in spec.ticks] == ["", "", "", "", ""]


def test_row_spec_counts_partition_the_data():
    # 8 distinct values into 4 bins: the Type-2 quantile edges fall between
    # data points, so each interior bin holds two values and each end bin
    # one, while the min and max sit on their ticks. Every value lands in
    # exactly one bin or tick.
    data = [1, 2, 3, 4, 5, 6, 7, 8]
    spec = row_spec(pavement_stats(data, bins=4), data=data)
    # Each count line leads with the share, then "(X of Y values)".
    assert [b.count for b in spec.bins] == [
        "12% (1 of 8 values)", "25% (2 of 8 values)",
        "25% (2 of 8 values)", "12% (1 of 8 values)"]
    assert [t.count for t in spec.ticks] == [
        "12% (1 of 8 values)", "0% (0 of 8 values)", "0% (0 of 8 values)",
        "0% (0 of 8 values)", "12% (1 of 8 values)"]


def test_row_spec_counts_sum_to_total():
    # The partition invariant on messier data (repeats, weights): the per-bin
    # (strictly inside) and per-tick (exactly on) counts always cover every
    # value exactly once, so the X's sum to Y.
    data = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9]
    for bins in (None, 1, 2, 3, 4, 8):
        spec = row_spec(pavement_stats(data, bins=bins), data=data)
        # X is the integer inside "P% (X of Y values)".
        xs = [int(s.count.split("(")[1].split()[0])
              for s in (*spec.bins, *spec.ticks)]
        assert sum(xs) == len(data), bins


def test_row_spec_counts_repeats_land_on_their_tick():
    # A repeated value is one tick reaching past the box; its count is every
    # copy. The zero-width bins it straddles hold nothing.
    data = [0, 0, 0, 1, 2]
    spec = row_spec(pavement_stats(data, bins=4), data=data)
    assert {t.value: t.count for t in spec.ticks}[0] == "60% (3 of 5 values)"
    assert all(b.count == "0% (0 of 5 values)" for b in spec.bins
               if b.low == b.high)


def test_row_spec_count_noun_singular_for_one_value():
    spec = row_spec(pavement_stats([7], bins=None), data=[7])
    assert spec.ticks[0].count == "100% (1 of 1 value)"


def test_row_spec_counts_drop_missing_values():
    # Missing values are in no bin and on no tick: a None must not break the
    # internal sort, and a NaN must not corrupt the bisect counts — the total
    # is the number of *present* values, matching pavement_stats.
    data = [1.0, 2.0, None, float("nan"), 3.0, 4.0]
    spec = row_spec(pavement_stats(data, bins=2), data=data)
    counts = [s.count for s in (*spec.bins, *spec.ticks)]
    assert all("of 4 values" in c for c in counts)
    xs = [int(c.split("(")[1].split()[0]) for c in counts]
    assert sum(xs) == 4


def test_row_spec_default_reach_is_half():
    spec = row_spec([1, 2, 3, 4, 5], width=0.6)
    assert all(t.reach == 0.3 for t in spec.ticks)  # no repeats -> no tassel


def test_row_spec_repeated_value_is_one_tick_with_tassel():
    # 0 lands on several quantile edges: one tick, reaching past the box.
    spec = row_spec([0, 0, 0, 1, 2], width=0.6, tassel_extent=0.1, show_tassels=True)
    assert len(spec.ticks) == 3  # one per distinct value
    assert max(t.reach for t in spec.ticks) > 0.3
    # the repeated value's quantile reads as a span
    assert " to " in {t.value: t.quantile for t in spec.ticks}[0]


def test_row_spec_show_tassels_false_keeps_half():
    spec = row_spec([0, 0, 0, 1, 2], width=0.6, show_tassels=False)
    assert all(t.reach == 0.3 for t in spec.ticks)


def test_row_spec_single_value_has_no_bins():
    spec = row_spec([5])
    assert spec.bins == []
    assert len(spec.ticks) == 1
    assert spec.ticks[0].quantile == ""  # no bins -> no quantile band
    assert (spec.value_low, spec.value_high) == (5, 5)


# --- orientation helpers --------------------------------------------------

def test_place_swaps_with_orientation():
    assert place(2, 9, "vertical") == (2, 9)      # (perp, value) -> (x, y)
    assert place(2, 9, "horizontal") == (9, 2)


def test_tick_segment_orientation():
    assert tick_segment(1, 0.3, 5, "vertical") == (0.7, 5, 1.3, 5)
    assert tick_segment(1, 0.3, 5, "horizontal") == (5, 0.7, 5, 1.3)


def test_box_edges_two_long_sides():
    assert box_edges(1, 0.3, 0, 10, "vertical") == [
        (0.7, 0, 0.7, 10), (1.3, 0, 1.3, 10)]


def test_box_edge_spans_auto_gaps_over_empty_bins():
    # None (auto): a span only for bins holding a data point strictly inside.
    # range(9) into 4 bins puts one point inside each -> all four spans.
    spec = row_spec(pavement_stats(list(range(9)), bins=4), data=list(range(9)))
    assert box_edge_spans(spec, None) == [(b.low, b.high) for b in spec.bins]
    # Evenly spaced data sitting on its own cut points has no interior -> none.
    on_edges = row_spec(pavement_stats([0, 1, 2, 3, 4], bins=4),
                        data=[0, 1, 2, 3, 4])
    assert box_edge_spans(on_edges, None) == []


def test_box_edge_spans_true_is_one_full_span_false_is_none():
    spec = row_spec(pavement_stats([0, 1, 2, 3, 4], bins=4), data=[0, 1, 2, 3, 4])
    assert box_edge_spans(spec, True) == [(spec.value_low, spec.value_high)]
    assert box_edge_spans(spec, False) == []


def test_box_edge_spans_rug_has_no_interior():
    # A rug's bins lie between consecutive data points, so none has a strict
    # interior: the auto box is empty (it reads as a plain rug), while True
    # still forces the complete span.
    spec = row_spec(pavement_stats([1, 2, 2, 3, 5], bins=None),
                    data=[1, 2, 2, 3, 5])
    assert box_edge_spans(spec, None) == []
    assert box_edge_spans(spec, True) == [(1, 5)]


def test_long_box_edges_maps_spans_to_segments():
    # One full span -> the two long sides, same as box_edges directly.
    spec = row_spec(pavement_stats([0, 1, 2, 3, 4], bins=4), data=[0, 1, 2, 3, 4],
                    position=1, width=0.6, orientation="vertical")
    assert long_box_edges(spec, True) == box_edges(
        1, 0.3, spec.value_low, spec.value_high, "vertical")
    assert long_box_edges(spec, False) == []


def test_bin_corners_orientation():
    assert bin_corners(0, 10, 1, 0.3, "vertical") == ((0.7, 0), (1.3, 10))
    assert bin_corners(0, 10, 1, 0.3, "horizontal") == ((0, 0.7), (10, 1.3))


def test_bin_polygon_is_closed_rectangle():
    xs, ys = bin_polygon(0, 10, 1, 0.3, "vertical")
    assert len(xs) == len(ys) == 5
    assert (xs[0], ys[0]) == (xs[-1], ys[-1])  # closed path


def test_orientations_are_transposes():
    # Building through place keeps the two orientations exact transposes.
    vx, vy = bin_polygon(0, 10, 1, 0.3, "vertical")
    hx, hy = bin_polygon(0, 10, 1, 0.3, "horizontal")
    assert (vx, vy) == (hy, hx)


# --- normalize_rows -------------------------------------------------------

def test_normalize_rows_single():
    data, weights, labels, labelled = normalize_rows([1, 2, 3], None, None, None)
    assert data == [[1, 2, 3]]
    assert weights == [None]
    assert labels == [1]
    assert labelled is False


def test_normalize_rows_wide():
    data, _, labels, labelled = normalize_rows([[1, 2], [3, 4]], None, None, None)
    assert data == [[1, 2], [3, 4]]
    assert labels == [1, 2]
    assert labelled is False


def test_normalize_rows_tidy_splits_and_is_labelled():
    data, _, labels, labelled = normalize_rows(
        [1, 2, 3, 4], None, ["a", "b", "a", "b"], None)
    assert data == [[1, 3], [2, 4]]
    assert labels == ["a", "b"]
    assert labelled is True


def test_normalize_rows_labels_select_and_order_categories():
    data, _, labels, _ = normalize_rows(
        [1, 2, 3], None, ["a", "b", "c"], ["c", "a"])
    assert labels == ["c", "a"]
    assert data == [[3], [1]]


def test_normalize_rows_weights_follow_the_split():
    _, weights, _, _ = normalize_rows(
        [1, 2, 3, 4], [10, 20, 30, 40], ["a", "b", "a", "b"], None)
    assert weights == [[10, 30], [20, 40]]


def test_normalize_rows_empty():
    with pytest.raises(ValueError, match="empty"):
        normalize_rows([], None, None, None)


def test_normalize_rows_empty_category_label():
    with pytest.raises(ValueError, match="no data for category 'c'"):
        normalize_rows([1, 2, 3], None, ["a", "b", "a"], ["a", "b", "c"])


def test_normalize_rows_labels_length_mismatch():
    with pytest.raises(ValueError, match="labels"):
        normalize_rows([[1, 2], [3, 4]], None, None, ["only-one"])


# --- broadcast / resolve_colors / hover_fields / complete_color_map -------

def test_broadcast_scalar_and_sequence():
    is_int = lambda v: isinstance(v, int)  # noqa: E731
    assert broadcast(5, 3, "x", is_int) == [5, 5, 5]
    assert broadcast([1, 2, 3], 3, "x", is_int) == [1, 2, 3]


def test_broadcast_length_mismatch():
    with pytest.raises(ValueError, match="x has length"):
        broadcast([1, 2], 3, "x", lambda v: isinstance(v, int))


def test_resolve_colors_default_str_and_sequence():
    assert resolve_colors(None, 3, _palette) == ["c0", "c1", "c2"]
    assert resolve_colors("red", 3, _palette) == ["red", "red", "red"]
    assert resolve_colors(["a", "b"], 2, _palette) == ["a", "b"]


def test_resolve_colors_length_mismatch():
    with pytest.raises(ValueError, match="color"):
        resolve_colors(["a", "b"], 3, _palette)


def test_hover_html_joins_non_empty_escaped():
    # Non-empty lines, in order, joined by <br>; empties (here a dropped band)
    # fall out rather than leaving a blank row, and the content is HTML-escaped
    # while the <br> separators stay literal.
    assert hover_html("a", "1 to 2", "", "0% (0 of 5)") == \
        "a<br>1 to 2<br>0% (0 of 5)"
    assert hover_html(None, "x", "p0 to p25", "") == "x<br>p0 to p25"
    assert hover_html("a < b & c") == "a &lt; b &amp; c"


def test_hover_bins_drops_zero_width_gaps_for_a_rug():
    # A pavement draws every bin; a rug drops the zero-width "bins" at its
    # repeated values (which coincide with the tick lines), keeping just the
    # gaps between distinct values.
    spec = row_spec(pavement_stats([1, 1, 2, 2, 5], bins=None), data=[1, 1, 2, 2, 5])
    assert len(hover_bins(spec, rug=False)) == len(spec.bins)
    gaps = hover_bins(spec, rug=True)
    assert [(b.low, b.high) for b in gaps] == [(1, 2), (2, 5)]


def test_complete_color_map_fills_and_skips_used():
    # 'a' is already c0; 'b' falls back to the next palette color, skipping
    # c0 which is taken.
    assert complete_color_map({"a": "c0"}, ["a", "b"], _palette) == {
        "a": "c0", "b": "c1"}
