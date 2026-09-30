"""API endpoints for asynchronous analysis jobs, real-time status polling, and run logs."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.dataset import Dataset
from backend.app.models.job import AnalysisJob
from backend.app.tasks.analysis_tasks import execute_job_synchronously, run_analysis_task

router = APIRouter()

class CreateJobRequest(BaseModel):
    dataset_id: str
    goal: Optional[str] = None
    max_steps: int = Field(default=5, ge=1, le=20)
    token_budget: int = Field(default=15000, ge=1000, le=100000)

class JobStatusResponse(BaseModel):
    job_id: str
    dataset_id: str
    status: str
    phase: str = "queued"
    current_step: int = 0
    current_step_name: str
    total_steps: int
    step_limit: int
    tokens_used: int
    token_budget: int
    execution_time_seconds: int
    results: Optional[Dict[str, Any]] = None
    verification: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str

@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_202_ACCEPTED)
def submit_analysis_job(
    req: CreateJobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Submit an autonomous analysis job.
    Dispatches via Celery worker if available; falls back to BackgroundTasks if broker is unreachable.
    """
    # 1. Verify dataset exists
    ds = db.query(Dataset).filter(Dataset.id == req.dataset_id).first()
    if not ds:
        # Also check if it's a sample dataset
        from backend.app.services.data_loader import get_dataset_dataframe
        try:
            get_dataset_dataframe(req.dataset_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset '{req.dataset_id}' not found."
            )

    # 2. Create Job in DB
    job = AnalysisJob(
        dataset_id=req.dataset_id,
        goal=req.goal,
        status="running",
        current_step_name="queued",
        step_limit=req.max_steps,
        token_budget=req.token_budget
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 3. Dispatch to Celery or BackgroundTasks
    dispatched_via = "background_tasks"
    use_celery = False
    try:
        import redis
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url, socket_timeout=0.3, socket_connect_timeout=0.3)
        use_celery = bool(r.ping())
    except Exception:
        use_celery = False

    if use_celery:
        try:
            run_analysis_task.delay(
                job_id=job.id,
                dataset_id=req.dataset_id,
                goal=req.goal,
                max_steps=req.max_steps,
                token_budget=req.token_budget
            )
            dispatched_via = "celery"
        except Exception:
            use_celery = False

    if not use_celery:
        background_tasks.add_task(
            execute_job_synchronously,
            job_id=job.id,
            dataset_id=req.dataset_id,
            goal=req.goal,
            max_steps=req.max_steps,
            token_budget=req.token_budget
        )

    return {
        "job_id": job.id,
        "dataset_id": job.dataset_id,
        "status": job.status,
        "current_step_name": job.current_step_name,
        "dispatched_via": dispatched_via,
        "message": f"Autonomous analysis job {job.id} dispatched successfully."
    }

@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Retrieve current execution status and live progress for an analysis job."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job '{job_id}' not found."
        )

    return JobStatusResponse(
        job_id=job.id,
        dataset_id=job.dataset_id,
        status=job.status,
        phase=job.phase or "queued",
        current_step=job.current_step or 0,
        current_step_name=job.current_step_name,
        total_steps=job.total_steps or 0,
        step_limit=job.step_limit or 5,
        tokens_used=job.tokens_used or 0,
        token_budget=job.token_budget or 15000,
        execution_time_seconds=job.execution_time_seconds or 0,
        results=job.get_results(),
        verification=job.get_verification(),
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat()
    )

@router.get("/{job_id}/logs")
def get_job_run_log(job_id: str, db: Session = Depends(get_db)):
    """Retrieve ordered explainability run log for an analysis job."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job '{job_id}' not found."
        )

    return {
        "job_id": job.id,
        "status": job.status,
        "total_steps": job.total_steps,
        "run_log": job.get_run_log()
    }

@router.get("/{job_id}/insights")
def get_job_insights(job_id: str, db: Session = Depends(get_db)):
    """Retrieve ranked insights for an analysis job."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job '{job_id}' not found."
        )

    insights = job.get_insights()
    return {
        "job_id": job.id,
        "status": job.status,
        "total_insights": len(insights),
        "insights": insights
    }

@router.post("/{job_id}/report")
def create_job_report(
    job_id: str,
    format: str = Query("pdf", pattern="^(pdf|docx)$", description="Report format: pdf or docx"),
    db: Session = Depends(get_db)
):
    """Generate and export a publication-ready PDF or Word document for an analysis job."""
    from backend.app.api.v1.endpoints.reports import generate_report_for_job
    return generate_report_for_job(job_id=job_id, format=format, db=db)
