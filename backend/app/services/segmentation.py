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

    # Detect if metric_column is categorical/binary (e.g. Attrition, Converted, Churn)
    from backend.app.services.data_loader import get_column_imputed_mask
    raw_metric_series = df[metric_column]
    is_categorical_target = False
    
    if not pd.api.types.is_numeric_dtype(raw_metric_series):
        cleaned_num = pd.to_numeric(
            raw_metric_series.astype(str).str.replace(r"[$,€£¥]", "", regex=True),
            errors="coerce"
        )
        if cleaned_num.notnull().mean() >= 0.5:
            metric_series = cleaned_num
        else:
            is_categorical_target = True
    elif raw_metric_series.nunique() <= 2 and set(raw_metric_series.dropna().unique()).issubset({0, 1, 0.0, 1.0}):
        is_categorical_target = True

    # -------------------------------------------------------------
    # PATH 1: Categorical / Binary Rate Analysis (e.g. Attrition by Dept)
    # -------------------------------------------------------------
    if is_categorical_target:
        seg_series = df[segment_column].astype(str).str.strip()
        tar_series = df[metric_column].astype(str).str.strip()
        seg_imputed = get_column_imputed_mask(df, segment_column)
        tar_imputed = get_column_imputed_mask(df, metric_column)
        imputed_mask = (seg_imputed | tar_imputed)
        
        working_df = pd.DataFrame({"segment": seg_series, "target": tar_series})[~imputed_mask].dropna()
        working_df = working_df[~working_df["target"].str.lower().isin(["nan", "none", "<na>", ""])]
        working_df = working_df[~working_df["segment"].str.lower().isin(["nan", "none", "<na>", ""])]

        if working_df.empty:
            return {
                "dataset_id": dataset_id,
                "tool": "segment_compare",
                "analysis_type": "categorical_rate",
                "status": "error",
                "message": "No non-null rows remaining for rate analysis.",
                "segment_column": segment_column,
                "metric_column": metric_column,
                "segments": []
            }

        # Identify positive class (prefer 'Yes', 'True', '1', or first category)
        unique_targets = list(working_df["target"].unique())
        pos_class = unique_targets[0]
        for candidate_pos in ["yes", "true", "1", "left", "churn"]:
            match = next((t for t in unique_targets if t.lower() == candidate_pos), None)
            if match:
                pos_class = match
                break

        overall_n = len(working_df)
        overall_pos = int((working_df["target"].str.lower() == pos_class.lower()).sum())
        overall_rate = overall_pos / overall_n if overall_n > 0 else 0.0

        segment_stats = []
        for seg_name, group in working_df.groupby("segment"):
            n_seg = len(group)
            if n_seg == 0:
                continue
            pos_seg = int((group["target"].str.lower() == pos_class.lower()).sum())
            s_rate = pos_seg / n_seg
            segment_stats.append({
                "segment": str(seg_name),
                "n_used": n_seg,
                "count": n_seg,
                "positive_count": pos_seg,
                "rate": round(float(s_rate), 4),
                "rate_percent": round(float(s_rate * 100), 2),
                "mean": round(float(s_rate * 100), 2),
                "denominator": n_seg
            })

        segment_stats.sort(key=lambda x: x["rate"], reverse=True)
        top_seg = segment_stats[0] if segment_stats else {}
        bot_seg = segment_stats[-1] if segment_stats else {}
        rate_diff = round((top_seg.get("rate_percent", 0.0) - bot_seg.get("rate_percent", 0.0)), 2)

        # Chi-square test of independence
        p_val = None
        chi2_stat = None
        ct = pd.crosstab(working_df["segment"], working_df["target"])
        if ct.shape[0] >= 2 and ct.shape[1] >= 2:
            try:
                c_res = stats.chi2_contingency(ct)
                chi2_stat = round(float(c_res.statistic), 4)
                p_val = round(float(c_res.pvalue), 5)
            except Exception:
                pass

        return {
            "dataset_id": dataset_id,
            "tool": "segment_compare",
            "analysis_type": "categorical_rate",
            "status": "success",
            "segment_column": segment_column,
            "metric_column": metric_column,
            "target_class": pos_class,
            "total_records": len(df),
            "n_used": overall_n,
            "n_excluded_imputed": len(df) - overall_n,
            "overall_rate": round(float(overall_rate), 4),
            "overall_rate_percent": round(float(overall_rate * 100), 2),
            "overall_numerator": overall_pos,
            "overall_denominator": overall_n,
            "total_segments": len(segment_stats),
            "top_segment": top_seg,
            "bottom_segment": bot_seg,
            "absolute_difference": rate_diff,
            "chi2_statistic": chi2_stat,
            "chi2_p_value": p_val,
            "anova_p_value": p_val,
            "is_statistically_significant": bool(p_val is not None and p_val < 0.05),
            "segments": segment_stats
        }

    # -------------------------------------------------------------
    # PATH 2: Continuous Numeric Metric Comparison
    # -------------------------------------------------------------
    # Strip string segments
    seg_series = df[segment_column].astype(str).str.strip()

    # Exclude imputed values from statistical segment comparison
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
            "analysis_type": "continuous_mean",
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
        "total_records": len(df),
        "n_used": len(working_df),
        "n_excluded_imputed": len(df) - len(working_df),
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
