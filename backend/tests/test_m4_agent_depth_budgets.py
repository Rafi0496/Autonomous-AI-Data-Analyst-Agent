"""Targeted Unit and Integration Tests for Milestone 4: Agent Depth and Budgets.

Tests:
a) Deterministic candidate follow-ups after each round:
   - segment p < 0.05 -> drill down by second categorical
   - outlier rate > 5% in a column -> inspect that column
   - |r| > 0.5 -> check pair by segment
   - When nothing triggers: reflector picks 0 follow-ups (stops).
b) Token and step budgets stop the run and return partial findings:
   - Proves a lower token budget trips guardrail and returns partial findings.
   - Proves lower step budget trips guardrail and returns partial findings.
c) Rounds table (round, tools, reason) recorded for all 3 datasets, explicitly stating where no trigger fired.
"""
import pytest
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.agent.follow_up_triggers import compute_candidate_follow_ups
from backend.app.agent.llm_client import HeuristicClient, TokenUsage, PlanResult, ToolCall


def test_deterministic_follow_up_triggers():
    """Verify deterministic candidate follow-up triggers."""
    profile = {
        "columns": {
            "Department": {"inferred_type": "categorical", "unique_count": 4},
            "Gender": {"inferred_type": "categorical", "unique_count": 2},
            "Annual_Salary": {"inferred_type": "numeric", "unique_count": 100},
            "Age": {"inferred_type": "numeric", "unique_count": 40},
            "Performance_Score": {"inferred_type": "numeric", "unique_count": 5}
        },
        "row_count": 100
    }

    # Trigger 1: Segment p < 0.05
    results_sig_seg = [
        {
            "tool": "segment_compare",
            "segment_column": "Department",
            "metric_column": "Annual_Salary",
            "p_value": 0.0123
        }
    ]
    cand1, reas1 = compute_candidate_follow_ups(results_sig_seg, profile, "test_ds")
    assert len(cand1) == 1
    assert "Gender" in cand1[0].arguments["sql"]
    assert "p=0.0123 < 0.05" in reas1[0]

    # Trigger 2: Outlier rate > 5%
    results_outliers = [
        {
            "tool": "detect_outliers",
            "total_records": 100,
            "top_outlier_columns": [
                {"column": "Annual_Salary", "count": 12, "outlier_rate": 0.12}
            ]
        }
    ]
    cand2, reas2 = compute_candidate_follow_ups(results_outliers, profile, "test_ds")
    assert len(cand2) == 1
    assert "Annual_Salary" in cand2[0].arguments["sql"]
    assert "outlier rate 12.0% > 5%" in reas2[0]

    # Trigger 3: |r| > 0.5
    results_corr = [
        {
            "tool": "run_correlation",
            "correlation": 0.78,
            "column1": "Age",
            "column2": "Annual_Salary"
        }
    ]
    cand3, reas3 = compute_candidate_follow_ups(results_corr, profile, "test_ds")
    assert len(cand3) == 1
    assert "Age" in cand3[0].arguments["sql"]
    assert "|r|=0.78 > 0.5" in reas3[0]

    # Nothing triggers
    results_none = [
        {
            "tool": "segment_compare",
            "segment_column": "Department",
            "metric_column": "Annual_Salary",
            "p_value": 0.4567
        },
        {
            "tool": "run_correlation",
            "correlation": 0.12,
            "column1": "Age",
            "column2": "Annual_Salary"
        },
        {
            "tool": "detect_outliers",
            "total_records": 100,
            "top_outlier_columns": [
                {"column": "Annual_Salary", "count": 2, "outlier_rate": 0.02}
            ]
        }
    ]
    cand_none, reas_none = compute_candidate_follow_ups(results_none, profile, "test_ds")
    assert len(cand_none) == 0
    assert len(reas_none) == 0


def test_rounds_table_records_and_no_trigger_explicit():
    """Verify rounds table (round, tools, reason) recorded for all 3 datasets, stating where no trigger fired."""
    datasets = ["hr_attrition_messy.csv", "marketing_campaign_messy.csv", "retail_sales_messy.csv"]
    
    for ds in datasets:
        orch = PlanActReflectOrchestrator(max_steps=5, provider="heuristic")
        res = orch.run_analysis(dataset_id=ds)
        rounds_table = res.get("rounds_table", [])
        assert len(rounds_table) >= 2
        
        # Verify Round 1 format
        r1 = rounds_table[0]
        assert r1["round"] == 1
        assert len(r1["tools"]) >= 2
        assert "Initial planned" in r1["reason"]
        
        # Verify Round 2 explicit reason
        r2 = rounds_table[1]
        assert r2["round"] == 2
        assert "reason" in r2
        if ds in ("hr_attrition_messy.csv", "retail_sales_messy.csv"):
            assert len(r2["tools"]) == 0
            assert "No trigger fired" in r2["reason"]
        elif ds == "marketing_campaign_messy.csv":
            assert len(r2["tools"]) > 0
            assert "outlier rate" in r2["reason"]


def test_step_budget_trips_and_returns_partial_findings():
    """Prove that a lower step budget trips the guardrail and returns partial findings."""
    orch = PlanActReflectOrchestrator(max_steps=2, provider="heuristic")
    result = orch.run_analysis(dataset_id="retail_sales_messy.csv")
    
    assert result["budget_tripped"] is True
    assert result["status"] == "budget_tripped"
    assert "Maximum step budget reached" in result["trip_reason"]
    assert result["total_steps_executed"] == 2
    assert len(result["run_log"]) == 2
    
    # Partial findings returned
    assert "synthesis" in result
    assert len(result["synthesis"]["key_findings"]) >= 1
    assert len(result["insights"]) >= 1


def test_token_budget_trips_and_returns_partial_findings():
    """Prove that a lower token budget trips the guardrail and returns partial findings."""
    class HRSimulatedTokenClient(HeuristicClient):
        def __init__(self):
            super().__init__()
            self.step = 0
            
        def plan(self, profile, goal, dataset_id, tools=None):
            res = super().plan(profile, goal, dataset_id, tools)
            # Simulated planning tokens
            res.usage = TokenUsage(prompt_tokens=15000, completion_tokens=1000, total_tokens=16000)
            return res

        def reflect(self, step_result, history, dataset_id, tools=None, candidates=None, candidate_reasons=None):
            res = super().reflect(step_result, history, dataset_id, tools, candidates, candidate_reasons)
            # Simulated reflection tokens bringing total over 30,000
            res.usage = TokenUsage(prompt_tokens=14000, completion_tokens=1041, total_tokens=15041)
            return res

    # Total tokens simulated across plan + reflect = 31,041 (representing the 30,041 HR run)
    # With a lower budget of 20,000 tokens, the guardrail MUST trip after step 1
    orch = PlanActReflectOrchestrator(
        max_steps=10,
        token_budget=20000,
        llm_client=HRSimulatedTokenClient()
    )
    result = orch.run_analysis(dataset_id="hr_attrition_messy.csv")

    assert result["budget_tripped"] is True
    assert result["status"] == "budget_tripped"
    assert "Token budget exceeded" in result["trip_reason"]
    assert result["tokens_consumed"] >= 20000
    assert result["total_steps_executed"] >= 1
    
    # Partial findings returned
    assert "synthesis" in result
    assert len(result["synthesis"]["key_findings"]) >= 1
    assert len(result["insights"]) >= 1


def test_planted_s1_effect_triggers_round2_drilldown():
    """Verify that a planted S1 effect (p < 0.05) triggers a round-2 drill-down tool call."""
    profile = {
        "columns": {
            "cohort": {"inferred_type": "categorical", "unique_count": 3},
            "decoy_cat": {"inferred_type": "categorical", "unique_count": 3},
            "metric_score": {"inferred_type": "numeric", "unique_count": 500},
            "var_x": {"inferred_type": "numeric", "unique_count": 500}
        },
        "row_count": 2000
    }

    # Planted S1 finding (Cohen's d ~ 0.8, p < 0.001)
    executed_s1 = [
        {
            "tool": "segment_compare",
            "segment_column": "cohort",
            "metric_column": "metric_score",
            "p_value": 0.0001,
            "status": "success"
        }
    ]

    candidates, reasons = compute_candidate_follow_ups(
        executed_results=executed_s1,
        profile=profile,
        dataset_id="planted_seed_1"
    )

    assert len(candidates) >= 1, "Expected candidate follow-up for significant segment effect"
    assert any("p=0.0001 < 0.05" in r or "segment p=" in r for r in reasons)
    s1_candidate = candidates[0]
    assert s1_candidate.name == "query_sql"
    assert "cohort" in s1_candidate.arguments["sql"]
    assert "decoy_cat" in s1_candidate.arguments["sql"]
    assert "avg_metric_score" in s1_candidate.arguments["sql"]
