import re
import xml.dom.minidom as minidom

import pytest

# The SVG backend is pure-Python (no optional plotting dependency), so it
# imports unconditionally — no importorskip here.
from pavement.svg import spark


def _wellformed(markup):
    minidom.parseString(markup)  # raises on malformed XML


def test_spark_returns_svg_string():
    out = spark([1, 2, 3, 4, 5])
    assert isinstance(out, str)
    assert out.startswith("<svg") and out.rstrip().endswith("</svg>")


@pytest.mark.parametrize("kwargs", [
    {},
    {"bins": 10},
    {"bins": None},
    {"color": "steelblue"},
    {"color": "teal", "bins": None},
    {"orientation": "vertical"},
    {"hover": False},
    {"highlight": False},
    {"inline": False},
])
def test_spark_is_wellformed_xml(kwargs):
    _wellformed(spark([1, 2, 3, 4, 5, 6, 7, 8], **kwargs))


def test_spark_binned_has_one_rect_per_bin():
    assert spark([1, 2, 3, 4, 5], bins=4).count('class="pvbin"') == 4
    assert spark([1, 2, 3, 4, 5], bins=7).count('class="pvbin"') == 7


def test_spark_rug_gap_boxes_hover_the_spaces_between_values():
    # bins=None is a rug, but the spaces between its distinct values are still
    # hover targets (like a pavement's bins): one box per gap, each carrying a
    # value range and a zero interior count — an easy target where a value line
    # is a thin one. Five distinct values -> four gaps.
    out = spark([1, 2, 3, 4, 5], bins=None)
    assert out.count('class="pvbin"') == 4
    gaps = re.findall(r'<rect class="pvbin".*?<title>(.*?)</title>', out, re.S)
    assert gaps == ["1 to 2\np0 to p25\n0% (0 of 5 values)",
                    "2 to 3\np25 to p50\n0% (0 of 5 values)",
                    "3 to 4\np50 to p75\n0% (0 of 5 values)",
                    "4 to 5\np75 to p100\n0% (0 of 5 values)"]


def test_spark_rug_gap_boxes_skip_repeated_values():
    # The zero-width "bins" at a rug's repeated values coincide with the tick
    # lines, so they are dropped: a heavily repeated, two-distinct-value rug
    # has just the one gap box between its two values, not one per point.
    assert spark([1] * 40 + [2] * 40, bins=None).count('class="pvbin"') == 1


def test_spark_rug_drops_box_edges_by_default():
    # A rug reads like a plain rug: no long box edges by default, just the
    # per-value tick marks.
    rug = spark([1, 2, 2, 3, 5], bins=None)
    forced = spark([1, 2, 2, 3, 5], bins=None, show_box=True)
    # show_box=True forces the complete box, adding exactly its two long edges
    # even for a rug (whose bins have no strict interior of their own).
    assert forced.count("<line") == rug.count("<line") + 2


def test_spark_show_box_true_forces_complete_box():
    # An explicit show_box=True draws the two long edges unbroken across the
    # whole value range, even where the default would leave a gap: data sitting
    # entirely on bin boundaries gets no edges by default but two full edges
    # when forced.
    on_edges = spark([0, 1, 2, 3, 4], bins=4, hover=False)
    forced = spark([0, 1, 2, 3, 4], bins=4, hover=False, show_box=True)
    assert forced.count("<line") == on_edges.count("<line") + 2


def test_spark_binned_box_edges_close_over_interior_bins():
    # Each bin draws its two long edges only over itself, and only when data
    # falls strictly inside it. With every bin populated (one interior point
    # apiece) that is eight edge segments on top of the ticks; show_box=False
    # drops all eight.
    full = spark(list(range(9)), bins=4, hover=False)
    no_box = spark(list(range(9)), bins=4, hover=False, show_box=False)
    assert full.count("<line") == no_box.count("<line") + 8


def test_spark_box_edges_gap_where_bin_has_no_interior():
    # Evenly spaced data binned at its own cut points has every point sitting
    # on a bin boundary, so no bin has an interior -> no box edges are drawn,
    # leaving only the value ticks (the gaps reveal mass clumped on the lines).
    on_edges = spark([0, 1, 2, 3, 4], bins=4, hover=False)
    no_box = spark([0, 1, 2, 3, 4], bins=4, hover=False, show_box=False)
    assert on_edges.count("<line") == no_box.count("<line")


def test_spark_horizontal_viewbox():
    assert 'viewBox="0 0 140 30"' in spark([1, 2, 3])


def test_spark_vertical_viewbox():
    assert 'viewBox="0 0 30 140"' in spark([1, 2, 3], orientation="vertical")


def test_spark_default_lines_use_currentcolor():
    assert 'stroke="currentColor"' in spark([1, 2, 3])


def test_spark_color_fills_and_tints():
    out = spark([1, 2, 3, 4, 5], color="#c0392b")
    assert 'fill="#c0392b"' in out          # bin fill
    assert 'stroke="#c0392b"' in out         # lines tinted to match


def test_spark_line_color_overrides_color_for_strokes():
    out = spark([1, 2, 3, 4, 5], color="red", line_color="black")
    assert 'stroke="black"' in out
    assert 'fill="red"' in out               # fill still uses color


def test_spark_colored_small_rug_fills_its_gap_boxes():
    # A small rug's gap boxes carry the fill (like a pavement's bins): the
    # color tints each, so the box reads filled while staying a hover target.
    out = spark([1, 2, 3, 4, 5], bins=None, color="teal")
    assert out.count('class="pvbin"') == 4   # one per gap between values
    assert 'fill="teal"' in out


def test_spark_colored_dense_rug_draws_single_fill():
    # A dense rug (no gap boxes, just the summary) still fills its box as one
    # background rect when a color is requested.
    out = spark(list(range(50)), bins=None, color="teal")
    assert out.count('class="pvbin"') == 0
    assert 'fill="teal"' in out              # one background fill rect


def test_spark_hover_adds_band_tooltip():
    out = spark([1, 2, 3, 4, 5], bins=4)
    assert "<title>" in out
    assert "p0 to p25" in out                # a percentile band


def test_spark_hover_adds_value_count_line():
    # Each bin tooltip ends with the share of values strictly inside it, and
    # each tick tooltip with the share falling exactly on it — every value
    # counted once across the eight. The quantile edges land between points,
    # so the interior bins hold two values and the extremes sit on ticks.
    # Layout is value range, then percentile band, then share-and-count.
    out = spark([1, 2, 3, 4, 5, 6, 7, 8], bins=4)
    assert "1 to 2.5\np0 to p25\n12% (1 of 8 values)" in out  # a bin tooltip
    assert "25% (2 of 8 values)" in out                  # a fuller interior bin
    assert "1\np0\n12% (1 of 8 values)" in out           # the min, on its tick


def test_spark_rug_tick_hover_includes_count():
    # A small rug is hoverable value-by-value; each tooltip ends with the
    # value's own share and count (one each, 20%, here).
    out = spark([10, 20, 30, 40, 50], bins=None)
    assert "30\np50\n20% (1 of 5 values)" in out   # the median value, on its tick


def test_spark_hover_false_omits_titles():
    assert "<title>" not in spark([1, 2, 3, 4, 5], hover=False)


def test_spark_value_format_customizes_bin_tooltips():
    # A custom value_format reformats the value range in each bin's
    # tooltip; the percentile band is unchanged.
    out = spark([1, 2, 3, 4, 5], bins=4, value_format=lambda v: f"${v:.2f}")
    assert "$1.00 to $2.00" in out
    assert "p0 to p25" in out


def test_spark_value_format_customizes_per_value_and_summary():
    # It also applies to a small rug's per-value tooltips and to the
    # whole-spark summary of a dense rug.
    small = spark([10, 20, 30], bins=None, value_format=lambda v: f"${v:.2f}")
    assert "$30.00" in small                   # a per-value tooltip
    dense = spark(list(range(30)), bins=None, value_format=lambda v: f"${v:.2f}")
    assert "$0.00 to $29.00" in dense          # the summary


def test_spark_small_rug_has_per_value_tooltips():
    # At or below tick_hover_limit, each rug value is hoverable (its
    # percentile and value), alongside the gap boxes between values; there is
    # no whole-spark summary — a spark is read value-by-value or summarised,
    # never both.
    out = spark([10, 20, 30, 40, 50], bins=None)
    assert out.count('class="pvtick"') == 5    # one hover per distinct value
    assert "30\np50" in out                    # the median value at p50
    assert "values," not in out                # no whole-spark summary tooltip


def test_spark_large_rug_has_only_summary():
    # Above the limit, a dense rug falls back to just the summary, so it
    # stays light instead of emitting one hit-area per point.
    out = spark(list(range(30)), bins=None)
    assert out.count("<title>") == 1
    assert "30 values, 0 to 29" in out
    assert 'class="pvtick"' not in out         # no per-value elements


def test_spark_binned_has_no_summary_tooltip():
    # Binned sparks are read via their bins/ticks, so they carry no
    # whole-spark summary.
    assert "values," not in spark([1, 2, 3, 4, 5], bins=4)


def test_spark_tick_hover_limit_boundary():
    # At the limit every value is individually hoverable; one past it, the rug
    # falls back to a single whole-spark summary (and drops the gap boxes).
    assert spark(list(range(24)), bins=None).count('class="pvtick"') == 24
    assert spark(list(range(25)), bins=None).count("<title>") == 1   # summary


def test_spark_tick_hover_limit_none_forces_all():
    out = spark(list(range(30)), bins=None, tick_hover_limit=None)
    assert out.count('class="pvtick"') == 30    # every value hoverable
    assert "values," not in out                 # still no whole-spark summary


def test_spark_tick_hover_limit_zero_disables_per_tick():
    out = spark([10, 20, 30, 40, 50], bins=None, tick_hover_limit=0)
    assert out.count("<title>") == 1           # summary only
    assert 'class="pvtick"' not in out


def test_spark_hoverable_ticks_pair_mark_and_hit():
    # Each hoverable value line is a visible mark plus a transparent
    # hit-area, grouped so CSS can react to the hover.
    out = spark([1, 2, 3, 4, 5], bins=4)
    assert out.count('class="pvtick"') == out.count('class="pvmark"')
    assert out.count('class="pvmark"') == out.count('class="pvhit"')
    assert out.count('class="pvtick"') >= 5    # one per distinct value


def test_spark_highlight_adds_tick_hover_effect():
    # The hover effect (mark thickens) is a scoped CSS rule.
    out = spark([1, 2, 3, 4, 5], bins=4, line_width=1.0)
    assert ".pvtick:hover .pvmark{stroke-width:2}" in out


def test_spark_highlight_false_omits_tick_effect():
    assert ".pvtick:hover" not in spark([1, 2, 3, 4, 5], highlight=False)


def test_spark_rug_hover_false_has_no_tooltip():
    assert "<title>" not in spark([1, 2, 3, 4, 5], bins=None, hover=False)


def test_spark_highlight_adds_hover_style():
    assert ":hover" in spark([1, 2, 3, 4, 5])


def test_spark_highlight_false_omits_style():
    assert "<style>" not in spark([1, 2, 3, 4, 5], highlight=False)


def test_spark_inline_sets_sizing_style():
    assert "height:1em" in spark([1, 2, 3])
    assert "height:1em" not in spark([1, 2, 3], inline=False)


def test_spark_custom_height():
    assert "height:18px" in spark([1, 2, 3], height="18px")


def test_spark_is_accessible():
    out = spark([1, 2, 3])
    assert 'role="img"' in out
    assert "aria-label=" in out
    assert "<desc>" in out


def test_spark_geometry_runs_flush_to_value_edges():
    # With every bin populated the box spans the full viewBox: its edges and
    # ticks should carry coordinates at both value-axis extremes (x = 0 and
    # x = 140). hover=False keeps every mark a plain <line> in the stroke <g>.
    out = spark(list(range(9)), bins=4, hover=False)
    group = re.search(r'pointer-events="none">(.*?)</g>', out, re.S).group(1)
    xs = [float(v) for v in re.findall(r'x[12]="([-\d.]+)"', group)]
    assert min(xs) == pytest.approx(0)
    assert max(xs) == pytest.approx(140)


def test_spark_whisker_reaches_full_height():
    # A repeated value makes a whisker that spans the whole viewBox
    # height (y = 0 to 30), while the box edges stay inset.
    out = spark([0, 0, 0, 1, 2, 3], bins=5, hover=False)
    group = re.search(r'pointer-events="none">(.*?)</g>', out, re.S).group(1)
    ys = [float(v) for v in re.findall(r'y[12]="([-\d.]+)"', group)]
    assert min(ys) == pytest.approx(0)       # whisker tip at the edge
    assert max(ys) == pytest.approx(30)


def test_spark_uses_non_scaling_stroke():
    assert 'vector-effect="non-scaling-stroke"' in spark([1, 2, 3])


def test_spark_writes_svg_file(tmp_path):
    out = tmp_path / "spark.svg"
    markup = spark([1, 2, 3, 4, 5], path=str(out))
    assert out.read_text() == markup


def test_spark_writes_standalone_html(tmp_path):
    out = tmp_path / "spark.html"
    markup = spark([1, 2, 3, 4, 5], path=str(out))
    text = out.read_text()
    assert text.startswith("<!doctype html>")
    assert markup in text


def test_spark_empty_data_raises():
    with pytest.raises(ValueError):
        spark([])


def _mark_lengths(markup):
    """The drawn length (viewBox units) of each value line's visible mark, in
    document order. Reads the stroke <g> and measures the .pvmark lines (or,
    when hover is off, the plain lines) along the perpendicular axis."""
    group = re.search(r'pointer-events="none">(.*?)</g>', markup, re.S).group(1)
    lengths = []
    for line in re.findall(r"<line[^>]*?/>", group):
        if "pvhit" in line:
            continue  # the transparent hit-area, not the visible mark
        y1 = float(re.search(r'y1="([-\d.]+)"', line).group(1))
        y2 = float(re.search(r'y2="([-\d.]+)"', line).group(1))
        lengths.append(abs(y2 - y1))
    return lengths


def test_spark_proportional_scales_lines_by_frequency():
    # 4 is the most common value, so its line spans the full box height (30);
    # the others reach proportionally less. Values ascend left to right, so the
    # lengths follow the per-value counts in value order.
    data = [1] * 12 + [2] * 40 + [3] * 94 + [4] * 97 + [5] * 60
    lengths = _mark_lengths(
        spark(data, bins=None, proportional_representation=True, hover=False))
    # Coordinates are rounded to 2 decimals each, so allow ~0.02 of slack.
    assert len(lengths) == 5                                    # one per value
    assert lengths[3] == pytest.approx(30)                      # value 4: max
    assert lengths[2] == pytest.approx(30 * 94 / 97, abs=0.02)  # value 3
    assert lengths[4] == pytest.approx(30 * 60 / 97, abs=0.02)  # value 5
    assert lengths[1] == pytest.approx(30 * 40 / 97, abs=0.02)  # value 2
    assert lengths[0] == pytest.approx(30 * 12 / 97, abs=0.02)  # value 1


def test_spark_proportional_lines_sit_on_bottom_baseline():
    # Frequency-rug lines are anchored on the bottom edge of a horizontal rug
    # (y = 30, the largest y) and grow upward, so every visible mark shares its
    # bottom endpoint regardless of length.
    data = [1] * 12 + [2] * 40 + [3] * 94 + [4] * 97 + [5] * 60
    out = spark(data, bins=None, proportional_representation=True, hover=False)
    group = re.search(r'pointer-events="none">(.*?)</g>', out, re.S).group(1)
    for line in re.findall(r"<line[^>]*?/>", group):
        if "pvhit" in line:
            continue
        y1 = float(re.search(r'y1="([-\d.]+)"', line).group(1))
        y2 = float(re.search(r'y2="([-\d.]+)"', line).group(1))
        assert max(y1, y2) == pytest.approx(30)    # bottom endpoint on baseline


def test_spark_proportional_enforces_minimum_length():
    # A value far rarer than min_representation still draws a visible line at
    # the floor (here 20% of the full 30 = 6), not a vanishing point.
    data = [1] + [2] * 100
    lengths = _mark_lengths(spark(
        data, bins=None, proportional_representation=True,
        min_representation=0.2, hover=False))
    assert lengths[0] == pytest.approx(30 * 0.2)   # the lone 1, floored
    assert lengths[1] == pytest.approx(30)         # the 100 twos, the max


def test_spark_proportional_keeps_full_hit_area():
    # Even a short visible mark keeps a full-height transparent hit-area, so a
    # rare value stays easy to hover.
    data = [1] + [2] * 100
    out = spark(data, bins=None, proportional_representation=True,
                min_representation=0.05)
    hits = re.findall(r'<line class="pvhit"[^>]*?/>', out)
    for line in hits:
        y1 = float(re.search(r'y1="([-\d.]+)"', line).group(1))
        y2 = float(re.search(r'y2="([-\d.]+)"', line).group(1))
        assert abs(y2 - y1) == pytest.approx(30)


def test_spark_proportional_requires_rug():
    with pytest.raises(ValueError):
        spark([1, 2, 3, 4], bins=4, proportional_representation=True)


def test_spark_proportional_rejects_whiskers():
    with pytest.raises(ValueError):
        spark([1, 2, 3, 4], bins=None, proportional_representation=True,
              show_whiskers=True)


def test_spark_proportional_off_leaves_lines_full():
    # Without the flag every rug line spans the full box, regardless of how
    # often the value repeats.
    data = [1] * 5 + [2] * 50
    lengths = _mark_lengths(spark(data, bins=None, hover=False))
    assert all(length == pytest.approx(30) for length in lengths)
