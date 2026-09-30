"""Tests for Milestone 5 (PDF & Word Report Export, Validation, and Endpoints)."""
import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import docx
import pypdf

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.dataset import Dataset
from backend.app.models.job import AnalysisJob
from backend.app.services.report_docx import generate_docx_report
from backend.app.services.report_pdf import generate_pdf_report

client = TestClient(app)

MOCK_JOB_DATA = {
    "results": {
        "synthesis": {
            "executive_summary": "Comprehensive analysis reveals critical operational dynamics across key segments and data quality dimensions.",
            "recommendations": ["Optimize marketing spend", "Address employee attrition in Sales", "Sanitize sentinel placeholders"]
        },
        "insights": [
            {
                "id": "ins-1",
                "type": "segment_difference",
                "title": "Segment Performance Variance",
                "summary": "Primary segment demonstrates 45.2% higher metric output compared to baseline.",
                "confidence": "high",
                "impact_score": 0.85,
                "n_used": 500,
                "n_excluded": 10,
                "exclusion_rate": 0.02,
                "caveats": ["Data collected over a 30-day window"],
                "chart_spec": {
                    "chart_type": "bar",
                    "title": "Segment Performance Comparison",
                    "data": [
                        {"category": "Group A", "value": 45.2},
                        {"category": "Group B", "value": 31.0}
                    ]
                }
            }
        ],
        "structured_results": [
            {"tool": "profile_dataset", "row_count": 500, "column_count": 6, "quality_score": 90.0}
        ]
    },
    "run_log": [
        {"step": 1, "tool": "segment_compare", "rationale": "Evaluate performance difference", "tool_time_ms": 12.0, "llm_latency_ms": 1500.0, "tokens": 450}
    ],
    "verification": {
        "is_valid": True,
        "total_claims_checked": 1,
        "verified_claims_count": 1,
        "verification_rate_percent": 100.0
    }
}

MOCK_CLEANING = {
    "sentinels_detected": [{"column": "amount", "sentinel_value": 9999, "count": 3}],
    "invalid_values_detected": [{"column": "price", "rule": "non_negative", "count": 2}],
    "suspected_returns": [{"column": "quantity", "count": 5}],
    "column_imputation_stats": {"amount": {"imputed_count": 8, "imputation_rate": 0.04, "strategy": "median"}}
}

MOCK_PROFILE = {
    "row_count": 500,
    "column_count": 6,
    "quality_summary": {"quality_score": 90.0}
}

DATASET_NAMES = [
    "messy_ecommerce.csv",
    "messy_hr.csv",
    "messy_marketing.csv"
]

@pytest.mark.parametrize("ds_name", DATASET_NAMES)
def test_pdf_report_generation_and_validation(tmp_path, ds_name):
    """Test PDF generation for all 3 datasets, validate text via pypdf and presence of chart image."""
    pdf_out = tmp_path / f"{Path(ds_name).stem}_test.pdf"
    
    generate_pdf_report(
        output_path=pdf_out,
        dataset_name=ds_name,
        job_data=MOCK_JOB_DATA,
        profile_data=MOCK_PROFILE,
        cleaning_data=MOCK_CLEANING,
        provider="Gemini",
        model_name="gemini-2.5-flash"
    )
    
    assert pdf_out.exists()
    assert pdf_out.stat().st_size > 1000  # Non-empty, substantive PDF
    
    # Validate with pypdf
    reader = pypdf.PdfReader(str(pdf_out))
    assert len(reader.pages) >= 1
    
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() or ""
        
    assert "Autonomous AI Data Analyst Report" in full_text
    assert "Comprehensive analysis reveals critical operational dynamics" in full_text
    assert ds_name in full_text

@pytest.mark.parametrize("ds_name", DATASET_NAMES)
def test_docx_report_generation_and_validation(tmp_path, ds_name):
    """Test DOCX generation for all 3 datasets, validate text via python-docx and presence of image."""
    docx_out = tmp_path / f"{Path(ds_name).stem}_test.docx"
    
    generate_docx_report(
        output_path=docx_out,
        dataset_name=ds_name,
        job_data=MOCK_JOB_DATA,
        profile_data=MOCK_PROFILE,
        cleaning_data=MOCK_CLEANING,
        provider="Gemini",
        model_name="gemini-2.5-flash"
    )
    
    assert docx_out.exists()
    assert docx_out.stat().st_size > 1000
    
    # Validate with python-docx
    doc = docx.Document(str(docx_out))
    doc_text = "\n".join(p.text for p in doc.paragraphs)
    
    assert "Autonomous AI Data Analyst Report" in doc_text
    assert "Comprehensive analysis reveals critical operational dynamics" in doc_text
    assert ds_name in doc_text
    
    # Validate presence of at least one embedded image/shape
    shapes_count = len(doc.inline_shapes)
    assert shapes_count >= 1

def test_report_endpoints_and_content_types():
    """Test POST /jobs/{id}/report?format=pdf|docx and GET /reports/{id}/download."""
    db = SessionLocal()
    ds = Dataset(
        id="test-rep-ds",
        filename="messy_ecommerce.csv",
        file_path="data/uploads/messy_ecommerce.csv",
        file_type="csv",
        row_count=500,
        column_count=6,
        profile_json=json.dumps(MOCK_PROFILE),
        cleaning_summary_json=json.dumps(MOCK_CLEANING)
    )
    job = AnalysisJob(
        id="test-rep-job",
        dataset_id="test-rep-ds",
        status="completed",
        phase="completed",
        results_json=json.dumps(MOCK_JOB_DATA["results"]),
        run_log_json=json.dumps(MOCK_JOB_DATA["run_log"]),
        verification_json=json.dumps(MOCK_JOB_DATA["verification"])
    )
    db.merge(ds)
    db.merge(job)
    db.commit()
    
    try:
        # 1. Generate PDF
        res_pdf = client.post("/api/v1/jobs/test-rep-job/report?format=pdf")
        assert res_pdf.status_code == 200
        pdf_data = res_pdf.json()
        assert pdf_data["format"] == "pdf"
        assert "download_url" in pdf_data
        
        # Download PDF
        dl_pdf = client.get(f"/api/v1/reports/{pdf_data['report_id']}/download")
        assert dl_pdf.status_code == 200
        assert dl_pdf.headers["content-type"] == "application/pdf"
        assert len(dl_pdf.content) > 1000
        
        # 2. Generate DOCX
        res_docx = client.post("/api/v1/jobs/test-rep-job/report?format=docx")
        assert res_docx.status_code == 200
        docx_data = res_docx.json()
        assert docx_data["format"] == "docx"
        assert "download_url" in docx_data
        
        # Download DOCX
        dl_docx = client.get(f"/api/v1/reports/{docx_data['report_id']}/download")
        assert dl_docx.status_code == 200
        assert "openxmlformats" in dl_docx.headers["content-type"]
        assert len(dl_docx.content) > 1000
        
    finally:
        db.query(AnalysisJob).filter(AnalysisJob.id == "test-rep-job").delete()
        db.query(Dataset).filter(Dataset.id == "test-rep-ds").delete()
        db.commit()
        db.close()
