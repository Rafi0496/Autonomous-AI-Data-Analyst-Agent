"""Tests for Phase 4 JWT Authentication and Multi-User Data Isolation."""
import io
import uuid
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_user_registration_and_login():
    uid = uuid.uuid4().hex[:8]
    email = f"user_{uid}@example.com"
    # 1. Register User A
    reg_payload = {
        "email": email,
        "password": "Password123!",
        "full_name": "User Alpha"
    }
    res = client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 201, res.text
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == email
    assert data["user"]["full_name"] == "User Alpha"
    token_a = data["access_token"]

    # 2. Duplicate registration should fail
    dup_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"]

    # 3. Login with wrong password
    bad_login = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
    assert bad_login.status_code == 401

    # 4. Login with correct password
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # 5. Access /auth/me with Bearer token
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == email

    # 6. Access /auth/me without token fails with 401
    unauth_res = client.get("/api/v1/auth/me")
    assert unauth_res.status_code == 401

def test_multi_user_data_isolation():
    uid1 = uuid.uuid4().hex[:8]
    uid2 = uuid.uuid4().hex[:8]
    # Register User 1
    u1 = client.post("/api/v1/auth/register", json={
        "email": f"owner1_{uid1}@test.com", "password": "SecurePassword1"
    }).json()
    token1 = u1["access_token"]

    # Register User 2
    u2 = client.post("/api/v1/auth/register", json={
        "email": f"owner2_{uid2}@test.com", "password": "SecurePassword2"
    }).json()
    token2 = u2["access_token"]

    # User 1 uploads a dataset
    csv_content = b"Item,Price,Quantity\nWidgetA,10.5,3\nWidgetB,20.0,5\n"
    file_tuple = ("user1_data.csv", io.BytesIO(csv_content), "text/csv")
    upload_res = client.post(
        "/api/v1/upload",
        files={"file": file_tuple},
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert upload_res.status_code == 201
    dataset1_id = upload_res.json()["dataset_id"]

    # User 1 lists datasets -> sees dataset1
    ds1_list = client.get("/api/v1/datasets", headers={"Authorization": f"Bearer {token1}"}).json()
    assert any(d["id"] == dataset1_id for d in ds1_list)

    # User 2 lists datasets -> does NOT see dataset1
    ds2_list = client.get("/api/v1/datasets", headers={"Authorization": f"Bearer {token2}"}).json()
    assert not any(d["id"] == dataset1_id for d in ds2_list)

    # User 2 attempts to get User 1's dataset -> 403 Forbidden
    forbidden_get = client.get(f"/api/v1/datasets/{dataset1_id}", headers={"Authorization": f"Bearer {token2}"})
    assert forbidden_get.status_code == 403

    # User 1 can access dataset1 -> 200 OK
    allowed_get = client.get(f"/api/v1/datasets/{dataset1_id}", headers={"Authorization": f"Bearer {token1}"})
    assert allowed_get.status_code == 200
    assert allowed_get.json()["id"] == dataset1_id

    # User 1 launches an analysis job on dataset1
    job_res = client.post(
        "/api/v1/jobs",
        json={"dataset_id": dataset1_id, "max_steps": 2},
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert job_res.status_code == 202
    job_id = job_res.json()["job_id"]

    # User 2 attempts to view User 1's job -> 403 Forbidden
    job_forbidden = client.get(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token2}"})
    assert job_forbidden.status_code == 403

    # User 1 can view their job
    job_allowed = client.get(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token1}"})
    assert job_allowed.status_code == 200
