"""Tests for Phase 3 Milestone 1: Phase 2 Leftovers + Insight Layer."""
import pytest
import numpy as np
import pandas as pd
from typing import Dict, Any

from backend.app.services.cleaning import clean_data
from shared.schemas.dataset import DatasetCleaningOptions
from backend.app.services.insights import generate_insights, compute_impact_score, determine_confidence
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.agent.llm_client import HeuristicClient
from backend.app.agent.citation_checker import validate_citations
from shared.schemas.insight import Insight, InsightType, ConfidenceLevel


def test_confidence_classification():
    # low if exclusion_rate > 0.4 or n_used < 30
    assert determine_confidence(n_used=25, exclusion_rate=0.1) == "low"
    assert determine_confidence(n_used=100, exclusion_rate=0.45) == "low"

    # medium if exclusion_rate > 0.2 or 30 <= n_used < 60
    assert determine_confidence(n_used=45, exclusion_rate=0.1) == "medium"
    assert determine_confidence(n_used=100, exclusion_rate=0.25) == "medium"

    # else high
    assert determine_confidence(n_used=100, exclusion_rate=0.05) == "high"


def test_sentinel_vs_suspected_repeated_extremes():
    # 999 repeated 4 times in a column of normal small numbers -> sentinel
    df_sentinel = pd.DataFrame({
        "id": list(range(11)),
        "metric": [10.0, 12.0, 11.0, 13.0, 10.5, 11.2, 12.1, 999.0, 999.0, 999.0, 999.0]
    })
    cleaned_df, report = clean_data(df_sentinel, dataset_id="test_sentinel")
    assert len(report.sentinels_detected) == 1
    assert report.sentinels_detected[0]["column"] == "metric"
    assert report.sentinels_detected[0]["sentinel_value"] == 999.0
    # Sentinels should be imputed, not kept as 999
    assert 999.0 not in cleaned_df["metric"].values

    # Conversions=90 repeated 4 times -> NOT a placeholder pattern (999, -1, etc.) -> kept as suspected_repeated_extremes
    df_extreme = pd.DataFrame({
        "id": list(range(11)),
        "conversions": [1.0, 2.0, 1.0, 3.0, 2.0, 1.0, 2.0, 90.0, 90.0, 90.0, 90.0]
    })
    cleaned_extreme, report_extreme = clean_data(df_extreme, dataset_id="test_extreme")
    assert len(report_extreme.sentinels_detected) == 0
    assert len(report_extreme.suspected_repeated_extremes) == 1
    assert report_extreme.suspected_repeated_extremes[0]["value"] == 90.0
    # Values must be KEPT in the cleaned data
    assert (cleaned_extreme["conversions"] == 90.0).sum() == 4


def test_suspected_returns_vs_invalid_negatives():
    # Negatives in quantity/count columns -> suspected_returns and KEPT
    df_returns = pd.DataFrame({
        "quantity": [10, 20, -5, -2, 15, 30],
        "salary": [50000, 60000, -10000, 75000, 80000, 90000],
        "age": [25, 45, 150, -5, 35, 40]
    })
    cleaned_df, report = clean_data(df_returns, dataset_id="test_returns")

    # Suspected returns kept
    assert len(report.suspected_returns) == 1
    assert report.suspected_returns[0]["column"] == "quantity"
    assert report.suspected_returns[0]["count"] == 2
    assert -5 in cleaned_df["quantity"].values
    assert -2 in cleaned_df["quantity"].values

    # Salary negatives and age bounds converted to NaN and imputed
    assert -10000 not in cleaned_df["salary"].values
    assert 150 not in cleaned_df["age"].values
    assert -5 not in cleaned_df["age"].values
    assert any(inv["column"] == "salary" for inv in report.invalid_values_detected)
    assert any(inv["column"] == "age" for inv in report.invalid_values_detected)


def test_llm_latency_measurement_and_budget_consistency():
    # Test orchestrator with HeuristicClient
    orchestrator = PlanActReflectOrchestrator(
        max_steps=3,
        llm_client=HeuristicClient()
    )
    result = orchestrator.run_analysis(
        dataset_id="retail_sales_messy",
        goal="Assess sales distribution and outliers"
    )

    run_log = result["run_log"]
    latencies = [step["llm_latency_ms"] for step in run_log]
    
    # 1. Step 1 has latency >= 0; pre-planned subsequent steps have 0.0 -> values differ per step if multi-step
    if len(latencies) >= 2:
        assert latencies[0] >= latencies[1]
        assert latencies[1] == 0.0

    # 2. Sum of LLM latencies <= total run time (converted to ms)
    total_run_ms = result["execution_time_seconds"] * 1000.0 + 100.0  # slight precision padding
    total_llm_lat = result["total_llm_latency_ms"]
    assert total_llm_lat <= total_run_ms


def test_insights_ranking_deduplication_and_citation():
    # Mock analysis results
    executed_results = [
        {
            "tool": "segment_compare",
            "category_column": "Region",
            "metric_column": "Sales",
            "top_segment": {"segment": "North", "mean": 150.0},
            "bottom_segment": {"segment": "South", "mean": 50.0},
            "n_rows_used": 100,
            "exclusion_rate": 0.05,
            "is_statistically_significant": True,
            "anova_p_value": 0.001,
            "effect_size": 0.45
        },
        {
            "tool": "segment_compare",
            "category_column": "Region",
            "metric_column": "Sales",
            "top_segment": {"segment": "North", "mean": 150.0},
            "bottom_segment": {"segment": "South", "mean": 50.0},
            "n_rows_used": 100,
            "exclusion_rate": 0.05,
            "is_statistically_significant": True,
            "anova_p_value": 0.001,
            "effect_size": 0.45
        },  # Duplicate
        {
            "tool": "segment_compare",
            "category_column": "Dept",
            "metric_column": "Performance",
            "top_segment": {"segment": "Tech", "mean": 80.0},
            "bottom_segment": {"segment": "HR", "mean": 78.0},
            "n_rows_used": 40,
            "exclusion_rate": 0.1,
            "is_statistically_significant": False,
            "anova_p_value": 0.65,
            "effect_size": 0.02
        }
    ]
    dataset_profile = {
        "row_count": 120,
        "sentinels_detected": [{"column": "Quantity", "sentinel_value": 999.0, "count": 15}],
        "suspected_returns": [{"column": "Quantity", "count": 5}],
        "suspected_repeated_extremes": [{"column": "Conversions", "value": 90.0, "count": 4}],
        "column_imputation_stats": {"Salary": {"imputation_rate": 0.46, "imputed_count": 51}}
    }

    insights = generate_insights(executed_results, dataset_profile, run_log=[])

    # Should deduplicate duplicate segment_compare
    assert len(insights) <= 8
    titles = [i.title for i in insights]
    assert len(titles) == len(set(titles))

    # Check non-significant result phrasing
    non_sig = [i for i in insights if i.significance and i.significance > 0.05]
    if non_sig:
        assert "no significant difference" in non_sig[0].title.lower() or "no significant difference" in non_sig[0].summary.lower()

    # Check data quality insights generation
    dq_insights = [i for i in insights if i.type == "data_quality"]
    assert len(dq_insights) >= 2  # Sentinel, high imputation, returns/extremes

    # Check citation checker accepts insight numeric values
    synthesis = {
        "executive_summary": "Top segment reached 150.0 mean sales while 15 sentinels were sanitized and 51 records were imputed.",
        "key_findings": []
    }
    audit = validate_citations(
        synthesis_result=synthesis,
        structured_results=executed_results,
        dataset_profile=dataset_profile,
        insights=insights
    )
    assert audit["is_valid"] is True
    assert 150.0 in audit["verified_numbers"]
    assert 15.0 in audit["verified_numbers"]
    assert 51.0 in audit["verified_numbers"]


def test_get_job_insights_endpoint():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.core.database import SessionLocal
    from backend.app.models.job import AnalysisJob
    import uuid

    client = TestClient(app)
    db = SessionLocal()
    job_id = f"test-job-{uuid.uuid4().hex[:8]}"
    job = AnalysisJob(
        id=job_id,
        dataset_id="retail_sales_messy",
        goal="Test insights endpoint",
        status="completed"
    )
    job.set_insights([
        {
            "id": "insight-1",
            "type": "segment_difference",
            "title": "North outperformed South",
            "summary": "North sales reached 150 vs 50 for South",
            "impact_score": 0.85
        }
    ])
    db.add(job)
    db.commit()
    db.close()

    res = client.get(f"/api/v1/jobs/{job_id}/insights")
    assert res.status_code == 200
    data = res.json()
    assert data["job_id"] == job_id
    assert data["total_insights"] == 1
    assert data["insights"][0]["title"] == "North outperformed South"
