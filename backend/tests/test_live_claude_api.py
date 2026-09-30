"""Dedicated Integration Test for Live LLM Provider (Claude or Gemini).

Runs against whichever provider has a key set (GEMINI_API_KEY or ANTHROPIC_API_KEY).
Measures real API latency and real token consumption, asserting that:
1. Live network call to provider completes successfully.
2. Real latency exceeds 0.5s (genuine network round-trip time, not a mock).
3. Real non-zero token usage is reported by the provider.
4. Function calling selects valid tools and schema arguments.
5. PlanActReflectOrchestrator generates an ordered plan with real token accounting.
"""
import os
import time
import pytest
from backend.app.agent.llm_client import get_llm_client, HeuristicClient, GeminiClient, ClaudeClient
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.services.data_loader import get_dataset_dataframe
from backend.app.services.profiling import profile_dataset
from backend.app.services.tool_catalogue import CANONICAL_TOOL_DEFINITIONS

RETAIL_DATASET = "retail_sales_messy.csv"

def get_active_provider_and_client():
    """Detect whichever provider has an active key set."""
    client = get_llm_client(allow_heuristic_fallback=False)
    if isinstance(client, HeuristicClient):
        return None, None
    return client.provider_name, client

@pytest.mark.live
def test_live_llm_api_call_and_latency():
    """Verify live LLM API connection, tool use, real latency (>0.5s), and non-zero tokens."""
    try:
        provider_name, client = get_active_provider_and_client()
    except Exception as e:
        pytest.skip(f"No active provider key available: {e}")

    if not client:
        pytest.skip(
            "Neither GEMINI_API_KEY nor ANTHROPIC_API_KEY is set with a valid key. "
            "Set GEMINI_API_KEY or ANTHROPIC_API_KEY in your environment/.env to execute this live test."
        )

    df = get_dataset_dataframe(RETAIL_DATASET)
    profile = profile_dataset(df, dataset_id=RETAIL_DATASET).model_dump()

    prompt_goal = "Identify pricing patterns and detect anomalous transactions."

    t_start = time.perf_counter()
    plan_result = client.plan(
        profile=profile,
        goal=prompt_goal,
        dataset_id=RETAIL_DATASET
    )
    latency_sec = time.perf_counter() - t_start

    print(f"\n{'=' * 60}")
    print(f"[LIVE LLM API TEST] Active Provider: {provider_name}")
    print(f"[LIVE LLM API TEST] Real Latency:    {latency_sec:.3f} seconds")
    print(f"[LIVE LLM API TEST] Token Usage:     {plan_result.usage.to_dict()}")
    print(f"[LIVE LLM API TEST] Planned Tools:   {[t.name for t in plan_result.tool_calls]}")
    print(f"{'=' * 60}")

    # Core requirements assertions:
    # 1. Assert real latency > 0.5s
    assert latency_sec > 0.5, (
        f"API latency was {latency_sec:.3f}s; must exceed 0.5s to prove genuine remote round-trip."
    )

    # 2. Assert real non-zero token usage
    assert plan_result.usage.total_tokens != "unknown", "Token usage must be known from provider metadata."
    assert isinstance(plan_result.usage.total_tokens, int) and plan_result.usage.total_tokens > 0, (
        f"Expected non-zero total tokens, got: {plan_result.usage.total_tokens}"
    )

    # 3. Assert tool calls returned
    assert len(plan_result.tool_calls) >= 1, "Expected at least one tool call planned by live model."
    catalogue_names = {t["name"] for t in CANONICAL_TOOL_DEFINITIONS}
    for tc in plan_result.tool_calls:
        assert tc.name in catalogue_names, f"Unknown tool returned: {tc.name}"

@pytest.mark.live
def test_live_llm_orchestrator_planning():
    """Verify PlanActReflectOrchestrator produces plan with live LLM, asserting latency > 0.5s and real tokens."""
    try:
        provider_name, client = get_active_provider_and_client()
    except Exception as e:
        pytest.skip(f"No active provider key available: {e}")

    if not client:
        pytest.skip(
            "Neither GEMINI_API_KEY nor ANTHROPIC_API_KEY is set. "
            "Set GEMINI_API_KEY or ANTHROPIC_API_KEY to run live orchestrator planning."
        )

    orchestrator = PlanActReflectOrchestrator(max_steps=3, token_budget=20000, llm_client=client)

    t_start = time.perf_counter()
    result = orchestrator.run_analysis(
        dataset_id=RETAIL_DATASET,
        goal="Identify pricing patterns, anomalous transactions, and category differentials."
    )
    total_latency = time.perf_counter() - t_start

    print(f"\n{'=' * 60}")
    print(f"[LIVE ORCHESTRATOR TEST] Provider:          {result['planner']}")
    print(f"[LIVE ORCHESTRATOR TEST] Execution Latency: {total_latency:.3f} seconds")
    print(f"[LIVE ORCHESTRATOR TEST] Tokens Consumed:   {result['tokens_consumed']}")
    print(f"[LIVE ORCHESTRATOR TEST] Steps Executed:    {result['total_steps_executed']}")
    print(f"[LIVE ORCHESTRATOR TEST] Citation Status:   {result['citation_audit']['status']}")
    print(f"{'=' * 60}")

    # Core requirements assertions:
    # 1. Assert real latency > 0.5s
    assert total_latency > 0.5, f"Orchestrator finished in {total_latency:.3f}s; must exceed 0.5s."

    # 2. Assert non-zero token usage
    assert result["tokens_consumed"] != "unknown", "Expected real tokens reported from provider."
    assert isinstance(result["tokens_consumed"], int) and result["tokens_consumed"] > 0, (
        f"Expected non-zero tokens consumed, got: {result['tokens_consumed']}"
    )

    # 3. Assert planner label recorded in run log
    assert result["planner"] == provider_name
    for step_log in result["run_log"]:
        assert step_log["planner"] == provider_name

    # 4. Assert citation verification rate
    assert result["citation_audit"]["verification_rate_percent"] >= 95.0
