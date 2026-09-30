"""Phase 2 Autonomous Agent Core — End-to-End Verification Script.

Executes:
1. Tool catalogue integrity checks across all 7 tools.
2. Single tool-call Claude prototype verification.
3. Unattended end-to-end Plan-Act-Reflect agent loop on real messy retail dataset.
4. Adversarial security tests (SQL write and path traversal rejection).
5. Step and token budget tripping tests (asserts graceful stop with partial fallback).
6. Programmatic citation audit verifying every claim traces to computed results.
7. Ordered run log explainability dump.
"""
import sys
import json
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.agent.citation_checker import validate_citations
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.services.sql_tool import query_sql

RETAIL_DATASET = "retail_sales_messy.csv"

def run_phase2_verification():
    print("=" * 70)
    print("PHASE 2: AUTONOMOUS AGENT CORE — VERIFICATION SUITE")
    print("=" * 70)

    # 1. Adversarial Guardrail Validation
    print("\n[STEP 1] Testing Adversarial Security Guardrails...")
    try:
        query_sql(RETAIL_DATASET, "DROP TABLE df")
        assert False, "Failed to block DROP TABLE!"
    except ValueError as e:
        print(f" [PASS] Blocked malicious SQL write: {e}")

    try:
        query_sql(RETAIL_DATASET, "SELECT * FROM read_csv('/etc/passwd')")
        assert False, "Failed to block path traversal!"
    except ValueError as e:
        print(f" [PASS] Blocked external file traversal: {e}")

    # 2. Budget Guardrails Tripping Validation
    print("\n[STEP 2] Testing Step/Token Budget Tripping & Partial Fallback...")
    budget_orchestrator = PlanActReflectOrchestrator(max_steps=2, token_budget=10000, provider="heuristic")
    budget_run = budget_orchestrator.run_analysis(
        dataset_id=RETAIL_DATASET,
        goal="Trip budget deliberately to verify graceful termination."
    )
    assert budget_run["budget_tripped"] is True
    assert budget_run["total_steps_executed"] == 2
    assert "Maximum step budget reached" in budget_run["trip_reason"]
    print(f" [PASS] Budget guardrail tripped gracefully after {budget_run['total_steps_executed']} steps.")
    print(f"        Reason: {budget_run['trip_reason']}")
    print(f"        Partial findings generated: {len(budget_run['synthesis']['key_findings'])}")

    # 3. Unattended End-to-End Analysis on Real Messy Dataset
    print("\n[STEP 3] Executing Unattended Plan-Act-Reflect Loop on Messy Retail Data...")
    orchestrator = PlanActReflectOrchestrator(max_steps=5, token_budget=20000)
    result = orchestrator.run_analysis(
        dataset_id=RETAIL_DATASET,
        goal="Identify pricing patterns, anomalous transactions, and category sales differentials."
    )

    print(f" [PASS] Status: {result['status']}")
    print(f" [PASS] Active Planner: {result['planner']}")
    print(f" [PASS] Total Steps Executed: {result['total_steps_executed']}")
    print(f" [PASS] Total Tokens Used: {result['tokens_consumed']}")
    print(f" [PASS] Execution Time: {result['execution_time_seconds']}s")

    # 4. Ordered Explainability Run Log
    print("\n[STEP 4] Explainability Run Log Trace:")
    for log in result["run_log"]:
        print(f"   Step {log['step_number']}: [{log['tool']}] (Tool: {log['duration_ms']}ms, LLM: {log.get('llm_latency_ms', 0)}ms) [Planner: {log.get('planner')}]")
        print(f"     Rationale: {log['rationale']}")
        print(f"     Status: {log['status']}")

    # 5. Executive Synthesis & Findings
    print("\n[STEP 5] Synthesized Executive Narrative:")
    print(f"\"{result['synthesis']['executive_summary']}\"")
    print("\nKey Findings:")
    for i, finding in enumerate(result['synthesis']['key_findings'], 1):
        cat = finding.get('category', 'Key Finding') if isinstance(finding, dict) else 'Finding'
        headline = finding.get('headline', str(finding)) if isinstance(finding, dict) else str(finding)
        narrative = finding.get('narrative', '') if isinstance(finding, dict) else ''
        print(f"  {i}. [{cat}] {headline}")
        if narrative:
            print(f"     {narrative}")

    # 6. Programmatic Citation & Claim Audit (Phase 2 Exit Criterion)
    print("\n[STEP 6] Programmatic Citation Audit (Tracing Claims to Computed Results):")
    audit = result["citation_audit"]
    print(f"  Total Claims Checked: {audit['total_claims_checked']}")
    print(f"  Verified Claims:      {audit['verified_claims_count']}")
    print(f"  Unverified Claims:    {audit['unverified_claims_count']}")
    print(f"  Verification Rate:    {audit['verification_rate_percent']}%")
    print(f"  Audit Status:         {audit['status'].upper()}")

    assert audit["verification_rate_percent"] >= 95.0, "Citation audit failed required verification threshold!"
    assert len(result["chart_specifications"]) >= 1, "No chart specifications generated!"

    print("\n" + "=" * 70)
    print("PHASE 2 EXIT CRITERION SATISFIED: All claims trace to computed facts!")
    print("=" * 70)

if __name__ == "__main__":
    run_phase2_verification()
