"""Celery periodic tasks for scheduled and recurring dataset analysis."""
from datetime import datetime
from typing import Dict, List
from backend.app.core.celery_app import celery_app
from backend.app.core.database import SessionLocal
from backend.app.models.job import AnalysisJob
from backend.app.models.schedule import AnalysisSchedule
from backend.app.tasks.analysis_tasks import execute_job_synchronously

@celery_app.task(name="check_and_run_schedules")
def check_and_run_schedules() -> Dict[str, int]:
    """Scan active schedules and execute any due for recurring analysis."""
    from backend.app.api.v1.endpoints.schedules import compute_next_run
    
    db = SessionLocal()
    triggered = 0
    try:
        now = datetime.utcnow()
        due_schedules: List[AnalysisSchedule] = db.query(AnalysisSchedule).filter(
            AnalysisSchedule.is_active == True,
            (AnalysisSchedule.next_run_at <= now) | (AnalysisSchedule.next_run_at == None)
        ).all()

        for schedule in due_schedules:
            job = AnalysisJob(
                dataset_id=schedule.dataset_id,
                user_id=schedule.user_id,
                status="pending",
                current_step_name="scheduled_execution",
                goal=schedule.goal
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            # Execute
            try:
                execute_job_synchronously(
                    job_id=job.id,
                    dataset_id=schedule.dataset_id,
                    goal=schedule.goal
                )
            except Exception:
                pass

            schedule.last_run_at = now
            schedule.last_job_id = job.id
            schedule.next_run_at = compute_next_run(schedule.frequency, now)
            db.commit()
            triggered += 1

        return {"triggered_count": triggered}
    finally:
        db.close()
