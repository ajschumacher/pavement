"""
Tests for ``pavement.svg.summary`` (re-exported as ``pavement.summary``): the
inline HTML summary table that pairs each column's tally with its
distribution, plus the bin-selection and row-key helpers behind it.
"""

import re
import xml.dom.minidom as minidom

import pytest

import pavement
from pavement.svg import (
    Summary,
    _choose_bins,
    _is_numeric,
    _plural,
    _row_key,
    summary,
)


def _wellformed(markup):
    # The whole fragment is one <table> of closed tags and well-formed SVGs,
    # so it parses as XML.
    minidom.parseString(markup)


def _titles(html):
    return re.findall(r"<title>(.*?)</title>", html, re.S)


# ---------------------------------------------------------------------------
# Bin selection: rug up to 24, then 4 / 8 / 16
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("distinct, expected", [
    (1, None), (24, None),          # rug while few enough to read tick-by-tick
    (25, 4), (95, 4),               # then four equal-mass bins
    (96, 8), (383, 8),              # eight past 96 distinct
    (384, 16), (10_000, 16),        # sixteen past 384, and capped there
])
def test_choose_bins_thresholds(distinct, expected):
    assert _choose_bins(distinct) == expected


def test_choose_bins_rug_limit_matches_spark_tick_hover_limit():
    # The rug cutoff is the count below which a spark keeps every value
    # individually hoverable, so a summary rug is fully hoverable.
    from pavement.svg import spark
    out = spark(list(range(24)), bins=None)
    assert out.count("<title>") == 24          # all hoverable at the limit
    assert _choose_bins(24) is None


# ---------------------------------------------------------------------------
# Numeric detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("singular, plural", [
    ("value", "values"),
    ("row", "rows"),
    ("entry", "entries"),       # consonant + y -> ies, not "entrys"
    ("day", "days"),            # vowel + y -> just s
])
def test_plural(singular, plural):
    assert _plural(singular) == plural


def test_is_numeric_accepts_ints_and_floats():
    assert _is_numeric(3) and _is_numeric(3.5) and _is_numeric(-2)


def test_is_numeric_rejects_bools_and_strings():
    # Booleans are ints but read as a two-level category, not a distribution.
    assert not _is_numeric(True)
    assert not _is_numeric(False)
    assert not _is_numeric("5")
    assert not _is_numeric(None)


# ---------------------------------------------------------------------------
# Whole-row key (the dataframe summary's top row)
# ---------------------------------------------------------------------------

def test_row_key_all_missing_row_is_none():
    assert _row_key([None, float("nan")]) is None


def test_row_key_matches_on_missing_position():
    # Two rows missing the *same* cell compare equal (raw NaN never would),
    # so they count as a repeat, not two distinct rows.
    assert _row_key([1, None]) == _row_key([1, float("nan")])
    assert _row_key([1, None]) != _row_key([2, None])


# ---------------------------------------------------------------------------
# Return type and the Jupyter hook
# ---------------------------------------------------------------------------

def test_summary_returns_summary_object():
    out = summary([1, 2, 3, 4, 5])
    assert isinstance(out, Summary)


def test_summary_repr_html_is_the_table_fragment():
    out = summary([1, 2, 3, 4, 5])
    html = out._repr_html_()
    assert html == str(out)                    # str() gives the same fragment
    assert html.startswith("<table") and html.rstrip().endswith("</table>")


def test_summary_is_exposed_at_top_level():
    assert pavement.summary is summary


@pytest.mark.parametrize("data", [
    [1, 2, 3, 4, 5],                                   # numeric series
    ["a", "a", "b", None],                             # categorical series
    {"x": [1, 2, 3], "y": ["a", "b", "a"]},            # dict "dataframe"
    {"only_missing": [None, None]},                    # all-missing column
])
def test_summary_is_wellformed_xml(data):
    _wellformed(str(summary(data)))


# ---------------------------------------------------------------------------
# Single series / sequence
# ---------------------------------------------------------------------------

def test_summary_series_shows_entry_count_where_a_name_would_be():
    # "entries", not "values": the count includes any missing, so "values"
    # would wrongly imply they are all present. And it pluralizes correctly
    # (entry -> entries, never "entrys").
    out = str(summary(list(range(1234))))
    assert "1,234 entries" in out              # thousands separator, plural
    assert "entrys" not in out


def test_summary_series_singular_entry_noun():
    assert "1 entry<" in str(summary([42]))    # one entry, singular


def test_summary_series_tally_tooltip_uses_entries():
    # The single-series tally talks of entries too, matching the label.
    out = str(summary([1, 1, 2, None]))        # 4 entries
    assert any("of 4 entries" in t for t in _titles(out))


def test_summary_numeric_series_uses_a_spark():
    out = str(summary([1, 2, 3, 4, 5]))
    assert 'class="pavement-spark"' in out
    assert 'class="pavement-proportion"' not in out
    assert 'class="pavement-tally"' in out     # always a tally too


def test_summary_categorical_series_uses_a_proportion():
    out = str(summary(["dog", "dog", "cat", "fish"]))
    assert 'class="pavement-proportion"' in out
    assert 'class="pavement-spark"' not in out


def test_summary_boolean_series_is_categorical():
    # Bools are a two-level category -> proportion, not a pavement.
    out = str(summary([True, False, True, True]))
    assert 'class="pavement-proportion"' in out
    assert 'class="pavement-spark"' not in out


def test_summary_numeric_resolution_follows_distinct_count():
    # <=24 distinct -> rug (no equal-mass bin rects); a larger spread -> bins.
    rug = str(summary(list(range(20))))
    assert 'class="pvbin"' not in rug
    binned = str(summary(list(range(50))))     # 50 distinct -> 4 bins
    assert binned.count('class="pvbin"') == 4


# ---------------------------------------------------------------------------
# Dataframe (dict of columns)
# ---------------------------------------------------------------------------

def test_summary_dataframe_has_total_row_and_one_row_per_column():
    out = str(summary({"a": [1, 2, 3], "b": ["x", "y", "z"], "c": [1.0, 2.0, 3.0]}))
    # Top "rows" row + 3 column rows -> 4 tally strips.
    assert out.count('class="pavement-tally"') == 4
    assert "3 rows" in out
    for name in ("a", "b", "c"):
        assert f">{name}</span>" in out        # each column labelled


def test_summary_dataframe_total_row_distribution_cell_is_empty():
    # The frame has no single distribution: exactly the per-column ones.
    out = str(summary({"a": [1, 2, 3], "b": [4, 5, 6]}))
    # Two numeric columns -> two sparks; the total row adds none.
    assert out.count('class="pavement-spark"') == 2


def test_summary_dataframe_row_tally_counts_whole_rows():
    # rows: (1,x), (1,x)=repeat, all-missing, (2,y)
    out = str(summary({"a": [1, 1, None, 2], "b": ["x", "x", None, "y"]}))
    top = _titles(out)
    assert any("distinct" in t and "2 of 4 rows" in t for t in top)
    assert any("duplicate" in t and "1 of 4 rows" in t for t in top)
    assert any("missing" in t and "1 of 4 rows" in t for t in top)


def test_summary_dataframe_row_tally_uses_row_noun():
    out = str(summary({"a": [1, 2], "b": [3, 4]}))
    assert "rows" in _titles(out)[0]           # the top tally talks of rows


def test_summary_all_missing_column_has_tally_but_no_distribution():
    out = str(summary({"good": [1, 2, 3], "blank": [None, None, float("nan")]}))
    # Both columns get a tally (top row too -> 3); only "good" gets a spark.
    assert out.count('class="pavement-tally"') == 3
    assert out.count('class="pavement-spark"') == 1
    assert 'class="pavement-proportion"' not in out


def test_summary_empty_dict_is_zero_rows():
    out = str(summary({}))
    assert "0 rows" in out
    _wellformed(out)


def test_summary_constant_numeric_column_does_not_crash():
    _wellformed(str(summary({"k": [5, 5, 5, 5]})))


def test_summary_empty_sequence_is_graceful():
    # A higher-level convenience: an empty input summarizes to "0 entries"
    # with empty strips rather than raising the way a bare strip would.
    out = str(summary([]))
    assert "0 entries" in out
    assert 'class="pavement-spark"' not in out
    assert 'class="pavement-tally"' not in out
    _wellformed(out)


def test_summary_all_missing_series_has_tally_but_no_distribution():
    out = str(summary([None, float("nan"), None]))
    assert "3 entries" in out
    assert 'class="pavement-tally"' in out          # all-missing tally (red)
    assert 'class="pavement-spark"' not in out
    assert 'class="pavement-proportion"' not in out


# ---------------------------------------------------------------------------
# Styling / options
# ---------------------------------------------------------------------------

def test_summary_class_is_on_the_table():
    assert 'class="pavement-summary"' in str(summary([1, 2, 3]))
    assert 'class="my-sum"' in str(summary([1, 2, 3], class_="my-sum"))


def test_summary_height_is_passed_to_strips():
    assert "height:2.5em" in str(summary([1, 2, 3], height="2.5em"))


def test_summary_hover_false_omits_titles():
    assert "<title>" not in str(summary({"a": [1, 2, 3], "b": ["x", "y", "z"]},
                                        hover=False))


def test_summary_highlight_false_omits_style():
    assert "<style>" not in str(summary([1, 2, 3, 4, 5], highlight=False))


def test_summary_color_tints_numeric_sparks():
    out = str(summary([1, 2, 3, 4, 5], color="#c0392b"))
    assert 'fill="#c0392b"' in out


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------

def test_summary_writes_standalone_html(tmp_path):
    out = tmp_path / "summary.html"
    result = summary({"a": [1, 2, 3]}, path=str(out))
    text = out.read_text()
    assert text.startswith("<!doctype html>")
    assert str(result) in text


def test_summary_writes_fragment_for_other_suffix(tmp_path):
    out = tmp_path / "summary.frag"
    result = summary([1, 2, 3], path=str(out))
    assert out.read_text() == str(result)
    assert out.read_text().startswith("<table")


# ---------------------------------------------------------------------------
# pandas / numpy (skipped if not installed)
# ---------------------------------------------------------------------------

def test_summary_accepts_a_pandas_series():
    pd = pytest.importorskip("pandas")
    out = str(summary(pd.Series([1, 2, 2, 3, None], name="ignored")))
    assert "5 entries" in out                  # the count, not the name
    assert 'class="pavement-spark"' in out
    _wellformed(out)


def test_summary_accepts_a_pandas_dataframe():
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    df = pd.DataFrame({
        "id": range(1, 201),
        "grp": (["a", "b", "c"] * 67)[:200],
        "score": np.r_[np.zeros(199), [np.nan]],
        "flag": [True, False] * 100,
    })
    out = str(summary(df))
    assert "200 rows" in out
    assert 'class="pavement-spark"' in out        # numeric id/score
    assert 'class="pavement-proportion"' in out   # grp / flag
    _wellformed(out)


def test_summary_pandas_nullable_integer_column_is_numeric():
    pd = pytest.importorskip("pandas")
    # A nullable Int64 column iterates to Python ints plus pd.NA; the ints
    # must read as numeric (a spark), the NA as missing.
    df = pd.DataFrame({"n": pd.array([1, 2, 3, None, 5], dtype="Int64")})
    out = str(summary(df))
    assert 'class="pavement-spark"' in out
    _wellformed(out)


def test_summary_numpy_integer_array_is_numeric():
    np = pytest.importorskip("numpy")
    out = str(summary(np.arange(50)))             # np.int64 values
    assert 'class="pavement-spark"' in out
    assert out.count('class="pvbin"') == 4        # 50 distinct -> 4 bins
