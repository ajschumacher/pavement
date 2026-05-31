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


def test_spark_rug_has_no_bin_rects():
    # bins=None is a rug: ticks, no equal-mass bin hover targets.
    assert spark([1, 2, 3, 4, 5], bins=None).count('class="pvbin"') == 0


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


def test_spark_colored_rug_draws_single_fill():
    out = spark([1, 2, 3, 4, 5], bins=None, color="teal")
    assert out.count('class="pvbin"') == 0
    assert 'fill="teal"' in out              # one background fill rect


def test_spark_hover_adds_band_tooltip():
    out = spark([1, 2, 3, 4, 5], bins=4)
    assert "<title>" in out
    assert "0% to 25%" in out                # a quantile band


def test_spark_hover_false_omits_titles():
    assert "<title>" not in spark([1, 2, 3, 4, 5], hover=False)


def test_spark_small_rug_has_per_value_tooltips():
    # At or below tick_hover_limit, each rug value is hoverable (its
    # percentile and value) and there is no whole-spark summary: a spark
    # is read value-by-value or summarised, never both.
    out = spark([10, 20, 30, 40, 50], bins=None)
    assert out.count("<title>") == 5           # 5 values, no summary
    assert "50%\n30" in out                    # the median value at 50%
    assert "values," not in out                # no summary tooltip


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
    assert spark(list(range(24)), bins=None).count("<title>") == 24  # per-value
    assert spark(list(range(25)), bins=None).count("<title>") == 1   # summary


def test_spark_tick_hover_limit_none_forces_all():
    out = spark(list(range(30)), bins=None, tick_hover_limit=None)
    assert out.count("<title>") == 30          # every value, no summary


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
    # No whiskers -> the box spans the full viewBox. The stroke <g> should
    # carry coordinates at both value-axis extremes (x = 0 and x = 140).
    out = spark([0, 1, 2, 3, 4], bins=4)
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
