"""FastAPI endpoints for Report Generation and Downloads (Milestone 5)."""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.dataset import Dataset
from backend.app.models.job import AnalysisJob
from backend.app.services.report_docx import generate_docx_report
from backend.app.services.report_pdf import generate_pdf_report

router = APIRouter()
REPORTS_DIR = Path("data/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

class ReportMetadata(BaseModel):
    report_id: str
    job_id: str
    dataset_name: str
    format: str
    filename: str
    created_at: str
    download_url: str

class GenerateReportResponse(BaseModel):
    report_id: str
    job_id: str
    format: str
    filename: str
    download_url: str

def generate_report_for_job(
    job_id: str,
    format: str,
    db: Session
) -> GenerateReportResponse:
    """Generate PDF or DOCX report for a job and persist file in data/reports/."""
    fmt = format.lower().strip()
    if fmt not in ("pdf", "docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{format}'. Must be 'pdf' or 'docx'."
        )
        
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job '{job_id}' not found."
        )
        
    ds = db.query(Dataset).filter(Dataset.id == job.dataset_id).first()
    dataset_name = ds.filename if ds else "Dataset"
    dataset_stem = Path(dataset_name).stem
    
    profile_data = (ds.get_profile() if ds and hasattr(ds, "get_profile") else None) or {}
    cleaning_data = (ds.get_cleaning_summary() if ds and hasattr(ds, "get_cleaning_summary") else None) or {}
    
    report_id = str(uuid.uuid4())[:12]
    filename = f"{dataset_stem}_report.{fmt}"
    file_path = REPORTS_DIR / f"{report_id}.{fmt}"
    meta_path = REPORTS_DIR / f"{report_id}.json"
    
    provider = os.getenv("LLM_PROVIDER", "gemini").capitalize()
    model_name = "gemini-2.5-flash" if provider.lower() == "gemini" else "claude-3-7-sonnet"
    
    job_dict = {
        "results": job.get_results() or {},
        "run_log": job.get_run_log() or [],
        "verification": job.get_verification() or {}
    }
    
    if fmt == "pdf":
        generate_pdf_report(
            output_path=file_path,
            dataset_name=dataset_name,
            job_data=job_dict,
            profile_data=profile_data,
            cleaning_data=cleaning_data,
            provider=provider,
            model_name=model_name
        )
    else:
        generate_docx_report(
            output_path=file_path,
            dataset_name=dataset_name,
            job_data=job_dict,
            profile_data=profile_data,
            cleaning_data=cleaning_data,
            provider=provider,
            model_name=model_name
        )
        
    # Save metadata
    meta = {
        "report_id": report_id,
        "job_id": job_id,
        "dataset_name": dataset_name,
        "format": fmt,
        "filename": filename,
        "created_at": datetime.utcnow().isoformat(),
        "download_url": f"/api/v1/reports/{report_id}/download"
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    
    return GenerateReportResponse(
        report_id=report_id,
        job_id=job_id,
        format=fmt,
        filename=filename,
        download_url=f"/api/v1/reports/{report_id}/download"
    )

@router.get("", response_model=List[ReportMetadata])
@router.get("/", response_model=List[ReportMetadata])
def list_reports() -> List[ReportMetadata]:
    """List all previously generated reports."""
    reports = []
    for meta_file in sorted(REPORTS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
        try:
            data = json.loads(meta_file.read_text())
            reports.append(ReportMetadata(**data))
        except Exception:
            continue
    return reports

@router.get("/{report_id}/download")
def download_report(report_id: str):
    """Download a generated PDF or Word report."""
    pdf_p = REPORTS_DIR / f"{report_id}.pdf"
    docx_p = REPORTS_DIR / f"{report_id}.docx"
    meta_p = REPORTS_DIR / f"{report_id}.json"
    
    filename = f"report_{report_id}"
    if meta_p.exists():
        try:
            meta = json.loads(meta_p.read_text())
            filename = meta.get("filename", filename)
        except Exception:
            pass
            
    if pdf_p.exists():
        return FileResponse(
            path=str(pdf_p),
            media_type="application/pdf",
            filename=filename if filename.endswith(".pdf") else f"{filename}.pdf"
        )
    elif docx_p.exists():
        return FileResponse(
            path=str(docx_p),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=filename if filename.endswith(".docx") else f"{filename}.docx"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found."
        )
