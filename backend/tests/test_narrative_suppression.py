import os
import re
import pytest
import pandas as pd
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.services.cleaning import clean_data
from backend.app.services.profiling import profile_dataset
from backend.app.services.insights import generate_insights
from backend.app.services.summary import write_summary
from backend.app.services.timeseries import trend_analysis
from backend.app.services.correlation import run_correlation

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "samples"))

def test_retail_narrative_has_no_unit_price_trend_pct():
    """Verify retail narrative has NO Unit_Price trend % while that trend is suppressed."""
    retail_csv = os.path.join(DATA_DIR, "retail_sales_messy.csv")
    raw_df = pd.read_csv(retail_csv)
    clean_df, cl_report = clean_data(raw_df, "retail_sales_messy.csv")
    n_total = len(clean_df)

    # Unit_Price trend is heavily excluded (sentinels/imputations) -> exclusion_rate > 50%
    tr_res = trend_analysis(clean_df, "Date", "Unit_Price", freq="ME")
    profile = {
        "row_count": n_total,
        "cleaned_row_count": n_total,
        "cleaning_report": cl_report,
        "filename": "retail_sales_messy.csv"
    }

    insights = generate_insights(structured_results=[tr_res], dataset_profile=profile)
    # Confirm trend is suppressed
    suppressed_trend = [i for i in insights if "insufficient" in i.id and "trend" in i.id]
    assert len(suppressed_trend) == 1, "Unit_Price trend must be suppressed"
    raw_trend_pct = tr_res.get("percentage_change")
    assert raw_trend_pct is not None

    # Write summary based on insights
    summary = write_summary(
        structured_results=[tr_res],
        dataset_profile=profile,
        insights=insights
    )
    exec_summary = summary["executive_summary"]
    findings = summary["key_findings"]

    # Invariant: retail narrative must NOT contain the suppressed raw trend percentage
    str_pct = f"{raw_trend_pct:.1f}%"
    assert str_pct not in exec_summary
    for f in findings:
        assert str_pct not in f.get("narrative", "")
        assert str_pct not in f.get("headline", "")

    # Suppressed mention must strictly follow the required format
    assert "insufficient data for trend on 'Unit_Price'" in exec_summary or "insufficient data for trend on 'Unit_Price'" in str(findings)


def test_hr_narrative_has_no_r_value_for_suppressed_correlation():
    """Verify HR narrative has NO r value for a suppressed correlation."""
    hr_csv = os.path.join(DATA_DIR, "hr_attrition_messy.csv")
    raw_df = pd.read_csv(hr_csv)
    clean_df, cl_report = clean_data(raw_df, "hr_attrition_messy.csv")
    n_total = len(clean_df)

    corr_res = run_correlation(clean_df, ["Performance_Score", "Last_Promotion_Year"])
    profile = {
        "row_count": n_total,
        "cleaned_row_count": n_total,
        "cleaning_report": cl_report,
        "filename": "hr_attrition_messy.csv"
    }

    insights = generate_insights(structured_results=[corr_res], dataset_profile=profile)
    suppressed_corr = [i for i in insights if "insufficient" in i.id and "correlation" in i.id]
    assert len(suppressed_corr) >= 1, "Performance_Score vs Last_Promotion_Year correlation must be suppressed"

    # Get the raw suppressed r value
    supp_r = None
    if corr_res.get("strong_relationships"):
        supp_r = corr_res["strong_relationships"][0]["correlation"]
    elif corr_res.get("highest_correlation"):
        supp_r = corr_res["highest_correlation"]["correlation"]
    assert supp_r is not None

    summary = write_summary(
        structured_results=[corr_res],
        dataset_profile=profile,
        insights=insights
    )
    exec_summary = summary["executive_summary"]
    findings = summary["key_findings"]

    # Invariant: narrative must NOT contain r value
    r_formatted_4 = f"{supp_r:.4f}"
    r_formatted_2 = f"{supp_r:.2f}"
    assert f"r={r_formatted_4}" not in exec_summary
    assert f"r={r_formatted_2}" not in exec_summary
    for f in findings:
        assert f"r={r_formatted_4}" not in f.get("narrative", "")
        assert f"r={r_formatted_2}" not in f.get("narrative", "")

    # Suppressed mention must strictly follow the required format
    assert "insufficient data for correlation" in exec_summary or "insufficient data for correlation" in str(findings)


def test_segment_p_greater_than_05_says_no_significant_difference():
    """Verify if p >= 0.05, narrative says 'no significant difference' and does not present top segment as finding."""
    ins = [
        {
            "id": "insight-seg-test",
            "type": "segment_difference",
            "title": "No significant difference in Salary across Region",
            "summary": "ANOVA p=0.4567 across 100 rows",
            "metric_values": {
                "segment_column": "Region",
                "metric_column": "Salary",
                "top_segment": "North",
                "top_median": 5500.0,
                "bottom_segment": "South",
                "bottom_median": 5400.0,
                "ratio": 1.02,
                "p_value": 0.4567
            },
            "significance": 0.4567,
            "n_used": 100,
            "n_excluded": 10,
            "exclusion_rate": 0.09
        }
    ]

    summary = write_summary(insights=ins)
    exec_summary = summary["executive_summary"]
    findings = summary["key_findings"]

    assert "no significant difference" in exec_summary.lower()
    assert "North recorded the highest" not in exec_summary
    assert findings[0]["headline"] == "No significant difference in Salary across Region"
    assert "no significant difference" in findings[0]["narrative"].lower()
