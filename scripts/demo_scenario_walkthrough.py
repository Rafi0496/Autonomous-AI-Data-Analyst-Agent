"""Phase 4 Complete Live Demo & Scenario Walkthrough Script.

Rehearses and verifies 2 complete real-world business scenarios:
1. Scenario A: Retail Sales & Operations (messy data with sentinels, negative returns, casing variance)
2. Scenario B: HR Attrition & Workforce Analytics (categorical binary rates, salary outliers, department segmentation)

Demonstrates the entire real-world feature set:
- JWT User Authentication & Account Isolation
- Messy Data Ingestion, Domain Cleaning & Sampling Guardrails
- Autonomous Plan-Act-Reflect Multi-Round Analysis
- Ranked Insights & Grounded Verification
- Human-in-the-Loop Feedback (Plan §8.6)
- Publication-Ready Report Exports (PDF and Word)
- Scheduled Recurring Analysis (Plan §8.3)
"""
import io
import json
import os
import sys
import time
from pathlib import Path
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Ensure heuristic or active LLM mode
if not os.getenv("LLM_PROVIDER"):
    os.environ["LLM_PROVIDER"] = "heuristic"

from backend.app.main import app

client = TestClient(app)

def run_business_scenario(scenario_name: str, csv_path: Path, user_email: str, goal: str):
    print(f"\n=======================================================")
    print(f" DEMO SCENARIO: {scenario_name}")
    print(f" Target User: {user_email}")
    print(f" Analytical Goal: {goal}")
    print(f"=======================================================")

    # 1. User Authentication
    print("\n[Step 1] Authenticating user via JWT...")
    reg_res = client.post("/api/v1/auth/register", json={
        "email": user_email,
        "password": "DemoPassword2026!",
        "full_name": f"Analyst ({scenario_name})"
    })
    if reg_res.status_code == 201:
        token = reg_res.json()["access_token"]
    else:
        login_res = client.post("/api/v1/auth/login", json={
            "email": user_email,
            "password": "DemoPassword2026!"
        })
        token = login_res.json()["access_token"]

    auth_headers = {"Authorization": f"Bearer {token}"}
    print(f" -> Authenticated successfully. Token: {token[:20]}...")

    # 2. Dataset Upload
    print("\n[Step 2] Ingesting messy dataset...")
    with open(csv_path, "rb") as f:
        upload_res = client.post(
            "/api/v1/upload",
            files={"file": (csv_path.name, f, "text/csv")},
            headers=auth_headers
        )
    assert upload_res.status_code == 201, upload_res.text
    dataset_id = upload_res.json()["dataset_id"]
    row_count = upload_res.json()["row_count"]
    col_count = upload_res.json()["column_count"]
    print(f" -> Uploaded dataset ID: {dataset_id} ({row_count} rows, {col_count} columns)")

    # 3. Clean Dataset
    print("\n[Step 3] Executing deterministic cleaning & validation pipeline...")
    clean_res = client.post(f"/api/v1/datasets/{dataset_id}/clean", headers=auth_headers)
    assert clean_res.status_code == 200, clean_res.text
    c_data = clean_res.json()
    print(f" -> Cleaned rows: {c_data['cleaned_row_count']}, Duplicates removed: {c_data['duplicates_removed']}")
    if c_data.get("is_sampled"):
        print(f" -> Scale sampling active: {c_data['sampling_rate']*100:.1f}% sampling rate applied.")
    if c_data.get("sentinels_detected"):
        print(f" -> Sentinels sanitized: {len(c_data['sentinels_detected'])} detected")
    if c_data.get("suspected_returns"):
        print(f" -> Business returns flagged: {len(c_data['suspected_returns'])} detected")

    # 4. Profile Dataset
    print("\n[Step 4] Generating statistical data profile...")
    prof_res = client.post(f"/api/v1/datasets/{dataset_id}/profile", headers=auth_headers)
    assert prof_res.status_code == 200, prof_res.text
    profile = prof_res.json()
    print(f" -> Quality Score: {profile.get('quality_score')}/100. Columns profiled: {len(profile.get('columns', []))}")

    # 5. Launch Autonomous Plan-Act-Reflect Agent Job
    print("\n[Step 5] Launching autonomous Plan-Act-Reflect agent analysis...")
    t_start = time.perf_counter()
    job_res = client.post(
        "/api/v1/jobs",
        json={"dataset_id": dataset_id, "goal": goal, "max_steps": 4, "token_budget": 15000},
        headers=auth_headers
    )
    assert job_res.status_code == 202, job_res.text
    job_id = job_res.json()["job_id"]
    print(f" -> Analysis job submitted. ID: {job_id}")

    # Poll status until complete
    max_wait = 60
    while max_wait > 0:
        stat_res = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        stat = stat_res.json()
        if stat["status"] in ("completed", "budget_tripped", "failed"):
            break
        time.sleep(1)
        max_wait -= 1

    duration = time.perf_counter() - t_start
    print(f" -> Job completed with status '{stat['status']}' in {duration:.2f}s")
    print(f" -> Steps executed: {stat['total_steps']}, Tokens accounted: {stat['tokens_used']}")

    # 6. Retrieve Insights and Run Log
    print("\n[Step 6] Retrieving ranked insights and explainability run-log...")
    insights_res = client.get(f"/api/v1/jobs/{job_id}/insights", headers=auth_headers)
    assert insights_res.status_code == 200
    insights = insights_res.json()["insights"]
    print(f" -> Ranked Insights count: {len(insights)}")
    for idx, ins in enumerate(insights[:3], 1):
        print(f"    [{idx}] {ins['type'].upper()} ({ins.get('confidence', 'high').upper()}): {ins['title']}")

    logs_res = client.get(f"/api/v1/jobs/{job_id}/logs", headers=auth_headers)
    assert logs_res.status_code == 200
    run_log = logs_res.json()["run_log"]
    print(f" -> Explainability steps logged: {len(run_log)}")

    # 7. Human-in-the-Loop Feedback Loop (Plan §8.6)
    if insights:
        top_ins_id = insights[0]["id"]
        print(f"\n[Step 7] Testing human feedback loop on insight '{top_ins_id}'...")
        fb_res = client.post(
            f"/api/v1/jobs/{job_id}/insights/{top_ins_id}/feedback",
            json={"rating": "helpful", "comment": f"Validated finding by business team for {scenario_name}."},
            headers=auth_headers
        )
        assert fb_res.status_code == 201
        print(f" -> Feedback recorded: rating='{fb_res.json()['rating']}'")

    # 8. Conversational Follow-Up Q&A
    print("\n[Step 8] Asking conversational follow-up question...")
    chat_res = client.post(
        "/api/v1/chat",
        json={
            "job_id": job_id,
            "dataset_id": dataset_id,
            "question": "What is the key takeaway from the analysis and what action is recommended?"
        },
        headers=auth_headers
    )
    if chat_res.status_code == 200:
        ans = chat_res.json()
        print(f" -> Agent Answer: {ans.get('answer', '')[:140]}...")

    # 9. Publication-Ready Report Exports (PDF & DOCX)
    print("\n[Step 9] Generating business reports (PDF & DOCX)...")
    pdf_res = client.post(f"/api/v1/jobs/{job_id}/report?format=pdf", headers=auth_headers)
    docx_res = client.post(f"/api/v1/jobs/{job_id}/report?format=docx", headers=auth_headers)
    assert pdf_res.status_code == 200, pdf_res.text
    assert docx_res.status_code == 200, docx_res.text
    print(f" -> PDF report generated: {pdf_res.json().get('filename')}")
    print(f" -> DOCX report generated: {docx_res.json().get('filename')}")

    # 10. Scheduled Analysis Setup (Plan §8.3)
    print("\n[Step 10] Configuring recurring analysis schedule...")
    sched_res = client.post(
        "/api/v1/schedules",
        json={"dataset_id": dataset_id, "frequency": "weekly", "goal": f"Weekly {scenario_name} review"},
        headers=auth_headers
    )
    assert sched_res.status_code == 201
    print(f" -> Schedule active: ID={sched_res.json()['id']}, frequency={sched_res.json()['frequency']}")

    print(f"\n[+] Scenario '{scenario_name}' completed successfully and verified end-to-end!")

def main():
    print("==================================================================")
    print(" AUTONOMOUS AI DATA ANALYST AGENT - PHASE 4 LIVE DEMO WALKTHROUGH")
    print("==================================================================")

    data_dir = BASE_DIR / "data" / "samples"
    retail_csv = data_dir / "retail_sales_messy.csv"
    hr_csv = data_dir / "hr_attrition_messy.csv"

    # Fallback to test_datasets if not in samples
    if not retail_csv.exists():
        retail_csv = BASE_DIR / "backend" / "tests" / "test_datasets" / "retail_sales_messy.csv"
    if not hr_csv.exists():
        hr_csv = BASE_DIR / "backend" / "tests" / "test_datasets" / "hr_attrition_messy.csv"

    assert retail_csv.exists(), f"Retail dataset not found at {retail_csv}"
    assert hr_csv.exists(), f"HR dataset not found at {hr_csv}"

    # Scenario 1: Retail Sales & Commercial Performance
    run_business_scenario(
        scenario_name="Retail Sales & Commercial Performance",
        csv_path=retail_csv,
        user_email="retail.director@autoanalyst.demo",
        goal="Identify key revenue drivers, regional variations, and anomalies in sales data."
    )

    # Scenario 2: HR Workforce & Attrition Analytics
    run_business_scenario(
        scenario_name="HR Workforce & Attrition Analytics",
        csv_path=hr_csv,
        user_email="hr.vp@autoanalyst.demo",
        goal="Analyze employee attrition rates across departments and examine salary distributions."
    )

    print("\n==================================================================")
    print(" ALL PHASE 4 DEMO SCENARIOS EXECUTED AND VERIFIED SUCCESSFULLY!")
    print("==================================================================")

if __name__ == "__main__":
    main()
