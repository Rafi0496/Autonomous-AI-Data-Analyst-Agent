"""Verify multi-format ingestion, auth, and analysis against live backend."""
import httpx
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_all():
    fixtures = [
        ("data/samples/retail_sales_messy.csv", "text/csv"),
        ("data/e2e_fixtures/sample_sales.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("data/e2e_fixtures/sample_marketing.json", "application/json"),
        ("data/e2e_fixtures/sample_inventory.xml", "application/xml"),
        ("data/e2e_fixtures/sample_clinical.parquet", "application/octet-stream"),
        ("data/e2e_fixtures/sample_report_table.pdf", "application/pdf"),
        ("data/e2e_fixtures/sample_archive.zip", "application/zip")
    ]

    with httpx.Client(timeout=45.0) as client:
        # 1. Health check
        h = client.get(f"{BASE_URL}/health")
        print("Health status:", h.status_code, h.json())
        assert h.status_code == 200

        # 2. Register or Login
        auth_headers = {}
        email = "analyst_e2e@example.com"
        password = "SecurePassword123!"
        
        reg = client.post(f"{BASE_URL}/auth/register", json={
            "email": email,
            "password": password,
            "full_name": "E2E Test Analyst"
        })
        if reg.status_code == 201:
            token = reg.json().get("access_token")
            auth_headers = {"Authorization": f"Bearer {token}"}
            print("Registered new user successfully, token obtained.")
        else:
            log = client.post(f"{BASE_URL}/auth/login", json={
                "email": email,
                "password": password
            })
            token = log.json().get("access_token")
            auth_headers = {"Authorization": f"Bearer {token}"}
            print("Logged in existing user successfully, token obtained.")

        # 3. General chat without job_id (e.g. "Hi")
        c1 = client.post(f"{BASE_URL}/chat", json={"question": "Hi"}, headers=auth_headers)
        print("Chat 'Hi':", c1.status_code, c1.json().get("answer"))
        assert c1.status_code == 200
        assert "Hello" in c1.json().get("answer") or "analyst" in c1.json().get("answer").lower()

        # 4. Upload all 7 formats
        uploaded_ids = []
        for file_path_str, mime in fixtures:
            p = Path(file_path_str)
            with open(p, "rb") as f:
                res = client.post(f"{BASE_URL}/upload", files={"file": (p.name, f, mime)}, headers=auth_headers)
                print(f"Upload {p.name}: status={res.status_code}, dataset_id={res.json().get('dataset_id')}")
                assert res.status_code in (200, 201, 202), f"Failed for {p.name}: {res.text}"
                ds_id = res.json()["dataset_id"]
                uploaded_ids.append((p.name, ds_id))

        # 5. Check dataset status & profiles
        for name, ds_id in uploaded_ids:
            d_res = client.get(f"{BASE_URL}/datasets/{ds_id}", headers=auth_headers)
            d_data = d_res.json()
            print(f"Dataset {name}: status={d_data.get('status')}, rows={d_data.get('row_count')}, cols={d_data.get('column_count')}, stage={d_data.get('stage')}")
            assert d_res.status_code == 200
            assert d_data.get("row_count", 0) > 0

        # 6. Dispatch job on the first dataset
        first_id = uploaded_ids[0][1]
        job_res = client.post(f"{BASE_URL}/jobs", json={
            "dataset_id": first_id,
            "goal": "Analyze regional revenue distribution and top anomalies",
            "max_steps": 3,
            "token_budget": 5000
        }, headers=auth_headers)
        print("Job creation:", job_res.status_code, job_res.json())
        assert job_res.status_code in (200, 201, 202)
        job_id = job_res.json()["job_id"]

        # 7. Chat with job_id
        c2 = client.post(f"{BASE_URL}/chat", json={
            "job_id": job_id,
            "dataset_id": first_id,
            "question": "What are the primary findings in this dataset?"
        }, headers=auth_headers)
        print("Chat with job_id:", c2.status_code, c2.json().get("answer")[:120])
        assert c2.status_code == 200

    print("\nALL LIVE BACKEND FORMAT & CHAT CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all()
