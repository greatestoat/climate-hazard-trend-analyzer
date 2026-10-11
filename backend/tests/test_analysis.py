from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.errors import InsufficientDataError
from app.services.analysis import (analyze, clean_series, compute_threshold, detect_events, linear_trend, pct_change)
from tests.helpers import synthetic_rows


def series_from(values, start=date(2020, 1, 1)):
    idx = pd.date_range(start, periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype=float)


def test_detects_runs_of_three_or_more_and_ignores_shorter():
    s = series_from([30, 40, 40, 30, 40, 40, 40, 40, 30, 40, 40, 30])
    thr = pd.Series(35.0, index=s.index)
    events, mask = detect_events(s, thr, 3)
    assert len(events) == 1
    e = events[0]
    assert e["duration_days"] == 4 and e["start"] == "2020-01-05" and e["end"] == "2020-01-08"
    assert e["peak_temp_c"] == 40 and mask.sum() == 4


def test_threshold_is_strictly_greater_than():
    s = series_from([35, 35, 35, 35])
    events, _ = detect_events(s, pd.Series(35.0, index=s.index), 3)
    assert events == []


def test_missing_day_breaks_an_event():
    s = series_from([40, 40, np.nan, 40, 40])
    events, _ = detect_events(s, pd.Series(35.0, index=s.index), 3)
    assert events == []


def test_clean_handles_duplicates_invalid_outliers_and_gaps():
    start, end = date(2020, 1, 1), date(2020, 1, 10)
    rows = [("2020-01-01", 20), ("2020-01-02", 22), ("2020-01-02", 24),   # duplicate -> mean 23
            ("2020-01-03", None), ("2020-01-04", 999),                    # gap + physical outlier
            ("2020-01-05", 25), ("bad-date", 5), ("2020-01-07", "x"),
            ("2020-01-08", 28), ("2020-01-10", 30)]
    c = clean_series(rows, start, end)
    q = c.quality
    assert q["duplicates_removed"] == 1 and q["invalid_rows"] == 1 and q["outliers_removed"] == 1
    assert c.series["2020-01-02"] == 23
    assert not np.isnan(c.series["2020-01-03"])  # 3rd-4th Jan gap (2 days) interpolated
    assert not np.isnan(c.series["2020-01-04"])
    assert q["interpolated_days"] >= 2


def test_long_gaps_are_not_interpolated():
    rows = [("2020-01-01", 20)] + [("2020-01-06", 25)]
    c = clean_series(rows, date(2020, 1, 1), date(2020, 1, 6))
    assert c.series.isna().sum() == 4 and c.quality["interpolated_days"] == 0


def test_statistical_outlier_removed_but_real_heat_kept():
    rows = synthetic_rows(date(2000, 1, 1), date(2009, 12, 31), seed=3, heatwaves=[(date(2005, 6, 1), 5, 6.0)])
    rows[1000] = (rows[1000][0], rows[1000][1] + 60)  # sensor spike
    c = clean_series(rows, date(2000, 1, 1), date(2009, 12, 31))
    assert c.quality["outliers_removed"] >= 1
    assert c.series.loc["2005-06-03"] > 30  # genuine heatwave retained


def test_seasonal_threshold_varies_through_year():
    rows = synthetic_rows(date(2000, 1, 1), date(2014, 12, 31))
    c = clean_series(rows, date(2000, 1, 1), date(2014, 12, 31))
    thr, nominal = compute_threshold(c.series, 95, "seasonal")
    assert thr.max() - thr.min() > 5


def test_insufficient_data_raises():
    s = series_from([np.nan] * 400)
    with pytest.raises(InsufficientDataError):
        compute_threshold(s, 95, "period")


def test_full_analysis_incomplete_years_trend_and_changes():
    start, end = date(1995, 1, 1), date(2024, 6, 30)  # final year is incomplete
    hw = [(date(2010, 6, 1), 6, 8.0), (date(2020, 5, 10), 4, 8.0)]
    rows = synthetic_rows(start, end, warming_per_year=0.08, seed=7, heatwaves=hw)
    r = analyze(clean_series(rows, start, end), start, end, 95, 3, "period")
    annual = {a["year"]: a for a in r["annual"]}
    assert annual[2024]["complete"] is False and 2024 in r["summary"]["incomplete_years"]
    assert r["summary"]["complete_years"] == 29
    t = r["trend"]["heatwave_days"]
    assert t["available"] and t["slope_per_decade"] > 0 and t["significant"]
    assert annual[2024]["trend_heatwave_days"] is None and annual[2024]["rolling_heatwave_days"] is None
    assert annual[2010]["max_duration_days"] >= 6
    assert r["summary"]["total_heatwave_days"] == sum(a["heatwave_days"] for a in r["annual"])
    assert r["changes"]["heatwave_days"]["valid"] and r["changes"]["heatwave_days"]["pct_change"] > 0
    assert all(i["text"] for i in r["insights"])


def test_pct_change_undefined_when_baseline_zero_or_short():
    assert pct_change([2000, 2001], [1, 2])["valid"] is False
    res = pct_change(list(range(2000, 2008)), [0, 0, 0, 0, 2, 3, 4, 5])
    assert res["valid"] is False and res["pct_change"] is None and "undefined" in res["reason"]
    assert pct_change(list(range(2000, 2008)), [2, 2, 2, 2, 3, 3, 3, 3])["pct_change"] == 50.0


def test_trend_requires_variation_and_enough_years():
    assert linear_trend(np.arange(3.0), np.arange(3.0))["available"] is False
    assert linear_trend(np.arange(10.0), np.ones(10))["available"] is False
    t = linear_trend(np.arange(10.0), np.arange(10.0) * 2)
    assert t["slope_per_year"] == 2.0 and t["direction"] == "increasing"
