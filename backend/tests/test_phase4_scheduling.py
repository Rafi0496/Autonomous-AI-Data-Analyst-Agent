"""Tests for Phase 4 Scheduled/Recurring Analysis (Automation)."""
from datetime import datetime, timedelta
import pandas as pd
from fastapi.testclient import TestClient
from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.models.dataset import Dataset
from backend.app.models.schedule import AnalysisSchedule
from backend.app.tasks.schedule_tasks import check_and_run_schedules

client = TestClient(app)

def test_scheduling_lifecycle_and_periodic_runner(tmp_path):
    # 1. Setup sample dataset in DB
    db = SessionLocal()
    csv_file = tmp_path / "scheduled_data.csv"
    pd.DataFrame({"Category": ["A", "B"], "Val": [10, 20]}).to_csv(csv_file, index=False)
    
    ds = Dataset(
        filename="scheduled_data.csv",
        file_type="csv",
        file_path=str(csv_file),
        file_size_bytes=100,
        row_count=2,
        column_count=2
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    dataset_id = ds.id
    db.close()

    # 2. Create Schedule
    create_res = client.post("/api/v1/schedules", json={
        "dataset_id": dataset_id,
        "frequency": "weekly",
        "goal": "Track weekly KPI trends"
    })
    assert create_res.status_code == 201
    s_data = create_res.json()
    schedule_id = s_data["id"]
    assert s_data["frequency"] == "weekly"
    assert s_data["is_active"] is True
    assert s_data["goal"] == "Track weekly KPI trends"

    # 3. List Schedules
    list_res = client.get("/api/v1/schedules")
    assert list_res.status_code == 200
    schedules = list_res.json()
    assert any(s["id"] == schedule_id for s in schedules)

    # 4. Trigger schedule manually
    trigger_res = client.post(f"/api/v1/schedules/{schedule_id}/trigger")
    assert trigger_res.status_code == 200
    t_data = trigger_res.json()
    assert t_data["last_run_at"] is not None
    assert t_data["last_job_id"] is not None
    assert t_data["next_run_at"] is not None

    # 5. Test Celery periodic task check_and_run_schedules
    db = SessionLocal()
    # Backdate next_run_at to past so it is due
    sch = db.query(AnalysisSchedule).filter(AnalysisSchedule.id == schedule_id).first()
    sch.next_run_at = datetime.utcnow() - timedelta(minutes=5)
    db.commit()
    db.close()

    res = check_and_run_schedules()
    assert "triggered_count" in res
    assert res["triggered_count"] >= 1

    # 6. Delete Schedule
    del_res = client.delete(f"/api/v1/schedules/{schedule_id}")
    assert del_res.status_code == 204
    # Confirm deletion
    get_all = client.get("/api/v1/schedules").json()
    assert not any(s["id"] == schedule_id for s in get_all)
