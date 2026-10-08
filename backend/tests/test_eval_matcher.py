"""Unit tests for Evaluation Matcher (Stage B2).

Verifies documented rules mapping surviving insights to planted IDs and false-positive detection on null datasets.
Runs fully offline in quick mode with zero external dependencies.
"""
import pytest
from evaluation.match import (
    match_single_planted_finding,
    audit_dataset_findings
)


def test_matcher_s1_segment_difference():
    planted = {
        "type": "segment_difference",
        "segment_column": "segment",
        "metric_column": "metric_score",
    }
    insights = [
        {
            "id": "ins-s1",
            "type": "segment_difference",
            "title": "Segment difference across segment on metric_score",
            "segment_column": "segment",
            "metric_column": "metric_score",
            "significance": 0.001
        }
    ]
    found, mid, note = match_single_planted_finding("S1", planted, insights)
    assert found is True
    assert mid == "ins-s1"


def test_matcher_c1_correlation():
    planted = {
        "type": "correlation",
        "column_1": "var_x",
        "column_2": "var_y"
    }
    insights = [
        {
            "id": "ins-c1",
            "type": "correlation",
            "title": "Strong positive correlation between var_x and var_y",
            "effect_size": 0.61
        }
    ]
    found, mid, note = match_single_planted_finding("C1", planted, insights)
    assert found is True
    assert mid == "ins-c1"


def test_matcher_t1_trend():
    planted = {
        "type": "trend",
        "metric_column": "trend_metric"
    }
    insights = [
        {
            "id": "ins-t1",
            "type": "trend",
            "title": "Upward trend on trend_metric over date",
            "direction": "upward"
        }
    ]
    found, mid, note = match_single_planted_finding("T1", planted, insights)
    assert found is True
    assert mid == "ins-t1"


def test_matcher_o1_outliers():
    planted = {
        "type": "outlier",
        "column": "volume"
    }
    insights = [
        {
            "id": "ins-o1",
            "type": "outlier",
            "title": "Extreme volume spikes detected",
            "metric_values": {"outlier_count": 40}
        }
    ]
    found, mid, note = match_single_planted_finding("O1", planted, insights)
    assert found is True
    assert mid == "ins-o1"


def test_matcher_data_quality_q1_q2_m1():
    # Q1: Sentinel 999 in satisfaction_score
    q1_spec = {"type": "sentinel", "column": "satisfaction_score"}
    dq_caveats = [
        {"id": "dq-1", "type": "data_quality", "headline": "Sanitized 60 sentinel values of 999 in satisfaction_score"},
        {"id": "dq-2", "type": "data_quality", "headline": "Detected 40 invalid negative salary values"},
        {"id": "dq-3", "type": "data_quality", "headline": "Missingness in activity_index required 20% imputation"}
    ]
    f1, _, _ = match_single_planted_finding("Q1", q1_spec, [], dq_caveats)
    assert f1 is True

    # Q2: Invalid negative salary
    q2_spec = {"type": "invalid_domain", "column": "salary"}
    f2, _, _ = match_single_planted_finding("Q2", q2_spec, [], dq_caveats)
    assert f2 is True

    # M1: Missingness in activity_index
    m1_spec = {"type": "missingness", "column": "activity_index"}
    f3, _, _ = match_single_planted_finding("M1", m1_spec, [], dq_caveats)
    assert f3 is True


def test_audit_null_dataset_false_positive():
    manifest = {
        "seed": 101,
        "is_null": True,
        "planted_findings": {}
    }
    # Synthetic insight spuriously discovered on null dataset
    insights = [
        {
            "id": "fp-1",
            "type": "correlation",
            "title": "Spurious correlation in white noise"
        }
    ]
    audit = audit_dataset_findings(manifest, insights)
    assert audit["is_null"] is True
    assert audit["false_positive_count"] == 1
    assert audit["false_positives"][0]["insight_id"] == "fp-1"
    assert "Matcher Audit Table: Seed 101" in audit["audit_table_markdown"]
