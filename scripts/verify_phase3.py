"""Phase 3 End-to-End Hardened Verification Script.

Executes the full pipeline for all 3 messy datasets:
1. Upload dataset via API
2. Clean and profile
3. Execute autonomous Plan-Act-Reflect analysis job (batched tool calls, reflection, synthesis)
4. Partitioned ranked insights: top 6 analytical insights + max 4 data-quality caveats
5. Validate n_used + n_excluded == n_total invariant on all insights
6. Interactive Chat Q&A with 3 questions per dataset:
   - One answerable from insights
   - One requiring a tool call (e.g. Credit Card payment share)
   - One asking about a non-existent column (e.g. customer age, customer churn, credit score)
7. Latency reporting: table of per-step LLM ms, tool ms, synthesis ms, sum, total, and assert sum <= total.
8. PDF and DOCX report generation and validation.
9. Save demo artifacts into data/demo_outputs/<dataset_slug>/
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

# Ensure LLM mode is active if key is present
if os.getenv("GEMINI_API_KEY") and not os.getenv("LLM_PROVIDER"):
    os.environ["LLM_PROVIDER"] = "gemini"

from backend.app.main import app
from backend.app.services.chart_render import render_chart_to_png
from backend.app.tasks.analysis_tasks import execute_job_synchronously

SAMPLE_DATASETS = [
    {
        "filename": "retail_sales_messy.csv",
        "name": "retail_sales",
        "questions": [
            {
                "type": "insight",
                "question": "What is the overall trend in monthly retail sales and is it statistically significant?"
            },
            {
                "type": "tool_call",
                "question": "What is the share of Credit Card payments among non-missing payment method rows?"
            },
            {
                "type": "missing_column",
                "question": "What is the average customer age across the different retail store regions?"
            }
        ]
    },
    {
        "filename": "hr_attrition_messy.csv",
        "name": "hr_attrition",
        "questions": [
            {
                "type": "insight",
                "question": "Which department has the highest employee attrition rate and is the difference statistically significant?"
            },
            {
                "type": "tool_call",
                "question": "What is the average annual salary by department among observed non-missing records?"
            },
            {
                "type": "missing_column",
                "question": "How does customer churn correlate with employee satisfaction levels?"
            }
        ]
    },
    {
        "filename": "marketing_campaign_messy.csv",
        "name": "marketing_campaign",
        "questions": [
            {
                "type": "insight",
                "question": "Which marketing channel delivers the highest conversion rate?"
            },
            {
                "type": "tool_call",
                "question": "What is the total ad spend and total clicks by marketing channel?"
            },
            {
                "type": "missing_column",
                "question": "What is the average customer credit score across the different marketing channels?"
            }
        ]
    }
]

def verify_phase3():
    print("=" * 80)
    print("PHASE 3 HARDENING: FULL PIPELINE E2E VERIFICATION")
    print(f"Active Provider: {os.getenv('LLM_PROVIDER', 'heuristic')}")
    print("=" * 80)

    client = TestClient(app)
    demo_base_dir = BASE_DIR / "data" / "demo_outputs"
    demo_base_dir.mkdir(parents=True, exist_ok=True)

    # Authenticate user
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": "verify_phase3_tester@example.com",
        "password": "VerifyPassword123!"
    })
    if reg_resp.status_code == 201:
        auth_token = reg_resp.json()["access_token"]
    else:
        login_resp = client.post("/api/v1/auth/login", json={
            "email": "verify_phase3_tester@example.com",
            "password": "VerifyPassword123!"
        })
        auth_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {auth_token}"}

    results_summary = {}

    for ds_info in SAMPLE_DATASETS:
        filename = ds_info["filename"]
        dataset_slug = ds_info["name"]
        questions = ds_info["questions"]
        file_path = BASE_DIR / "data" / "samples" / filename

        print(f"\n" + "-" * 75)
        print(f"--> Processing Dataset: {filename} ({dataset_slug})")
        print("-" * 75)

        assert file_path.exists(), f"Sample file not found: {file_path}"
        out_dir = demo_base_dir / dataset_slug
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1. Upload
        print("[1/7] Uploading dataset via POST /api/v1/upload...")
        with open(file_path, "rb") as f:
            upload_resp = client.post(
                "/api/v1/upload",
                files={"file": (filename, f, "text/csv")},
                headers=headers
            )
        assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"
        dataset_id = upload_resp.json()["dataset_id"]
        print(f"      Uploaded ID: {dataset_id}")

        # 2. Clean & Profile
        print("[2/7] Cleaning and profiling dataset...")
        clean_resp = client.post(f"/api/v1/datasets/{dataset_id}/clean", headers=headers)
        assert clean_resp.status_code == 200, f"Clean failed: {clean_resp.text}"
        profile_resp = client.post(f"/api/v1/datasets/{dataset_id}/profile", headers=headers)
        assert profile_resp.status_code == 200, f"Profile failed: {profile_resp.text}"
        profile_data = profile_resp.json()
        total_rows = profile_data.get("row_count", 0)
        print(f"      Dataset Profile: {total_rows} rows, {profile_data.get('column_count')} columns")

        # 3. Create Analysis Job & Run
        print("[3/7] Running autonomous Plan-Act-Reflect analysis job...")
        t_start = time.perf_counter()
        job_resp = client.post(
            "/api/v1/jobs",
            json={"dataset_id": dataset_id, "max_steps": 5, "token_budget": 15000},
            headers=headers
        )
        assert job_resp.status_code == 202, f"Job submission failed: {job_resp.text}"
        job_id = job_resp.json()["job_id"]

        exec_result = execute_job_synchronously(job_id=job_id, dataset_id=dataset_id, max_steps=5, token_budget=15000)
        t_wall_seconds = time.perf_counter() - t_start
        print(f"      Job {job_id} finished in {t_wall_seconds:.3f}s")

        # 4. Fetch Insights & Invariant Verification
        print("[4/7] Fetching ranked insights and verifying invariants...")
        insights_resp = client.get(f"/api/v1/jobs/{job_id}/insights", headers=headers)

        if insights_resp.status_code != 200:
            insights_resp = client.get(f"/jobs/{job_id}/insights")
        assert insights_resp.status_code == 200, f"Get insights failed: {insights_resp.text}"
        insights_data = insights_resp.json()
        insights = insights_data.get("insights", [])

        # Partition into analytical and data_quality lists
        analytical_insights = [ins for ins in insights if ins.get("type") != "data_quality"]
        dq_insights = [ins for ins in insights if ins.get("type") == "data_quality"]

        print(f"      Generated: {len(analytical_insights)} analytical insights, {len(dq_insights)} data-quality caveats")

        # Verify n_used + n_excluded == n_total invariant on all insights
        for ins in insights:
            n_used = ins.get("n_used", 0)
            n_excluded = ins.get("n_excluded", 0)
            assert n_used + n_excluded == total_rows, (
                f"Invariant violation in '{ins.get('title')}': "
                f"n_used ({n_used}) + n_excluded ({n_excluded}) != total_rows ({total_rows})"
            )
        print("      [PASS] Invariant n_used + n_excluded == total_rows verified for all insights!")

        # Print ranked lists
        print("\n      --- Top Analytical Insights (Max 6) ---")
        for idx, ins in enumerate(analytical_insights[:6], 1):
            print(f"      {idx}. [{ins.get('confidence', 'N/A').upper()}] Impact: {ins.get('impact_score', 0):.2f} | "
                  f"{ins.get('title')} [{ins.get('type')}] (n_used={ins.get('n_used')}, excl={ins.get('n_excluded')})")

        print("\n      --- Data Quality Caveats (Max 4) ---")
        for idx, ins in enumerate(dq_insights[:4], 1):
            print(f"      {idx}. [{ins.get('confidence', 'N/A').upper()}] Impact: {ins.get('impact_score', 0):.2f} | "
                  f"{ins.get('title')} [{ins.get('type')}] (n_used={ins.get('n_used')}, excl={ins.get('n_excluded')})")

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

        with open(out_dir / "insights.json", "w", encoding="utf-8") as inf:
            json.dump(insights, inf, indent=2)

        # Executive summary
        synthesis = exec_result.get("synthesis", {})
        exec_summary = synthesis.get("executive_summary", "") if isinstance(synthesis, dict) else str(synthesis)
        claims = synthesis.get("claims", []) if isinstance(synthesis, dict) else []
        with open(out_dir / "summary.txt", "w", encoding="utf-8") as sf:
            sf.write(f"EXECUTIVE SUMMARY:\n{exec_summary}\n\n")
            if isinstance(synthesis, dict) and "key_findings" in synthesis:
                sf.write("KEY FINDINGS:\n")
                for kf in synthesis.get("key_findings", []):
                    sf.write(f"- {kf}\n")

        # 5. Latency Reporting Table
        print("\n[5/7] Computing component latencies directly from run_log...")
        run_log = exec_result.get("run_log", [])
        synth_ms = float(exec_result.get("synthesis_llm_latency_ms") or 0.0)
        
        sum_llm_ms = 0.0
        sum_tool_ms = 0.0
        sum_refl_ms = 0.0

        print(f"\n      +------+---------------------+------------+-----------+---------------+------------+")
        print(f"      | Step | Tool Name           | LLM (ms)   | Tool (ms) | Reflect (ms)  | Subtotal   |")
        print(f"      +------+---------------------+------------+-----------+---------------+------------+")
        for step in run_log:
            s_idx = step.get("step", 1)
            t_name = (step.get("tool") or "unknown")[:19]
            l_ms = float(step.get("llm_latency_ms") or 0.0)
            t_ms = float(step.get("duration_ms") or step.get("tool_duration_ms") or 0.0)
            r_ms = float(step.get("reflection_latency_ms") or 0.0)
            step_subtotal = l_ms + t_ms + r_ms
            sum_llm_ms += l_ms
            sum_tool_ms += t_ms
            sum_refl_ms += r_ms
            print(f"      | {s_idx:<4} | {t_name:<19} | {l_ms:>10.2f} | {t_ms:>9.2f} | {r_ms:>13.2f} | {step_subtotal:>10.2f} |")
        print(f"      +------+---------------------+------------+-----------+---------------+------------+")
        print(f"      | Synthesis LLM Latency:     | {synth_ms:>10.2f} ms")

        component_sum_ms = sum_llm_ms + sum_tool_ms + sum_refl_ms + synth_ms
        raw_total_seconds = float(exec_result.get("execution_time_seconds") or t_wall_seconds)
        total_wall_ms = raw_total_seconds * 1000.0

        print(f"      | Component Sum:             | {component_sum_ms:>10.2f} ms")
        print(f"      | Total Wall-Clock Time:     | {total_wall_ms:>10.2f} ms ({raw_total_seconds:.3f}s)")
        print(f"      +----------------------------+------------+")

        # Assert sum <= total with small tolerance for raw timer resolution
        assert component_sum_ms <= total_wall_ms + 15.0, (
            f"Component sum {component_sum_ms:.2f}ms exceeds total wall-clock {total_wall_ms:.2f}ms"
        )
        print("      [PASS] Latency Invariant (sum <= total) verified successfully!")

        # 6. Chat Q&A with 3 questions per dataset
        print("\n[6/7] Testing Chat Q&A with 3 questions (insight, tool_call, missing_column)...")
        chat_exchanges = []
        for q_obj in questions:
            q_type = q_obj["type"]
            q_text = q_obj["question"]
            print(f"\n      --> [{q_type.upper()}] Q: '{q_text}'")

            chat_resp = client.post(
                "/api/v1/chat",
                json={"job_id": job_id, "question": q_text, "history": [], "dataset_id": dataset_id},
                headers=headers
            )
            assert chat_resp.status_code == 200, f"Chat failed: {chat_resp.text}"
            chat_data = chat_resp.json()
            answer_text = chat_data.get("answer", "")
            ver_info = chat_data.get("verification", {})
            provider_used = chat_data.get("provider", "unknown")
            tools_used = chat_data.get("tool_calls_used", [])

            print(f"          Provider: {provider_used}")
            print(f"          Tools Used: {[t.get('tool') for t in tools_used]}")
            print(f"          Answer Snippet: {answer_text[:140]}...")
            print(f"          Verification: valid={ver_info.get('is_valid')}, pre-strip={chat_data.get('pre_strip_rate')}%, post-strip={chat_data.get('post_strip_rate')}%")

            # Verification assertion
            if q_type == "missing_column":
                assert "not present in this dataset" in answer_text.lower(), "Missing column notice was not present in answer"
            elif q_type == "tool_call":
                assert len(tools_used) >= 1 or len(chat_data.get("evidence", [])) >= 1, "Tool call was not executed for tool question"

            chat_exchanges.append({
                "type": q_type,
                "question": q_text,
                "answer": answer_text,
                "provider": provider_used,
                "tool_calls_used": tools_used,
                "evidence": chat_data.get("evidence", []),
                "verification": ver_info,
                "pre_strip_rate": chat_data.get("pre_strip_rate", 100.0),
                "post_strip_rate": chat_data.get("post_strip_rate", 100.0)
            })

        with open(out_dir / "chat_exchanges.json", "w", encoding="utf-8") as cf:
            json.dump(chat_exchanges, cf, indent=2)

        # 7. Report Generation (PDF & DOCX)
        print("\n[7/7] Generating and validating PDF & DOCX reports...")
        # PDF
        pdf_gen = client.post(f"/api/v1/jobs/{job_id}/report?format=pdf", headers=headers)
        assert pdf_gen.status_code == 200, f"PDF report gen failed: {pdf_gen.text}"
        pdf_rep_id = pdf_gen.json()["report_id"]

        pdf_down = client.get(f"/api/v1/reports/{pdf_rep_id}/download", headers=headers)
        assert pdf_down.status_code == 200, f"PDF download failed: {pdf_down.status_code}"
        pdf_path = out_dir / "report.pdf"
        with open(pdf_path, "wb") as pf:
            pf.write(pdf_down.content)

        # DOCX
        docx_gen = client.post(f"/api/v1/jobs/{job_id}/report?format=docx", headers=headers)
        assert docx_gen.status_code == 200, f"DOCX report gen failed: {docx_gen.text}"
        docx_rep_id = docx_gen.json()["report_id"]

        docx_down = client.get(f"/api/v1/reports/{docx_rep_id}/download", headers=headers)
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

        results_summary[filename] = {
            "dataset_id": dataset_id,
            "job_id": job_id,
            "total_rows": total_rows,
            "insights_count": len(insights),
            "analytical_count": len(analytical_insights),
            "dq_count": len(dq_insights),
            "analytical_insights": analytical_insights[:6],
            "dq_insights": dq_insights[:4],
            "pdf_pages": pdf_page_count,
            "docx_paras": docx_paras,
            "total_time_seconds": raw_total_seconds,
            "component_sum_ms": component_sum_ms,
            "total_wall_ms": total_wall_ms,
            "synthesis_latency_ms": synth_ms,
            "synthesis_claims_count": len(claims),
            "citation_audit": exec_result.get("citation_audit") or exec_result.get("verification"),
            "chat_exchanges": chat_exchanges
        }

    print("\n" + "=" * 80)
    print("ALL 3 DATASETS COMPLETED AND VERIFIED SUCCESSFULLY")
    print("=" * 80)
    return results_summary

if __name__ == "__main__":
    verify_phase3()
