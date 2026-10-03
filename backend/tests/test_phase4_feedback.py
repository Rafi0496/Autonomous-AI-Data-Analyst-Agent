"""Tests for Phase 4 Insight Feedback loop (Plan §8.6)."""
from fastapi.testclient import TestClient
from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.models.job import AnalysisJob

client = TestClient(app)

def test_insight_feedback_submission_and_aggregation():
    # 1. Create a dummy job
    db = SessionLocal()
    job = AnalysisJob(
        dataset_id="test_ds_feedback",
        status="completed",
        current_step_name="completed"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    db.close()

    insight_id = "insight-correlation-Sales-Profit"

    # 2. Submit helpful feedback
    res1 = client.post(
        f"/api/v1/jobs/{job_id}/insights/{insight_id}/feedback",
        json={"rating": "helpful", "comment": "Very useful correlation finding for sales team."}
    )
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["rating"] == "helpful"
    assert data1["comment"] == "Very useful correlation finding for sales team."
    assert data1["insight_id"] == insight_id

    # 3. Submit not_relevant feedback
    res2 = client.post(
        f"/api/v1/jobs/{job_id}/insights/{insight_id}/feedback",
        json={"rating": "not_relevant", "comment": "Already known by the department."}
    )
    assert res2.status_code == 201
    assert res2.json()["rating"] == "not_relevant"

    # 4. Reject invalid rating
    bad_res = client.post(
        f"/api/v1/jobs/{job_id}/insights/{insight_id}/feedback",
        json={"rating": "neutral"}
    )
    assert bad_res.status_code == 422

    # 5. Fetch feedback summary
    summary_res = client.get(f"/api/v1/jobs/{job_id}/insights/{insight_id}/feedback")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["insight_id"] == insight_id
    assert summary["total_feedbacks"] == 2
    assert summary["helpful_count"] == 1
    assert summary["not_relevant_count"] == 1
    assert len(summary["feedbacks"]) == 2
