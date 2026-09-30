"""Unit tests for categorical/binary rates analysis (Item 3)."""
import pytest
from backend.app.services.segmentation import segment_compare
from backend.app.services.insights import generate_insights

def test_categorical_rate_attrition_by_department():
    """
    Test: Add an analysis path for rates of a binary or categorical target by segment
    (e.g. Attrition by Department): compute on non-imputed rows only, chi-square test,
    report n_used per segment and the overall rate with its denominator.
    """
    res = segment_compare(
        dataset_id="hr_attrition_messy.csv",
        segment_column="Department",
        metric_column="Attrition"
    )

    assert res["status"] == "success"
    assert res["analysis_type"] == "categorical_rate"
    assert res["target_class"].lower() == "yes"
    assert res["n_used"] > 0
    assert res["overall_denominator"] == res["n_used"]
    assert "overall_rate_percent" in res
    assert "chi2_p_value" in res
    assert len(res["segments"]) >= 2

    # Check each segment has n_used, positive_count, rate_percent
    for seg in res["segments"]:
        assert "n_used" in seg
        assert "positive_count" in seg
        assert "rate_percent" in seg
        assert seg["n_used"] > 0

    print(f"Attrition by Department: overall {res['overall_rate_percent']}% (denom={res['overall_denominator']}), chi2 p={res['chi2_p_value']}")
    for seg in res["segments"]:
        print(f"  - {seg['segment']}: {seg['rate_percent']}% (n={seg['n_used']})")

    # Generate insights from this result
    insights = generate_insights(structured_results=[res])
    rate_insights = [ins for ins in insights if ins.type == "segment_difference"]
    assert len(rate_insights) >= 1
    ins = rate_insights[0]
    assert "Attrition" in ins.title or "Department" in ins.title
    assert ins.n_used == res["n_used"]
    assert ins.n_excluded == res["n_excluded_imputed"]
    assert ins.n_used + ins.n_excluded == res["total_records"]
    assert ins.chart_spec is not None
    assert ins.chart_spec["chart_type"] == "bar"
