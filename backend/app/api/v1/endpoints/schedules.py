"""Endpoints for Scheduled and Recurring Analysis (Phase 4 Automation)."""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from backend.app.api.deps import get_optional_current_user
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.dataset import Dataset
from backend.app.models.job import AnalysisJob
from backend.app.models.schedule import AnalysisSchedule
from backend.app.models.user import User
from backend.app.tasks.analysis_tasks import execute_job_synchronously

router = APIRouter()

def compute_next_run(frequency: str, base_time: Optional[datetime] = None) -> datetime:
    base = base_time or datetime.utcnow()
    freq = frequency.lower()
    if freq == "hourly":
        return base + timedelta(hours=1)
    elif freq == "weekly":
        return base + timedelta(days=7)
    else:  # default daily
        return base + timedelta(days=1)

class ScheduleCreateRequest(BaseModel):
    dataset_id: str
    frequency: str = "daily"  # "hourly", "daily", "weekly"
    goal: Optional[str] = None

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("hourly", "daily", "weekly"):
            raise ValueError("Frequency must be 'hourly', 'daily', or 'weekly'")
        return v

class ScheduleResponse(BaseModel):
    id: str
    dataset_id: str
    user_id: Optional[str]
    frequency: str
    goal: Optional[str]
    is_active: bool
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    last_job_id: Optional[str]
    created_at: datetime

@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    req: ScheduleCreateRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Create a recurring analysis schedule for a dataset."""
    if not settings.ALLOW_ANONYMOUS and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )

    dataset = db.query(Dataset).filter(Dataset.id == req.dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {req.dataset_id} not found."
        )
    if dataset.user_id and (not current_user or dataset.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {req.dataset_id} not found."
        )

    next_run = compute_next_run(req.frequency)
    schedule = AnalysisSchedule(
        dataset_id=req.dataset_id,
        user_id=current_user.id if current_user else None,
        frequency=req.frequency,
        goal=req.goal,
        is_active=True,
        next_run_at=next_run
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    return ScheduleResponse(
        id=schedule.id,
        dataset_id=schedule.dataset_id,
        user_id=schedule.user_id,
        frequency=schedule.frequency,
        goal=schedule.goal,
        is_active=schedule.is_active,
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        last_job_id=schedule.last_job_id,
        created_at=schedule.created_at
    )

@router.get("", response_model=List[ScheduleResponse])
def list_schedules(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """List recurring schedules."""
    if not settings.ALLOW_ANONYMOUS and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )

    query = db.query(AnalysisSchedule)
    if current_user:
        query = query.filter(
            (AnalysisSchedule.user_id == current_user.id) | (AnalysisSchedule.user_id == None)
        )
    schedules = query.order_by(AnalysisSchedule.created_at.desc()).all()
    return [
        ScheduleResponse(
            id=s.id,
            dataset_id=s.dataset_id,
            user_id=s.user_id,
            frequency=s.frequency,
            goal=s.goal,
            is_active=s.is_active,
            last_run_at=s.last_run_at,
            next_run_at=s.next_run_at,
            last_job_id=s.last_job_id,
            created_at=s.created_at
        )
        for s in schedules
    ]

@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Delete a recurring schedule."""
    if not settings.ALLOW_ANONYMOUS and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )

    schedule = db.query(AnalysisSchedule).filter(AnalysisSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found."
        )
    if schedule.user_id and (not current_user or schedule.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found."
        )
    db.delete(schedule)
    db.commit()

@router.post("/{schedule_id}/trigger", response_model=ScheduleResponse)
def trigger_schedule(
    schedule_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Manually trigger immediate execution of a scheduled recurring analysis."""
    if not settings.ALLOW_ANONYMOUS and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )

    schedule = db.query(AnalysisSchedule).filter(AnalysisSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found."
        )
    if schedule.user_id and (not current_user or schedule.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found."
        )


    # Create AnalysisJob
    job = AnalysisJob(
        dataset_id=schedule.dataset_id,
        user_id=schedule.user_id or (current_user.id if current_user else None),
        status="pending",
        current_step_name="queued_via_schedule",
        goal=schedule.goal
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Queue background task
    background_tasks.add_task(
        execute_job_synchronously,
        job_id=job.id,
        dataset_id=schedule.dataset_id,
        goal=schedule.goal
    )

    now = datetime.utcnow()
    schedule.last_run_at = now
    schedule.last_job_id = job.id
    schedule.next_run_at = compute_next_run(schedule.frequency, now)
    db.commit()
    db.refresh(schedule)

    return ScheduleResponse(
        id=schedule.id,
        dataset_id=schedule.dataset_id,
        user_id=schedule.user_id,
        frequency=schedule.frequency,
        goal=schedule.goal,
        is_active=schedule.is_active,
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        last_job_id=schedule.last_job_id,
        created_at=schedule.created_at
    )
