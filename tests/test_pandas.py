"""
Tests for the pandas integration in ``pavement.pandas``: the ``.pave``
accessor on DataFrame and Series, and the opt-in ``enable_repr`` /
``disable_repr`` summary display. Skipped wholesale when pandas is absent.
"""

import pytest

pd = pytest.importorskip("pandas")

import pavement.pandas as pp  # noqa: E402  (importing registers the accessor)
from pavement._inline import SVG  # noqa: E402
from pavement.svg import Summary  # noqa: E402


# ---------------------------------------------------------------------------
# The renderable svg wrapper
# ---------------------------------------------------------------------------

def test_svg_wrapper_is_a_string_that_also_renders():
    x = SVG("<svg>hi</svg>")
    assert isinstance(x, str)                 # behaves like the plain string
    assert x.startswith("<svg")
    assert x._repr_html_() == "<svg>hi</svg>"  # but renders inline in Jupyter


# ---------------------------------------------------------------------------
# DataFrame accessor
# ---------------------------------------------------------------------------

def test_accessor_is_registered():
    assert hasattr(pd.DataFrame({"a": [1]}), "pave")
    assert hasattr(pd.Series([1]), "pave")


def test_df_pave_call_and_summary_return_a_summary():
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "x"]})
    assert isinstance(df.pave(), Summary)
    assert isinstance(df.pave.summary(), Summary)
    assert "<table" in str(df.pave())
    assert "3 rows" in str(df.pave())          # the whole-frame summary


def test_df_pave_forwards_kwargs_to_summary():
    df = pd.DataFrame({"a": [1, 2, 3]})
    assert "height:2.5em" in str(df.pave(height="2.5em"))


def test_df_pave_spark_returns_renderable_svg_string():
    df = pd.DataFrame({"n": [1, 2, 3, 4, 5]})
    out = df.pave.spark("n")
    assert isinstance(out, str)                # is the svg string…
    assert out.startswith("<svg")
    assert out._repr_html_() == str(out)       # …and renders inline
    assert 'class="pavement-spark"' in out


def test_df_pave_spark_drops_missing():
    # A raw spark can't sort NaN; the accessor drops missing first.
    df = pd.DataFrame({"n": [1.0, 2.0, float("nan"), 4.0, 5.0]})
    assert df.pave.spark("n").startswith("<svg")


def test_df_pave_spark_forwards_kwargs():
    df = pd.DataFrame({"n": list(range(50))})  # 50 distinct -> 4 bins by default
    assert df.pave.spark("n", bins=None).count('class="pvbin"') == 0  # forced rug


def test_df_pave_tally_counts_entries_including_missing():
    df = pd.DataFrame({"c": ["a", "a", "b", None]})
    out = df.pave.tally("c")
    assert out.startswith("<svg")
    assert "entries" in out                    # tally counts entries (incl. missing)


def test_df_pave_proportion_counts_present_values():
    df = pd.DataFrame({"c": ["a", "a", "b", None]})
    out = df.pave.proportion("c")
    assert out.startswith("<svg")
    assert "values" in out                     # proportion counts present values


# ---------------------------------------------------------------------------
# Series accessor — the column helpers take no column name
# ---------------------------------------------------------------------------

def test_series_pave_call_and_summary():
    s = pd.Series([1, 2, 2, 3, None], name="ignored")
    assert isinstance(s.pave(), Summary)
    assert isinstance(s.pave.summary(), Summary)
    assert "5 entries" in str(s.pave())        # the count, not the name


def test_series_pave_strip_helpers():
    s = pd.Series([1, 2, 2, 3, None])
    assert s.pave.spark().startswith("<svg")   # numeric, missing dropped
    assert s.pave.tally().startswith("<svg")
    assert pd.Series(["a", "a", "b"]).pave.proportion().startswith("<svg")


# ---------------------------------------------------------------------------
# Opt-in summary repr
# ---------------------------------------------------------------------------

@pytest.fixture
def ipython_shell(monkeypatch):
    """A throwaway IPython shell that `get_ipython()` resolves to, torn down
    (and its formatters cleared) afterward so tests don't leak into each
    other."""
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
    html = fmt.lookup_by_type(pd.DataFrame)(
        pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "x"]}))
    assert "<table" in html and "height:2em" in html           # forwarded kwarg
    assert "<table" in fmt.lookup_by_type(pd.Series)(pd.Series([1, 2, 3]))


def test_disable_repr_restores_default(ipython_shell):
    pp.enable_repr()
    fmt = ipython_shell.display_formatter.formatters["text/html"]
    fmt.lookup_by_type(pd.DataFrame)                # registered now
    pp.disable_repr()
    with pytest.raises(KeyError):                   # gone again
        fmt.lookup_by_type(pd.DataFrame)


def test_enable_repr_series_false_leaves_series_alone(ipython_shell):
    pp.enable_repr(series=False)
    fmt = ipython_shell.display_formatter.formatters["text/html"]
    assert "<table" in fmt.lookup_by_type(pd.DataFrame)(pd.DataFrame({"a": [1]}))
    with pytest.raises(KeyError):
        fmt.lookup_by_type(pd.Series)


def test_enable_repr_without_a_session_raises(monkeypatch):
    # No running IPython -> a clear error rather than silently doing nothing.
    # Whether IPython is merely not *running* (get_ipython() is None) or not
    # installed at all (ModuleNotFoundError), the functions must raise.
    try:
        import IPython
    except ModuleNotFoundError:
        pass  # not installed: enable_repr raises for that reason on its own
    else:
        monkeypatch.setattr(IPython, "get_ipython", lambda: None)
    with pytest.raises(RuntimeError):
        pp.enable_repr()
    with pytest.raises(RuntimeError):
        pp.disable_repr()
