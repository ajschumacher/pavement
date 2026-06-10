"""
Tests for the polars integration: `pavement.summary` on a polars frame/series
(via the `_as_columns` extension) and the ``.pave`` namespace plus opt-in
``enable_repr`` / ``disable_repr`` in ``pavement.polars``. Skipped wholesale
when polars is absent.
"""

import re
import xml.dom.minidom as minidom

import pytest

pl = pytest.importorskip("polars")

import pavement.polars as pp  # noqa: E402  (importing registers the namespace)
from pavement.svg import Summary, summary  # noqa: E402


def _wellformed(markup):
    minidom.parseString(markup)


def _titles(html):
    return re.findall(r"<title>(.*?)</title>", html, re.S)


# ---------------------------------------------------------------------------
# summary() on polars objects (the _as_columns extension)
# ---------------------------------------------------------------------------

def test_summary_on_polars_dataframe():
    df = pl.DataFrame({
        "id": list(range(1, 61)),                          # numeric -> spark
        "grp": (["a", "b", "c"] * 20),                     # categorical -> proportion
        "flag": [True, False] * 30,                        # bool -> proportion
    })
    out = str(summary(df))
    _wellformed(out)
    assert "60 rows" in out
    assert 'class="pavement-spark"' in out
    assert 'class="pavement-proportion"' in out
    for name in ("id", "grp", "flag"):
        assert f">{name}</span>" in out


def test_summary_polars_numeric_with_nulls_is_a_spark():
    # Nulls (and a NaN) are dropped for the spark, not mistaken for non-numeric.
    df = pl.DataFrame({"x": [1.0, 2.0, None, 4.0, float("nan"), 6.0]})
    out = str(summary(df))
    assert 'class="pavement-spark"' in out
    _wellformed(out)


def test_summary_polars_row_tally_counts_whole_rows():
    # rows: (1,x), (1,x)=repeat, all-null, (2,y)
    df = pl.DataFrame({"a": [1, 1, None, 2], "b": ["x", "x", None, "y"]})
    top = _titles(str(summary(df)))
    assert any("distinct" in t and "2 of 4 rows" in t for t in top)
    assert any("duplicate" in t and "1 of 4 rows" in t for t in top)
    assert any("missing" in t and "1 of 4 rows" in t for t in top)


def test_summary_on_polars_series():
    s = pl.Series("ignored", [1, 2, 2, 3, None])
    out = str(summary(s))
    assert "5 entries" in out                  # the count, not the name
    assert 'class="pavement-spark"' in out
    _wellformed(out)


# ---------------------------------------------------------------------------
# The .pave namespace
# ---------------------------------------------------------------------------

def test_namespace_is_registered():
    df = pl.DataFrame({"a": [1, 2, 3]})
    assert hasattr(df, "pave")
    assert hasattr(pl.Series("s", [1]), "pave")


def test_df_pave_call_and_summary_return_a_summary():
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "x"]})
    assert isinstance(df.pave(), Summary)
    assert isinstance(df.pave.summary(), Summary)
    assert "3 rows" in str(df.pave())


def test_df_pave_forwards_kwargs():
    df = pl.DataFrame({"a": [1, 2, 3]})
    assert "height:2.5em" in str(df.pave(height="2.5em"))


def test_df_pave_spark_returns_renderable_svg_string():
    df = pl.DataFrame({"n": [1, 2, 3, 4, 5]})
    out = df.pave.spark("n")
    assert isinstance(out, str) and out.startswith("<svg")
    assert out._repr_html_() == str(out)
    assert 'class="pavement-spark"' in out


def test_df_pave_spark_drops_nulls():
    df = pl.DataFrame({"n": [1.0, 2.0, None, 4.0, 5.0]})
    assert df.pave.spark("n").startswith("<svg")


def test_df_pave_spark_forwards_kwargs():
    df = pl.DataFrame({"n": list(range(50))})
    assert df.pave.spark("n", bins=None).count('class="pvbin"') == 0   # forced rug


def test_df_pave_tally_and_proportion():
    df = pl.DataFrame({"c": ["a", "a", "b", None]})
    assert "entries" in df.pave.tally("c")     # tally counts entries (incl. null)
    assert "values" in df.pave.proportion("c")  # proportion counts present values


def test_series_pave_helpers():
    s = pl.Series("x", [1, 2, 2, 3, None])
    assert isinstance(s.pave(), Summary)
    assert isinstance(s.pave.summary(), Summary)
    assert "5 entries" in str(s.pave())
    assert s.pave.spark().startswith("<svg")    # numeric, nulls dropped
    assert s.pave.tally().startswith("<svg")
    assert pl.Series("c", ["a", "a", "b"]).pave.proportion().startswith("<svg")


# ---------------------------------------------------------------------------
# .pebbles namespace — a polars Series has no index, so pebbles comes from a
# two-column (labels, values) frame, e.g. group_by(k).agg(...).
# ---------------------------------------------------------------------------

def test_df_pebbles_is_registered():
    assert hasattr(pl.DataFrame({"k": ["a"], "v": [1]}), "pebbles")


def test_df_pebbles_renders_one_pebble_per_label():
    df = pl.DataFrame({"team": ["a", "a", "b", "b", "c"],
                       "score": [1, 2, 10, 12, 5]})
    agg = df.group_by("team").agg(pl.col("score").mean()).sort("team")
    out = str(agg.pebbles())
    assert isinstance(agg.pebbles(), Summary)
    assert out.count('class="pavement-spark"') == 4   # pooled header + 3 labels
    _wellformed(out)
    for label in ("a", "b", "c"):
        assert f">{label}</span>" in out


def test_df_pebbles_value_column_names_the_header():
    agg = pl.DataFrame({"team": ["a", "b", "c"], "score": [1.5, 11.0, 5.0]})
    out = str(agg.pebbles())
    assert "score" in out          # the value column titles the pooled header
    assert "3 labels" in out


def test_df_pebbles_forwards_kwargs():
    agg = pl.DataFrame({"team": ["a", "b", "c"], "score": [1.5, 11.0, 5.0]})
    assert "height:2.5em" in str(agg.pebbles(height="2.5em"))


@pytest.mark.parametrize("cols", [{"only": [1, 2]},
                                  {"a": [1], "b": [2], "c": [3]}])
def test_df_pebbles_requires_exactly_two_columns(cols):
    with pytest.raises(ValueError, match="exactly 2 columns"):
        pl.DataFrame(cols).pebbles()


# ---------------------------------------------------------------------------
# Opt-in summary repr
# ---------------------------------------------------------------------------

@pytest.fixture
def ipython_shell(monkeypatch):
    """A throwaway IPython shell `get_ipython()` resolves to, torn down (and its
    formatters cleared) afterward so tests don't leak into each other."""
    pytest.importorskip("IPython")
    from IPython.core.interactiveshell import InteractiveShell
    shell = InteractiveShell.instance()
    monkeypatch.setattr("IPython.get_ipython", lambda: shell)
    try:
        yield shell
    finally:
        try:
            pp.disable_repr()
        except Exception:
            pass
        InteractiveShell.clear_instance()


def test_enable_repr_renders_frames_as_summaries(ipython_shell):
    pp.enable_repr(height="2em")
    fmt = ipython_shell.display_formatter.formatters["text/html"]
    html = fmt.lookup_by_type(pl.DataFrame)(pl.DataFrame({"a": [1, 2, 3]}))
    assert "<table" in html and "height:2em" in html
    assert "<table" in fmt.lookup_by_type(pl.Series)(pl.Series("s", [1, 2, 3]))


def test_disable_repr_restores_default(ipython_shell):
    pp.enable_repr()
    fmt = ipython_shell.display_formatter.formatters["text/html"]
    fmt.lookup_by_type(pl.DataFrame)               # registered now
    pp.disable_repr()
    with pytest.raises(KeyError):
        fmt.lookup_by_type(pl.DataFrame)


# ---------------------------------------------------------------------------
# GroupBy — summary() and .pave accessor
# ---------------------------------------------------------------------------

def test_summary_on_polars_groupby():
    df = pl.DataFrame({"k": list("aabbb"), "v": [1, 2, 3, 4, 5]})
    out = str(summary(df.group_by("k", maintain_order=True)))
    assert "2 groups" in out
    assert ">a<" in out
    assert ">b<" in out


def test_summary_polars_groupby_header_tally_covers_all_rows():
    df = pl.DataFrame({"k": list("aab"), "v": [1, 1, 2]})
    titles = _titles(str(summary(df.group_by("k"))))
    assert any("of 3 rows" in t for t in titles)


def test_summary_polars_groupby_no_distribution_cells():
    df = pl.DataFrame({"k": list("aab"), "v": [1, 2, 3]})
    out = str(summary(df.group_by("k")))
    assert 'class="pavement-spark"' not in out
    assert 'class="pavement-proportion"' not in out


def test_summary_polars_groupby_multi_key():
    df = pl.DataFrame({"region": list("NNSS"), "dept": ["eng","eng","mkt","mkt"],
                       "v": [1, 2, 3, 4]})
    out = str(summary(df.group_by("region", "dept", maintain_order=True)))
    assert "N / eng" in out
    assert "S / mkt" in out


def test_summary_polars_groupby_is_wellformed_xml():
    import xml.dom.minidom as minidom
    df = pl.DataFrame({"k": list("aabbc"), "v": [1, 2, None, 4, 5]})
    minidom.parseString(str(summary(df.group_by("k"))))


def test_polars_groupby_pave_accessor_registered():
    df = pl.DataFrame({"k": list("aab"), "v": [1, 2, 3]})
    assert hasattr(df.group_by("k"), "pave")


def test_polars_groupby_pave_call_returns_summary():
    df = pl.DataFrame({"k": list("aab"), "v": [1, 2, 3]})
    result = df.group_by("k").pave()
    assert isinstance(result, Summary)
    assert "2 groups" in str(result)


def test_polars_groupby_pave_summary_method():
    df = pl.DataFrame({"k": list("aab"), "v": [1, 2, 3]})
    assert isinstance(df.group_by("k").pave.summary(), Summary)


def test_polars_groupby_pave_forwards_kwargs():
    df = pl.DataFrame({"k": list("aab"), "v": [1, 2, 3]})
    assert "height:2.5em" in str(df.group_by("k").pave(height="2.5em"))


def test_enable_repr_without_a_session_raises(monkeypatch):
    try:
        import IPython
    except ModuleNotFoundError:
        pass
    else:
        monkeypatch.setattr(IPython, "get_ipython", lambda: None)
    with pytest.raises(RuntimeError):
        pp.enable_repr()
    with pytest.raises(RuntimeError):
        pp.disable_repr()
