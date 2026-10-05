"""Celery tasks for executing autonomous analysis jobs asynchronously."""
import logging
from typing import Any, Dict, Optional
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.core.celery_app import celery_app
from backend.app.core.database import SessionLocal
from backend.app.models.job import AnalysisJob

logger = logging.getLogger(__name__)

try:
    from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
except ImportError:
    class SoftTimeLimitExceeded(Exception):
        pass
    class TimeLimitExceeded(Exception):
        pass

def mark_job_failed(job_id: str, error_message: str) -> None:
    """Helper to safely record failure status and message on an AnalysisJob."""
    db = SessionLocal()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.current_step_name = "failed"
            results = job.get_results() or {}
            results["error"] = error_message
            job.set_results(results)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to record failure status for job {job_id}: {str(e)}")
    finally:
        db.close()

def execute_job_synchronously(
    job_id: str,
    dataset_id: str,
    goal: Optional[str] = None,
    max_steps: int = 5,
    token_budget: int = 15000
) -> Dict[str, Any]:
    """Helper used both by Celery workers and FastAPI BackgroundTasks fallback."""
    def progress_callback(step_name: str, step_index: int, phase: str = "execution"):
        db = SessionLocal()
        try:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job:
                job.current_step_name = step_name
                job.current_step = step_index
                job.total_steps = max(job.total_steps or 0, step_index)
                job.phase = phase
                db.commit()
        finally:
            db.close()

    try:
        orchestrator = PlanActReflectOrchestrator(
            max_steps=max_steps,
            token_budget=token_budget,
            progress_callback=progress_callback
        )
        return orchestrator.run_analysis(dataset_id=dataset_id, goal=goal, job_id=job_id)
    except Exception as e:
        logger.exception(f"Job {job_id} encountered execution error: {str(e)}")
        mark_job_failed(job_id, "Analysis job execution failed.")
        raise

@celery_app.task(bind=True, name="run_analysis_job", time_limit=300, soft_time_limit=270)
def run_analysis_task(
    self,
    job_id: str,
    dataset_id: str,
    goal: Optional[str] = None,
    max_steps: int = 5,
    token_budget: int = 15000
) -> Dict[str, Any]:
    """Celery worker task executing the Plan-Act-Reflect analysis loop with timeout and error handling."""
    try:
        return execute_job_synchronously(
            job_id=job_id,
            dataset_id=dataset_id,
            goal=goal,
            max_steps=max_steps,
            token_budget=token_budget
        )
    except (SoftTimeLimitExceeded, TimeLimitExceeded):
        logger.error(f"Job {job_id} exceeded maximum execution time (stuck-job timeout).")
        mark_job_failed(job_id, "Task exceeded maximum allowable execution time (stuck-job timeout).")
        return {"status": "failed", "error": "Task execution timed out."}
    except Exception as e:
        logger.exception(f"Job {job_id} failed in celery worker: {str(e)}")
        mark_job_failed(job_id, "Analysis job execution failed.")
        return {"status": "failed", "error": "Analysis job execution failed."}

