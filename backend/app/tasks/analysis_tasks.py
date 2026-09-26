"""Celery tasks for executing autonomous analysis jobs asynchronously."""
from typing import Any, Dict, Optional
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.core.celery_app import celery_app
from backend.app.core.database import SessionLocal
from backend.app.models.job import AnalysisJob

def execute_job_synchronously(
    job_id: str,
    dataset_id: str,
    goal: Optional[str] = None,
    max_steps: int = 5,
    token_budget: int = 15000
) -> Dict[str, Any]:
    """Helper used both by Celery workers and FastAPI BackgroundTasks fallback."""
    def progress_callback(step_name: str, step_index: int):
        db = SessionLocal()
        try:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job:
                job.current_step_name = step_name
                job.total_steps = step_index
                db.commit()
        finally:
            db.close()

    orchestrator = PlanActReflectOrchestrator(
        max_steps=max_steps,
        token_budget=token_budget,
        progress_callback=progress_callback
    )
    return orchestrator.run_analysis(dataset_id=dataset_id, goal=goal, job_id=job_id)

@celery_app.task(bind=True, name="run_analysis_job")
def run_analysis_task(
    self,
    job_id: str,
    dataset_id: str,
    goal: Optional[str] = None,
    max_steps: int = 5,
    token_budget: int = 15000
) -> Dict[str, Any]:
    """Celery worker task executing the Plan-Act-Reflect analysis loop."""
    return execute_job_synchronously(
        job_id=job_id,
        dataset_id=dataset_id,
        goal=goal,
        max_steps=max_steps,
        token_budget=token_budget
    )
