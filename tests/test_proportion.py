"""
Tests for the "proportion" plot: the core value counts in
``pavement.core.proportion_stats`` and the inline SVG strip in
``pavement.svg.proportion``. Kept in one file, like the tally tests.
"""

import re
import xml.dom.minidom as minidom

import pytest

from pavement.core import proportion_stats
from pavement.svg import proportion


# ---------------------------------------------------------------------------
# Core value counts: proportion_stats
# ---------------------------------------------------------------------------

def test_counts_sorted_descending():
    assert proportion_stats(['dog'] * 10 + ['cat'] * 6 + ['fish'] * 4) == {
        'counts': [('dog', 10), ('cat', 6), ('fish', 4)],
        'total': 20, 'missing': 0}


def test_ties_broken_by_first_appearance():
    # 'b' and 'a' both appear twice; 'b' is seen first, so it sorts first.
    assert proportion_stats(['b', 'a', 'b', 'a', 'c'])['counts'] == [
        ('b', 2), ('a', 2), ('c', 1)]


def test_missing_values_are_dropped_and_counted():
    stats = proportion_stats(['a', 'a', None, 'b', float('nan')])
    assert stats['counts'] == [('a', 2), ('b', 1)]
    assert stats['total'] == 3
    assert stats['missing'] == 2


def test_all_missing_gives_empty_counts():
    assert proportion_stats([None, float('nan')]) == {
        'counts': [], 'total': 0, 'missing': 2}


def test_empty_gives_empty_counts():
    assert proportion_stats([]) == {'counts': [], 'total': 0, 'missing': 0}


def test_total_equals_sum_of_counts():
    stats = proportion_stats(['x', 'y', 'y', 'z', 'z', 'z'])
    assert stats['total'] == sum(c for _, c in stats['counts'])


def test_unhashable_values_fall_back_to_equality():
    assert proportion_stats([[1], [1], [2]])['counts'] == [([1], 2), ([2], 1)]


def test_accepts_a_generator():
    assert proportion_stats(x for x in ['a', 'a', 'b'])['counts'] == [
        ('a', 2), ('b', 1)]


# ---------------------------------------------------------------------------
# SVG strip: proportion
# ---------------------------------------------------------------------------

def _wellformed(markup):
    minidom.parseString(markup)


def _box_widths(out):
    return [float(w) for w in re.findall(
        r'<rect class="tvbox"[^>]*?width="([-\d.]+)"', out)]


def _titles(out):
    return re.findall(r'<title>(.*?)</title>', out, re.S)


def test_proportion_returns_svg_string():
    out = proportion(['a', 'a', 'b'])
    assert isinstance(out, str)
    assert out.startswith("<svg") and out.rstrip().endswith("</svg>")


@pytest.mark.parametrize("kwargs", [
    {},
    {"orientation": "vertical"},
    {"hover": False},
    {"highlight": False},
    {"inline": False},
    {"line_color": "white"},
    {"max_boxes": 3},
])
def test_proportion_is_wellformed_xml(kwargs):
    _wellformed(proportion(['a', 'a', 'b', 'c', 'c', 'd', 'e'], **kwargs))


def test_proportion_one_box_per_value():
    assert proportion(['a', 'a', 'b', 'c']).count('class="tvbox"') == 3


def test_proportion_boxes_are_proportional_and_fill_the_strip():
    # dog 10, cat 6, fish 4 of 20 -> 70, 42, 28.
    widths = _box_widths(proportion(['dog'] * 10 + ['cat'] * 6 + ['fish'] * 4))
    assert widths == pytest.approx([70.0, 42.0, 28.0])
    assert sum(widths) == pytest.approx(140.0)


def test_proportion_most_common_is_leftmost_and_widest():
    widths = _box_widths(proportion(['rare', 'common', 'common', 'common']))
    assert widths[0] > widths[1]          # 'common' first and widest


def test_proportion_hover_text_mirrors_tally():
    out = proportion(['dog'] * 10 + ['x'] * 90)   # dog 10 of 100
    assert '10% "dog"' in out
    assert "10 of 100 values" in out


def test_proportion_is_borderless_by_default():
    assert 'stroke=' not in proportion(['a', 'a', 'b'])


def test_proportion_line_color_outlines_boxes():
    assert 'stroke="white"' in proportion(['a', 'a', 'b'], line_color="white")


def test_proportion_alternates_colors():
    out = proportion(['a', 'a', 'a', 'b', 'b', 'c'])   # three value boxes
    fills = re.findall(r'<rect class="tvbox"[^>]*?fill="([^"]+)"', out)
    assert fills == ["#2166ac", "#92c5de", "#2166ac"]  # dark, light, dark


def test_proportion_hover_false_omits_titles():
    assert "<title>" not in proportion(['a', 'a', 'b'], hover=False)


def test_proportion_value_is_cropped_with_ellipsis():
    long_value = "z" * 200
    out = proportion([long_value, long_value, "b"], value_crop=128)
    assert "z" * 128 + "…" in out
    assert "z" * 129 not in out


def test_proportion_value_crop_none_keeps_full_value():
    long_value = "z" * 200
    out = proportion([long_value, "b"], value_crop=None)
    assert "z" * 200 in out


def test_proportion_special_characters_are_escaped():
    out = proportion(['a<b&c', 'a<b&c', 'plain'])
    _wellformed(out)
    assert "&lt;" in out and "&amp;" in out


# --- high cardinality: the catch-all box ----------------------------------

def test_proportion_caps_at_max_boxes_with_catch_all():
    # 30 distinct values, all equally common -> 12 shown + 1 catch-all.
    col = [f"v{i}" for i in range(30) for _ in range(5)]
    out = proportion(col)
    assert out.count('class="tvbox"') == 13          # max_boxes + catch-all
    assert "other" in _titles(out)[-1]               # last box is the catch-all


def test_proportion_catch_all_reports_lumped_values():
    col = [f"v{i}" for i in range(30) for _ in range(5)]   # 150 values
    catch = _titles(proportion(col))[-1]
    # 18 of the 30 distinct values are lumped (30 - 12 shown).
    assert "other" in catch
    assert "(across 18 distinct values)" in catch
    assert "of 150 values" in catch


def test_proportion_catch_all_uses_other_color():
    col = [f"v{i}" for i in range(30) for _ in range(5)]
    fills = re.findall(r'<rect class="tvbox"[^>]*?fill="([^"]+)"',
                       proportion(col, other_color="#5995c5"))
    assert fills[-1] == "#5995c5"            # the catch-all box


def test_proportion_no_catch_all_when_values_fit():
    out = proportion(['a', 'a', 'b', 'c'], max_boxes=12)
    assert "other" not in out                # all three fit; no catch-all


def test_proportion_max_boxes_respected():
    col = [f"v{i}" for i in range(20) for _ in range(5)]
    out = proportion(col, max_boxes=5)
    assert out.count('class="tvbox"') == 6   # 5 shown + catch-all


def test_proportion_early_cutoff_when_catch_all_would_distort():
    # One dominant value plus a long tail of singletons: the cutoff lands
    # well below max_boxes, because more tiny boxes would squeeze the
    # catch-all past the tolerance.
    col = ['BIG'] * 200 + [f"u{i}" for i in range(800)]
    out = proportion(col)
    boxes = out.count('class="tvbox"')
    assert boxes < 13                        # fewer than max_boxes + catch-all
    # And the drawn catch-all stays within tolerance of its true width.
    widths = _box_widths(out)
    total = 1000
    lumped = total - 200 - (boxes - 2)       # BIG + (boxes-2) singletons shown
    true_catch = 140 * lumped / total
    assert abs(widths[-1] - true_catch) / true_catch < 0.10


def test_proportion_min_box_keeps_a_rare_value_visible():
    col = ['common'] * 1000 + ['rare']       # rare is ~0.1%
    widths = _box_widths(proportion(col))
    assert widths[-1] == pytest.approx(3.0)  # bumped up to the minimum
    assert sum(widths) == pytest.approx(140.0)


def test_proportion_vertical_viewbox_and_layout():
    out = proportion(['a'] * 2 + ['b'], orientation="vertical")
    assert 'viewBox="0 0 30 140"' in out


def test_proportion_horizontal_viewbox():
    assert 'viewBox="0 0 140 30"' in proportion(['a', 'b'])


def test_proportion_highlight_adds_hover_style():
    out = proportion(['a', 'a', 'b'])
    assert "<style>" in out and ".tvbox:hover" in out


def test_proportion_highlight_false_omits_style():
    assert "<style>" not in proportion(['a', 'a', 'b'], highlight=False)


def test_proportion_inline_sets_sizing_style():
    assert "height:1em" in proportion(['a', 'b'])
    assert "height:1em" not in proportion(['a', 'b'], inline=False)


def test_proportion_is_accessible():
    out = proportion(['a', 'a', 'b'])
    assert 'role="img"' in out
    assert "aria-label=" in out
    assert "<desc>" in out
    assert "distinct value" in out           # summary in the label


def test_proportion_writes_standalone_html(tmp_path):
    out = tmp_path / "p.html"
    markup = proportion(['a', 'a', 'b'], path=str(out))
    text = out.read_text()
    assert text.startswith("<!doctype html>")
    assert markup in text


def test_proportion_empty_data_raises():
    with pytest.raises(ValueError):
        proportion([])


def test_proportion_all_missing_raises():
    with pytest.raises(ValueError):
        proportion([None, float('nan')])


def test_proportion_singular_value_noun():
    out = proportion(['only'])
    assert "1 of 1 value<" in out            # singular noun, no trailing "s"
    assert '100% "only"' in out
