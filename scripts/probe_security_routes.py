"""Script to perform REAL introspection and probe all FastAPI routes for security & isolation."""
import io
import json
from fastapi.testclient import TestClient
from backend.app.main import app

def probe_all_routes():
    client = TestClient(app)
    import uuid
    uid = uuid.uuid4().hex[:6]

    # 1. Setup User A and User B
    res_a = client.post("/api/v1/auth/register", json={
        "email": f"probe_user_a_{uid}@example.com",
        "password": "UserAPassword123!"
    })
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    res_b = client.post("/api/v1/auth/register", json={
        "email": f"probe_user_b_{uid}@example.com",
        "password": "UserBPassword123!"
    })
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}


    # User A creates sample resources
    csv_bytes = b"dept,salary\nHR,50000\nIT,70000\n"
    up_res = client.post(
        "/api/v1/upload",
        files={"file": ("probe_sample.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers=headers_a
    )
    dataset_id = up_res.json()["dataset_id"]
    client.post(f"/api/v1/datasets/{dataset_id}/clean", headers=headers_a)

    job_res = client.post(
        "/api/v1/jobs",
        json={"dataset_id": dataset_id, "goal": "Security probe analysis"},
        headers=headers_a
    )
    job_id = job_res.json()["job_id"]

    sched_res = client.post(
        "/api/v1/schedules",
        json={"dataset_id": dataset_id, "frequency": "daily"},
        headers=headers_a
    )
    schedule_id = sched_res.json()["id"]

    rep_res = client.post(f"/api/v1/jobs/{job_id}/report?format=pdf", headers=headers_a)
    report_id = rep_res.json()["report_id"]

    sample_substitutions = {
        "{dataset_id}": dataset_id,
        "{job_id}": job_id,
        "{schedule_id}": schedule_id,
        "{report_id}": report_id,
        "{insight_id}": "insight-123"
    }

    # Inspect all registered routes from OpenAPI schema
    rows = []
    paths_dict = app.openapi()["paths"]

    for path, methods_dict in paths_dict.items():
        for method_lower in methods_dict.keys():
            method = method_lower.upper()
            if method in ("HEAD", "OPTIONS"):
                continue

            # Concrete path for testing
            concrete_path = path
            for param, val in sample_substitutions.items():
                concrete_path = concrete_path.replace(param, val)

            # Build dummy body or files if needed
            body = None
            files = None
            if "upload" in path and method == "POST":
                files = {"file": ("probe_dummy.csv", io.BytesIO(b"id,val\n1,2\n"), "text/csv")}
            elif "chat" in path and method == "POST":
                body = {"job_id": job_id, "question": "Probe test question"}
            elif "schedules" in path and method == "POST" and "{" not in path:
                body = {"dataset_id": dataset_id, "frequency": "daily"}
            elif "feedback" in path and method == "POST":
                body = {"rating": "helpful"}
            elif "jobs" in path and method == "POST" and "{" not in path:
                body = {"dataset_id": dataset_id, "goal": "Probe job"}

            # Probe Anonymous
            if method == "GET":
                res_anon = client.get(concrete_path)
            elif method == "POST":
                if files:
                    res_anon = client.post(concrete_path, files={"file": ("probe_dummy.csv", io.BytesIO(b"id,val\n1,2\n"), "text/csv")})
                elif body:
                    res_anon = client.post(concrete_path, json=body)
                else:
                    res_anon = client.post(concrete_path)
            elif method == "DELETE":
                res_anon = client.delete(concrete_path)
            else:
                res_anon = client.request(method, concrete_path)

            # Probe User B (Non-owner)
            if method == "GET":
                res_b = client.get(concrete_path, headers=headers_b)
            elif method == "POST":
                if files:
                    res_b = client.post(concrete_path, files={"file": ("probe_dummy.csv", io.BytesIO(b"id,val\n1,2\n"), "text/csv")}, headers=headers_b)
                elif body:
                    res_b = client.post(concrete_path, json=body, headers=headers_b)
                else:
                    res_b = client.post(concrete_path, headers=headers_b)
            elif method == "DELETE":
                res_b = client.delete(concrete_path, headers=headers_b)
            else:
                res_b = client.request(method, concrete_path, headers=headers_b)

            rows.append({
                "method": method,
                "path": path,
                "anon_status": res_anon.status_code,
                "user_b_status": res_b.status_code
            })

    # Print markdown table
    print("\n### Real Route Security Probe Results\n")
    print("| Method | Route Path | Anonymous Status | User B (Non-Owner) Status | Protection Level |")
    print("|---|---|:---:|:---:|---|")
    for r in sorted(rows, key=lambda x: (x["path"], x["method"])):
        prot = "Public"
        if r["anon_status"] == 401:
            if r["user_b_status"] in (403, 404):
                prot = "Authenticated & Isolated (Owner Only)"
            elif r["user_b_status"] == 200:
                prot = "Authenticated (Shared/Scoped)"
            else:
                prot = f"Authenticated ({r['user_b_status']})"
        elif r["anon_status"] == 200:
            prot = "Public Open"
        print(f"| {r['method']} | `{r['path']}` | {r['anon_status']} | {r['user_b_status']} | {prot} |")

if __name__ == "__main__":
    probe_all_routes()
