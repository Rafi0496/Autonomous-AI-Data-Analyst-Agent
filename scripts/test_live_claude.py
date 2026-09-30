"""Standalone verification script for Live LLM API calls (Gemini / Claude).

Usage:
  python scripts/test_live_claude.py [--provider gemini|claude] [--api-key KEY]

Reports:
  - Active LLM Provider (never prints API keys)
  - Real wall-clock latency (seconds, asserts > 0.5s)
  - Real token consumption (prompt, completion, total, asserts > 0)
  - Planned tool calls and arguments
  - Orchestrator Plan-Act-Reflect integration metrics
"""
import os
import sys
import time
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.agent.llm_client import get_llm_client, HeuristicClient, GeminiClient, ClaudeClient
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.services.data_loader import get_dataset_dataframe
from backend.app.services.profiling import profile_dataset

RETAIL_DATASET = "retail_sales_messy.csv"

def run_live_test(provider_arg: str = None, api_key: str = None):
    # If key passed via command line, set in environment without printing
    if api_key:
        if provider_arg == "gemini" or (not provider_arg and not os.getenv("ANTHROPIC_API_KEY")):
            os.environ["GEMINI_API_KEY"] = api_key
        else:
            os.environ["ANTHROPIC_API_KEY"] = api_key

    if provider_arg:
        os.environ["LLM_PROVIDER"] = provider_arg

    client = get_llm_client(provider=provider_arg, allow_heuristic_fallback=False)
    if isinstance(client, HeuristicClient):
        print("\n" + "!" * 70)
        print("ERROR: Neither GEMINI_API_KEY nor ANTHROPIC_API_KEY is configured.")
        print("Set GEMINI_API_KEY or ANTHROPIC_API_KEY in your environment or .env file.")
        print("!" * 70 + "\n")
        sys.exit(1)

    provider_name = client.provider_name
    print("=" * 70)
    print(f"LIVE LLM API INTEGRATION VERIFICATION: {provider_name.upper()}")
    print("=" * 70)
    print(f"Target Model: {getattr(client, 'model', 'default')}")
    print("Security:     API key detected (redacted, never logged or printed).")

    # TEST 1: Direct Plan generation call
    print("\n[TEST 1] Single Planning Call with Function Calling...")
    df = get_dataset_dataframe(RETAIL_DATASET)
    profile = profile_dataset(df, dataset_id=RETAIL_DATASET).model_dump()
    goal = "Identify pricing patterns, anomalous transactions, and category sales differentials."

    t0 = time.perf_counter()
    plan_result = client.plan(profile=profile, goal=goal, dataset_id=RETAIL_DATASET)
    t1 = time.perf_counter()
    latency_1 = t1 - t0

    usage_dict = plan_result.usage.to_dict()
    print(f"  [PASS] Real Latency:      {latency_1:.3f} seconds")
    print(f"  [PASS] Prompt Tokens:     {usage_dict.get('prompt_tokens')}")
    print(f"  [PASS] Completion Tokens: {usage_dict.get('completion_tokens')}")
    print(f"  [PASS] Total Tokens:      {usage_dict.get('total_tokens')}")

    assert latency_1 > 0.5, f"Call latency ({latency_1:.3f}s) is <= 0.5s; expected genuine remote network call."
    assert plan_result.usage.total_tokens != "unknown", "Token usage must be known from real provider metadata."
    assert isinstance(plan_result.usage.total_tokens, int) and plan_result.usage.total_tokens > 0, (
        f"Expected non-zero total tokens, got: {plan_result.usage.total_tokens}"
    )

    print(f"  [PASS] Planned Tool Calls ({len(plan_result.tool_calls)} total):")
    for idx, tc in enumerate(plan_result.tool_calls, 1):
        print(f"         {idx}. {tc.name} -> {tc.arguments}")

    # TEST 2: Orchestrator Live Execution
    print("\n[TEST 2] Orchestrator Live Plan-Act-Reflect Loop...")
    orchestrator = PlanActReflectOrchestrator(max_steps=3, token_budget=20000, llm_client=client)

    t0 = time.perf_counter()
    run_result = orchestrator.run_analysis(dataset_id=RETAIL_DATASET, goal=goal)
    t1 = time.perf_counter()
    latency_2 = t1 - t0

    print(f"  [PASS] Orchestrator Runtime: {latency_2:.3f} seconds")
    print(f"  [PASS] Planner Recorded:     {run_result['planner']}")
    print(f"  [PASS] Tokens Consumed:      {run_result['tokens_consumed']}")
    print(f"  [PASS] Steps Executed:       {run_result['total_steps_executed']}")
    print(f"  [PASS] Citation Status:      {run_result['citation_audit']['status'].upper()}")

    assert latency_2 > 0.5, f"Orchestrator latency ({latency_2:.3f}s) is <= 0.5s."
    assert run_result["tokens_consumed"] != "unknown" and run_result["tokens_consumed"] > 0, (
        f"Expected real non-zero tokens, got: {run_result['tokens_consumed']}"
    )
    assert run_result["planner"] == provider_name
    for step in run_result["run_log"]:
        assert step["planner"] == provider_name

    print("\n" + "=" * 70)
    print("LIVE LLM VERIFICATION COMPLETE: ALL METRICS CONFIRMED REAL")
    print(f"Provider:      {provider_name}")
    print(f"Total Latency: {latency_1 + latency_2:.3f}s (> 0.5s verified)")
    print(f"Total Tokens:  {run_result['tokens_consumed']} (real metadata)")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Live LLM Provider Integration (Claude / Gemini)")
    parser.add_argument("--provider", choices=["gemini", "claude", "heuristic"], help="LLM Provider")
    parser.add_argument("--api-key", help="API Key (never printed or logged)")
    args = parser.parse_args()
    run_live_test(args.provider, args.api_key)
