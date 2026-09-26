"""Plan-Act-Reflect Orchestration Engine for Autonomous Data Analysis.

Implements:
1. Plan: Structured multi-step task planning over dataset profile + user goal
2. Act: Real execution of closed-catalogue tool calls
3. Reflect: Iterative observation, bounded re-planning, and strict guardrails
4. Synthesize: Plain-language executive report, Plotly charts, and citation verification
5. Run Log: Ordered explainability trace stored per session
"""
import os
import time
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import pandas as pd

from backend.app.agent.citation_checker import validate_citations
from backend.app.core.database import SessionLocal
from backend.app.models.job import AnalysisJob
from backend.app.services.charts import generate_chart
from backend.app.services.data_loader import get_dataset_dataframe
from backend.app.services.profiling import profile_dataset
from backend.app.services.summary import write_summary
from backend.app.services.tool_catalogue import (
    CLAUDE_TOOL_DEFINITIONS,
    execute_tool
)

class PlanActReflectOrchestrator:
    def __init__(
        self,
        max_steps: int = 5,
        token_budget: int = 15000,
        timeout_seconds: float = 45.0,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ):
        self.max_steps = max_steps
        self.token_budget = token_budget
        self.timeout_seconds = timeout_seconds
        self.progress_callback = progress_callback
        self.tokens_used = 0
        self.step_count = 0
        self.start_time = 0.0
        self.run_log: List[Dict[str, Any]] = []
        self.budget_tripped = False
        self.trip_reason = ""

    def _emit_progress(self, message: str, step_index: int = 0):
        if self.progress_callback:
            try:
                self.progress_callback(message, step_index)
            except Exception:
                pass

    def _generate_heuristic_plan(
        self,
        profile: Dict[str, Any],
        dataset_id: str,
        goal: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate an ordered initial plan based on profile diagnostics and semantic cues.
        Used as primary planning strategy or fallback when Anthropic API key is absent.
        """
        plan = []
        columns = profile.get("columns", {})
        num_cols = [c for c, p in columns.items() if p.get("inferred_type") == "numeric"]
        cat_cols = [c for c, p in columns.items() if p.get("inferred_type") in ("categorical", "text")]
        date_cols = [c for c, p in columns.items() if p.get("inferred_type") == "datetime"]
        
        # 1. First step: Outlier detection
        if num_cols:
            plan.append({
                "step": 1,
                "tool": "detect_outliers",
                "arguments": {"dataset_id": dataset_id, "method": "iqr", "columns": num_cols},
                "rationale": "Identify statistical anomalies and extreme values that could distort analytical aggregates."
            })

        # 2. Second step: Correlation analysis
        if len(num_cols) >= 2:
            plan.append({
                "step": len(plan) + 1,
                "tool": "run_correlation",
                "arguments": {"dataset_id": dataset_id, "columns": num_cols, "threshold": 0.3},
                "rationale": "Measure pairwise linear associations across quantitative features to surface dependencies."
            })

        # 3. Third step: Segment comparison
        if cat_cols and num_cols:
            plan.append({
                "step": len(plan) + 1,
                "tool": "segment_compare",
                "arguments": {"dataset_id": dataset_id, "segment_column": cat_cols[0], "metric_column": num_cols[0]},
                "rationale": f"Compare distribution of '{num_cols[0]}' across key segment '{cat_cols[0]}'."
            })

        # 4. Fourth step: Chronological Trend
        if date_cols and num_cols:
            plan.append({
                "step": len(plan) + 1,
                "tool": "trend_analysis",
                "arguments": {"dataset_id": dataset_id, "date_column": date_cols[0], "value_column": num_cols[0]},
                "rationale": f"Evaluate rolling trajectory of '{num_cols[0]}' across chronological index '{date_cols[0]}'."
            })

        return plan

    def _call_claude_planner(
        self,
        profile: Dict[str, Any],
        dataset_id: str,
        goal: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Call Claude API for multi-step plan generation with function calling."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key or api_key.startswith("your-") or api_key == "dummy":
            return self._generate_heuristic_plan(profile, dataset_id, goal)

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            prompt = (
                f"You are an autonomous senior data analyst. You have access to a tool catalogue.\n"
                f"Dataset Profile:\n{json.dumps(profile, indent=2)}\n\n"
                f"User Goal: {goal or 'Comprehensive exploratory analysis'}\n"
                f"Return an ordered plan of 2 to 4 tool calls with dataset_id='{dataset_id}' and explicit arguments."
            )
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                tools=CLAUDE_TOOL_DEFINITIONS,
                messages=[{"role": "user", "content": prompt}]
            )
            
            self.tokens_used += response.usage.input_tokens + response.usage.output_tokens
            
            plan = []
            for block in response.content:
                if block.type == "tool_use":
                    plan.append({
                        "step": len(plan) + 1,
                        "tool": block.name,
                        "arguments": block.input,
                        "rationale": f"Claude tool selection: {block.name}"
                    })
                    
            if plan:
                return plan
        except Exception as e:
            # Fall back safely on error
            pass

        return self._generate_heuristic_plan(profile, dataset_id, goal)

    def run_analysis(
        self,
        dataset_id: str,
        goal: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute full Plan-Act-Reflect agent loop unattended.
        Guarantees step/token budgets, explainability logging, and citation verification.
        """
        self.start_time = time.perf_counter()
        self.step_count = 0
        self.tokens_used = 0
        self.run_log = []
        self.budget_tripped = False
        self.trip_reason = ""

        # Update DB Job if job_id provided
        db = SessionLocal()
        job = None
        if job_id:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job:
                job.status = "running"
                job.current_step_name = "profiling dataset"
                db.commit()

        # Step 0: Ensure dataset is profiled
        self._emit_progress("Profiling dataset structure and quality...", 0)
        df = get_dataset_dataframe(dataset_id)
        profile_obj = profile_dataset(df, dataset_id=dataset_id)
        profile_dict = profile_obj.model_dump()

        # Step 1: PLAN
        self._emit_progress("Generating autonomous analysis plan...", 1)
        plan = self._call_claude_planner(profile_dict, dataset_id, goal)
        
        executed_results = []
        pending_plan = list(plan)

        # Loop: ACT & REFLECT
        while pending_plan:
            # Check budgets before execution
            elapsed = time.perf_counter() - self.start_time
            if elapsed >= self.timeout_seconds:
                self.budget_tripped = True
                self.trip_reason = f"Execution timeout exceeded ({elapsed:.1f}s >= {self.timeout_seconds}s limit)"
                break

            if self.step_count >= self.max_steps:
                self.budget_tripped = True
                self.trip_reason = f"Maximum step budget reached ({self.step_count} >= {self.max_steps} steps limit)"
                break

            if self.tokens_used >= self.token_budget:
                self.budget_tripped = True
                self.trip_reason = f"Token budget exceeded ({self.tokens_used} >= {self.token_budget} tokens limit)"
                break

            current_step = pending_plan.pop(0)
            self.step_count += 1
            tool_name = current_step["tool"]
            args = current_step["arguments"]
            rationale = current_step.get("rationale", "")

            # Ensure dataset_id is correct
            args["dataset_id"] = dataset_id

            self._emit_progress(f"Executing step {self.step_count}: {tool_name}...", self.step_count)
            if job:
                job.current_step_name = f"Step {self.step_count}: {tool_name}"
                job.total_steps = self.step_count
                db.commit()

            # ACT: Execute Tool
            step_start = time.perf_counter()
            tool_output = execute_tool(tool_name, args)
            duration_ms = round((time.perf_counter() - step_start) * 1000, 2)
            
            # Estimate tokens for local reflection simulation
            self.tokens_used += 350

            # Record step in run log
            log_entry = {
                "step_number": self.step_count,
                "timestamp": datetime.utcnow().isoformat(),
                "tool": tool_name,
                "arguments": args,
                "duration_ms": duration_ms,
                "status": tool_output.get("status", "success"),
                "rationale": rationale,
                "summary": str(tool_output.get("message") or f"Executed {tool_name} successfully.")
            }
            self.run_log.append(log_entry)
            executed_results.append(tool_output)

            # REFLECT: Evaluate result & decide on follow-up
            if tool_name == "detect_outliers" and tool_output.get("total_anomalous_rows", 0) > 0:
                # If high outliers found, dynamically reflect and check if SQL drilldown or chart needed
                if len(pending_plan) < 2 and self.step_count < self.max_steps:
                    top_cols = tool_output.get("top_outlier_columns", [])
                    if top_cols:
                        col_target = top_cols[0]["column"]
                        pending_plan.insert(0, {
                            "step": self.step_count + 1,
                            "tool": "query_sql",
                            "arguments": {
                                "dataset_id": dataset_id,
                                "sql": f"SELECT {col_target}, COUNT(*) as frequency FROM df GROUP BY {col_target} ORDER BY frequency DESC LIMIT 5"
                            },
                            "rationale": f"Reflect: High anomaly rate in '{col_target}'; drill down to investigate value distribution."
                        })

        # Step 4: SYNTHESIZE
        self._emit_progress("Synthesizing findings and verifying numeric claims...", self.step_count + 1)
        if job:
            job.current_step_name = "Synthesizing executive report"
            db.commit()

        synthesis = write_summary(
            structured_results=executed_results,
            dataset_profile=profile_dict,
            goal=goal
        )

        # Generate Visualizations for Key Findings
        chart_specs = []
        for res in executed_results:
            t_name = res.get("tool")
            if t_name in ("run_correlation", "trend_analysis", "segment_compare", "detect_outliers"):
                try:
                    c_spec = generate_chart(t_name, res)
                    if c_spec.get("status") == "success":
                        chart_specs.append(c_spec)
                except Exception:
                    pass

        # Programmatic Citation Verification
        verification = validate_citations(
            synthesis_result=synthesis,
            structured_results=executed_results,
            dataset_profile=profile_dict
        )

        final_status = "budget_tripped" if self.budget_tripped else "completed"
        total_runtime_seconds = round(time.perf_counter() - self.start_time, 2)

        final_payload = {
            "dataset_id": dataset_id,
            "status": final_status,
            "goal": goal,
            "total_steps_executed": self.step_count,
            "max_steps_limit": self.max_steps,
            "tokens_consumed": self.tokens_used,
            "token_budget": self.token_budget,
            "execution_time_seconds": total_runtime_seconds,
            "budget_tripped": self.budget_tripped,
            "trip_reason": self.trip_reason if self.budget_tripped else None,
            "synthesis": synthesis,
            "chart_specifications": chart_specs,
            "citation_audit": verification,
            "run_log": self.run_log
        }

        # Update DB Job
        if job:
            job.status = final_status
            job.current_step_name = "Completed"
            job.total_steps = self.step_count
            job.tokens_used = self.tokens_used
            job.execution_time_seconds = int(total_runtime_seconds)
            job.set_run_log(self.run_log)
            job.set_results({
                "synthesis": synthesis,
                "chart_specifications": chart_specs
            })
            job.set_verification(verification)
            db.commit()

        db.close()
        return final_payload
