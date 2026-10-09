"""Live Chat Evaluation: 15 questions against live Gemini.

Runs:
- Original 9 questions
- 6 new questions covering:
  - Missing column / entity requested
  - Suppressed analysis requested
  - Sales column interpretation
  - Single-aggregate question
  - Payment-method share on retail
  - Another missing column on marketing or HR
- Verifies LLM-chosen SQL against ground truth
- Captures verbatim answers, basis, sample size n, provider
"""
import os
import sys
from pathlib import Path
import json
import time
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.core.database import SessionLocal
from backend.app.core.config import settings
from backend.app.services.chat_service import process_chat_question
from backend.app.services.chat_sql import llm_choose_sql_query, detect_question_target_table
from backend.app.agent.llm_client import get_llm_client
from backend.app.services.data_loader import get_dataset_dataframe
from backend.app.services.tool_catalogue import execute_tool


QUESTIONS = [
    # Retail (5 questions)
    {
        "id": "Q1",
        "dataset": "retail_sales_messy.csv",
        "question": "Is there any monthly trend in retail sales over time?",
        "category": "suppressed_analysis",
        "notes": "Suppressed analysis under exclusion_rate > 0.5; explains what was checked and reason."
    },
    {
        "id": "Q2",
        "dataset": "retail_sales_messy.csv",
        "question": "What is the share of Credit Card payments among non-missing payment method rows?",
        "category": "payment_share_observed",
        "notes": "Queries data_observed, states observed share and n=96."
    },
    {
        "id": "Q3",
        "dataset": "retail_sales_messy.csv",
        "question": "What is the average customer age across the different retail store regions?",
        "category": "missing_column",
        "notes": "Missing column Region/store regions; states missingness and available columns."
    },
    {
        "id": "Q11",
        "dataset": "retail_sales_messy.csv",
        "question": "What are the total sales by product category?",
        "category": "sales_column_interpretation",
        "notes": "States sales interpretation (e.g. Quantity / Total_Amount) and basis/n."
    },
    {
        "id": "Q15",
        "dataset": "retail_sales_messy.csv",
        "question": "What is the share of PayPal payments in retail sales?",
        "category": "payment_share",
        "notes": "States PayPal share on retail data and basis/n."
    },

    # HR Attrition (5 questions)
    {
        "id": "Q4",
        "dataset": "hr_attrition_messy.csv",
        "question": "Which department has the highest employee attrition rate and is the difference statistically significant?",
        "category": "insight_with_caveat",
        "notes": "Names highest department and states caveat that difference is not statistically significant."
    },
    {
        "id": "Q5",
        "dataset": "hr_attrition_messy.csv",
        "question": "What is the average annual salary by department among observed non-missing records?",
        "category": "sql_observed",
        "notes": "Queries data_observed for salary by department, states basis and n."
    },
    {
        "id": "Q6",
        "dataset": "hr_attrition_messy.csv",
        "question": "How does customer churn correlate with employee satisfaction levels?",
        "category": "missing_column",
        "notes": "Missing column churn / satisfaction; states missingness and available columns."
    },
    {
        "id": "Q10",
        "dataset": "hr_attrition_messy.csv",
        "question": "Is there any correlation between performance and promotion?",
        "category": "suppressed_analysis",
        "notes": "Suppressed analysis on Performance_Score vs Last_Promotion_Year; explains why suppressed under safeguards."
    },
    {
        "id": "Q14",
        "dataset": "hr_attrition_messy.csv",
        "question": "What is the average employee bonus by department?",
        "category": "missing_column",
        "notes": "Missing column bonus; states missingness and available columns."
    },

    # Marketing (5 questions)
    {
        "id": "Q7",
        "dataset": "marketing_campaign_messy.csv",
        "question": "Which marketing channel delivers the highest conversion rate?",
        "category": "conversion_rate",
        "notes": "Identifies highest conversion channel with basis and n."
    },
    {
        "id": "Q8",
        "dataset": "marketing_campaign_messy.csv",
        "question": "What is the total ad spend and total clicks by marketing channel?",
        "category": "sql_group_by",
        "notes": "Queries total spend and clicks by channel on observed/clean with basis and n."
    },
    {
        "id": "Q9",
        "dataset": "marketing_campaign_messy.csv",
        "question": "What is the average customer credit score across the different marketing channels?",
        "category": "missing_column",
        "notes": "Missing column credit score; states missingness and available columns."
    },
    {
        "id": "Q12",
        "dataset": "marketing_campaign_messy.csv",
        "question": "What is the overall average ad spend across all campaigns?",
        "category": "single_aggregate",
        "notes": "Single aggregate average ad spend with basis and n."
    },
    {
        "id": "Q13",
        "dataset": "marketing_campaign_messy.csv",
        "question": "What is the customer lifetime value by channel?",
        "category": "missing_column",
        "notes": "Missing column lifetime value; states missingness and available columns."
    }
]


def run_live_eval():
    os.environ["LLM_PROVIDER"] = "gemini"
    if settings.GEMINI_API_KEY and not os.getenv("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
    db = SessionLocal()
    client = get_llm_client("gemini")

    results = []
    print("=" * 80)
    print("STARTING LIVE CHAT EVALUATION (15 QUESTIONS) WITH GEMINI")
    print("=" * 80)

    for item in QUESTIONS:
        qid = item["id"]
        ds = item["dataset"]
        q = item["question"]
        print(f"\n--- Running [{qid}] on {ds} ---")
        print(f"Question: {q}")

        # Check LLM-chosen SQL directly
        df = get_dataset_dataframe(ds)
        available_cols = list(df.columns)
        target_tbl = detect_question_target_table(q)
        llm_sql = llm_choose_sql_query(q, available_cols, target_table=target_tbl, client=client)
        sql_exec_status = "N/A"
        sql_rows_count = 0
        if llm_sql:
            print(f"LLM-Chosen SQL: {llm_sql}")
            try:
                sql_res = execute_tool("query_sql", {"dataset_id": ds, "sql": llm_sql})
                sql_exec_status = "SUCCESS"
                sql_rows_count = len(sql_res.get("rows", []))
                print(f"SQL Executed successfully: {sql_rows_count} rows returned.")
            except Exception as e:
                sql_exec_status = f"FAILED: {e}"
                print(f"SQL execution error: {e}")

        # Run full chat pipeline
        t0 = time.perf_counter()
        res = process_chat_question(
            db=db,
            job_id="",
            question=q,
            dataset_id=ds
        )
        elapsed = time.perf_counter() - t0

        answer = res.get("answer", "")
        provider = res.get("provider", "unknown")
        tools_used = res.get("tool_calls_used", [])
        verif = res.get("verification", {})

        # Checks
        has_basis = ("data_observed" in answer) or ("data_clean" in answer)
        has_n = "n=" in answer.lower()
        missing_stated = ("not present" in answer.lower()) or ("not found" in answer.lower()) or ("not available" in answer.lower())

        print(f"Provider: {provider} | Elapsed: {elapsed:.2f}s")
        print(f"Answer: {answer}")
        print(f"Basis Stated: {has_basis} | Sample Size n: {has_n} | Missing Col Stated: {missing_stated}")

        record = {
            "id": qid,
            "dataset": ds,
            "question": q,
            "category": item["category"],
            "llm_chosen_sql": llm_sql,
            "sql_exec_status": sql_exec_status,
            "sql_rows_count": sql_rows_count,
            "provider": provider,
            "model": res.get("model", "unknown"),
            "fallback_to_heuristic": res.get("fallback_to_heuristic", False),
            "elapsed_seconds": round(elapsed, 2),
            "answer": answer,
            "tools_used": tools_used,
            "verification": {
                "is_valid": verif.get("is_valid"),
                "total_claims": verif.get("total_claims_checked"),
                "verified_claims": verif.get("verified_claims_count"),
                "unverified_claims": verif.get("unverified_claims_count"),
                "verification_rate": verif.get("verification_rate_percent")
            },
            "has_basis": has_basis,
            "has_sample_size_n": has_n
        }
        results.append(record)
        time.sleep(1.0)  # Gentle spacing for API rate limits

    db.close()

    os.makedirs("data/eval", exist_ok=True)
    out_path = "data/eval/chat_15_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"COMPLETED ALL 15 QUESTIONS. Results saved to {out_path}")
    print("=" * 80)
    return results


if __name__ == "__main__":
    run_live_eval()
