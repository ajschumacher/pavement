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
    _column_extent,
    _crop_value,
    _fmt_extent,
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
# Bin selection: rug up to 24 (or up to 16 distinct), then 4 / 8 / 16 based on
# total value count. All-distinct inputs isolate the count-based thresholds.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n, expected", [
    (1, None), (24, None),          # rug while few enough to read tick-by-tick
    (25, 4), (96, 4),               # then four equal-mass bins up to 96
    (97, 8), (256, 8),              # eight bins up to 256
    (257, 16), (10_000, 16),        # sixteen past 256, and capped there
])
def test_choose_bins_thresholds(n, expected):
    # range(n) is n distinct values, so the distinct-value rug rule never fires
    # and the count thresholds are what's exercised.
    assert _choose_bins(range(n)) == expected


def test_choose_bins_rugs_few_distinct_values():
    # Many values but few distinct levels (a discrete rating, say) rug rather
    # than bin, however large the column — the frequency rug carries the counts.
    assert _choose_bins([1, 2, 3, 4, 5] * 1000) is None        # 5 distinct
    assert _choose_bins(list(range(16)) * 100) is None         # 16 distinct, at the limit
    assert _choose_bins(list(range(17)) * 100) == 16           # 17 distinct -> binned


def test_summary_rugs_discrete_column_proportionally():
    # A many-row, few-distinct numeric column rugs, drawn as a frequency rug:
    # the value lines differ in length (carrying the counts) rather than all
    # spanning the box as a binned pavement or a plain rug would.
    data = {"rating": [1] * 10 + [2] * 40 + [3] * 90 + [4] * 95 + [5] * 50}
    html = str(summary(data))
    # The numeric column's spark is a rug, not a binned pavement: one tick per
    # distinct value, and its only boxes are the zero-interior gaps between
    # those values (a binned pavement's bins would carry real interior counts).
    assert html.count('class="pvtick"') == 5
    gaps = re.findall(r'<rect class="pvbin".*?<title>(.*?)</title>', html, re.S)
    assert gaps and all("(0 of" in g for g in gaps)
    # Its visible marks (.pvmark) vary in length, the signature of a frequency
    # rug — a plain rug or a pavement would draw them all full height.
    marks = re.findall(r'<line class="pvmark"[^>]*?/>', html)
    lengths = set()
    for line in marks:
        y1 = float(re.search(r'y1="([-\d.]+)"', line).group(1))
        y2 = float(re.search(r'y2="([-\d.]+)"', line).group(1))
        lengths.add(round(abs(y2 - y1), 2))
    assert len(lengths) > 1


def test_choose_bins_rug_limit_matches_spark_tick_hover_limit():
    # The rug cutoff is the count below which a spark keeps every value
    # individually hoverable, so a summary rug is fully hoverable.
    from pavement.svg import spark
    out = spark(list(range(24)), bins=None)
    assert out.count('class="pvtick"') == 24    # every value hoverable at the limit
    assert _choose_bins(range(24)) is None


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
    # A responsive wrapper div contains the table — still a plain HTML fragment
    assert html.startswith("<div") and html.rstrip().endswith("</div>")
    assert "<table" in html and "</table>" in html


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
# draggable=True: a browser-only, self-contained reorder of the column rows
# ---------------------------------------------------------------------------

def test_summary_draggable_is_the_default():
    out = str(summary({"x": [1, 2, 3], "y": ["a", "b", "a"]}))
    assert "pavement-handle" in out
    assert "<script" in out


def test_summary_draggable_false_is_a_script_free_fragment():
    out = str(summary({"x": [1, 2, 3], "y": ["a", "b", "a"]}, draggable=False))
    assert "draggable" not in out
    assert "pavement-handle" not in out
    assert "<script" not in out


@pytest.mark.parametrize("data", [
    {"only": [1, 2, 3]},        # single-column frame — one reorderable row
    [1, 2, 3, 4, 5],            # bare sequence — a single row
    {"a": [1], "b": [2]},       # two columns, but each a single value
])
def test_summary_no_handle_when_nothing_to_reorder(data):
    # Dragging needs 2+ column rows; with fewer there is no handle and no
    # script (the multi-column case still gets them — that is two rows).
    out = str(summary(data))
    if isinstance(data, dict) and len(data) >= 2:
        assert "pavement-handle" in out
    else:
        assert "pavement-handle" not in out
        assert "<script" not in out


def test_summary_default_output_is_wellformed_xml():
    # The default now carries a <script>; it stays well-formed XML — the script
    # lives inside the wrapper div (one root) and its body is a CDATA section.
    _wellformed(str(summary({"x": [1, 2, 3], "y": ["a", "b", None]})))


def test_summary_draggable_gives_each_column_row_a_handle():
    # Three columns → three grip handles (the top "N by M" total row gets none).
    # The handle is the only draggable element — the rows themselves are not.
    out = str(summary({"x": [1, 2, 3], "y": [4, 5, 6], "z": [7, 8, 9]},
                      draggable=True))
    assert out.count('class="pavement-handle"') == 3
    assert out.count('draggable="true"') == 3   # one per handle, none on <tr>
    assert "<tr draggable" not in out


def test_summary_draggable_handles_start_hidden():
    # Hidden in the markup; the script reveals them, so a stripped script (a
    # notebook) leaves no grip on a table that cannot be dragged.
    out = str(summary({"x": [1, 2, 3], "y": [4, 5, 6]}, draggable=True))
    handle = out.split('class="pavement-handle"', 1)[1].split(">", 1)[0]
    assert "display:none" in handle


def test_summary_draggable_total_row_stays_pinned():
    # The first row in the table is the frame's total row — no handle, not a
    # drop-target row (no data-pave-row marker).
    out = str(summary({"x": [1, 2, 3], "y": ["a", "b", "a"]}, draggable=True))
    body = out.split("</colgroup>", 1)[1]
    first_row = body.split("</tr>", 1)[0]
    assert "pavement-handle" not in first_row
    assert "data-pave-row" not in first_row


def test_summary_draggable_adds_one_scoped_script_keyed_to_the_table():
    out = str(summary({"x": [1, 2, 3], "y": [4, 5, 6]}, draggable=True))
    assert out.count("<script>") == 1
    # The id on the table is the id the script looks up — same string, once each.
    m = re.search(r'id="(pavement-summary-[0-9a-f]+)"', out)
    assert m and out.count(m.group(1)) == 2


def test_summary_draggable_ids_are_unique_across_tables():
    a = re.search(r'id="(pavement-summary-[0-9a-f]+)"',
                  str(summary({"x": [1, 2], "y": [3, 4]}, draggable=True))).group(1)
    b = re.search(r'id="(pavement-summary-[0-9a-f]+)"',
                  str(summary({"x": [1, 2], "y": [3, 4]}, draggable=True))).group(1)
    assert a != b


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
    # <=24 distinct -> rug (one tick per value); a larger spread -> bins.
    rug = str(summary(list(range(20))))
    assert rug.count('class="pvtick"') == 20    # per-value ticks, a rug
    binned = str(summary(list(range(50))))     # 50 distinct -> 4 bins
    assert binned.count('class="pvbin"') == 4


# ---------------------------------------------------------------------------
# Extent number formatter
# ---------------------------------------------------------------------------

def test_fmt_extent_whole_numbers_use_commas():
    assert _fmt_extent(100_000) == "100,000"
    assert _fmt_extent(1_234_567) == "1,234,567"


def test_fmt_extent_small_numbers_unchanged():
    assert _fmt_extent(3) == "3"
    assert _fmt_extent(-42) == "-42"


def test_fmt_extent_fractional_uses_commas_when_short():
    assert _fmt_extent(1234.5) == "1,234.5"


def test_fmt_extent_comma_repr_at_16_chars_fits():
    # "1,000,000,000,000" is exactly 17 chars (too long), "999,999,999,999" is 15 (fine).
    assert _fmt_extent(999_999_999_999) == "999,999,999,999"


def test_fmt_extent_falls_back_to_sci_notation_when_too_long():
    # 10^18 comma-formatted is "1,000,000,000,000,000,000" (25 chars) → scientific.
    result = _fmt_extent(1e18)
    assert len(result) <= 16
    assert "e" in result.lower()


def test_fmt_extent_scientific_uses_max_sig_figs_in_16_chars():
    # Should squeeze in more precision than the 3-sig-fig default fmt.
    result = _fmt_extent(1.23456789e18)
    assert len(result) <= 16
    assert result != "1.23e+18"   # should have more sig figs than :.3g


def test_fmt_extent_used_for_numeric_column_extent():
    # user_id-style integers should display as "100,000" not "1e+05".
    lo, hi = _column_extent(list(range(100_000, 100_010)),
                            list(range(100_000, 100_010)))
    assert lo == "100,000"
    assert hi == "100,009"


# ---------------------------------------------------------------------------
# Spark extent (min/max axis labels)
# ---------------------------------------------------------------------------

def test_crop_value_short_values_unchanged():
    assert _crop_value("hello") == "hello"
    assert _crop_value("x" * 127) == "x" * 127


def test_crop_value_long_values_truncated():
    assert _crop_value("x" * 129) == "x" * 127 + "…"
    assert len(_crop_value("a" * 200)) == 128


def test_crop_value_empty_string_gets_quoted():
    assert _crop_value("") == '""'


def test_crop_value_whitespace_only_gets_quoted():
    assert _crop_value("   ") == '"   "'
    assert _crop_value("\t") == '"\t"'


def test_crop_value_non_printable_gets_quoted():
    assert _crop_value("\x00") == '"\x00"'


def test_crop_value_normal_strings_no_quotes():
    assert _crop_value("hello") == "hello"
    assert _crop_value("  hello  ") == "  hello  "   # whitespace around printable: no quotes


def test_column_extent_numeric():
    lo, hi = _column_extent([1, 5, 3], [1, 5, 3])
    assert lo == "1"
    assert hi == "5"


def test_column_extent_empty():
    assert _column_extent([], []) == ('', '')


def test_column_extent_categorical():
    # proportion_stats sorts descending; ties broken by first appearance.
    # ["a","b","a","c"] -> counts: a=2, b=1, c=1 -> most="a", least="c"
    lo, hi = _column_extent(["a", "b", "a", "c"], ["a", "b", "a", "c"])
    assert lo == "a"
    assert hi == "c"


def test_column_extent_categorical_crops_long_values():
    long = "x" * 130
    lo, hi = _column_extent([long, "z"], [long, "z"])
    assert lo == "x" * 127 + "…"
    assert hi == "z"


def test_column_extent_appears_in_summary_for_numeric_column():
    out = str(summary({"score": [10, 20, 30, 40, 50]}))
    assert "10" in out and "50" in out   # min and max visible


def test_column_extent_appears_in_summary_for_categorical_column():
    # "a" (most common) on left, "c" (least common, last) on right.
    out = str(summary({"cat": ["a", "b", "a", "c"]}))
    assert 'pavement-proportion' in out
    import re
    extent_spans = re.findall(r'font-size:\.85em[^>]*>([^<]+)<', out)
    assert "a" in extent_spans
    assert "c" in extent_spans


# ---------------------------------------------------------------------------
# Dataframe (dict of columns)
# ---------------------------------------------------------------------------

def test_summary_dataframe_has_total_row_and_one_row_per_column():
    out = str(summary({"a": [1, 2, 3], "b": ["x", "y", "z"], "c": [1.0, 2.0, 3.0]}))
    # Top header row + 3 column rows -> 4 tally strips.
    assert out.count('class="pavement-tally"') == 4
    assert "3 by 3" in out      # shape label: columns by rows
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
    assert "0 by 0" in out
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
    out = str(summary([1, 2, 3], height="2.5em"))
    # All strips keep the same height; widths differ (75% tally, 130% dist).
    assert out.count("height:2.5em") >= 2           # base height on every strip
    assert "width:8.75em" in out    # tally: 2.5 × (140/30) × 0.75
    assert "width:15.17em" in out   # distribution: 2.5 × (140/30) × 1.30


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
    text = out.read_text()
    assert text.startswith("<div")  # responsive wrapper div, table inside
    assert "<table" in text


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


# ---------------------------------------------------------------------------
# pandas SeriesGroupBy
# ---------------------------------------------------------------------------

def test_summary_groupby_one_row_per_group():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"team": ["a", "a", "b", "b", "b"], "score": [1, 2, 3, 4, 5]})
    out = str(summary(df["score"].groupby(df["team"])))
    # Header row + 2 group rows -> 3 tally strips.
    assert out.count('class="pavement-tally"') == 3
    assert ">a<" in out
    assert ">b<" in out


def test_summary_groupby_header_shows_series_name_and_group_count():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"team": list("abc"), "score": [10, 20, 30]})
    out = str(summary(df["score"].groupby(df["team"])))
    assert "score" in out
    assert "3 groups" in out


def test_summary_groupby_singular_group_noun():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"team": ["a", "a"], "score": [1, 2]})
    out = str(summary(df["score"].groupby(df["team"])))
    assert "1 group" in out
    assert "1 groups" not in out


def test_summary_groupby_unnamed_series_shows_only_group_count():
    pd = pytest.importorskip("pandas")
    s = pd.Series([1, 2, 3, 4], name=None)
    keys = pd.Series(["x", "x", "y", "y"])
    out = str(summary(s.groupby(keys)))
    assert "2 groups" in out


def test_summary_groupby_header_tally_covers_all_values():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"k": ["a", "a", "b", "b"], "v": [1, 1, 2, None]})
    out = str(summary(df["v"].groupby(df["k"])))
    titles = _titles(out)
    # Header tally: 4 total entries (1 missing), noun is "entry/entries".
    assert any("of 4 entries" in t for t in titles)


def test_summary_groupby_header_has_distribution():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"k": list("aabb"), "v": [1, 2, 3, 4]})
    out = str(summary(df["v"].groupby(df["k"])))
    # Numeric values -> spark in both the header and each group row.
    assert out.count('class="pavement-spark"') == 3   # header + 2 groups


def test_summary_groupby_multi_key_labels_joined_with_slash():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({
        "region": ["N", "N", "S", "S"],
        "dept": ["eng", "eng", "mkt", "mkt"],
        "v": [1, 2, 3, 4],
    })
    out = str(summary(df["v"].groupby([df["region"], df["dept"]])))
    assert "N / eng" in out
    assert "S / mkt" in out


def test_summary_groupby_is_wellformed_xml():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"k": list("aabbc"), "v": [1, 2, None, 4, 5]})
    _wellformed(str(summary(df["v"].groupby(df["k"]))))


# ---------------------------------------------------------------------------
# pandas DataFrameGroupBy
# ---------------------------------------------------------------------------

def test_summary_dataframe_groupby_one_row_per_group():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"team": list("aabbb"), "score": [1, 2, 3, 4, 5], "rank": range(5)})
    out = str(summary(df.groupby("team")))
    # Header row + 2 group rows -> 3 tally strips.
    assert out.count('class="pavement-tally"') == 3
    assert ">a<" in out
    assert ">b<" in out


def test_summary_dataframe_groupby_header_shape():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"team": list("abc"), "x": [1, 2, 3], "y": [4, 5, 6]})
    out = str(summary(df.groupby("team")))
    assert "3 groups" in out
    assert "3 columns" in out   # team + x + y (all columns, including key)


def test_summary_dataframe_groupby_header_tally_counts_rows():
    pd = pytest.importorskip("pandas")
    # 3 groups, 1 row each → 3 distinct rows total, no duplicates
    df = pd.DataFrame({"k": list("abc"), "v": [1, 2, 3]})
    out = str(summary(df.groupby("k")))
    titles = _titles(out)
    assert any("of 3 rows" in t for t in titles)


def test_summary_dataframe_groupby_per_group_row_tally():
    pd = pytest.importorskip("pandas")
    # group "a" has 2 identical rows (duplicates)
    df = pd.DataFrame({"k": list("aab"), "v": [1, 1, 2]})
    out = str(summary(df.groupby("k")))
    titles = _titles(out)
    assert any("duplicate" in t and "of 2 rows" in t for t in titles)


def test_summary_dataframe_groupby_no_distribution_cells():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"k": list("aab"), "v": [1, 2, 3]})
    out = str(summary(df.groupby("k")))
    assert 'class="pavement-spark"' not in out
    assert 'class="pavement-proportion"' not in out


def test_summary_dataframe_groupby_is_wellformed_xml():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"k": list("aabbc"), "v": [1, 2, None, 4, 5], "w": range(5)})
    _wellformed(str(summary(df.groupby("k"))))
