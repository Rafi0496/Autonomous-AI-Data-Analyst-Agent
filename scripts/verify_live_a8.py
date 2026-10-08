"""Live Verification Script for Task A8.

Runs with LLM_PROVIDER=gemini:
1. 4 chat questions per dataset (3 original + 1 unseen).
2. One full agent run per dataset.
3. Prints provider, model, tools used, rounds table, tokens, and token budget limit used in the HR run and whether the guard tripped.
"""
import os
import sys
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Ensure LLM_PROVIDER is gemini
os.environ["LLM_PROVIDER"] = "gemini"

from backend.app.core.database import SessionLocal
from backend.app.agent.llm_client import get_llm_client
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.services.chat_service import process_chat_question

DATASETS_CONFIG = [
    {
        "name": "Retail Sales Messy",
        "dataset_id": "retail_sales_messy.csv",
        "goal": "Analyze product category performance, pricing patterns, and anomalous transactions.",
        "chat_questions": [
            "What is the total quantity sold?",
            "What are the sales by region?",
            "Is there any trend in sales over time?",
            "number of transactions per region"  # unseen
        ],
        "token_budget": 35000
    },
    {
        "name": "HR Workforce Attrition Messy",
        "dataset_id": "hr_attrition_messy.csv",
        "goal": "Examine department attrition rates, salary distributions across observed records, and performance promotion correlations.",
        "chat_questions": [
            "Which department has the highest attrition rate?",
            "What is the average salary by department?",
            "Is there any correlation between performance and promotion?",
            "average annual salary by department among observed records"  # unseen
        ],
        # HR token budget: test with default budget 20000 (earlier run consumed 30,041 tokens)
        "token_budget": 20000
    },
    {
        "name": "Marketing Campaign Messy",
        "dataset_id": "marketing_campaign_messy.csv",
        "goal": "Identify top performing marketing channels, spend efficiency, and correlation between ad spend and clicks.",
        "chat_questions": [
            "Which channel had the highest conversion rate?",
            "What was the total ad spend by channel?",
            "Is there a correlation between ad spend and clicks?",
            "total ad spend and total clicks by channel"  # unseen
        ],
        "token_budget": 35000
    }
]

def main():
    print("=" * 80)
    print("  TASK A8: LIVE VERIFICATION (LLM_PROVIDER=gemini)")
    print("=" * 80)

    client = get_llm_client(provider="gemini", allow_heuristic_fallback=False)
    provider_name = client.provider_name
    model_name = getattr(client, "model", "gemini-3.1-flash-lite")
    print(f"Provider: {provider_name}")
    print(f"Model:    {model_name}")
    print("=" * 80)

    db = SessionLocal()

    for ds_idx, ds in enumerate(DATASETS_CONFIG, 1):
        print(f"\n{'#' * 80}")
        print(f"  DATASET {ds_idx}/3: {ds['name']} ({ds['dataset_id']})")
        print(f"{'#' * 80}")

        # 1. 4 Chat Questions
        print(f"\n--- [1] 4 CHAT QUESTIONS ({ds['dataset_id']}) ---")
        for q_idx, q in enumerate(ds["chat_questions"], 1):
            unseen_tag = " [UNSEEN]" if q_idx == 4 else ""
            print(f"\nQuestion {q_idx}/4{unseen_tag}: '{q}'")
            try:
                t0 = time.time()
                chat_res = process_chat_question(
                    db=db,
                    job_id="",
                    question=q,
                    dataset_id=ds["dataset_id"]
                )
                dt = time.time() - t0
                print(f"  LLM Provider: {provider_name}")
                print(f"  Model:        {model_name}")
                print(f"  Latency:      {dt:.2f}s")
                print(f"  Tool Used:    {chat_res.get('tool_called', 'None')}")
                print(f"  Status:       {chat_res.get('status')}")
                print(f"  Verbatim Answer:\n    {chat_res.get('answer')}")
                verif = chat_res.get("verification") or {}
                print(f"  Verification: valid={verif.get('is_valid')}, checked={verif.get('total_claims_checked')}, verified={verif.get('verified_claims_count')}")
            except Exception as e:
                print(f"  ERROR executing chat question: {e}")

        # 2. Full Agent Run
        print(f"\n--- [2] FULL AGENT RUN ({ds['dataset_id']}) ---")
        token_budget = ds["token_budget"]
        print(f"  Goal:         {ds['goal']}")
        print(f"  Token Budget: {token_budget} tokens")

        try:
            t0 = time.time()
            orch = PlanActReflectOrchestrator(
                max_steps=4,
                token_budget=token_budget,
                llm_client=client
            )
            result = orch.run_analysis(dataset_id=ds["dataset_id"], goal=ds["goal"])
            dt = time.time() - t0

            print(f"  Execution Time:      {dt:.2f}s")
            print(f"  LLM Provider:        {provider_name}")
            print(f"  Model:               {model_name}")
            print(f"  Status:              {result.get('status')}")
            print(f"  Total Steps:         {result.get('total_steps_executed')}")
            print(f"  Tokens Consumed:     {result.get('tokens_consumed'):,}")
            print(f"  Token Budget Limit:  {token_budget:,}")
            print(f"  Budget Tripped:      {result.get('budget_tripped', False)}")
            if result.get("trip_reason"):
                print(f"  Trip Reason:         {result.get('trip_reason')}")

            # Rounds table
            print("\n  ROUNDS TABLE (from run_log):")
            print("  | Round | Tool Name | Tool Arguments | Status | Duration (ms) |")
            print("  |---|---|---|---|---|")
            for step in result.get("run_log", []):
                s_idx = step.get("step")
                tool_name = step.get("tool")
                args_str = json.dumps(step.get("tool_args", {}))
                if len(args_str) > 40:
                    args_str = args_str[:37] + "..."
                s_status = step.get("status")
                s_dur = step.get("duration_ms", 0.0)
                print(f"  | {s_idx} | `{tool_name}` | `{args_str}` | {s_status} | {s_dur:.1f}ms |")

            if result.get("rounds_table"):
                print("\n  PLAN-ACT-REFLECT ROUNDS SUMMARY:")
                for r in result.get("rounds_table", []):
                    print(f"    - Round {r.get('round')}: tools={r.get('tools')}, reason={r.get('reason')}")

            # Insights summary
            print(f"\n  Total Insights Generated: {len(result.get('insights', []))}")
            for ins in result.get("insights", [])[:3]:
                print(f"    - [{ins.get('type')}] {ins.get('headline')}")

            # Executive summary excerpt
            synth = result.get("synthesis", {})
            summary_text = synth.get("executive_summary", "")
            print(f"\n  Executive Summary Excerpt:\n    {summary_text[:300]}...")

        except Exception as e:
            print(f"  ERROR executing agent run: {e}")

    db.close()
    print("\n" + "=" * 80)
    print("  TASK A8 COMPLETED SUCCESSFULLY")
    print("=" * 80)

if __name__ == "__main__":
    main()
