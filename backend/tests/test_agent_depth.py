"""Tests for multi-round Agent Depth (Plan-Act-Reflect up to 3 rounds)."""
import pytest
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.agent.llm_client import HeuristicClient, ReflectResult, ToolCall, TokenUsage

def test_multi_round_agent_depth_logging():
    """Verify that multi-round reflection executes up to 3 rounds, logging round, reflection, and follow_ups."""
    class MultiRoundMockClient(HeuristicClient):
        def __init__(self):
            super().__init__()
            self.reflect_count = 0

        def reflect(self, step_result, history, dataset_id, tools=None):
            self.reflect_count += 1
            if self.reflect_count <= 2:
                # Return follow-up tool call
                return ReflectResult(
                    tool_calls=[
                        ToolCall(
                            name="query_sql",
                            arguments={"dataset_id": dataset_id, "sql": "SELECT COUNT(*) as total_rows FROM df"},
                            rationale=f"Round {self.reflect_count} follow-up drilldown"
                        )
                    ],
                    should_continue=True,
                    observation=f"Reflection observation for round {self.reflect_count}",
                    usage=TokenUsage(total_tokens="unknown"),
                    provider=self.provider_name,
                    latency_seconds=0.01
                )
            # Round 3 reflection stops
            return ReflectResult(
                tool_calls=[],
                should_continue=False,
                observation="Satisfied with evidence, stopping search.",
                usage=TokenUsage(total_tokens="unknown"),
                provider=self.provider_name,
                latency_seconds=0.01
            )

    orchestrator = PlanActReflectOrchestrator(
        max_steps=10,
        token_budget=50000,
        llm_client=MultiRoundMockClient()
    )

    result = orchestrator.run_analysis(
        dataset_id="retail_sales_messy.csv",
        goal="Examine multi-round drilldown capability."
    )

    assert result["status"] == "completed"
    run_log = result["run_log"]
    assert len(run_log) > 0

    # Verify rounds logged
    rounds_present = {step.get("round") for step in run_log}
    assert 1 in rounds_present
    assert 2 in rounds_present

    # Verify reflection and follow_ups fields exist in run_log entries
    for step in run_log:
        assert "round" in step
        assert "reflection" in step
        assert "follow_ups" in step
