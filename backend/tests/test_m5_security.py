"""Tests for Milestone 5: Security, Authentication, and Multi-Tenant Isolation."""
import io
import pytest
from fastapi.testclient import TestClient
from backend.app.core.config import settings
from backend.app.core.security import hash_password, verify_password
from backend.app.main import app
from backend.app.models.dataset import Dataset
from backend.app.models.job import AnalysisJob
from backend.app.models.schedule import AnalysisSchedule
from backend.app.models.user import User

@pytest.fixture
def client():
    return TestClient(app)

def test_security_settings_values():
    """Verify security settings meet or exceed M5 specification."""
    assert settings.ALLOW_ANONYMOUS is False, "ALLOW_ANONYMOUS must be False by default"
    assert settings.PBKDF2_ITERATIONS >= 600_000, "PBKDF2 iterations must be >= 600,000"
    assert settings.MIN_PASSWORD_LENGTH >= 8, "Minimum password length must be >= 8"
    assert settings.ALLOWED_EXTENSIONS == [".csv"], "Allowed upload extensions must be CSV only"
    assert settings.MAX_ROW_COUNT_LIMIT == 100_000, "Max row count limit must be 100,000"

def test_pbkdf2_iterations_and_hmac_verification():
    """Verify password hashing uses >= 600,000 iterations and verifies correctly."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)
    parts = hashed.split("$")
    assert len(parts) == 3, f"Expected 3 parts in hash (salt$iter$key), got {len(parts)}"
    iterations = int(parts[1])
    assert iterations >= 600_000, f"Expected iterations >= 600,000, got {iterations}"
    
    # Verify correct password matches
    assert verify_password(password, hashed) is True
    # Verify incorrect password fails
    assert verify_password("WrongPassword!", hashed) is False
    
    # Verify backward compatibility with legacy 2-part hash (100k iterations)
    import hashlib
    import os
    salt = os.urandom(16)
    legacy_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    legacy_hash = f"{salt.hex()}${legacy_key.hex()}"
    assert verify_password(password, legacy_hash) is True

def test_password_length_validation(client):
    """Verify registration rejects passwords shorter than MIN_PASSWORD_LENGTH."""
    res = client.post("/api/v1/auth/register", json={
        "email": "short_pw_user@example.com",
        "password": "short"  # 5 chars < 8
    })
    assert res.status_code == 400
    assert "at least 8 characters" in res.json().get("detail", "")

def test_login_rate_limiting(client):
    """Verify basic login rate limit trips after rapid repeated attempts."""
    test_email = "ratelimit_test@example.com"
    for _ in range(10):
        client.post("/api/v1/auth/login", json={
            "email": test_email,
            "password": "SomePassword123!"
        })
    # 11th attempt should trigger 429
    res = client.post("/api/v1/auth/login", json={
        "email": test_email,
        "password": "SomePassword123!"
    })
    assert res.status_code == 429
    assert "Too many login attempts" in res.json().get("detail", "")

def test_upload_validation_csv_only(client):
    """Verify upload rejects non-CSV files and directory-traversal filenames."""
    # Register and login a user
    email = "upload_tester@example.com"
    reg = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Non-csv rejected
    xlsx_file = ("test.xlsx", io.BytesIO(b"fake xlsx data"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    res = client.post("/api/v1/upload", files={"file": xlsx_file}, headers=headers)
    assert res.status_code == 400
    assert "Unsupported file format" in res.json().get("detail", "")

    # 2. Directory traversal filename sanitized
    csv_content = b"a,b,c\n1,2,3\n4,5,6\n"
    traversal_file = ("../../malicious.csv", io.BytesIO(csv_content), "text/csv")
    res = client.post("/api/v1/upload", files={"file": traversal_file}, headers=headers)
    assert res.status_code == 201
    uploaded_filename = res.json()["filename"]
    assert ".." not in uploaded_filename
    assert "/" not in uploaded_filename
    assert "\\" not in uploaded_filename

def test_production_jwt_secret_validation():
    """Verify production startup fails if DEFAULT_DEV_SECRET is used outside dev."""
    from backend.app.core.config import Settings
    with pytest.raises(ValueError, match="Production configuration error"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="autonomous-data-analyst-super-secret-key-2026"
        )


def _setup_user_and_resources(client):
    """Register User A and User B, create User A's private resources, return tokens and IDs."""
    import uuid
    uid = uuid.uuid4().hex[:6]
    # Register User A
    res_a = client.post("/api/v1/auth/register", json={
        "email": f"usera_{uid}@example.com",
        "password": "UserAPassword123!"
    })
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register User B
    res_b = client.post("/api/v1/auth/register", json={
        "email": f"userb_{uid}@example.com",
        "password": "UserBPassword123!"
    })
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A uploads a dataset
    csv_bytes = b"department,salary,age\nSales,50000,30\nEngineering,90000,35\nSales,55000,32\n"
    up_res = client.post(
        "/api/v1/upload",
        files={"file": (f"test_data_{uid}.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers=headers_a
    )
    dataset_id = up_res.json()["dataset_id"]

    # User A cleans dataset
    client.post(f"/api/v1/datasets/{dataset_id}/clean", headers=headers_a)

    # User A creates a job
    job_res = client.post(
        "/api/v1/jobs",
        json={"dataset_id": dataset_id, "goal": "Analyze salary distribution"},
        headers=headers_a
    )
    job_id = job_res.json()["job_id"]

    # User A creates a schedule
    sched_res = client.post(
        "/api/v1/schedules",
        json={"dataset_id": dataset_id, "frequency": "daily", "goal": "Scheduled salary check"},
        headers=headers_a
    )
    schedule_id = sched_res.json()["id"]

    # User A creates a report
    rep_res = client.post(
        f"/api/v1/jobs/{job_id}/report?format=pdf",
        headers=headers_a
    )
    report_id = rep_res.json()["report_id"]

    return {
        "headers_a": headers_a,
        "headers_b": headers_b,
        "dataset_id": dataset_id,
        "job_id": job_id,
        "schedule_id": schedule_id,
        "report_id": report_id
    }


# All routes that take dataset_id, job_id, report_id, chat/job reference, schedule_id or insight_id
ROUTES_TO_TEST = [
    ("GET", "/api/v1/datasets/{dataset_id}", None),
    ("POST", "/api/v1/datasets/{dataset_id}/clean", None),
    ("POST", "/api/v1/datasets/{dataset_id}/profile", None),
    ("GET", "/api/v1/datasets/{dataset_id}/profile", None),
    ("GET", "/api/v1/datasets/{dataset_id}/preview", None),
    ("GET", "/api/v1/datasets/{dataset_id}/cleaning-report", None),
    ("POST", "/api/v1/jobs", lambda r: {"dataset_id": r["dataset_id"], "goal": "Unauthorized Job"}),
    ("GET", "/api/v1/jobs/{job_id}", None),
    ("GET", "/api/v1/jobs/{job_id}/logs", None),
    ("GET", "/api/v1/jobs/{job_id}/insights", None),
    ("POST", "/api/v1/jobs/{job_id}/report?format=pdf", None),
    ("POST", "/api/v1/chat", lambda r: {"job_id": r["job_id"], "question": "What is the salary?"}),
    ("GET", "/api/v1/reports/{report_id}/download", None),
    ("POST", "/api/v1/jobs/{job_id}/insights/insight-123/feedback", lambda r: {"rating": "helpful"}),
    ("GET", "/api/v1/jobs/{job_id}/insights/insight-123/feedback", None),
    ("POST", "/api/v1/schedules", lambda r: {"dataset_id": r["dataset_id"], "frequency": "daily"}),
    ("DELETE", "/api/v1/schedules/{schedule_id}", None),
    ("POST", "/api/v1/schedules/{schedule_id}/trigger", None),
]

@pytest.mark.parametrize("method,path_template,body_func", ROUTES_TO_TEST)
def test_ownership_and_anonymous_rejection(client, method, path_template, body_func):
    """
    Parametrized test registering User A and User B:
    - User B gets 401/403/404 for User A's resources on EVERY route.
    - Anonymous (no token) gets 401 on EVERY route.
    """
    resources = _setup_user_and_resources(client)
    
    # Resolve path
    path = path_template.format(
        dataset_id=resources["dataset_id"],
        job_id=resources["job_id"],
        schedule_id=resources["schedule_id"],
        report_id=resources["report_id"]
    )
    body = body_func(resources) if body_func else None

    # 1. Anonymous test: no token -> must return 401 Unauthorized
    if method == "GET":
        res_anon = client.get(path)
    elif method == "POST":
        res_anon = client.post(path, json=body) if body else client.post(path)
    elif method == "DELETE":
        res_anon = client.delete(path)
    else:
        raise ValueError(f"Unsupported method {method}")
        
    assert res_anon.status_code == 401, (
        f"Anonymous request to {method} {path} expected 401, got {res_anon.status_code} ({res_anon.text})"
    )

    # 2. User B test: User B token on User A's resource -> must return 403 Forbidden (or 404)
    if method == "GET":
        res_b = client.get(path, headers=resources["headers_b"])
    elif method == "POST":
        res_b = client.post(path, json=body, headers=resources["headers_b"]) if body else client.post(path, headers=resources["headers_b"])
    elif method == "DELETE":
        res_b = client.delete(path, headers=resources["headers_b"])
    else:
        raise ValueError(f"Unsupported method {method}")

    assert res_b.status_code in (403, 404), (
        f"User B request to {method} {path} expected 403/404, got {res_b.status_code} ({res_b.text})"
    )
