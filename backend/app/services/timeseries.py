"""Time-series and trend analysis tool: trend_analysis().

Performs chronological aggregation, slope detection, rolling averages, and peak/trough identification.
"""
import warnings
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from backend.app.services.data_loader import get_dataset_dataframe

# Standard stability threshold: within +/- 5.0% change is classified as stable
STABILITY_THRESHOLD_PCT: float = 5.0

def trend_analysis(
    dataset_id: str,
    date_column: str,
    value_column: str,
    freq: str = "auto"
) -> Dict[str, Any]:
    """
    Analyze chronological trends and rolling patterns over time.
    """
    df = get_dataset_dataframe(dataset_id, prefer_cleaned=True)
    from backend.app.services.data_loader import get_column_imputed_mask
    
    if date_column not in df.columns:
        raise ValueError(f"Date column '{date_column}' not found. Available: {list(df.columns)}")
    if value_column not in df.columns:
        raise ValueError(f"Value column '{value_column}' not found. Available: {list(df.columns)}")

    # Parse dates
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dates = pd.to_datetime(df[date_column], errors="coerce")
    
    # Parse numbers
    val_series = df[value_column]
    if not pd.api.types.is_numeric_dtype(val_series):
        val_series = pd.to_numeric(
            val_series.astype(str).str.replace(r"[$,€£¥]", "", regex=True),
            errors="coerce"
        )
        
    date_imputed = get_column_imputed_mask(df, date_column)
    val_imputed = get_column_imputed_mask(df, value_column)
    imputed_mask = (date_imputed | val_imputed)
    n_excluded_imputed = int(imputed_mask.sum())

    ts_df = pd.DataFrame({"ds": dates, "y": val_series})[~imputed_mask].dropna().sort_values("ds").reset_index(drop=True)
    n_used = len(ts_df)

    if n_used < 3:
        return {
            "dataset_id": dataset_id,
            "tool": "trend_analysis",
            "status": "skipped",
            "message": "Fewer than 3 valid non-imputed date/value pairs found for trend analysis.",
            "total_points": n_used,
            "n_used": n_used,
            "n_excluded_imputed": n_excluded_imputed
        }

    # Aggregate duplicate dates
    daily_agg = ts_df.groupby("ds")["y"].agg(["mean", "sum", "count"]).reset_index()
    
    # Choose frequency if auto
    timespan_days = (daily_agg["ds"].max() - daily_agg["ds"].min()).days
    if freq == "auto":
        if timespan_days > 180:
            agg_freq = "ME"  # Monthly
        elif timespan_days > 30:
            agg_freq = "W"   # Weekly
        else:
            agg_freq = "D"   # Daily
    else:
        agg_freq = freq

    try:
        resampled = daily_agg.set_index("ds").resample(agg_freq)["mean"].mean().dropna().reset_index()
    except Exception:
        resampled = daily_agg[["ds", "mean"]].rename(columns={"mean": "y"})

    if len(resampled) < 2:
        resampled = daily_agg[["ds", "mean"]].rename(columns={"mean": "y"})

    # Compute trend metrics
    y_vals = resampled.iloc[:, 1].values
    x_idx = np.arange(len(y_vals))
    
    # Linear slope
    slope, intercept = np.polyfit(x_idx, y_vals, 1) if len(y_vals) > 1 else (0.0, float(y_vals[0]))
    
    # Percentage change
    start_val = float(y_vals[0])
    end_val = float(y_vals[-1])
    pct_change = round(((end_val - start_val) / abs(start_val)) * 100, 2) if start_val != 0 else 0.0
    
    # Classify direction based on percentage change
    if pct_change <= -STABILITY_THRESHOLD_PCT:
        direction = "downward"
    elif pct_change >= STABILITY_THRESHOLD_PCT:
        direction = "upward"
    else:
        direction = "stable"

    # Peak and Trough
    peak_idx = int(np.argmax(y_vals))
    trough_idx = int(np.argmin(y_vals))
    peak_date = str(resampled.iloc[peak_idx, 0])
    peak_val = round(float(y_vals[peak_idx]), 2)
    trough_date = str(resampled.iloc[trough_idx, 0])
    trough_val = round(float(y_vals[trough_idx]), 2)

    # Rolling average (window of 3 or len/3)
    rolling_window = max(2, min(5, len(y_vals) // 3))
    rolling_mean = pd.Series(y_vals).rolling(window=rolling_window, min_periods=1).mean().round(2).tolist()

    timeline_points = [
        {
            "date": str(resampled.iloc[i, 0])[:10],
            "value": round(float(y_vals[i]), 2),
            "rolling_avg": float(rolling_mean[i])
        }
        for i in range(len(y_vals))
    ]

    return {
        "dataset_id": dataset_id,
        "tool": "trend_analysis",
        "status": "success",
        "date_column": date_column,
        "value_column": value_column,
        "timespan_days": timespan_days,
        "start_date": str(ts_df["ds"].min())[:10],
        "end_date": str(ts_df["ds"].max())[:10],
        "total_observations": len(ts_df),
        "n_used": len(ts_df),
        "n_excluded_imputed": n_excluded_imputed,
        "aggregated_periods": len(resampled),
        "overall_trend": direction,
        "linear_slope": round(float(slope), 4),
        "percentage_change": pct_change,
        "start_value": round(start_val, 2),
        "end_value": round(end_val, 2),
        "peak_period": {"date": peak_date[:10], "value": peak_val},
        "trough_period": {"date": trough_date[:10], "value": trough_val},
        "timeline": timeline_points
    }
