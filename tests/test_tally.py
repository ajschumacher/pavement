"""
Tests for the experimental column "tally" (working title): the core
counts in ``pavement.core.tally_stats`` and the inline SVG strip in
``pavement.svg.tally``. Kept in one file so the experiment is easy to find
— and to remove — while it lives separately from the pavement plots.
"""

import math
import xml.dom.minidom as minidom

import pytest

from pavement.core import tally_stats
from pavement.svg import tally


# ---------------------------------------------------------------------------
# Core counts: tally_stats
# ---------------------------------------------------------------------------

def test_basic_breakdown():
    # present: [1, 1, 2, 3, 3, 3] -> distinct {1, 2, 3} = 3, repeated = 3.
    assert tally_stats([1, 1, 2, None, 3, 3, 3]) == {
        'distinct': 3, 'repeated': 3, 'missing': 1, 'total': 7}


def test_counts_always_sum_to_total():
    counts = tally_stats([1, 1, 2, 2, 2, None, float('nan'), 'x', 'x'])
    assert counts['distinct'] + counts['repeated'] + counts['missing'] \
        == counts['total']


def test_all_distinct():
    assert tally_stats([1, 2, 3, 4, 5]) == {
        'distinct': 5, 'repeated': 0, 'missing': 0, 'total': 5}


def test_all_repeats_of_one_value():
    assert tally_stats(['a', 'a', 'a', 'a']) == {
        'distinct': 1, 'repeated': 3, 'missing': 0, 'total': 4}


def test_all_missing():
    assert tally_stats([None, None, float('nan')]) == {
        'distinct': 0, 'repeated': 0, 'missing': 3, 'total': 3}


def test_empty_is_all_zeros():
    assert tally_stats([]) == {
        'distinct': 0, 'repeated': 0, 'missing': 0, 'total': 0}


def test_accepts_any_iterable():
    # A generator, not just a list.
    assert tally_stats(x for x in [1, 1, 2]) == {
        'distinct': 2, 'repeated': 1, 'missing': 0, 'total': 3}


# --- the different ways a value can be "missing" --------------------------

def test_none_is_missing():
    assert tally_stats([None]) == {
        'distinct': 0, 'repeated': 0, 'missing': 1, 'total': 1}


def test_float_nan_is_missing():
    assert tally_stats([float('nan'), math.nan])['missing'] == 2


def test_self_unequal_sentinel_is_missing():
    # numpy's nan and pandas' NaT both compare unequal to themselves; this
    # stands in for them without the dependency.
    class SelfUnequal:
        def __eq__(self, other):
            return False

        def __ne__(self, other):
            return True

    assert tally_stats([SelfUnequal()])['missing'] == 1


def test_pandas_na_like_sentinel_is_missing():
    # pandas.NA's ``!=`` yields a non-boolean and its truth value raises;
    # detection falls back to the type name. Mimic that here.
    class NAType:
        def __ne__(self, other):
            return self

        def __bool__(self):
            raise TypeError("boolean value of NA is ambiguous")

    assert tally_stats([NAType()])['missing'] == 1


def test_mixed_missing_kinds_counted_together():
    class NAType:
        def __ne__(self, other):
            return self

        def __bool__(self):
            raise TypeError

    data = [None, float('nan'), NAType(), 1, 2, 2]
    counts = tally_stats(data)
    assert counts['missing'] == 3
    assert counts['distinct'] == 2  # {1, 2}
    assert counts['repeated'] == 1


def test_empty_string_zero_and_false_are_real_values():
    # Falsy, but present — not missing.
    assert tally_stats(['', 0, False])['missing'] == 0
    assert tally_stats([''])['missing'] == 0


def test_unhashable_values_fall_back_to_equality():
    # Lists can't go in a set; the distinct count still works.
    assert tally_stats([[1], [1], [2]]) == {
        'distinct': 2, 'repeated': 1, 'missing': 0, 'total': 3}


# ---------------------------------------------------------------------------
# SVG strip: tally
# ---------------------------------------------------------------------------

def _wellformed(markup):
    minidom.parseString(markup)  # raises on malformed XML


def test_tally_returns_svg_string():
    out = tally([1, 1, 2, None])
    assert isinstance(out, str)
    assert out.startswith("<svg") and out.rstrip().endswith("</svg>")


@pytest.mark.parametrize("kwargs", [
    {},
    {"orientation": "vertical"},
    {"hover": False},
    {"highlight": False},
    {"inline": False},
    {"line_color": None},
])
def test_tally_is_wellformed_xml(kwargs):
    _wellformed(tally([1, 1, 2, 2, None, 3], **kwargs))


def test_tally_one_box_per_nonzero_category():
    # distinct, repeated, and missing all present -> three boxes.
    assert tally([1, 1, 2, None]).count('class="tvbox"') == 3


def test_tally_absent_category_draws_no_box():
    # All distinct, nothing repeated or missing -> a single box.
    assert tally([1, 2, 3, 4]).count('class="tvbox"') == 1
    # Distinct + repeated, no missing -> two boxes, no red.
    out = tally([1, 1, 2, 2])
    assert out.count('class="tvbox"') == 2
    assert "#b2182b" not in out      # the missing color is absent


def test_tally_uses_default_palette():
    out = tally([1, 1, 2, None])
    assert "#2166ac" in out          # distinct: dark blue
    assert "#92c5de" in out          # repeated: light blue
    assert "#b2182b" in out          # missing: dark red


def test_tally_custom_colors():
    out = tally([1, 1, None], distinct_color="navy", missing_color="crimson")
    assert 'fill="navy"' in out
    assert 'fill="crimson"' in out


def test_tally_boxes_are_proportional_and_fill_the_strip():
    import re
    # distinct {1, 2} = 2, repeated = 2, missing = 1; total 5.
    out = tally([1, 1, 2, 2, None])
    widths = [float(w) for w in re.findall(r'<rect class="tvbox"[^>]*?'
                                           r'width="([-\d.]+)"', out)]
    assert widths == pytest.approx([56.0, 56.0, 28.0])   # 140 * 2/5, 2/5, 1/5
    assert sum(widths) == pytest.approx(140.0)           # edge to edge


def _box_widths(out):
    import re
    return [float(w) for w in re.findall(
        r'<rect class="tvbox"[^>]*?width="([-\d.]+)"', out)]


def test_tally_min_box_keeps_a_tiny_slice_visible():
    # 1 missing of 1001 is ~0.1% — far below the default 3-unit minimum, so
    # it's bumped up to 3 and the distinct box gives up the difference.
    widths = _box_widths(tally(list(range(1000)) + [None]))
    assert widths == pytest.approx([137.0, 3.0])   # distinct, missing
    assert sum(widths) == pytest.approx(140.0)     # still edge to edge


def test_tally_min_box_zero_is_purely_proportional():
    # The missing slice keeps its true, tiny proportional width (~0.14),
    # nowhere near the default 3-unit minimum — i.e. it isn't clamped.
    widths = _box_widths(tally(list(range(1000)) + [None], min_box=0))
    assert 0 < widths[1] < 1.0
    assert sum(widths) == pytest.approx(140.0)


def test_tally_min_box_custom_value():
    widths = _box_widths(tally(list(range(1000)) + [None], min_box=10))
    assert widths == pytest.approx([130.0, 10.0])


def test_tally_min_box_does_not_resurrect_empty_categories():
    # No missing values -> still no missing box, even with a minimum width.
    assert tally([1, 2, 3, 4]).count('class="tvbox"') == 1


def test_tally_vertical_uses_height_and_viewbox():
    import re
    out = tally([1, 1, 2, 2, None], orientation="vertical")
    assert 'viewBox="0 0 30 140"' in out
    heights = [float(h) for h in re.findall(r'<rect class="tvbox"[^>]*?'
                                            r'height="([-\d.]+)"', out)]
    assert heights == pytest.approx([56.0, 56.0, 28.0])  # 140 * 2/5, 2/5, 1/5


def test_tally_horizontal_viewbox():
    assert 'viewBox="0 0 140 30"' in tally([1, 2, 3])


def test_tally_hover_text_has_share_and_count():
    out = tally([1, 1, 2, 2, None])   # distinct 2/5, repeated 2/5, missing 1/5
    assert "40% distinct" in out
    assert "2 of 5 values" in out
    assert "20% missing" in out
    assert "1 of 5 values" in out


def test_tally_tiny_share_reads_as_lt_one_percent():
    data = list(range(1000)) + [None]   # 1 missing of 1001 ~ 0.1%
    out = tally(data)
    assert "&lt;1% missing" in out      # "<" escaped in markup, shows as "<1%"
    assert "1 of 1,001 values" in out   # exact count still shown


def test_tally_singular_value_noun():
    out = tally([42])               # one value, all distinct
    assert "1 of 1 value<" in out   # singular noun, no trailing "s"


def test_tally_hover_false_omits_titles():
    assert "<title>" not in tally([1, 1, 2, None], hover=False)


def test_tally_lines_have_no_hover():
    # Hover lives on the boxes, never on the outline strokes: every <title>
    # sits inside a tvbox rect, so the title count matches the box count.
    out = tally([1, 1, 2, None])
    assert out.count("<title>") == out.count('class="tvbox"') == 3


def test_tally_is_borderless_by_default():
    assert 'stroke=' not in tally([1, 1, 2, None])        # no outline


def test_tally_line_color_outlines_boxes():
    assert 'stroke="white"' in tally([1, 1, 2, None], line_color="white")


def test_tally_uses_non_scaling_stroke_when_outlined():
    # The constant-width stroke only applies when an outline is requested.
    assert 'vector-effect="non-scaling-stroke"' in tally(
        [1, 2, 3], line_color="white")
    assert 'vector-effect' not in tally([1, 2, 3])


def test_tally_highlight_adds_hover_style():
    out = tally([1, 1, 2, None])
    assert "<style>" in out
    assert ".tvbox:hover" in out


def test_tally_highlight_false_omits_style():
    out = tally([1, 1, 2, None], highlight=False)
    assert "<style>" not in out


def test_tally_inline_sets_sizing_style():
    assert "height:1em" in tally([1, 2, 3])
    assert "height:1em" not in tally([1, 2, 3], inline=False)


def test_tally_custom_height():
    assert "height:24px" in tally([1, 2, 3], height="24px")


def test_tally_is_accessible():
    out = tally([1, 1, 2, None])
    assert 'role="img"' in out
    assert "aria-label=" in out
    assert "<desc>" in out
    # [1, 1, 2, None]: distinct {1, 2} = 2, repeated 1, missing 1.
    assert "2 distinct" in out and "missing" in out  # summary in the label


def test_tally_writes_svg_file(tmp_path):
    out = tmp_path / "tally.svg"
    markup = tally([1, 1, 2, None], path=str(out))
    assert out.read_text() == markup


def test_tally_writes_standalone_html(tmp_path):
    out = tmp_path / "tally.html"
    markup = tally([1, 1, 2, None], path=str(out))
    text = out.read_text()
    assert text.startswith("<!doctype html>")
    assert markup in text


def test_tally_empty_data_raises():
    with pytest.raises(ValueError):
        tally([])


def test_tally_all_missing_is_single_full_box():
    import re
    out = tally([None, None, float('nan')])
    assert out.count('class="tvbox"') == 1
    width = float(re.search(r'width="([-\d.]+)"', out).group(1))
    assert width == pytest.approx(140.0)
    assert "100% missing" in out
