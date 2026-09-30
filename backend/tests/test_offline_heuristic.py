"""Offline Mode E2E Test (Milestone 6).

Verifies that with LLM_PROVIDER=heuristic, the complete analytical lifecycle:
1. Ingestion & Profiling
2. Sanitization & Cleaning
3. Plan-Act-Reflect Autonomous Execution
4. Insights Generation & Impact Ranking
5. Citation Audit
6. Chat Q&A Interaction
7. PDF & DOCX Export
executes 100% deterministically without requiring any external LLM API key.
"""
import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.core.database import SessionLocal
from backend.app.models.dataset import Dataset
from backend.app.models.job import AnalysisJob
from backend.app.services.chat_service import process_chat_question
from backend.app.services.cleaning import clean_data
import pandas as pd
from backend.app.services.insights import generate_insights
from backend.app.services.profiling import profile_dataset
from backend.app.services.report_docx import generate_docx_report
from backend.app.services.report_pdf import generate_pdf_report

client = TestClient(app)

def test_offline_heuristic_full_flow(tmp_path, monkeypatch):
    """Verify that entire analysis flow runs completely offline without any API keys."""
    # Force heuristic mode and wipe API keys in environment
    monkeypatch.setenv("LLM_PROVIDER", "heuristic")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    sample_csv = Path("data/samples/retail_sales_messy.csv")
    assert sample_csv.exists(), "Sample dataset must exist"

    # 1. Load & Validate
    df_raw = pd.read_csv(sample_csv)
    assert len(df_raw) > 0

    # 2. Clean & Profile
    df_cleaned, cleaning_result = clean_data(df_raw, "retail_sales_messy.csv")
    cleaning_report = cleaning_result.model_dump()
    profile = profile_dataset(df_cleaned).model_dump()
    assert profile["quality_summary"]["quality_score"] > 0

    # 3. Autonomous Orchestrator Execution
    orchestrator = PlanActReflectOrchestrator(
        max_steps=5,
        token_budget=15000,
        provider="heuristic"
    )
    run_result = orchestrator.run_analysis(
        dataset_id="retail_sales_messy.csv",
        goal="Analyze revenue differences and marketing performance"
    )

    assert run_result["status"] in ("completed", "budget_tripped")
    assert len(run_result["run_log"]) >= 1
    assert "synthesis" in run_result
    
    # 4. Insights Generation & Ranking
    raw_insights = run_result.get("insights") or []
    if not raw_insights:
        raw_insights = generate_insights(
            structured_results=[s.get("result", {}) for s in run_result["run_log"]],
            dataset_profile=profile,
            cleaning_report=cleaning_report,
            run_log=run_result["run_log"]
        )
    assert len(raw_insights) >= 1
    assert len(raw_insights) <= 8
    
    # Verify impact score ordering
    impacts = [ins.impact_score if hasattr(ins, "impact_score") else ins["impact_score"] for ins in raw_insights]
    assert impacts == sorted(impacts, reverse=True)

    # 5. Citation Audit
    verification = run_result.get("verification") or {}
    assert "verification_rate_percent" in verification

    # 6. Database record setup & Chat Q&A
    db = SessionLocal()
    ds_id = f"test-offline-{tmp_path.name}"
    job_id = f"job-offline-{tmp_path.name}"
    
    ds = Dataset(
        id=ds_id,
        filename="retail_sales_messy.csv",
        file_path=str(sample_csv),
        file_type="csv",
        row_count=len(df_cleaned),
        column_count=len(df_cleaned.columns),
        profile_json=json.dumps(profile),
        cleaning_summary_json=json.dumps(cleaning_report)
    )
    job = AnalysisJob(
        id=job_id,
        dataset_id=ds_id,
        status="completed",
        phase="completed",
        results_json=json.dumps({
            "insights": [ins.model_dump() if hasattr(ins, "model_dump") else ins for ins in raw_insights],
            "synthesis": run_result["synthesis"],
            "structured_results": [s.get("result", {}) for s in run_result["run_log"]]
        }),
        run_log_json=json.dumps(run_result["run_log"]),
        verification_json=json.dumps(verification)
    )
    db.merge(ds)
    db.merge(job)
    db.commit()

    try:
        # Chat question
        chat_res = process_chat_question(
            db=db,
            job_id=job_id,
            question="What data quality issues were sanitized?"
        )
        assert len(chat_res["answer"]) > 10
        assert chat_res["verification"]["is_valid"] is True

        # 7. PDF and DOCX Report Exports
        pdf_out = tmp_path / "offline_report.pdf"
        docx_out = tmp_path / "offline_report.docx"

        generate_pdf_report(
            output_path=pdf_out,
            dataset_name="retail_sales_messy.csv",
            job_data={"results": job.get_results(), "run_log": run_result["run_log"], "verification": verification},
            profile_data=profile,
            cleaning_data=cleaning_report,
            provider="Heuristic",
            model_name="deterministic-engine"
        )
        assert pdf_out.exists() and pdf_out.stat().st_size > 1000

        generate_docx_report(
            output_path=docx_out,
            dataset_name="retail_sales_messy.csv",
            job_data={"results": job.get_results(), "run_log": run_result["run_log"], "verification": verification},
            profile_data=profile,
            cleaning_data=cleaning_report,
            provider="Heuristic",
            model_name="deterministic-engine"
        )
        assert docx_out.exists() and docx_out.stat().st_size > 1000

    finally:
        db.query(AnalysisJob).filter(AnalysisJob.id == job_id).delete()
        db.query(Dataset).filter(Dataset.id == ds_id).delete()
        db.commit()
        db.close()
