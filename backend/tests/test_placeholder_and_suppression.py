import os
import re
import pytest
import pandas as pd
from backend.app.services.insights import generate_insights, check_suppression, validate_no_placeholders
from backend.app.services.cleaning import clean_data
from backend.app.services.segmentation import segment_compare
from backend.app.services.correlation import run_correlation
from backend.app.services.timeseries import trend_analysis
from backend.app.services.outliers import detect_outliers

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "samples"))

def test_validate_no_placeholders_fails_loudly():
    """Verify that placeholder tokens fail loudly by raising ValueError."""
    with pytest.raises(ValueError, match="Disallowed placeholder pattern"):
        validate_no_placeholders("Variance in Metric across Segment", "test")

    with pytest.raises(ValueError, match="Disallowed placeholder pattern"):
        validate_no_placeholders("None recorded the highest Metric (median None)", "test")

    with pytest.raises(ValueError, match="Placeholder token 'None'"):
        validate_no_placeholders("Sales in None was 500", "test")

    with pytest.raises(ValueError, match="Placeholder token 'nan'"):
        validate_no_placeholders("Median value was nan", "test")

    # Valid string must pass through unmodified
    valid_text = "Sales in North region reached $50,000 with p=0.0123"
    assert validate_no_placeholders(valid_text, "test") == valid_text


def test_suppression_rules_exact_reason():
    """Verify exact triggering rule text without string/number mismatches."""
    # Rule 1: exclusion_rate > 0.5 with n_used >= 20
    # e.g., n_used=46, n_excluded=64, total_rows=110
    sup1 = check_suppression("correlation", "A vs B", n_used=46, n_excluded=64, total_rows=110)
    assert sup1 is not None
    assert "exclusion_rate=58.2% > 50%" in sup1.metric_values["rule_detail"]
    assert "n_used=46 < 20" not in sup1.metric_values["rule_detail"]
    assert sup1.metric_values["trigger_rule"] == "exclusion_rate > 0.5"

    # Rule 2: n_used < 20 with exclusion_rate <= 0.5
    # e.g., n_used=15, n_excluded=5, total_rows=20
    sup2 = check_suppression("correlation", "X vs Y", n_used=15, n_excluded=5, total_rows=20)
    assert sup2 is not None
    assert "n_used=15 < 20" in sup2.metric_values["rule_detail"]
    assert "> 50%" not in sup2.metric_values["rule_detail"]
    assert sup2.metric_values["trigger_rule"] == "n_used < 20"

    # Rule 3: both trigger
    sup3 = check_suppression("correlation", "P vs Q", n_used=10, n_excluded=40, total_rows=50)
    assert sup3 is not None
    assert "n_used=10 < 20" in sup3.metric_values["rule_detail"]
    assert "exclusion_rate=80.0% > 50%" in sup3.metric_values["rule_detail"]
    assert sup3.metric_values["trigger_rule"] == "n_used < 20 and exclusion_rate > 0.5"


def test_no_placeholders_in_insights_across_all_three_datasets():
    """Run tools on all 3 datasets and verify zero placeholders in insight titles, summaries, and metric_values."""
    datasets = [
        ("retail_sales_messy.csv", "Region", "Total_Amount", "Date", "Quantity"),
        ("hr_attrition_messy.csv", "Department", "Monthly_Salary", None, None),
        ("marketing_campaign_messy.csv", "Channel", "Conversions", None, None),
    ]

    for filename, seg_col, met_col, date_col, trend_val_col in datasets:
        path = os.path.join(DATA_DIR, filename)
        raw_df = pd.read_csv(path)
        clean_df, cl_report = clean_data(raw_df, filename)
        n_total = len(clean_df)

        tools_res = []
        # Segment compare
        if seg_col in clean_df.columns and met_col in clean_df.columns:
            sc_res = segment_compare(clean_df, seg_col, met_col)
            tools_res.append(sc_res)

        # Correlation
        num_cols = list(clean_df.select_dtypes(include=["number"]).columns)
        if len(num_cols) >= 2:
            corr_res = run_correlation(clean_df, num_cols)
            tools_res.append(corr_res)

        # Outliers
        out_res = detect_outliers(clean_df, method="iqr", columns=num_cols)
        tools_res.append(out_res)

        # Trend if applicable
        if date_col and trend_val_col and date_col in clean_df.columns and trend_val_col in clean_df.columns:
            tr_res = trend_analysis(clean_df, date_col, trend_val_col, freq="ME")
            tools_res.append(tr_res)

        profile = {
            "row_count": n_total,
            "cleaned_row_count": n_total,
            "cleaning_report": cl_report,
            "filename": filename
        }

        insights = generate_insights(structured_results=tools_res, dataset_profile=profile)
        assert len(insights) > 0

        for ins in insights:
            # Test no placeholders in title and summary
            assert not re.search(r"\bNone\b", ins.title), f"Placeholder 'None' in {ins.id} title: {ins.title}"
            assert not re.search(r"\bNone\b", ins.summary), f"Placeholder 'None' in {ins.id} summary: {ins.summary}"
            assert not re.search(r"\b(?:nan|NaN)\b", ins.title), f"Placeholder 'nan' in {ins.id} title: {ins.title}"
            assert not re.search(r"\b(?:nan|NaN)\b", ins.summary), f"Placeholder 'nan' in {ins.id} summary: {ins.summary}"
            assert "Metric across Segment" not in ins.title, f"Generic placeholder in {ins.id} title: {ins.title}"
            assert "Metric across Segment" not in ins.summary, f"Generic placeholder in {ins.id} summary: {ins.summary}"

            # Invariant: n_used + n_excluded == n_total
            assert ins.n_used + ins.n_excluded == n_total, (
                f"Invariant violation in {ins.id}: n_used({ins.n_used}) + n_excluded({ins.n_excluded}) != n_total({n_total})"
            )

            # Segment difference insights must carry required metric_values keys
            if ins.type == "segment_difference" and not ins.id.startswith("insight-dq-insufficient"):
                mv = ins.metric_values
                assert "segment_column" in mv
                assert "metric_column" in mv
                assert "top_segment" in mv
                assert "bottom_segment" in mv
                assert mv["top_segment"] is not None
                assert mv["bottom_segment"] is not None
                assert mv["segment_column"] != "Segment"
                assert mv["metric_column"] != "Metric"
