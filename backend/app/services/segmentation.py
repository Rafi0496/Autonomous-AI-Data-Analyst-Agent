"""Segment comparison tool: segment_compare().

Groups dataset by a categorical feature and compares key metrics across segments.
"""
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from backend.app.services.data_loader import get_dataset_dataframe

def segment_compare(
    dataset_id: str,
    segment_column: str,
    metric_column: str
) -> Dict[str, Any]:
    """
    Compare a numeric metric across categories in a segment column.
    Computes summary metrics, relative differences, and statistical significance.
    """
    df = get_dataset_dataframe(dataset_id)
    
    if segment_column not in df.columns:
        raise ValueError(f"Segment column '{segment_column}' not found in dataset. Available: {list(df.columns)}")
    if metric_column not in df.columns:
        raise ValueError(f"Metric column '{metric_column}' not found in dataset. Available: {list(df.columns)}")

    # Clean metric column if formatted as currency or string
    metric_series = df[metric_column]
    if not pd.api.types.is_numeric_dtype(metric_series):
        metric_series = pd.to_numeric(
            metric_series.astype(str).str.replace(r"[$,€£¥]", "", regex=True),
            errors="coerce"
        )
    
    # Strip string segments
    seg_series = df[segment_column].astype(str).str.strip()

    working_df = pd.DataFrame({
        "segment": seg_series,
        "metric": metric_series
    }).dropna()

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
    if top_segment and bottom_segment and bottom_segment["mean"] > 0:
        relative_diff_ratio = round(top_segment["mean"] / bottom_segment["mean"], 2)

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
        "overall_mean": round(overall_mean, 2),
        "overall_sum": round(total_metric_sum, 2),
        "total_segments": len(segment_stats),
        "top_segment": top_segment,
        "bottom_segment": bottom_segment,
        "top_vs_bottom_ratio": relative_diff_ratio,
        "anova_p_value": p_value,
        "is_statistically_significant": is_significant,
        "segments": segment_stats
    }
