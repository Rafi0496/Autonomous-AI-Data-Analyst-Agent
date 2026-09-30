"""Segment comparison tool: segment_compare().

Groups dataset by a categorical feature and compares key metrics across segments.
Includes cardinality guardrails to reject individual record IDs and ensure meaningful comparisons.
"""
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from backend.app.services.data_loader import get_dataset_dataframe

def segment_compare(
    dataset_id: str,
    segment_column: str,
    metric_column: str,
    allow_high_cardinality: bool = False
) -> Dict[str, Any]:
    """
    Compare a numeric metric across categories in a segment column.
    Computes summary metrics, relative differences, and statistical significance.
    Rejects high-cardinality identifier columns (e.g. Transaction_ID) by default.
    """
    df = get_dataset_dataframe(dataset_id, prefer_cleaned=True)
    
    if segment_column not in df.columns:
        raise ValueError(f"Segment column '{segment_column}' not found in dataset. Available: {list(df.columns)}")
    if metric_column not in df.columns:
        raise ValueError(f"Metric column '{metric_column}' not found in dataset. Available: {list(df.columns)}")

    # Normalize whitespace on segment_column; casing is preserved from cleaned data canonicalization
    if df[segment_column].dtype == "object" or str(df[segment_column].dtype).startswith("str"):
        df = df.copy()
        df[segment_column] = df[segment_column].apply(lambda x: x.strip() if isinstance(x, str) else x)

    # Clean metric column if formatted as currency or string
    metric_series = df[metric_column]
    if not pd.api.types.is_numeric_dtype(metric_series):
        metric_series = pd.to_numeric(
            metric_series.astype(str).str.replace(r"[$,€£¥]", "", regex=True),
            errors="coerce"
        )
    
    # Strip string segments
    seg_series = df[segment_column].astype(str).str.strip()

    # Exclude imputed values from statistical segment comparison
    from backend.app.services.data_loader import get_column_imputed_mask
    seg_imputed = get_column_imputed_mask(df, segment_column)
    metric_imputed = get_column_imputed_mask(df, metric_column)
    imputed_mask = (seg_imputed | metric_imputed)
    n_excluded_imputed = int(imputed_mask.sum())

    working_df = pd.DataFrame({
        "segment": seg_series,
        "metric": metric_series
    })[~imputed_mask].dropna()
    n_used = len(working_df)

    if working_df.empty:
        return {
            "dataset_id": dataset_id,
            "tool": "segment_compare",
            "status": "error",
            "message": "No valid non-null rows remaining after alignment.",
            "segment_column": segment_column,
            "metric_column": metric_column,
            "segments": []
        }

    # Guard against high-cardinality ID-like columns
    unique_segments = int(working_df["segment"].nunique())
    total_rows = len(working_df)
    cardinality_ratio = unique_segments / total_rows if total_rows > 0 else 0.0
    is_id_name = any(
        segment_column.lower().endswith(suffix) or segment_column.lower().startswith(suffix)
        for suffix in ["_id", "id", "uuid", "guid", "key", "code", "hash", "num", "number"]
    )

    if not allow_high_cardinality:
        if cardinality_ratio >= 0.70 and unique_segments > 15:
            raise ValueError(
                f"Column '{segment_column}' has high cardinality ({unique_segments} unique values across {total_rows} rows, {cardinality_ratio:.1%}) "
                f"and resembles a unique record identifier rather than a categorical business segment. "
                f"Segment comparison requires a categorical grouping column with shared groups (e.g. Category, Region, Department)."
            )
        if is_id_name and (cardinality_ratio >= 0.50 or unique_segments > 30):
            raise ValueError(
                f"Column '{segment_column}' appears to be a unique identifier (ID-like name and {unique_segments} distinct values). "
                f"Please choose a categorical segment with repeated groups (e.g. Category, Department, Region, Channel)."
            )

    grouped = working_df.groupby("segment")["metric"]
    total_metric_sum = float(working_df["metric"].sum())
    overall_mean = float(working_df["metric"].mean())

    segment_stats = []
    group_values_list = []

    for seg_name, group in grouped:
        if len(group) == 0:
            continue
        group_values_list.append(group.values)
        count = int(len(group))
        s_sum = float(group.sum())
        mean_val = round(float(group.mean()), 2)
        med_val = round(float(group.median()), 2)
        std_val = round(float(group.std()), 2) if len(group) > 1 else 0.0
        min_val = round(float(group.min()), 2)
        max_val = round(float(group.max()), 2)
        share = round((s_sum / total_metric_sum) * 100, 2) if total_metric_sum != 0 else 0.0

        segment_stats.append({
            "segment": str(seg_name),
            "count": count,
            "sum": round(s_sum, 2),
            "mean": mean_val,
            "median": med_val,
            "std": std_val,
            "min": min_val,
            "max": max_val,
            "share_of_total_percent": share,
            "relative_to_overall_mean": round(mean_val / overall_mean, 2) if overall_mean != 0 else 1.0
        })

    # Sort segments by mean metric descending
    segment_stats.sort(key=lambda x: x["mean"], reverse=True)
    
    top_segment = segment_stats[0] if segment_stats else None
    bottom_segment = segment_stats[-1] if segment_stats else None
    
    relative_diff_ratio = None
    abs_diff = None
    if top_segment and bottom_segment:
        top_m = top_segment["mean"]
        bot_m = bottom_segment["mean"]
        abs_diff = round(top_m - bot_m, 2)
        if bot_m > 0 and top_m >= bot_m:
            relative_diff_ratio = round(top_m / bot_m, 2)
        elif bot_m > 0 and top_m < bot_m:
            relative_diff_ratio = round(bot_m / top_m, 2)
        else:
            # Baseline is negative or zero, ratio is mathematically undefined
            relative_diff_ratio = None

    # Statistical significance test (One-way ANOVA) if >= 2 groups
    p_value = None
    is_significant = False
    if len(group_values_list) >= 2 and all(len(g) >= 2 for g in group_values_list):
        try:
            f_stat, p_val = stats.f_oneway(*group_values_list)
            if not np.isnan(p_val):
                p_value = round(float(p_val), 5)
                is_significant = bool(p_value < 0.05)
        except Exception:
            pass

    return {
        "dataset_id": dataset_id,
        "tool": "segment_compare",
        "status": "success",
        "segment_column": segment_column,
        "metric_column": metric_column,
        "total_records": len(working_df),
        "n_used": len(working_df),
        "n_excluded_imputed": n_excluded_imputed,
        "overall_mean": round(overall_mean, 2),
        "overall_sum": round(total_metric_sum, 2),
        "total_segments": len(segment_stats),
        "top_segment": top_segment,
        "bottom_segment": bottom_segment,
        "top_vs_bottom_ratio": relative_diff_ratio,
        "absolute_difference": abs_diff,
        "anova_p_value": p_value,
        "is_statistically_significant": is_significant,
        "segments": segment_stats
    }
