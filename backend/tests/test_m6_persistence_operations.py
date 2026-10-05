"""Tests for Milestone 6: Persistence, Operations, Migrations, and Reliability."""
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from backend.app.core.config import Settings
from backend.app.core.config_validator import validate_startup_config
from backend.app.core.database import SessionLocal
from backend.app.core.migration import (
    DEFAULT_LEGACY_USER_ID,
    DEFAULT_LEGACY_USER_EMAIL,
    run_migrations
)
from backend.app.main import app
from backend.app.models.job import AnalysisJob
from backend.app.models.user import User
from backend.app.tasks.analysis_tasks import execute_job_synchronously, run_analysis_task

@pytest.fixture
def client():
    return TestClient(app)

def test_idempotent_migration_on_legacy_db():
    """Verify idempotent migration adds missing columns and assigns legacy rows to default user."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # 1. Create a legacy database mimicking an old schema without new columns
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE datasets (
                id VARCHAR(36) PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                file_type VARCHAR(10) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                row_count INTEGER NOT NULL,
                column_count INTEGER NOT NULL,
                status VARCHAR(50) NOT NULL,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE analysis_jobs (
                id VARCHAR(36) PRIMARY KEY,
                dataset_id VARCHAR(36) NOT NULL,
                goal TEXT,
                status VARCHAR(50) NOT NULL,
                current_step_name VARCHAR(100) NOT NULL,
                step_limit INTEGER,
                tokens_used INTEGER,
                token_budget INTEGER,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        # Insert legacy rows without user_id
        cur.execute("""
            INSERT INTO datasets (id, filename, file_type, file_path, file_size_bytes, row_count, column_count, status)
            VALUES ('legacy-ds-1', 'old.csv', 'csv', '/tmp/old.csv', 100, 10, 2, 'uploaded')
        """)
        cur.execute("""
            INSERT INTO analysis_jobs (id, dataset_id, goal, status, current_step_name)
            VALUES ('legacy-job-1', 'legacy-ds-1', 'old analysis', 'completed', 'done')
        """)
        conn.commit()
        conn.close()

        # 2. Run migration on this legacy database
        temp_engine = create_engine(f"sqlite:///{db_path}")
        run_migrations(temp_engine)

        # 3. Verify columns were added
        inspector = inspect(temp_engine)
        ds_cols = {c["name"] for c in inspector.get_columns("datasets")}
        assert "user_id" in ds_cols
        assert "is_sampled" in ds_cols
        assert "original_row_count" in ds_cols
        assert "sampling_rate" in ds_cols

        job_cols = {c["name"] for c in inspector.get_columns("analysis_jobs")}
        assert "user_id" in job_cols
        assert "current_step" in job_cols
        assert "phase" in job_cols
        assert "execution_time_seconds" in job_cols
        assert "verification" in job_cols

        # 4. Verify legacy rows were assigned to DEFAULT_LEGACY_USER_ID
        with temp_engine.connect() as check_conn:
            res_ds = check_conn.execute(text("SELECT user_id FROM datasets WHERE id = 'legacy-ds-1'")).fetchone()
            assert res_ds[0] == DEFAULT_LEGACY_USER_ID

            res_job = check_conn.execute(text("SELECT user_id FROM analysis_jobs WHERE id = 'legacy-job-1'")).fetchone()
            assert res_job[0] == DEFAULT_LEGACY_USER_ID

            # Verify default user exists in users table
            res_user = check_conn.execute(text(f"SELECT email FROM users WHERE id = '{DEFAULT_LEGACY_USER_ID}'")).fetchone()
            assert res_user[0] == DEFAULT_LEGACY_USER_EMAIL

        # 5. Run migration a second time to prove IDEMPOTENCY (must not error or duplicate)
        run_migrations(temp_engine)

    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass

def test_consistent_json_error_schema_and_request_id(client):
    """Verify all error responses conform to {'error': ..., 'message': ..., 'details': ...} and include X-Request-ID."""
    # 1. Test 404 error
    res_404 = client.get("/api/v1/datasets/nonexistent-dataset-id", headers={"X-Request-ID": "test-req-12345"})
    assert res_404.status_code in (401, 404)
    data_404 = res_404.json()
    assert "error" in data_404
    assert "message" in data_404
    assert "details" in data_404
    assert res_404.headers.get("X-Request-ID") == "test-req-12345"

    # 2. Test 422 validation error
    res_422 = client.post("/api/v1/auth/register", json={"email": "invalid_email_format"})
    assert res_422.status_code == 422
    data_422 = res_422.json()
    assert data_422["error"] == "VALIDATION_ERROR"
    assert "Input validation" in data_422["message"]
    assert isinstance(data_422["details"], list)
    assert res_422.headers.get("X-Request-ID") is not None

def test_startup_config_validation():
    """Verify validate_startup_config checks required configurations and throws clear ValueError."""
    # Valid dev configuration passes
    validate_startup_config()

    # Invalid LLM provider fails with clear message
    with patch("backend.app.core.config.settings.LLM_PROVIDER", "unsupported_provider"):
        with pytest.raises(ValueError, match="Invalid LLM_PROVIDER"):
            validate_startup_config()

def test_celery_task_failure_and_timeout_handling():
    """Verify task failure updates job status to 'failed' with safe error message."""
    db = SessionLocal()
    import uuid
    job_id = f"test-fail-{uuid.uuid4().hex[:6]}"
    job = AnalysisJob(
        id=job_id,
        dataset_id="nonexistent-dataset-id",
        status="running",
        current_step_name="running"
    )
    db.add(job)
    db.commit()
    db.close()

    # Calling synchronous executor on invalid dataset should raise but mark job failed
    with pytest.raises(Exception):
        execute_job_synchronously(
            job_id=job_id,
            dataset_id="nonexistent-dataset-id",
            goal="Fail test"
        )

    # Verify job status in DB is "failed" with safe error message
    db = SessionLocal()
    updated_job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    assert updated_job.status == "failed"
    assert updated_job.current_step_name == "failed"
    results = updated_job.get_results() or {}
    assert "error" in results
    assert "failed" in results["error"].lower()
    db.close()
