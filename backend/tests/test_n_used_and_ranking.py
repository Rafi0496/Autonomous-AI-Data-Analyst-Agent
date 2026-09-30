"""Unit tests for n_used invariant, ranking, suppression, and trend OLS test (Items 4 & 5)."""
import os
import pandas as pd
import pytest
from backend.app.services.cleaning import clean_data
from backend.app.services.segmentation import segment_compare
from backend.app.services.correlation import run_correlation
from backend.app.services.timeseries import trend_analysis
from backend.app.services.outliers import detect_outliers
from backend.app.services.insights import generate_insights, compute_impact_score, check_suppression, partition_insights

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "samples"))

def test_hr_outlier_and_correlation_invariant():
    """Verify HR correlation and outlier satisfy n_used + n_excluded == 110."""
    csv_path = os.path.join(DATA_DIR, "hr_attrition_messy.csv")
    raw_df = pd.read_csv(csv_path)
    clean_df, cl_report = clean_data(raw_df, "test-ds")
    n_total = len(clean_df)
    assert n_total == 110

    # 1. Outlier detection
    out_res = detect_outliers(clean_df, method="iqr")
    assert out_res["n_rows_used"] + out_res["n_excluded_imputed"] == n_total
    assert out_res["n_rows_used"] > 0

    # 2. Correlation
    corr_res = run_correlation(clean_df)
    assert corr_res["n_used"] + corr_res["n_excluded_imputed"] == n_total
    highest_rel = corr_res.get("highest_correlation") or corr_res["strong_relationships"][0]
    assert highest_rel["n_used"] + highest_rel["n_excluded_imputed"] == n_total
    assert highest_rel["n_used"] < n_total
    assert highest_rel["n_excluded_imputed"] > 0

    # 3. Categorical rates in segment_compare
    seg_res = segment_compare(clean_df, "Department", "Attrition")
    assert seg_res["n_used"] + seg_res["n_excluded_imputed"] == n_total

    # 4. Generate Insights
    profile = {"row_count": n_total, "cleaned_row_count": n_total, "cleaning_report": cl_report}
    insights = generate_insights(
        structured_results=[out_res, corr_res, seg_res],
        dataset_profile=profile
    )
    for ins in insights:
        assert ins.n_used + ins.n_excluded == n_total, f"Insight {ins.id} violated invariant: {ins.n_used} + {ins.n_excluded} != {n_total}"

def test_invariant_on_all_three_datasets():
    """Test n_used invariant across all 3 messy datasets."""
    datasets = ["hr_attrition_messy.csv", "retail_sales_messy.csv", "marketing_campaign_messy.csv"]
    for ds_name in datasets:
        csv_path = os.path.join(DATA_DIR, ds_name)
        raw_df = pd.read_csv(csv_path)
        clean_df, cl_report = clean_data(raw_df, "test-ds")
        n_total = len(clean_df)

        corr_res = run_correlation(clean_df)
        out_res = detect_outliers(clean_df, method="iqr")
        profile = {"row_count": n_total, "cleaned_row_count": n_total, "cleaning_report": cl_report}
        
        insights = generate_insights(
            structured_results=[corr_res, out_res],
            dataset_profile=profile
        )
        assert len(insights) > 0
        for ins in insights:
            assert ins.n_used + ins.n_excluded == n_total, f"Dataset {ds_name} insight {ins.id} invariant failed: {ins.n_used} + {ins.n_excluded} != {n_total}"

def test_trend_ols_p_value_and_n_periods():
    """Test trend analysis OLS p-value, standardized slope effect size, and n_periods."""
    csv_path = os.path.join(DATA_DIR, "retail_sales_messy.csv")
    raw_df = pd.read_csv(csv_path)
    clean_df, cl_report = clean_data(raw_df, "test-ds")
    n_total = len(clean_df)

    res = trend_analysis(clean_df, "Date", "Quantity", freq="ME")
    assert res["status"] == "success"
    assert res["n_used"] + res["n_excluded_imputed"] == n_total
    assert "n_periods" in res
    assert res["n_periods"] > 0
    assert "standardized_slope" in res
    assert "p_value" in res

    profile = {"row_count": n_total, "cleaned_row_count": n_total, "cleaning_report": cl_report}
    insights = generate_insights(structured_results=[res], dataset_profile=profile)
    trend_ins = next((i for i in insights if i.type == "trend"), None)
    if trend_ins:
        assert trend_ins.n_used + trend_ins.n_excluded == n_total
        assert trend_ins.metric_values["n_periods"] == res["n_periods"]
        if res["p_value"] is not None and res["p_value"] >= 0.05:
            assert "no significant trend" in trend_ins.title.lower()

def test_suppression_and_ranking():
    """Verify suppression when n_used < 20 or exclusion_rate > 0.5, and 0 outliers impact <= 0.1."""
    # 1. Suppression check
    suppressed = check_suppression("correlation", "A vs B", n_used=15, n_excluded=10, total_rows=25)
    assert suppressed is not None
    assert suppressed.type == "data_quality"
    assert "insufficient data for correlation" in suppressed.caveats

    suppressed_high_excl = check_suppression("trend", "Revenue", n_used=40, n_excluded=60, total_rows=100)
    assert suppressed_high_excl is not None
    assert suppressed_high_excl.type == "data_quality"

    # 2. 0 outliers impact <= 0.1
    score_zero = compute_impact_score("outlier", 0.0, None, 100, 0, "high", anomaly_count=0)
    assert score_zero <= 0.10

    # 3. Confidence multiplier
    score_high = compute_impact_score("correlation", 0.5, 0.01, 100, 0, "high")
    score_med = compute_impact_score("correlation", 0.5, 0.01, 100, 0, "medium")
    score_low = compute_impact_score("correlation", 0.5, 0.01, 100, 0, "low")
    assert score_high > score_med > score_low

    # 4. Partition insights
    dummy_insights = [
        suppressed,
        suppressed_high_excl,
    ]
    analytical, dq = partition_insights(dummy_insights)
    assert len(analytical) == 0
    assert len(dq) == 2
