import pytest

from pavement._geometry import (
    bin_corners,
    bin_polygon,
    box_edges,
    broadcast,
    complete_color_map,
    fmt,
    hover_fields,
    normalize_rows,
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


# --- row_spec -------------------------------------------------------------

def test_row_spec_bins_ticks_and_extent():
    spec = row_spec([1, 2, 3, 4, 5])  # 4 equal-mass bins, all distinct
    assert len(spec.bins) == 4
    assert len(spec.ticks) == 5
    assert (spec.value_low, spec.value_high) == (1, 5)
    assert [b.band for b in spec.bins] == [
        "0% to 25%", "25% to 50%", "50% to 75%", "75% to 100%"]
    assert [b.value_range for b in spec.bins] == [
        "1 to 2", "2 to 3", "3 to 4", "4 to 5"]
    assert [t.quantile for t in spec.ticks] == [
        "0%", "25%", "50%", "75%", "100%"]
    assert [t.value_str for t in spec.ticks] == ["1", "2", "3", "4", "5"]


def test_row_spec_value_format_formats_values_not_quantiles():
    # A custom value_format reformats the value strings (bin ranges and
    # tick values) but leaves the quantile/percent strings untouched.
    spec = row_spec([1, 2, 3, 4, 5], value_format=lambda v: f"${v:.2f}")
    assert [b.value_range for b in spec.bins] == [
        "$1.00 to $2.00", "$2.00 to $3.00",
        "$3.00 to $4.00", "$4.00 to $5.00"]
    assert [t.value_str for t in spec.ticks] == [
        "$1.00", "$2.00", "$3.00", "$4.00", "$5.00"]
    # Quantile bands are percentages, not values, so they don't change.
    assert [b.band for b in spec.bins] == [
        "0% to 25%", "25% to 50%", "50% to 75%", "75% to 100%"]


def test_row_spec_value_format_defaults_to_fmt():
    # None (the default) is the 3-sig-fig fmt — same as omitting it.
    assert (row_spec([1, 2, 3, 4, 5], value_format=None).bins[0].value_range
            == row_spec([1, 2, 3, 4, 5]).bins[0].value_range == "1 to 2")


def test_row_spec_default_reach_is_half():
    spec = row_spec([1, 2, 3, 4, 5], width=0.6)
    assert all(t.reach == 0.3 for t in spec.ticks)  # no repeats -> no whisker


def test_row_spec_repeated_value_is_one_tick_with_whisker():
    # 0 lands on several quantile edges: one tick, reaching past the box.
    spec = row_spec([0, 0, 0, 1, 2], width=0.6, whisker_extent=0.1)
    assert len(spec.ticks) == 3  # one per distinct value
    assert max(t.reach for t in spec.ticks) > 0.3
    # the repeated value's quantile reads as a span
    assert " to " in {t.value: t.quantile for t in spec.ticks}[0]


def test_row_spec_show_whiskers_false_keeps_half():
    spec = row_spec([0, 0, 0, 1, 2], width=0.6, show_whiskers=False)
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


def test_hover_fields():
    assert hover_fields(False) == ["quantiles", "values"]
    assert hover_fields(True) == ["group", "quantiles", "values"]


def test_complete_color_map_fills_and_skips_used():
    # 'a' is already c0; 'b' falls back to the next palette color, skipping
    # c0 which is taken.
    assert complete_color_map({"a": "c0"}, ["a", "b"], _palette) == {
        "a": "c0", "b": "c1"}
