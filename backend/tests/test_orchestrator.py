"""Integration & Guardrail Tests for the Autonomous Agent Core.

Tests:
1. Full agent loop execution on real messy dataset
2. Adversarial guardrail tests (SQL writes, system file paths, network access rejection)
3. Step & token budget tripping (asserts loop stops gracefully with partial results)
4. Programmatic claim verification & citation checker
5. Explainability run log structure
6. Async jobs API dispatch and polling
"""
import time
import pytest
from fastapi import status
from backend.app.agent.citation_checker import extract_numeric_tokens, validate_citations
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.services.sql_tool import query_sql

RETAIL_DATASET = "retail_sales_messy.csv"
HR_DATASET = "hr_attrition_messy.csv"

# 1. FULL UNATTENDED AGENT LOOP TEST (ON REAL MESSY DATASET)
def test_full_agent_loop_unattended():
    """Verify that the full Plan-Act-Reflect loop runs unattended on real messy dataset."""
    orchestrator = PlanActReflectOrchestrator(
        max_steps=5,
        token_budget=20000
    )
    result = orchestrator.run_analysis(
        dataset_id=RETAIL_DATASET,
        goal="Identify pricing patterns, anomalous transactions, and category sales differentials."
    )

    assert result["status"] in ("completed", "budget_tripped")
    assert result["total_steps_executed"] >= 2
    assert len(result["run_log"]) == result["total_steps_executed"]
    assert "synthesis" in result
    assert len(result["synthesis"]["key_findings"]) >= 2
    assert len(result["chart_specifications"]) >= 1

    # Verify every claim in narrative traces to computed facts
    citation_audit = result["citation_audit"]
    assert citation_audit["verification_rate_percent"] >= 90.0

# 2. ADVERSARIAL SECURITY GUARDRAIL TESTS
def test_adversarial_sql_write_blocked():
    """Adversarial test: Agent-generated or malicious SQL trying to modify data or drop tables."""
    with pytest.raises(ValueError, match="Forbidden SQL keyword"):
        query_sql(RETAIL_DATASET, "DROP TABLE df")

    with pytest.raises(ValueError, match="Forbidden SQL keyword"):
        query_sql(RETAIL_DATASET, "DELETE FROM df WHERE Quantity < 0")

    with pytest.raises(ValueError, match="Forbidden SQL keyword"):
        query_sql(RETAIL_DATASET, "UPDATE df SET Unit_Price = 0")

def test_adversarial_filesystem_and_network_escape_blocked():
    """Adversarial test: Agent-generated query attempting file traversal or network exfiltration."""
    with pytest.raises(ValueError, match="External filesystem access"):
        query_sql(RETAIL_DATASET, "SELECT * FROM read_csv('C:\\Windows\\System32\\drivers\\etc\\hosts')")

    with pytest.raises(ValueError, match="External filesystem access"):
        query_sql(RETAIL_DATASET, "SELECT * FROM read_csv('http://malicious-exfil.com/leak')")

    with pytest.raises(ValueError, match="External filesystem access"):
        query_sql(RETAIL_DATASET, "SELECT * FROM scan_parquet('../../secret_keys.parquet')")

# 3. BUDGET GUARDRAIL TRIPPING TESTS (DELIBERATELY FORCES TRIP)
def test_step_budget_tripping_graceful_partial_fallback():
    """
    Deliberately trip the step budget with max_steps=2 when more steps are available.
    Asserts loop terminates gracefully and returns partial results.
    """
    orchestrator = PlanActReflectOrchestrator(
        max_steps=2,
        token_budget=50000
    )
    result = orchestrator.run_analysis(
        dataset_id=RETAIL_DATASET,
        goal="Exhaustive exploratory investigation."
    )

    assert result["budget_tripped"] is True
    assert result["status"] == "budget_tripped"
    assert result["total_steps_executed"] == 2
    assert "Maximum step budget reached" in result["trip_reason"]
    # Partial results must still be synthesized
    assert "synthesis" in result
    assert len(result["synthesis"]["key_findings"]) >= 1
    assert len(result["run_log"]) == 2

def test_token_budget_tripping_graceful_partial_fallback():
    """
    Deliberately trip the token budget with token_budget=400.
    Asserts loop stops immediately once token limit is breached.
    """
    orchestrator = PlanActReflectOrchestrator(
        max_steps=10,
        token_budget=400  # Will trip after 1 step
    )
    result = orchestrator.run_analysis(
        dataset_id=HR_DATASET,
        goal="Investigate employee satisfaction and attrition."
    )

    assert result["budget_tripped"] is True
    assert result["status"] == "budget_tripped"
    assert "Token budget exceeded" in result["trip_reason"]
    assert result["total_steps_executed"] >= 1
    assert len(result["run_log"]) >= 1

# 4. PROGRAMMATIC CITATION CHECKER TEST
def test_citation_checker_detects_hallucinations():
    """Test that citation checker flags numbers not present in tool results."""
    mock_tool_results = [
        {"tool": "run_correlation", "correlation": 0.75, "sample_size": 100},
        {"tool": "detect_outliers", "total_anomalous_rows": 12}
    ]
    
    # 1. Truthful synthesis
    truthful_synthesis = {
        "executive_summary": "Analysis of 100 rows identified 12 outliers and a correlation of 0.75.",
        "key_findings": []
    }
    audit_clean = validate_citations(truthful_synthesis, mock_tool_results)
    assert audit_clean["is_valid"] is True
    assert audit_clean["unverified_claims_count"] == 0

    # 2. Hallucinated synthesis with made-up numbers
    hallucinated_synthesis = {
        "executive_summary": "Analysis identified 999.85 uncomputed widgets and 45.7% phantom revenue growth.",
        "key_findings": []
    }
    audit_flagged = validate_citations(hallucinated_synthesis, mock_tool_results)
    assert audit_flagged["is_valid"] is False
    assert 999.85 in audit_flagged["unverified_numbers"]
    assert audit_flagged["unverified_claims_count"] > 0

# 5. EXPLAINABILITY RUN LOG STRUCTURE TEST
def test_run_log_explainability():
    """Verify run log contains timestamps, tool name, arguments, execution duration in ms, and rationale."""
    orchestrator = PlanActReflectOrchestrator(max_steps=2)
    result = orchestrator.run_analysis(dataset_id=RETAIL_DATASET)
    run_log = result["run_log"]

    assert len(run_log) > 0
    step1 = run_log[0]
    assert "step_number" in step1
    assert "timestamp" in step1
    assert "tool" in step1
    assert "arguments" in step1
    assert "duration_ms" in step1
    assert "rationale" in step1
    assert "summary" in step1

# 6. ASYNC JOBS API ENDPOINT & POLLING TEST
def test_jobs_api_lifecycle(client):
    """Test creating an async analysis job and polling for status and logs."""
    # 1. Submit job
    res = client.post(
        "/api/v1/jobs",
        json={"dataset_id": RETAIL_DATASET, "goal": "Find top sales insights", "max_steps": 2}
    )
    assert res.status_code == status.HTTP_202_ACCEPTED
    job_id = res.json()["job_id"]
    assert res.json()["status"] in ("running", "completed")

    # 2. Poll job status
    poll_res = client.get(f"/api/v1/jobs/{job_id}")
    assert poll_res.status_code == status.HTTP_200_OK
    data = poll_res.json()
    assert data["job_id"] == job_id
    assert "current_step_name" in data

    # 3. Retrieve run log
    log_res = client.get(f"/api/v1/jobs/{job_id}/logs")
    assert log_res.status_code == status.HTTP_200_OK
    assert "run_log" in log_res.json()
