"""
Tests for ordered non-float column types — ``date``, ``datetime``,
``Decimal``, ``timedelta``, and numpy ``datetime64``/``timedelta64``. They are
projected onto a numeric axis (`pavement.svg._project`) and drawn as pavement
sparks in `spark` — and so in `summary` and the accessors — rather than
treated as categorical.
"""

import datetime as dt
import re
import xml.dom.minidom as minidom
from decimal import Decimal

import pytest

from pavement.svg import _pavement_column, _project, spark, summary


def _wf(markup):
    minidom.parseString(markup)


def _titles(html):
    return re.findall(r"<title>(.*?)</title>", html, re.S)


# ---------------------------------------------------------------------------
# _project: map an ordered family onto a numeric axis + a back-formatter
# ---------------------------------------------------------------------------

def test_project_real_numbers_pass_through():
    data, value_format = _project([1, 2, 3])
    assert data == [1, 2, 3]
    assert value_format is None


def test_project_decimal_becomes_float():
    data, value_format = _project([Decimal("1.5"), Decimal("2.5")])
    assert data == [1.5, 2.5]
    assert all(isinstance(x, float) for x in data)
    assert value_format is None


def test_project_date_to_monotonic_seconds_with_date_formatter():
    data, value_format = _project([dt.date(2020, 1, 1), dt.date(2020, 6, 1)])
    assert all(isinstance(x, float) for x in data)
    assert data[0] < data[1]                       # order preserved
    assert value_format(data[0]) == "2020-01-01"   # rendered back as a date


def test_project_datetime_formatter_shows_time():
    data, value_format = _project([dt.datetime(2020, 1, 1, 9, 30),
                                   dt.datetime(2020, 1, 1, 17, 0)])
    assert value_format(data[1]) == "2020-01-01 17:00"


def test_project_all_midnight_datetimes_render_as_dates():
    # pandas "date" columns are midnight Timestamps; show them as plain dates.
    data, value_format = _project([dt.datetime(2020, 1, 1), dt.datetime(2020, 1, 2)])
    assert value_format(data[0]) == "2020-01-01"   # no trailing " 00:00"


# ---------------------------------------------------------------------------
# spark draws the projected families
# ---------------------------------------------------------------------------

def test_spark_on_dates():
    dates = [dt.date(2020, 1, 1) + dt.timedelta(days=30 * i) for i in range(12)]
    out = spark(dates, bins=4)
    _wf(out)
    assert out.count('class="pvbin"') == 4
    assert "2020-01-01" in out                     # a date appears in a tooltip


def test_spark_on_datetimes_shows_time_in_tooltip():
    dts = [dt.datetime(2021, 1, 1, 8) + dt.timedelta(hours=3 * i) for i in range(12)]
    out = spark(dts, bins=4)
    _wf(out)
    assert re.search(r"2021-\d\d-\d\d \d\d:\d\d", out)


def test_spark_on_decimals():
    out = spark([Decimal(n) / Decimal(7) for n in range(1, 20)], bins=4)
    _wf(out)
    assert out.count('class="pvbin"') == 4


def test_spark_date_rug_has_per_value_dates():
    dates = [dt.date(2020, 1, 1) + dt.timedelta(days=i) for i in range(10)]
    out = spark(dates, bins=None)
    _wf(out)
    assert any("2020-01-0" in t for t in _titles(out))   # a date in a tick tooltip


def test_spark_numbers_unchanged_by_projection():
    # Real numbers pass straight through — identical to before the feature.
    out = spark([1, 2, 3, 4, 5], bins=4)
    assert out.count('class="pvbin"') == 4
    assert "1 to 2" in out                         # value range still numeric


def test_spark_custom_value_format_overrides_date_default():
    dates = [dt.date(2020, 1, 1), dt.date(2020, 1, 2), dt.date(2020, 1, 3)]
    out = spark(dates, bins=None, value_format=lambda _s: "X")
    titles = _titles(out)
    # The value part of every tick tooltip is the custom "X" (the quantile
    # percent prefix remains), and the default date rendering is gone.
    assert titles and all("X" in t for t in titles)
    assert "2020-01-01" not in out


# ---------------------------------------------------------------------------
# _pavement_column: one ordered family -> a spark; mixed/other -> proportion
# ---------------------------------------------------------------------------

def test_pavement_column_accepts_single_ordered_families():
    assert _pavement_column([1, 2, 3])
    assert _pavement_column([Decimal("1"), Decimal("2")])
    assert _pavement_column([dt.date(2020, 1, 1), dt.date(2020, 1, 2)])
    # datetime is a subclass of date, so they count as one family.
    assert _pavement_column([dt.date(2020, 1, 1), dt.datetime(2020, 1, 2, 5)])


def test_pavement_column_rejects_mixed_or_categorical():
    assert not _pavement_column([1, dt.date(2020, 1, 1)])   # mixed families
    assert not _pavement_column(["a", "b"])
    assert not _pavement_column([True, False])              # two-level category
    assert not _pavement_column([])


# ---------------------------------------------------------------------------
# summary draws these columns as pavements, not proportions
# ---------------------------------------------------------------------------

def test_summary_date_column_is_a_spark():
    dates = [dt.date(2020, 1, 1) + dt.timedelta(days=i) for i in range(40)]
    out = str(summary({"d": dates}))
    assert 'class="pavement-spark"' in out
    assert 'class="pavement-proportion"' not in out


def test_summary_datetime_column_is_a_spark():
    dts = [dt.datetime(2020, 1, 1) + dt.timedelta(hours=i) for i in range(40)]
    assert 'class="pavement-spark"' in str(summary({"t": dts}))


def test_summary_decimal_column_is_a_spark():
    out = str(summary({"p": [Decimal(n) / Decimal(3) for n in range(40)]}))
    assert 'class="pavement-spark"' in out


def test_summary_date_column_resolution_follows_distinct_count():
    # <=24 distinct dates -> a rug: one tick per distinct date, and any boxes
    # are the zero-interior gaps between values rather than equal-mass bins.
    few = [dt.date(2020, 1, 1), dt.date(2020, 1, 2), dt.date(2020, 1, 3)] * 5
    html = str(summary({"d": few}))
    assert html.count('class="pvtick"') == 3       # one tick per distinct date
    gaps = re.findall(r'<rect class="pvbin".*?<title>(.*?)</title>', html, re.S)
    assert gaps and all("(0 of" in g for g in gaps)


def test_summary_mixed_date_and_number_column_is_categorical():
    # Not one family -> falls back to a proportion (and doesn't crash).
    out = str(summary({"m": [1, dt.date(2020, 1, 1), "x"]}))
    assert 'class="pavement-proportion"' in out
    assert 'class="pavement-spark"' not in out


# ---------------------------------------------------------------------------
# pandas / polars temporal columns (skipped if not installed)
# ---------------------------------------------------------------------------

def test_summary_pandas_datetime_column_is_a_spark():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"d": pd.to_datetime(
        ["2020-01-01", "2020-02-01", "2020-03-01", "2020-04-01", "2020-05-01"])})
    assert 'class="pavement-spark"' in str(summary(df))


def test_summary_polars_date_column_is_a_spark():
    pl = pytest.importorskip("polars")
    df = pl.DataFrame({"d": [dt.date(2020, 1, 1), dt.date(2020, 2, 1),
                             dt.date(2020, 3, 1), dt.date(2020, 4, 1)]})
    assert 'class="pavement-spark"' in str(summary(df))


# ---------------------------------------------------------------------------
# timedelta: Python timedelta, pandas Timedelta, polars Duration
# ---------------------------------------------------------------------------

def test_project_timedelta_whole_days():
    data, fmt = _project([dt.timedelta(days=1), dt.timedelta(days=7)])
    assert data == [86400.0, 7 * 86400.0]
    assert fmt(86400.0) == "1 day"
    assert fmt(7 * 86400.0) == "7 days"


def test_project_timedelta_sub_day():
    data, fmt = _project([dt.timedelta(hours=1, minutes=30),
                          dt.timedelta(hours=25, minutes=5)])
    assert data[0] == pytest.approx(5400.0)
    assert fmt(5400.0) == "01:30"
    assert fmt(25 * 3600 + 5 * 60) == "1d 01:05"


def test_project_timedelta_with_seconds():
    # When any value has a non-zero second component, format includes :SS.
    data, fmt = _project([dt.timedelta(seconds=45),
                          dt.timedelta(hours=1, minutes=2, seconds=3)])
    assert fmt(45.0) == "00:00:45"
    assert fmt(3600 + 120 + 3) == "01:02:03"


def test_project_timedelta_with_seconds_multi_day():
    _, fmt = _project([dt.timedelta(days=1, seconds=30),
                       dt.timedelta(hours=2)])
    assert fmt(86400 + 30) == "1d 00:00:30"
    assert fmt(7200.0) == "02:00:00"   # whole-minute value rendered with :SS


def test_project_timedelta_negative_whole_days():
    _, fmt = _project([dt.timedelta(days=-2), dt.timedelta(days=-1)])
    assert fmt(-2 * 86400.0) == "-2 days"
    assert fmt(-86400.0) == "-1 day"


def test_pavement_column_accepts_timedelta():
    assert _pavement_column([dt.timedelta(1), dt.timedelta(2), dt.timedelta(3)])


def test_pavement_column_rejects_mixed_timedelta_and_number():
    assert not _pavement_column([dt.timedelta(1), 1])


def test_spark_on_timedeltas():
    deltas = [dt.timedelta(hours=i) for i in range(1, 25)]
    out = spark(deltas, bins=4)
    _wf(out)
    assert out.count('class="pvbin"') == 4
    assert re.search(r"\d+:\d{2}", out)          # an HH:MM appears in a tooltip


def test_summary_timedelta_column_is_a_spark():
    deltas = [dt.timedelta(hours=i) for i in range(1, 41)]
    out = str(summary({"duration": deltas}))
    assert 'class="pavement-spark"' in out
    assert 'class="pavement-proportion"' not in out


def test_summary_pandas_timedelta_column_is_a_spark():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"delta": pd.to_timedelta(
        [f"{i} days" for i in range(1, 30)])})
    assert 'class="pavement-spark"' in str(summary(df))


def test_summary_polars_duration_column_is_a_spark():
    pl = pytest.importorskip("polars")
    df = pl.DataFrame({"dur": [dt.timedelta(hours=i) for i in range(1, 30)]})
    assert 'class="pavement-spark"' in str(summary(df))


# ---------------------------------------------------------------------------
# numpy datetime64 / timedelta64 (skipped if numpy not installed)
# ---------------------------------------------------------------------------

def test_project_numpy_datetime64():
    np = pytest.importorskip("numpy")
    dates = [np.datetime64('2020-01-01', 'D') + np.timedelta64(i * 30, 'D')
             for i in range(5)]
    data, fmt = _project(dates)
    assert all(isinstance(x, float) for x in data)
    assert data[0] < data[-1]                        # order preserved
    assert re.match(r"\d{4}-\d{2}-\d{2}", fmt(data[0]))


def test_project_numpy_timedelta64():
    np = pytest.importorskip("numpy")
    deltas = [np.timedelta64(i * 3600, 's') for i in range(1, 6)]
    data, fmt = _project(deltas)
    assert all(isinstance(x, float) for x in data)
    assert data[0] < data[-1]
    assert ":" in fmt(data[0])                       # HH:MM appears


def test_project_numpy_datetime64_ns_precision():
    np = pytest.importorskip("numpy")
    dates = [np.datetime64('2020-01-01T12:00:00', 'ns'),
             np.datetime64('2020-06-01T00:00:00', 'ns')]
    data, fmt = _project(dates)
    assert all(isinstance(x, float) for x in data)
    assert data[0] < data[1]


def test_pavement_column_accepts_numpy_datetime64():
    np = pytest.importorskip("numpy")
    col = [np.datetime64('2020-01-01', 'D') + np.timedelta64(i, 'D')
           for i in range(5)]
    assert _pavement_column(col)


def test_pavement_column_accepts_numpy_timedelta64():
    np = pytest.importorskip("numpy")
    col = [np.timedelta64(i * 3600, 's') for i in range(1, 6)]
    assert _pavement_column(col)


def test_pavement_column_rejects_mixed_numpy_temporal_types():
    np = pytest.importorskip("numpy")
    assert not _pavement_column([np.datetime64('2020-01-01', 'D'),
                                 np.timedelta64(1, 'D')])


def test_summary_numpy_datetime64_column_is_a_spark():
    np = pytest.importorskip("numpy")
    col = [np.datetime64('2020-01-01', 'D') + np.timedelta64(i * 30, 'D')
           for i in range(40)]
    out = str(summary({"event": col}))
    assert 'class="pavement-spark"' in out


def test_summary_numpy_timedelta64_column_is_a_spark():
    np = pytest.importorskip("numpy")
    col = [np.timedelta64(i * 3600, 's') for i in range(1, 41)]
    out = str(summary({"delay": col}))
    assert 'class="pavement-spark"' in out
