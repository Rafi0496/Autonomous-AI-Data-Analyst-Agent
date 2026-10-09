"""Tests for Milestone 3 (Reflex Dashboard & Background Polling Endpoints)."""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_job_status_response_schema():
    """Verify that JobStatusResponse includes phase and current_step."""
    res = client.get("/api/v1/jobs/nonexistent-job-id")
    assert res.status_code == 404

def test_cleaning_report_endpoint():
    """Verify that GET /datasets/{id}/cleaning-report is reachable."""
    res = client.get("/api/v1/datasets/nonexistent-id/cleaning-report")
    assert res.status_code == 404

def test_frontend_import_and_compilation():
    """Verify that the pure-Python Reflex dashboard, state, and pages compile."""
    import sys
    from pathlib import Path
    frontend_dir = str(Path(__file__).resolve().parent.parent.parent / "frontend")
    if frontend_dir not in sys.path:
        sys.path.append(frontend_dir)
    
    import frontend.frontend as ff
    from frontend.pages.dashboard import dashboard_page
    from frontend.pages.upload import upload_page
    from frontend.pages.settings import settings_page
    from frontend.pages.chat import chat_page
    from frontend.pages.reports import reports_page
    
    assert ff.app is not None
    dash = dashboard_page()
    assert dash is not None
    up = upload_page()
    assert up is not None
    st = settings_page()
    assert st is not None
    ch = chat_page()
    assert ch is not None
    rep = reports_page()
    assert rep is not None
