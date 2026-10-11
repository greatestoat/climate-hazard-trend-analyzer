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


def clean_series(rows: list[tuple] | list[dict], start: date, end: date, metric: str = "tmax") -> CleanResult:
    q = dict(rows_received=len(rows), invalid_rows=0, duplicates_removed=0,
             outliers_removed=0, interpolated_days=0)
    if rows and isinstance(rows[0], dict):
        df = pd.DataFrame(rows)
    elif rows and len(rows[0]) > 2:
        df = pd.DataFrame(rows, columns=["date", "tmax", "tmin", "precipitation_mm"][:len(rows[0])])
    else:
        df = pd.DataFrame(rows, columns=["date", metric])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if metric not in df:
        df[metric] = np.nan
    df[metric] = pd.to_numeric(df[metric], errors="coerce")
    bad = df["date"].isna()
    q["invalid_rows"] = int(bad.sum())
    df = df[~bad].copy()
    df["date"] = df["date"].dt.normalize()
    df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]
    q["duplicates_removed"] = int(len(df) - df["date"].nunique())
    s = df.groupby("date")[metric].mean()  # duplicate dates are averaged

    phys = (s < 0) if metric == "precipitation_mm" else ((s < PHYS_MIN) | (s > PHYS_MAX))
    q["outliers_removed"] += int(phys.sum())
    s = s.mask(phys)

    idx = pd.date_range(start, end, freq="D")
    s = s.reindex(idx)

    if metric != "precipitation_mm" and s.notna().sum() >= 5 * 300:
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

    if metric != "precipitation_mm":
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


def compute_threshold(s: pd.Series, percentile: float, method: str, direction: str = "above",
                      wet_day_threshold: float | None = None):
    valid = s.dropna()
    if wet_day_threshold is not None:
        valid = valid[valid >= wet_day_threshold]
    if len(valid) < 30:
        raise InsufficientDataError("Not enough valid observations to compute a hazard threshold.")
    if method == "period":
        t = float(np.percentile(valid.values, percentile))
        return pd.Series(t, index=s.index), t
    fallback = float(np.percentile(valid.values, percentile))
    doy = np.minimum(s.index.dayofyear.values, 365)
    vals = s.values
    by_doy = np.full(366, np.nan)
    for d in range(1, 366):
        offs = (np.arange(-SEASONAL_HALF_WINDOW, SEASONAL_HALF_WINDOW + 1) + d - 1) % 365 + 1
        m = np.isin(doy, offs) & ~np.isnan(vals)
        if wet_day_threshold is not None:
            m &= vals >= wet_day_threshold
        min_samples = 10 if wet_day_threshold is not None else 30
        if m.sum() >= min_samples:
            by_doy[d] = np.percentile(vals[m], percentile)
        elif wet_day_threshold is not None:
            # A sparse wet-day seasonal window falls back to the valid
            # period-wide wet-day threshold instead of creating blind dates.
            by_doy[d] = fallback
    return pd.Series(by_doy[doy], index=s.index), float(np.nanmean(by_doy[1:]))


def detect_events(s: pd.Series, thr: pd.Series, min_duration: int, direction: str = "above"):
    vals, th = s.values, thr.values
    compare = vals < th if direction == "below" else vals > th
    exceed = compare & ~np.isnan(vals)      # NaN comparisons are False, so gaps break events
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
        extreme = int(np.argmin(seg)) if direction == "below" else int(np.argmax(seg))
        excess = tseg - seg if direction == "below" else seg - tseg
        events.append({
            "start": s.index[a].date().isoformat(),
            "end": s.index[b - 1].date().isoformat(),
            "year": int(s.index[a].year),
            "duration_days": n,
            "extreme_value": _f(seg[extreme]),
            "extreme_date": s.index[a + extreme].date().isoformat(),
            "mean_value": _f(seg.mean()),
            "mean_excess": _f(excess.mean()),
            "cumulative_excess": _f(excess.sum()),
            "threshold_value": _f(tseg.mean()),
        })
    return events, mask


def annual_stats(s: pd.Series, events: list[dict], event_mask: np.ndarray, start: date, end: date,
                 direction: str = "above", hazard: str = "heatwave"):
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
            "event_days": int(event_mask[m].sum()),
            "mean_duration_days": _f(np.mean(durs)) if durs else None,
            "max_duration_days": max(durs) if durs else None,
            "extreme_value": _f(np.nanmin(yv) if direction == "below" else np.nanmax(yv)) if valid else None,
            "mean_value": _f(np.nanmean(yv)) if valid else None,
        })
        if hazard == "heatwave":
            rows[-1]["heatwave_days"] = rows[-1]["event_days"]
            rows[-1]["peak_temp_c"] = rows[-1]["extreme_value"]
            rows[-1]["mean_tmax_c"] = rows[-1]["mean_value"]
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
                "reason": "The early baseline had no event days, so a percentage change is undefined."}
    return {**base, "valid": True, "pct_change": _f((l - e) / e * 100, 1), "reason": None}


def build_insights(summary, trend, changes, quality, params) -> list[dict]:
    hazard = params["hazard"]
    label = {"heatwave": "heatwave", "cold_wave": "cold wave", "heavy_rainfall": "heavy-rainfall"}[hazard]
    unit = summary["unit"]
    t = trend["event_days"]
    out = []
    if t["available"]:
        out.append({"id": "trend", "severity": "info", "title": f"Exploratory OLS estimate for {label} days",
                    "text": f"Fitted slope: {t['slope_per_decade']:+.2f} event days per decade across {t['n_years']} complete years "
                            f"(R2 {t['r_squared']:.2f}, nominal p = {t['p_value']:.4f}). This estimate does not adjust for serial "
                            f"correlation or multiple comparisons and does not establish causation or the presence or absence of a trend."})
    else:
        out.append({"id": "trend", "severity": "notice", "title": "Trend estimate unavailable", "text": t["reason"]})

    c = changes["event_days"]
    if c["valid"]:
        out.append({"id": "change", "severity": "info", "title": f"{c['pct_change']:+.0f}% {label} days, late vs early period",
                    "text": f"{c['early_period'][0]}-{c['early_period'][1]} averaged {c['early_mean']:.2f} event days per year; "
                            f"{c['late_period'][0]}-{c['late_period'][1]} averaged {c['late_mean']:.2f}. This compares period averages "
                            f"and is not a causal estimate."})
    else:
        out.append({"id": "change", "severity": "notice", "title": "Percentage change not reported", "text": c["reason"]})

    if summary["total_events"]:
        longest = summary["longest_event"]
        out.append({"id": "extremes", "severity": "info", "title": f"Most extreme {label} conditions",
                    "text": f"The most extreme daily value was {summary['extreme_value']:.1f} {unit} on {summary['extreme_date']}. "
                            f"The longest event lasted {longest['duration_days']} days ({longest['start']} to {longest['end']}); "
                            f"{summary['most_active_year']['year']} had the most event days "
                            f"({summary['most_active_year']['event_days']})."})
    else:
        out.append({"id": "extremes", "severity": "notice", "title": f"No {label} events detected",
                    "text": f"No run of {params['min_duration']} or more days met the selected threshold in this period."})

    method = "period-wide" if params["threshold_method"] == "period" else "seasonal day-of-year"
    if hazard == "heatwave":
        rule = f"daily maximum temperature above the {params['percentile']:g}th percentile"
    elif hazard == "cold_wave":
        rule = f"daily minimum temperature below the {params['percentile']:g}th percentile"
    else:
        rule = f"daily precipitation above the {params['percentile']:g}th percentile of days with at least 1 mm"
    out.append({"id": "threshold", "severity": "info", "title": f"How {label} events were defined",
                "text": f"At least {params['min_duration']} consecutive day(s) with {rule} "
                        f"({summary['threshold_value']:.1f} {unit}; {method} method)."})

    notes = []
    if summary["incomplete_years"]:
        notes.append(f"{len(summary['incomplete_years'])} incomplete year(s) are shown but excluded from trends, averages and percentage changes")
    if quality["missing_pct"] and quality["missing_pct"] > 0.5:
        notes.append(f"{quality['missing_pct']:.1f}% of days had no valid reading")
    if quality["outliers_removed"] or quality["duplicates_removed"]:
        notes.append(f"{quality['outliers_removed']} outlier(s) removed and {quality['duplicates_removed']} duplicate date(s) merged")
    if notes:
        out.append({"id": "quality", "severity": "notice", "title": "Data quality notes", "text": "; ".join(notes) + "."})
    return out


def analyze(clean: CleanResult, start: date, end: date, percentile: float,
            min_duration: int, method: str, hazard: str = "heatwave") -> dict:
    direction = "below" if hazard == "cold_wave" else "above"
    unit = "mm" if hazard == "heavy_rainfall" else "C"
    wet_filter = 1.0 if hazard == "heavy_rainfall" else None
    threshold_percentile = percentile
    threshold, nominal = compute_threshold(clean.series, threshold_percentile, method, direction, wet_filter)
    events, mask = detect_events(clean.series, threshold, min_duration, direction)
    annual = annual_stats(clean.series, events, mask, start, end, direction, hazard)

    complete = [r for r in annual if r["complete"]]
    years = np.array([r["year"] for r in complete], dtype=float)
    event_days = np.array([r["event_days"] for r in complete], dtype=float)
    event_counts = np.array([r["event_count"] for r in complete], dtype=float)
    trend = {"event_days": linear_trend(years, event_days), "event_count": linear_trend(years, event_counts)}
    changes = {"event_days": pct_change([int(y) for y in years], event_days.tolist()),
               "event_count": pct_change([int(y) for y in years], event_counts.tolist())}
    if hazard == "heatwave":
        trend["heatwave_days"] = trend["event_days"]
        changes["heatwave_days"] = changes["event_days"]

    rolling = pd.DataFrame({"days": event_days, "count": event_counts}, index=years.astype(int)).rolling(ROLLING_WINDOW, min_periods=3).mean()
    for row in annual:
        row.update(rolling_event_days=None, trend_event_days=None, rolling_event_count=None, trend_event_count=None)
        if row["complete"]:
            row["rolling_event_days"] = _f(rolling.loc[row["year"], "days"])
            row["rolling_event_count"] = _f(rolling.loc[row["year"], "count"])
            for key, column in (("event_days", "trend_event_days"), ("event_count", "trend_event_count")):
                fit = trend[key]
                if fit["available"]:
                    row[column] = _f(fit["intercept"] + fit["slope_per_year"] * row["year"])
        if hazard == "heatwave":
            row["rolling_heatwave_days"] = row["rolling_event_days"]
            row["trend_heatwave_days"] = row["trend_event_days"]

    for fit in trend.values():
        fit.pop("intercept", None)
    total_event_days = int(mask.sum())
    extreme_event = (max(events, key=lambda event: event["extreme_value"]) if direction == "above" else
                     min(events, key=lambda event: event["extreme_value"])) if events else None
    longest = max(events, key=lambda event: event["duration_days"]) if events else None
    most_active = max(annual, key=lambda row: row["event_days"]) if events else None
    summary = {
        "threshold_value": _f(nominal), "unit": unit,
        "total_events": len(events), "total_event_days": total_event_days,
        "mean_duration_days": _f(np.mean([event["duration_days"] for event in events])) if events else None,
        "longest_event": {k: longest[k] for k in ("start", "end", "duration_days")} if longest else None,
        "extreme_value": extreme_event["extreme_value"] if extreme_event else None,
        "extreme_date": extreme_event["extreme_date"] if extreme_event else None,
        "mean_events_per_year": _f(event_counts.mean()) if len(event_counts) else None,
        "mean_event_days_per_year": _f(event_days.mean()) if len(event_days) else None,
        "years_in_range": len(annual), "complete_years": len(complete),
        "incomplete_years": [row["year"] for row in annual if not row["complete"]],
        "most_active_year": {"year": most_active["year"], "event_days": most_active["event_days"]} if most_active else None,
    }
    if hazard == "heatwave":
        summary.update(threshold_c=summary["threshold_value"], total_heatwave_days=total_event_days,
                       peak_temp_c=summary["extreme_value"], peak_date=summary["extreme_date"],
                       mean_heatwave_days_per_year=summary["mean_event_days_per_year"])
        for event in events:
            event.update(peak_temp_c=event["extreme_value"], peak_date=event["extreme_date"],
                         mean_temp_c=event["mean_value"], mean_excess_c=event["mean_excess"],
                         cumulative_excess_c=event["cumulative_excess"], threshold_c=event["threshold_value"])
    params = {"hazard": hazard, "percentile": percentile, "min_duration": min_duration, "threshold_method": method}
    return {
        "summary": summary, "annual": annual, "trend": trend, "changes": changes,
        "quality": clean.quality,
        "insights": build_insights(summary, trend, changes, clean.quality, params),
        "events": events,
    }
