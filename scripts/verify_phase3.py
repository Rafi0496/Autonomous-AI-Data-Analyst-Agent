"""Phase 3 End-to-End Verification Script.

Executes the full pipeline for all 3 messy datasets:
1. Upload dataset via API
2. Trigger cleaning and profiling
3. Execute autonomous Plan-Act-Reflect analysis job
4. Retrieve ranked insights with confidence and impact scores
5. Query chat Q&A endpoint with domain-relevant analytical questions
6. Export PDF and DOCX reports via API and validate integrity
7. Save demo artifacts (insights.json, summary.txt, report.pdf, report.docx, chart PNGs)
"""
import sys
import os
import json
import time
from pathlib import Path
from fastapi.testclient import TestClient
import docx
import pypdf

# Set project root in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.main import app
from backend.app.services.chart_render import render_chart_to_png
from backend.app.tasks.analysis_tasks import execute_job_synchronously

SAMPLE_DATASETS = [
    {
        "filename": "retail_sales_messy.csv",
        "name": "retail_sales",
        "question": "What is the relationship between customer age, product category, and purchase amount?"
    },
    {
        "filename": "hr_attrition_messy.csv",
        "name": "hr_attrition",
        "question": "What are the primary factors and salary dynamics associated with employee attrition?"
    },
    {
        "filename": "marketing_campaign_messy.csv",
        "name": "marketing_campaign",
        "question": "Which channels and campaign strategies delivered the highest conversion rate and ROI?"
    }
]

def verify_phase3():
    print("=" * 80)
    print("PHASE 3: FULL AUTONOMOUS PIPELINE E2E VERIFICATION")
    print("=" * 80)

    client = TestClient(app)
    demo_base_dir = BASE_DIR / "data" / "demo_outputs"
    demo_base_dir.mkdir(parents=True, exist_ok=True)

    results_summary = {}

    for ds_info in SAMPLE_DATASETS:
        filename = ds_info["filename"]
        dataset_slug = ds_info["name"]
        chat_q = ds_info["question"]
        file_path = BASE_DIR / "data" / "samples" / filename

        print(f"\n" + "-" * 70)
        print(f"--> Processing Dataset: {filename}")
        print("-" * 70)

        assert file_path.exists(), f"Sample file not found: {file_path}"
        out_dir = demo_base_dir / dataset_slug
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1. Upload
        print("[1/6] Uploading dataset via POST /api/v1/datasets/upload...")
        with open(file_path, "rb") as f:
            upload_resp = client.post(
                "/api/v1/datasets/upload",
                files={"file": (filename, f, "text/csv")}
            )
        assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"
        dataset_id = upload_resp.json()["dataset_id"]
        print(f"      Uploaded ID: {dataset_id}")

        # 2. Clean & Profile
        print("[2/6] Cleaning and profiling dataset...")
        clean_resp = client.post(f"/api/v1/datasets/{dataset_id}/clean")
        assert clean_resp.status_code == 200, f"Clean failed: {clean_resp.text}"
        profile_resp = client.post(f"/api/v1/datasets/{dataset_id}/profile")
        assert profile_resp.status_code == 200, f"Profile failed: {profile_resp.text}"

        # 3. Create Analysis Job & Run
        print("[3/6] Running autonomous analysis job...")
        t_start = time.perf_counter()
        job_resp = client.post(
            "/api/v1/jobs",
            json={"dataset_id": dataset_id, "max_steps": 5, "token_budget": 15000}
        )
        assert job_resp.status_code == 202, f"Job submission failed: {job_resp.text}"
        job_id = job_resp.json()["job_id"]

        # Ensure execution completes (in test environment, execute_job_synchronously guarantees finish)
        exec_result = execute_job_synchronously(job_id=job_id, dataset_id=dataset_id, max_steps=5, token_budget=15000)
        t_total = time.perf_counter() - t_start
        print(f"      Job {job_id} finished in {t_total:.2f}s")

        # 4. Fetch Insights
        print("[4/6] Fetching ranked insights via GET /jobs/{id}/insights...")
        insights_resp = client.get(f"/api/v1/jobs/{job_id}/insights")
        if insights_resp.status_code != 200:
            insights_resp = client.get(f"/jobs/{job_id}/insights")
        assert insights_resp.status_code == 200, f"Get insights failed: {insights_resp.text}"
        insights_data = insights_resp.json()
        insights = insights_data.get("insights", [])
        print(f"      Total Insights Generated: {len(insights)}")

        # Print ranked insights summary
        print("\n      Ranked Insights:")
        for idx, ins in enumerate(insights, 1):
            print(f"      {idx}. [{ins.get('confidence', 'N/A').upper()}] (Impact: {ins.get('impact_score', 0):.2f}) "
                  f"{ins.get('title')} [{ins.get('type')}] "
                  f"(n_used={ins.get('n_used')}, excl_rate={ins.get('exclusion_rate', 0):.1%})")

        # Render and save chart PNGs
        chart_png_paths = []
        for idx, ins in enumerate(insights, 1):
            cs = ins.get("chart_spec")
            if cs:
                png_bytes = render_chart_to_png(cs)
                png_path = out_dir / f"chart_{idx}_{ins.get('type')}.png"
                with open(png_path, "wb") as pf:
                    pf.write(png_bytes)
                chart_png_paths.append(str(png_path))

        # Save insights.json
        with open(out_dir / "insights.json", "w", encoding="utf-8") as inf:
            json.dump(insights, inf, indent=2)

        # Executive summary
        synthesis = exec_result.get("synthesis", {})
        exec_summary = synthesis.get("executive_summary", "") if isinstance(synthesis, dict) else str(synthesis)
        with open(out_dir / "summary.txt", "w", encoding="utf-8") as sf:
            sf.write(f"EXECUTIVE SUMMARY:\n{exec_summary}\n\n")
            if isinstance(synthesis, dict) and "key_findings" in synthesis:
                sf.write("KEY FINDINGS:\n")
                for kf in synthesis.get("key_findings", []):
                    sf.write(f"- {kf}\n")

        # 5. Chat Question
        print(f"\n[5/6] Testing Chat Q&A: '{chat_q}'...")
        chat_resp = client.post(
            "/api/v1/chat",
            json={"job_id": job_id, "question": chat_q, "history": []}
        )
        if chat_resp.status_code != 200:
            chat_resp = client.post(
                "/chat",
                json={"job_id": job_id, "question": chat_q, "history": []}
            )
        assert chat_resp.status_code == 200, f"Chat failed: {chat_resp.text}"
        chat_data = chat_resp.json()
        print(f"      Answer: {chat_data.get('answer')[:120]}...")
        print(f"      Evidence steps: {chat_data.get('evidence')}")
        print(f"      Verification: {chat_data.get('verification')}")

        with open(out_dir / "chat_exchange.json", "w", encoding="utf-8") as cf:
            json.dump({
                "question": chat_q,
                "response": chat_data
            }, cf, indent=2)

        # 6. Report Generation (PDF & DOCX)
        print("\n[6/6] Generating and validating PDF & DOCX reports...")
        # PDF
        pdf_gen = client.post(f"/api/v1/jobs/{job_id}/report?format=pdf")
        if pdf_gen.status_code != 200:
            pdf_gen = client.post(f"/jobs/{job_id}/report?format=pdf")
        assert pdf_gen.status_code == 200, f"PDF report gen failed: {pdf_gen.text}"
        pdf_rep_id = pdf_gen.json()["report_id"]

        pdf_down = client.get(f"/api/v1/reports/{pdf_rep_id}/download")
        if pdf_down.status_code != 200:
            pdf_down = client.get(f"/reports/{pdf_rep_id}/download")
        assert pdf_down.status_code == 200, f"PDF download failed: {pdf_down.status_code}"
        pdf_path = out_dir / "report.pdf"
        with open(pdf_path, "wb") as pf:
            pf.write(pdf_down.content)

        # DOCX
        docx_gen = client.post(f"/api/v1/jobs/{job_id}/report?format=docx")
        if docx_gen.status_code != 200:
            docx_gen = client.post(f"/jobs/{job_id}/report?format=docx")
        assert docx_gen.status_code == 200, f"DOCX report gen failed: {docx_gen.text}"
        docx_rep_id = docx_gen.json()["report_id"]

        docx_down = client.get(f"/api/v1/reports/{docx_rep_id}/download")
        if docx_down.status_code != 200:
            docx_down = client.get(f"/reports/{docx_rep_id}/download")
        assert docx_down.status_code == 200, f"DOCX download failed: {docx_down.status_code}"
        docx_path = out_dir / "report.docx"
        with open(docx_path, "wb") as df:
            df.write(docx_down.content)

        # Validate PDF
        reader = pypdf.PdfReader(str(pdf_path))
        pdf_page_count = len(reader.pages)
        pdf_text = " ".join(p.extract_text() or "" for p in reader.pages)
        assert pdf_page_count >= 1, "PDF has 0 pages"
        assert len(pdf_text) > 100, "PDF has insufficient text"
        print(f"      [PASS] PDF generated: {pdf_path} ({pdf_page_count} pages)")

        # Validate DOCX
        doc = docx.Document(str(docx_path))
        docx_paras = len(doc.paragraphs)
        assert docx_paras >= 5, "DOCX has insufficient paragraphs"
        print(f"      [PASS] DOCX generated: {docx_path} ({docx_paras} paragraphs)")

        # Per-call latency breakdown
        run_log = exec_result.get("run_log", [])
        latencies = [
            {"step": step.get("step"), "tool": step.get("tool"), "llm_latency_ms": step.get("llm_latency_ms"), "tool_duration_ms": step.get("duration_ms")}
            for step in run_log
        ]

        results_summary[filename] = {
            "dataset_id": dataset_id,
            "job_id": job_id,
            "insights_count": len(insights),
            "insights": insights,
            "pdf_pages": pdf_page_count,
            "docx_paras": docx_paras,
            "total_time_s": t_total,
            "latencies": latencies,
            "synthesis_latency_ms": exec_result.get("synthesis_llm_latency_ms"),
            "verification": exec_result.get("citation_audit") or exec_result.get("verification"),
            "chat_exchange": {
                "question": chat_q,
                "answer": chat_data.get("answer"),
                "verification": chat_data.get("verification"),
                "evidence": chat_data.get("evidence")
            }
        }

    print("\n" + "=" * 80)
    print("ALL 3 DATASETS VERIFIED SUCCESSFULLY")
    print("=" * 80)
    return results_summary

if __name__ == "__main__":
    verify_phase3()
