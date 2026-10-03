from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.app.api.deps import get_optional_current_user
from backend.app.core.database import get_db
from backend.app.models.dataset import Dataset
from backend.app.models.job import AnalysisJob
from backend.app.models.user import User
from backend.app.tasks.analysis_tasks import execute_job_synchronously, run_analysis_task

router = APIRouter()

def check_job_access(job: AnalysisJob, current_user: Optional[User]):
    """Verify that current_user has access to private job, allowing shared public/demo jobs."""
    if job.user_id and (not current_user or job.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this analysis job."
        )

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
    execution_time_seconds: float = 0.0
    results: Optional[Dict[str, Any]] = None
    verification: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str

@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_202_ACCEPTED)
def submit_analysis_job(
    req: CreateJobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Submit an autonomous analysis job.
    Dispatches via Celery worker if available; falls back to BackgroundTasks if broker is unreachable.
    """
    # 1. Verify dataset exists and check permissions
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
    elif ds.user_id and (not current_user or ds.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this dataset."
        )

    # 2. Create Job in DB
    job = AnalysisJob(
        dataset_id=req.dataset_id,
        user_id=current_user.id if current_user else None,
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

@router.get("", response_model=List[JobStatusResponse])
def list_analysis_jobs(
    limit: int = 10,
    dataset_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Retrieve list of recent analysis jobs scoped to user or public demo jobs."""
    query = db.query(AnalysisJob)
    if current_user:
        query = query.filter((AnalysisJob.user_id == current_user.id) | (AnalysisJob.user_id == None))
    else:
        query = query.filter(AnalysisJob.user_id == None)
        
    if dataset_id:
        query = query.filter(AnalysisJob.dataset_id == dataset_id)
    jobs = query.order_by(AnalysisJob.created_at.desc()).limit(limit).all()
    return [
        JobStatusResponse(
            job_id=j.id,
            dataset_id=j.dataset_id,
            status=j.status,
            phase=j.phase or "queued",
            current_step=j.current_step or 0,
            current_step_name=j.current_step_name,
            total_steps=j.total_steps or 0,
            step_limit=j.step_limit or 5,
            tokens_used=j.tokens_used or 0,
            token_budget=j.token_budget or 15000,
            execution_time_seconds=j.execution_time_seconds or 0,
            results=j.get_results(),
            verification=j.get_verification(),
            created_at=j.created_at.isoformat(),
            updated_at=j.updated_at.isoformat()
        )
        for j in jobs
    ]

@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Retrieve current execution status and live progress for an analysis job."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job '{job_id}' not found."
        )
    check_job_access(job, current_user)

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
def get_job_run_log(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Retrieve ordered explainability run log for an analysis job."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job '{job_id}' not found."
        )
    check_job_access(job, current_user)

    return {
        "job_id": job.id,
        "status": job.status,
        "total_steps": job.total_steps,
        "run_log": job.get_run_log()
    }

@router.get("/{job_id}/insights")
def get_job_insights(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Retrieve ranked insights for an analysis job."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job '{job_id}' not found."
        )
    check_job_access(job, current_user)

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
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Generate and export a publication-ready PDF or Word document for an analysis job."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job '{job_id}' not found."
        )
    check_job_access(job, current_user)

    from backend.app.api.v1.endpoints.reports import generate_report_for_job
    return generate_report_for_job(job_id=job_id, format=format, db=db)
