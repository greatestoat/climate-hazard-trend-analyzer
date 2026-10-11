"""Pure analysis logic (no I/O): cleaning, thresholds, heatwave detection, trends."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from scipy import stats

from app.errors import InsufficientDataError

MIN_COVERAGE = 0.90        # a year needs >= 90% valid days to count as complete
MAX_INTERP_GAP = 2         # only gaps of <= 2 consecutive days are interpolated
PHYS_MIN, PHYS_MAX = -90.0, 60.0
OUTLIER_SIGMA = 8.0        # robust sigma on day-of-year anomalies; real extreme heat is kept
SEASONAL_HALF_WINDOW = 7
ROLLING_WINDOW = 5
MIN_TREND_YEARS = 5
MIN_CHANGE_YEARS = 6


def _f(x, nd: int = 2):
    if x is None:
        return None
    x = float(x)
    return None if np.isnan(x) or np.isinf(x) else round(x, nd)


@dataclass
class CleanResult:
    series: pd.Series       # daily, full range, gaps <=2 days interpolated
    raw_valid: pd.Series    # cleaned but not interpolated, NaN dropped (what we persist)
    quality: dict


def clean_series(rows: list[tuple], start: date, end: date) -> CleanResult:
    q = dict(rows_received=len(rows), invalid_rows=0, duplicates_removed=0,
             outliers_removed=0, interpolated_days=0)
    df = pd.DataFrame(rows, columns=["date", "tmax"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["tmax"] = pd.to_numeric(df["tmax"], errors="coerce")
    bad = df["date"].isna()
    q["invalid_rows"] = int(bad.sum())
    df = df[~bad].copy()
    df["date"] = df["date"].dt.normalize()
    df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]
    q["duplicates_removed"] = int(len(df) - df["date"].nunique())
    s = df.groupby("date")["tmax"].mean()  # duplicate dates are averaged

    phys = (s < PHYS_MIN) | (s > PHYS_MAX)
    q["outliers_removed"] += int(phys.sum())
    s = s.mask(phys)

    idx = pd.date_range(start, end, freq="D")
    s = s.reindex(idx)

    if s.notna().sum() >= 5 * 300:
        doy = np.minimum(idx.dayofyear.values, 365)
        clim = s.groupby(doy).transform("median")
        anom = s - clim
        mad = np.nanmedian(np.abs(anom - np.nanmedian(anom)))
        sigma = 1.4826 * mad
        if sigma > 0:
            out = (anom.abs() > OUTLIER_SIGMA * sigma) & s.notna()
            q["outliers_removed"] += int(out.sum())
            s = s.mask(out)

    raw_valid = s.dropna()

    isna = s.isna()
    run_id = (isna != isna.shift()).cumsum()
    run_len = isna.groupby(run_id).transform("sum")
    fillable = isna & (run_len <= MAX_INTERP_GAP)
    interp = s.interpolate(limit_area="inside")
    filled = s.where(~fillable, interp)
    q["interpolated_days"] = int((fillable & filled.notna()).sum())
    s = filled

    q["total_days"] = int(len(s))
    q["valid_days"] = int(s.notna().sum())
    q["missing_days"] = q["total_days"] - q["valid_days"]
    q["missing_pct"] = _f(100 * q["missing_days"] / max(q["total_days"], 1), 2)
    return CleanResult(s, raw_valid, q)


def compute_threshold(s: pd.Series, percentile: float, method: str):
    valid = s.dropna()
    if len(valid) < 3 * 365 * 0.5:
        raise InsufficientDataError("Not enough valid temperature data to compute a threshold.")
    if method == "period":
        t = float(np.percentile(valid.values, percentile))
        return pd.Series(t, index=s.index), t
    doy = np.minimum(s.index.dayofyear.values, 365)
    vals = s.values
    by_doy = np.full(366, np.nan)
    for d in range(1, 366):
        offs = (np.arange(-SEASONAL_HALF_WINDOW, SEASONAL_HALF_WINDOW + 1) + d - 1) % 365 + 1
        m = np.isin(doy, offs) & ~np.isnan(vals)
        if m.sum() >= 30:
            by_doy[d] = np.percentile(vals[m], percentile)
    return pd.Series(by_doy[doy], index=s.index), float(np.nanmean(by_doy[1:]))


def detect_events(s: pd.Series, thr: pd.Series, min_duration: int):
    vals, th = s.values, thr.values
    exceed = (vals > th) & ~np.isnan(vals)      # NaN comparisons are False, so gaps break events
    diff = np.diff(np.concatenate([[0], exceed.astype(np.int8), [0]]))
    starts, ends = np.flatnonzero(diff == 1), np.flatnonzero(diff == -1)
    mask = np.zeros(len(s), dtype=bool)
    events = []
    for a, b in zip(starts, ends):
        n = int(b - a)
        if n < min_duration:
            continue
        seg, tseg = vals[a:b], th[a:b]
        mask[a:b] = True
        pk = int(np.argmax(seg))
        events.append({
            "start": s.index[a].date().isoformat(),
            "end": s.index[b - 1].date().isoformat(),
            "year": int(s.index[a].year),
            "duration_days": n,
            "peak_temp_c": _f(seg[pk]),
            "peak_date": s.index[a + pk].date().isoformat(),
            "mean_temp_c": _f(seg.mean()),
            "mean_excess_c": _f((seg - tseg).mean()),
            "cumulative_excess_c": _f((seg - tseg).sum()),
            "threshold_c": _f(tseg.mean()),
        })
    return events, mask


def annual_stats(s: pd.Series, events: list[dict], hw_mask: np.ndarray, start: date, end: date):
    vals, yrs = s.values, s.index.year.values
    rows = []
    for y in range(start.year, end.year + 1):
        m = yrs == y
        expected = int(m.sum())
        full = 366 if calendar.isleap(y) else 365
        yv = vals[m]
        valid = int(np.count_nonzero(~np.isnan(yv)))
        durs = [e["duration_days"] for e in events if e["year"] == y]
        rows.append({
            "year": y,
            "complete": bool(expected == full and valid / full >= MIN_COVERAGE),
            "expected_days": expected,
            "valid_days": valid,
            "coverage_pct": _f(100 * valid / expected, 1) if expected else 0.0,
            "event_count": len(durs),
            "heatwave_days": int(hw_mask[m].sum()),
            "mean_duration_days": _f(np.mean(durs)) if durs else None,
            "max_duration_days": max(durs) if durs else None,
            "peak_temp_c": _f(np.nanmax(yv)) if valid else None,
            "mean_tmax_c": _f(np.nanmean(yv)) if valid else None,
        })
    return rows


def linear_trend(x: np.ndarray, y: np.ndarray) -> dict:
    n = len(x)
    if n < MIN_TREND_YEARS:
        return {"available": False, "n_years": n,
                "reason": f"Needs at least {MIN_TREND_YEARS} complete years (have {n})."}
    if np.ptp(y) == 0:
        return {"available": False, "n_years": n, "reason": "No variation across complete years."}
    r = stats.linregress(x, y)
    p = _f(r.pvalue, 4)
    return {
        "available": True, "n_years": n,
        "slope_per_year": _f(r.slope, 4), "slope_per_decade": _f(r.slope * 10, 3),
        "intercept": float(r.intercept), "r_squared": _f(r.rvalue ** 2, 3),
        "p_value": p, "std_err": _f(r.stderr, 4),
        "significant": bool(p is not None and p < 0.05),
        "direction": "increasing" if r.slope > 0 else "decreasing" if r.slope < 0 else "flat",
    }


def pct_change(years: list[int], values: list[float]) -> dict:
    n = len(values)
    if n < MIN_CHANGE_YEARS:
        return {"valid": False, "pct_change": None,
                "reason": f"Needs at least {MIN_CHANGE_YEARS} complete years (have {n})."}
    h = n // 2
    early, late = values[:h], values[-h:]
    e, l = float(np.mean(early)), float(np.mean(late))
    base = {"early_mean": _f(e, 3), "late_mean": _f(l, 3),
            "early_period": [years[0], years[h - 1]], "late_period": [years[-h], years[-1]]}
    if e == 0:
        return {**base, "valid": False, "pct_change": None,
                "reason": "The early baseline had no heatwave activity, so a percentage change is undefined."}
    return {**base, "valid": True, "pct_change": _f((l - e) / e * 100, 1), "reason": None}


def build_insights(summary, trend, changes, quality, annual, params) -> list[dict]:
    out = []
    t = trend["heatwave_days"]
    if t["available"]:
        d, p = t["slope_per_decade"], t["p_value"]
        if t["significant"]:
            out.append({"id": "trend", "severity": "warning" if d > 0 else "info",
                        "title": f"OLS estimate: {'increase' if d > 0 else 'decrease'} in heatwave days",
                        "text": f"Heatwave days change by {d:+.2f} per decade (R² {t['r_squared']:.2f}, p = {p:.3f}) "
                                f"across {t['n_years']} complete years. This is exploratory: the p-value does not account for "
                                f"serial correlation or multiple comparisons and is not evidence of causation."})
        else:
            out.append({"id": "trend", "severity": "info", "title": "OLS estimate is inconclusive",
                        "text": f"The fitted slope is {d:+.2f} heatwave days per decade, but p = {p:.3f} "
                                f"(R² {t['r_squared']:.2f}) is above 0.05. This exploratory test does not account for "
                                f"serial correlation or multiple comparisons; it cannot establish that a trend is present or absent."})
    else:
        out.append({"id": "trend", "severity": "notice", "title": "Trend unavailable", "text": t["reason"]})

    c = changes["heatwave_days"]
    if c["valid"]:
        out.append({"id": "change", "severity": "warning" if c["pct_change"] > 0 else "info",
                    "title": f"{c['pct_change']:+.0f}% heatwave days, late vs early period",
                    "text": f"{c['early_period'][0]}–{c['early_period'][1]} averaged {c['early_mean']:.2f} heatwave days "
                            f"per year; {c['late_period'][0]}–{c['late_period'][1]} averaged {c['late_mean']:.2f}."})
    else:
        out.append({"id": "change", "severity": "notice", "title": "Percentage change not reported", "text": c["reason"]})

    if summary["total_events"]:
        ly = summary["longest_event"]
        out.append({"id": "extremes", "severity": "info", "title": "Most intense and longest episodes",
                    "text": f"The hottest recorded heatwave day reached {summary['peak_temp_c']:.1f} °C on {summary['peak_date']}. "
                            f"The longest event lasted {ly['duration_days']} days ({ly['start']} to {ly['end']}). "
                            f"{summary['most_active_year']['year']} had the most heatwave days "
                            f"({summary['most_active_year']['heatwave_days']})."})
    else:
        out.append({"id": "extremes", "severity": "notice", "title": "No heatwaves detected",
                    "text": f"No run of {params['min_duration']}+ days above {summary['threshold_c']:.1f} °C was found in this period."})

    out.append({"id": "threshold", "severity": "info", "title": "How heatwaves were defined",
                "text": f"A heatwave is {params['min_duration']}+ consecutive days with maximum temperature above the "
                        f"{params['percentile']:g}th percentile ({summary['threshold_c']:.1f} °C, "
                        f"{'period-wide' if params['threshold_method'] == 'period' else 'seasonal, day-of-year'} method)."})

    notes = []
    if summary["incomplete_years"]:
        notes.append(f"{len(summary['incomplete_years'])} incomplete year(s) ({', '.join(map(str, summary['incomplete_years']))}) "
                     "are shown but excluded from trends, averages and percentage changes")
    if quality["missing_pct"] and quality["missing_pct"] > 0.5:
        notes.append(f"{quality['missing_pct']:.1f}% of days had no valid reading")
    if quality["outliers_removed"] or quality["duplicates_removed"]:
        notes.append(f"{quality['outliers_removed']} outlier(s) removed and {quality['duplicates_removed']} duplicate date(s) merged")
    if notes:
        out.append({"id": "quality", "severity": "notice", "title": "Data quality notes", "text": "; ".join(notes) + "."})
    return out


def analyze(clean: CleanResult, start: date, end: date, percentile: float,
            min_duration: int, method: str) -> dict:
    s = clean.series
    thr, thr_nominal = compute_threshold(s, percentile, method)
    events, mask = detect_events(s, thr, min_duration)
    annual = annual_stats(s, events, mask, start, end)

    comp = [r for r in annual if r["complete"]]
    years = np.array([r["year"] for r in comp], dtype=float)
    hd = np.array([r["heatwave_days"] for r in comp], dtype=float)
    ec = np.array([r["event_count"] for r in comp], dtype=float)
    trend = {"heatwave_days": linear_trend(years, hd), "event_count": linear_trend(years, ec)}
    changes = {"heatwave_days": pct_change([int(y) for y in years], hd.tolist()),
               "event_count": pct_change([int(y) for y in years], ec.tolist())}

    roll = pd.DataFrame({"hd": hd, "ec": ec}, index=years.astype(int)).rolling(ROLLING_WINDOW, min_periods=3).mean()
    for r in annual:
        r.update(rolling_heatwave_days=None, rolling_event_count=None, trend_heatwave_days=None, trend_event_count=None)
        if r["complete"]:
            r["rolling_heatwave_days"] = _f(roll.loc[r["year"], "hd"])
            r["rolling_event_count"] = _f(roll.loc[r["year"], "ec"])
            for k, col in (("heatwave_days", "trend_heatwave_days"), ("event_count", "trend_event_count")):
                t = trend[k]
                if t["available"]:
                    r[col] = _f(t["intercept"] + t["slope_per_year"] * r["year"])
    for t in trend.values():
        t.pop("intercept", None)

    total_days = int(mask.sum())
    peak_ev = max(events, key=lambda e: e["peak_temp_c"]) if events else None
    long_ev = max(events, key=lambda e: e["duration_days"]) if events else None
    most = max(annual, key=lambda r: r["heatwave_days"]) if events else None
    summary = {
        "threshold_c": _f(thr_nominal),
        "total_events": len(events),
        "total_heatwave_days": total_days,
        "mean_duration_days": _f(np.mean([e["duration_days"] for e in events])) if events else None,
        "longest_event": {k: long_ev[k] for k in ("start", "end", "duration_days")} if long_ev else None,
        "peak_temp_c": peak_ev["peak_temp_c"] if peak_ev else None,
        "peak_date": peak_ev["peak_date"] if peak_ev else None,
        "mean_events_per_year": _f(ec.mean()) if len(ec) else None,
        "mean_heatwave_days_per_year": _f(hd.mean()) if len(hd) else None,
        "years_in_range": len(annual),
        "complete_years": len(comp),
        "incomplete_years": [r["year"] for r in annual if not r["complete"]],
        "most_active_year": {"year": most["year"], "heatwave_days": most["heatwave_days"]} if most else None,
    }
    params = {"percentile": percentile, "min_duration": min_duration, "threshold_method": method}
    return {
        "summary": summary, "annual": annual, "trend": trend, "changes": changes,
        "quality": clean.quality,
        "insights": build_insights(summary, trend, changes, clean.quality, annual, params),
        "events": events,
    }
