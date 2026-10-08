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
from typing import Any, Callable, Dict, List, Optional, Union
import pandas as pd

from backend.app.agent.citation_checker import validate_citations
from backend.app.agent.llm_client import LLMClient, TokenUsage, get_llm_client
from backend.app.core.database import SessionLocal
from backend.app.models.job import AnalysisJob
from backend.app.services.charts import generate_chart
from backend.app.services.data_loader import get_dataset_dataframe
from backend.app.services.insights import generate_insights
from backend.app.services.profiling import profile_dataset
from backend.app.services.tool_catalogue import execute_tool
from backend.app.agent.follow_up_triggers import compute_candidate_follow_ups

class PlanActReflectOrchestrator:
    def __init__(
        self,
        max_steps: int = 5,
        token_budget: int = 15000,
        timeout_seconds: float = 45.0,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        llm_client: Optional[LLMClient] = None,
        provider: Optional[str] = None
    ):
        self.max_steps = max_steps
        self.token_budget = token_budget
        self.timeout_seconds = timeout_seconds
        self.progress_callback = progress_callback
        self.llm_client = llm_client or get_llm_client(provider=provider)
        self.tokens_used: int = 0
        self.tokens_unknown: bool = False
        self.step_count = 0
        self.start_time = 0.0
        self.run_log: List[Dict[str, Any]] = []
        self.budget_tripped = False
        self.trip_reason = ""

    def _accumulate_tokens(self, usage: TokenUsage):
        """Accumulate token accounting from real provider usage metadata."""
        if usage.is_known and isinstance(usage.total_tokens, int):
            self.tokens_used += usage.total_tokens
            if self.step_count > 0 and self.tokens_used >= self.token_budget:
                self.budget_tripped = True
                self.trip_reason = f"Token budget exceeded ({self.tokens_used} >= {self.token_budget} tokens limit)"
        else:
            self.tokens_unknown = True

    def _generate_heuristic_plan(
        self,
        profile: Dict[str, Any],
        dataset_id: str,
        goal: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Delegates to HeuristicClient for offline/test plan generation."""
        from backend.app.agent.llm_client import HeuristicClient
        client = HeuristicClient()
        plan_res = client.plan(profile=profile, goal=goal, dataset_id=dataset_id)
        return [
            {
                "step": idx + 1,
                "tool": tc.name,
                "arguments": tc.arguments,
                "rationale": tc.rationale
            }
            for idx, tc in enumerate(plan_res.tool_calls)
        ]

    def _emit_progress(self, message: str, step_index: int = 0, phase: str = "execution"):
        if self.progress_callback:
            try:
                self.progress_callback(message, step_index, phase)
            except TypeError:
                try:
                    self.progress_callback(message, step_index)
                except Exception:
                    pass
            except Exception:
                pass

    def _run_baseline_scan(
        self,
        df: pd.DataFrame,
        dataset_id: str,
        profile_dict: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Execute deterministic baseline scan across dataset distributions:
        1. Outliers on all numeric columns (3.0x IQR fence)
        2. Correlation matrix across numeric columns
        3. segment_compare for top categorical x numeric pairs
        The LLM adds depth on top.
        """
        import numpy as np
        baseline_results: List[Dict[str, Any]] = []
        columns_meta = profile_dict.get("columns", {})
        num_cols = [c for c, p in columns_meta.items() if p.get("inferred_type") == "numeric"]
        if not num_cols:
            num_cols = list(df.select_dtypes(include=[np.number]).columns)
        cat_cols = [c for c, p in columns_meta.items() if p.get("inferred_type") in ("categorical", "text")]
        if not cat_cols:
            cat_cols = list(df.select_dtypes(include=["object", "category"]).columns)

        # 1. Outlier scan across all numeric columns (3.0x IQR fence)
        if num_cols:
            try:
                out_res = execute_tool("detect_outliers", {
                    "dataset_id": dataset_id,
                    "method": "iqr",
                    "columns": num_cols,
                    "threshold": 3.0
                })
                baseline_results.append(out_res)
            except Exception:
                pass

        # 2. Correlation matrix across numeric columns
        if len(num_cols) >= 2:
            try:
                corr_res = execute_tool("run_correlation", {
                    "dataset_id": dataset_id,
                    "columns": num_cols[:10]
                })
                baseline_results.append(corr_res)
            except Exception:
                pass

        # 3. segment_compare for top categorical x numeric pairs
        valid_cats = []
        for c in cat_cols:
            if c in df.columns:
                card = df[c].nunique()
                if 2 <= card <= 20:
                    valid_cats.append(c)

        for cat in valid_cats[:2]:
            for num in num_cols[:2]:
                try:
                    seg_res = execute_tool("segment_compare", {
                        "dataset_id": dataset_id,
                        "segment_column": cat,
                        "metric_column": num
                    })
                    baseline_results.append(seg_res)
                except Exception:
                    pass

        return baseline_results

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
        self.tokens_unknown = False
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
                job.phase = "profiling"
                job.current_step = 0
                job.current_step_name = "Profiling dataset"
                db.commit()

        # Step 0: Ensure dataset is profiled
        self._emit_progress("Profiling dataset structure and quality...", 0, phase="profiling")
        df = get_dataset_dataframe(dataset_id, prefer_cleaned=True)
        profile_obj = profile_dataset(df, dataset_id=dataset_id)
        profile_dict = profile_obj.model_dump()
        profile_dict["cleaned_row_count"] = len(df)
        profile_dict["n_rows_used"] = len(df)

        # Surface data quality findings (sentinels, invalid values, imputation rates)
        from backend.app.services.data_loader import get_dataset_cleaning_report
        cleaning_report = df.attrs.get("cleaning_report") or get_dataset_cleaning_report(df, dataset_id)
        if cleaning_report:
            profile_dict["cleaning_report"] = cleaning_report
            profile_dict["sentinels_detected"] = cleaning_report.get("sentinels_detected", [])
            profile_dict["invalid_values_detected"] = cleaning_report.get("invalid_values_detected", [])
            profile_dict["column_imputation_stats"] = cleaning_report.get("column_imputation_stats", {})
            profile_dict["missing_values_imputed"] = cleaning_report.get("missing_values_imputed", {})

        # Step 0b: Execute Deterministic Baseline Scan
        self._emit_progress("Executing deterministic baseline scan (outliers, correlation, segment comparisons)...", 0, phase="baseline")
        baseline_results = self._run_baseline_scan(df, dataset_id, profile_dict)
        executed_results = list(baseline_results)

        # Step 1: PLAN (Provider-agnostic via LLMClient, adding depth on top)
        if job:
            job.phase = "planning"
            job.current_step = 0
            job.current_step_name = f"Planning analysis via {self.llm_client.provider_name}"
            db.commit()

        # Proactive token estimation check before plan call
        est_plan_tokens = 1200
        if self.tokens_used + est_plan_tokens > self.token_budget and self.token_budget > 0 and self.llm_client.provider_name != "heuristic":
            self.budget_tripped = True
            self.trip_reason = f"Token budget projected to exceed before planning ({self.tokens_used} + {est_plan_tokens} > {self.token_budget})"

        self._emit_progress(f"Step 0/{self.max_steps}: Initial Plan (calling LLM {self.llm_client.provider_name})...", 0, phase="planning")
        plan_result = self.llm_client.plan(
            profile=profile_dict,
            goal=goal,
            dataset_id=dataset_id
        )
        self._accumulate_tokens(plan_result.usage)
        initial_llm_latency_ms = round(plan_result.latency_seconds * 1000, 2)
        
        current_round = 1
        max_rounds = 3
        pending_plan = [
            {
                "step": idx + 1,
                "round": 1,
                "tool": tc.name,
                "arguments": tc.arguments,
                "rationale": tc.rationale,
                "llm_latency_ms": initial_llm_latency_ms if idx == 0 else 0.0
            }
            for idx, tc in enumerate(plan_result.tool_calls)
        ]

        rounds_table = [
            {
                "round": 1,
                "tools": [tc.name for tc in plan_result.tool_calls],
                "reason": "Initial planned exploratory analysis"
            }
        ]

        # Loop: ACT & REFLECT (up to 3 rounds, <=3 follow-up tool calls per reflection)
        while pending_plan or current_round < max_rounds:
            # If current round's queue is empty, trigger reflection to decide on next round
            if not pending_plan:
                if current_round >= max_rounds:
                    break

                # Check budgets before triggering reflection
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

                # M4 (a): Deterministic candidate follow-up computation
                candidates, reasons = compute_candidate_follow_ups(
                    executed_results=executed_results,
                    profile=profile_dict,
                    dataset_id=dataset_id
                )

                self._emit_progress(f"Round {current_round} complete. Reflecting on {len(candidates)} candidate triggers...", self.step_count, phase="reflection")
                if job:
                    job.phase = "reflection"
                    db.commit()
                try:
                    last_output = executed_results[-1] if executed_results else {}
                    import inspect
                    sig = inspect.signature(self.llm_client.reflect)
                    ref_kwargs = {}
                    if "candidates" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                        ref_kwargs["candidates"] = candidates
                        ref_kwargs["candidate_reasons"] = reasons

                    # Proactive token estimation check before reflection call
                    est_reflect_tokens = 1200
                    if self.tokens_used + est_reflect_tokens > self.token_budget and self.token_budget > 0 and self.llm_client.provider_name != "heuristic":
                        self.budget_tripped = True
                        self.trip_reason = f"Token budget projected to exceed before reflection ({self.tokens_used} + {est_reflect_tokens} > {self.token_budget})"
                        break

                    reflect_res = self.llm_client.reflect(
                        step_result=last_output,
                        history=self.run_log,
                        dataset_id=dataset_id,
                        **ref_kwargs
                    )
                    self._accumulate_tokens(reflect_res.usage)
                    reflect_latency_ms = round(reflect_res.latency_seconds * 1000, 3)

                    if self.budget_tripped:
                        break

                    # Reflection may request <= 3 follow-up tool calls or stop
                    follow_ups = reflect_res.tool_calls[:3]

                    # Log reflection on the last step of this round
                    if self.run_log:
                        self.run_log[-1]["reflection"] = reflect_res.observation
                        self.run_log[-1]["reflection_latency_ms"] = reflect_latency_ms
                        self.run_log[-1]["follow_ups"] = [f.name for f in follow_ups]
                        self.run_log[-1]["round"] = current_round

                    if not follow_ups:
                        rounds_table.append({
                            "round": current_round + 1,
                            "tools": [],
                            "reason": "No trigger fired (no segment p < 0.05, no outlier rate > 5%, no |r| > 0.5); reflection stopped." if not candidates else "Reflector assessed candidate triggers and decided to stop."
                        })
                        break

                    current_round += 1
                    follow_up_reasons = reasons[:len(follow_ups)] if reasons else [f.rationale for f in follow_ups]
                    rounds_table.append({
                        "round": current_round,
                        "tools": [f.name for f in follow_ups],
                        "reason": "; ".join(follow_up_reasons)
                    })

                    for f_idx, follow_up in enumerate(follow_ups):
                        pending_plan.append({
                            "step": self.step_count + len(pending_plan) + 1,
                            "round": current_round,
                            "tool": follow_up.name,
                            "arguments": follow_up.arguments,
                            "rationale": follow_up.rationale,
                            "llm_latency_ms": reflect_latency_ms if f_idx == 0 else 0.0
                        })
                except Exception as e:
                    logger.warning("Reflection failed in round %d: %s", current_round, e)
                    break

            if not pending_plan:
                break

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

            if self.step_count > 0 and self.tokens_used >= self.token_budget:
                self.budget_tripped = True
                self.trip_reason = f"Token budget exceeded ({self.tokens_used} >= {self.token_budget} tokens limit)"
                break

            current_step = pending_plan.pop(0)
            self.step_count += 1
            tool_name = current_step["tool"]
            args = current_step["arguments"]
            rationale = current_step.get("rationale", "")
            step_round = current_step.get("round", current_round)
            current_llm_latency = current_step.get("llm_latency_ms", 0.0)

            # Ensure dataset_id is correct
            args["dataset_id"] = dataset_id

            self._emit_progress(f"Round {step_round} - Step {self.step_count}/{self.max_steps}: {tool_name}...", self.step_count, phase="execution")
            if job:
                job.phase = "execution"
                job.current_step = self.step_count
                job.current_step_name = f"Round {step_round} - Step {self.step_count}: {tool_name}"
                job.total_steps = self.step_count
                db.commit()

            # ACT: Execute Tool
            step_start = time.perf_counter()
            tool_output = execute_tool(tool_name, args)
            duration_ms = round((time.perf_counter() - step_start) * 1000, 2)

            # Record step in run log with explicit planner provider, model label, round, and llm latency
            log_entry = {
                "step_number": self.step_count,
                "round": step_round,
                "timestamp": datetime.utcnow().isoformat(),
                "tool": tool_name,
                "arguments": args,
                "duration_ms": duration_ms,
                "llm_latency_ms": current_llm_latency,
                "reflection_latency_ms": 0.0,
                "reflection": None,
                "follow_ups": [],
                "status": tool_output.get("status", "success"),
                "rationale": rationale,
                "planner": self.llm_client.provider_name,
                "model": self.llm_client.model_name,
                "summary": str(tool_output.get("message") or f"Executed {tool_name} successfully.")
            }
            self.run_log.append(log_entry)
            executed_results.append(tool_output)

        # Step 4: Generate Structured Insights (ranked and deduplicated: top 6 analytical, max 4 data quality)
        insights_objects = generate_insights(
            executed_results=executed_results,
            dataset_profile=profile_dict,
            run_log=self.run_log
        )
        insights = [i.model_dump() for i in insights_objects]
        analytical_insights = [i for i in insights if i.get("type") != "data_quality"][:6]
        data_quality_insights = [i for i in insights if i.get("type") == "data_quality"][:4]
        profile_dict["insights"] = insights
        profile_dict["analytical_insights"] = analytical_insights
        profile_dict["data_quality_insights"] = data_quality_insights

        # Step 5: SYNTHESIZE (via LLMClient)
        self._emit_progress(f"Step {self.step_count + 1}/{self.max_steps + 1}: Synthesizing executive report (calling LLM...)", self.step_count + 1, phase="synthesis")
        if job:
            job.phase = "synthesis"
            job.current_step = self.step_count + 1
            job.current_step_name = "Synthesizing executive report"
            db.commit()

        synth_goal = (
            f"{goal or 'Comprehensive exploratory analysis'}. "
            "When citing percentages, use the n_rows_used reported by each tool as the denominator. "
            "Do not calculate rates against original raw row counts. "
            "Surface relevant data quality findings (such as sentinel values like Quantity=999, invalid domain values, and imputation) in the findings and narrative."
        )
        # Proactive token estimation check before synthesis call
        est_synth_tokens = 1800
        if self.tokens_used + est_synth_tokens > self.token_budget and self.token_budget > 0 and self.llm_client.provider_name != "heuristic":
            self.budget_tripped = True
            self.trip_reason = f"Token budget projected to exceed before synthesis ({self.tokens_used} + {est_synth_tokens} > {self.token_budget})"

        synth_start = time.perf_counter()
        if self.budget_tripped and self.llm_client.provider_name != "heuristic":
            from backend.app.agent.llm_client import HeuristicClient
            synth_client = HeuristicClient()
        else:
            synth_client = self.llm_client

        synth_res = synth_client.synthesize(
            results=executed_results,
            dataset_profile=profile_dict,
            goal=synth_goal,
            insights=insights
        )
        synth_latency_ms = round((time.perf_counter() - synth_start) * 1000, 2)
        self._accumulate_tokens(synth_res.usage)

        # Initial Bound Citation Verification (strictly against insights + profile, NEVER raw tool results)
        initial_payload = {
            "executive_summary": synth_res.executive_summary,
            "key_findings": synth_res.key_findings,
            "claims": synth_res.claims or []
        }
        verification = validate_citations(
            synthesis_result=initial_payload,
            structured_results=None,
            dataset_profile=profile_dict,
            insights=insights
        )

        # Retry once if unverified claims/numbers exist and LLM is configured
        if not verification["is_valid"] and self.llm_client.provider_name != "heuristic":
            failing_claims = list(verification.get("unverified_claims", []))
            for un in verification.get("unverified_numbers", []):
                failing_claims.append({
                    "unverified_number": un,
                    "instruction": f"Remove any sentence containing {un} or provide an exact matching claim in 'claims'."
                })
            retry_start = time.perf_counter()
            retry_res = self.llm_client.synthesize(
                results=executed_results,
                dataset_profile=profile_dict,
                goal=synth_goal,
                failing_claims=failing_claims,
                insights=insights
            )
            synth_latency_ms += round((time.perf_counter() - retry_start) * 1000, 2)
            self._accumulate_tokens(retry_res.usage)
            retry_payload = {
                "executive_summary": retry_res.executive_summary,
                "key_findings": retry_res.key_findings,
                "claims": retry_res.claims or []
            }
            verification = validate_citations(
                synthesis_result=retry_payload,
                structured_results=None,
                dataset_profile=profile_dict,
                insights=insights
            )
            synth_res = retry_res

        # If unverified claims or numbers persist, strip offending sentences
        clean_summary = verification.get("cleaned_executive_summary") or synth_res.executive_summary
        stripped_sentences = verification.get("stripped_sentences", [])

        synthesis = {
            "status": "success",
            "executive_summary": clean_summary,
            "key_findings": synth_res.key_findings,
            "recommendations": synth_res.recommendations,
            "total_findings": len(synth_res.key_findings),
            "total_tools_executed": len(executed_results),
            "citations_index": synth_res.citations_index,
            "claims": synth_res.claims or [],
            "stripped_sentences": stripped_sentences,
            "llm_latency_ms": synth_latency_ms
        }

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


        final_status = "budget_tripped" if self.budget_tripped else "completed"
        total_runtime_seconds = round(time.perf_counter() - self.start_time, 3)

        # Real token accounting: report exact integer or "unknown"
        if self.tokens_used > 0:
            tokens_reported: Union[int, str] = self.tokens_used
        elif self.tokens_unknown or self.llm_client.provider_name == "heuristic":
            tokens_reported = "unknown"
        else:
            tokens_reported = 0

        total_tool_latency = sum(s.get("duration_ms", 0.0) for s in self.run_log)
        total_llm_latency = sum(s.get("llm_latency_ms", 0.0) + s.get("reflection_latency_ms", 0.0) for s in self.run_log) + synth_latency_ms

        final_payload = {
            "dataset_id": dataset_id,
            "status": final_status,
            "goal": goal,
            "planner": self.llm_client.provider_name,
            "model": self.llm_client.model_name,
            "total_steps_executed": self.step_count,
            "max_steps_limit": self.max_steps,
            "tokens_consumed": tokens_reported,
            "token_budget": self.token_budget,
            "execution_time_seconds": total_runtime_seconds,
            "synthesis_llm_latency_ms": round(synth_latency_ms, 3),
            "total_tool_latency_ms": round(total_tool_latency, 3),
            "total_llm_latency_ms": round(total_llm_latency, 3),
            "budget_tripped": self.budget_tripped,
            "trip_reason": self.trip_reason if self.budget_tripped else None,
            "insights": insights,
            "analytical_insights": analytical_insights,
            "data_quality_insights": data_quality_insights,
            "synthesis": synthesis,
            "chart_specifications": chart_specs,
            "citation_audit": verification,
            "verification": verification,
            "run_log": self.run_log,
            "rounds_table": rounds_table,
            "rounds_summary": rounds_table
        }

        # Update DB Job
        if job:
            job.status = final_status
            job.phase = "completed" if not self.budget_tripped else "budget_tripped"
            job.current_step = self.step_count
            job.current_step_name = "Completed"
            job.total_steps = self.step_count
            job.tokens_used = self.tokens_used
            job.execution_time_seconds = float(total_runtime_seconds)
            job.set_run_log(self.run_log)
            job.set_insights(insights)
            job.set_results({
                "synthesis": synthesis,
                "chart_specifications": chart_specs,
                "insights": insights,
                "analytical_insights": analytical_insights,
                "data_quality_insights": data_quality_insights
            })
            job.set_verification(verification)
            db.commit()

        db.close()
        return final_payload
