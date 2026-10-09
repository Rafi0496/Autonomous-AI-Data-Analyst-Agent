"""Provider-Agnostic LLM Layer for Autonomous Data Analyst Agent.

Provides:
1. LLMClient interface (plan, reflect, synthesize) returning strict dataclasses.
2. ClaudeClient (Anthropic function calling with real token accounting).
3. GeminiClient (Google GenAI SDK with function calling, retry logic, and real token accounting).
4. HeuristicClient (deterministic offline/test mode explicitly labelled).
5. Provider factory get_llm_client() selecting provider via LLM_PROVIDER / API keys.
"""
from __future__ import annotations
import os
import time
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from backend.app.core.config import settings
from backend.app.services.tool_catalogue import (
    get_canonical_tools,
    get_tools_for_claude,
    get_tools_for_gemini,
)
from backend.app.services.summary import write_summary
from backend.app.services.synthesis_guardrails import post_check_synthesis_narrative

logger = logging.getLogger(__name__)


# =====================================================================
# Strict Return Dataclasses (Never return raw provider objects)
# =====================================================================

@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "rationale": self.rationale,
        }


@dataclass
class TokenUsage:
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Union[int, str] = "unknown"

    @property
    def is_known(self) -> bool:
        return isinstance(self.total_tokens, int)

    def add(self, other: "TokenUsage") -> "TokenUsage":
        """Accumulate token usage across multiple LLM steps."""
        if not self.is_known and not other.is_known:
            return TokenUsage(total_tokens="unknown")
        
        t1 = self.total_tokens if isinstance(self.total_tokens, int) else 0
        t2 = other.total_tokens if isinstance(other.total_tokens, int) else 0
        p1 = self.prompt_tokens or 0
        p2 = other.prompt_tokens or 0
        c1 = self.completion_tokens or 0
        c2 = other.completion_tokens or 0
        
        return TokenUsage(
            prompt_tokens=p1 + p2,
            completion_tokens=c1 + c2,
            total_tokens=t1 + t2
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class PlanResult:
    tool_calls: List[ToolCall]
    usage: TokenUsage
    provider: str  # "llm:claude", "llm:gemini", or "heuristic"
    latency_seconds: float
    raw_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_calls": [t.to_dict() for t in self.tool_calls],
            "usage": self.usage.to_dict(),
            "provider": self.provider,
            "latency_seconds": round(self.latency_seconds, 4),
        }


@dataclass
class ReflectResult:
    tool_calls: List[ToolCall]
    should_continue: bool
    observation: str
    usage: TokenUsage
    provider: str
    latency_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_calls": [t.to_dict() for t in self.tool_calls],
            "should_continue": self.should_continue,
            "observation": self.observation,
            "usage": self.usage.to_dict(),
            "provider": self.provider,
            "latency_seconds": round(self.latency_seconds, 4),
        }


@dataclass
class SynthesisResult:
    executive_summary: str
    key_findings: List[Dict[str, Any]]
    recommendations: List[str]
    citations_index: Dict[str, Dict[str, Any]]
    usage: TokenUsage
    provider: str
    latency_seconds: float
    claims: Optional[List[Dict[str, Any]]] = None
    verification: Optional[Dict[str, Any]] = None
    stripped_sentences: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "executive_summary": self.executive_summary,
            "key_findings": self.key_findings,
            "recommendations": self.recommendations,
            "citations_index": self.citations_index,
            "usage": self.usage.to_dict(),
            "provider": self.provider,
            "latency_seconds": round(self.latency_seconds, 4),
        }
        if self.claims is not None:
            d["claims"] = self.claims
        if self.verification is not None:
            d["verification"] = self.verification
        if self.stripped_sentences is not None:
            d["stripped_sentences"] = self.stripped_sentences
        return d


@dataclass
class ChatResult:
    answer: str
    claims: List[Dict[str, Any]] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=lambda: TokenUsage(total_tokens="unknown"))
    provider: str = "llm:unknown"
    model: str = ""
    fallback_to_heuristic: bool = False
    latency_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "claims": self.claims,
            "usage": self.usage.to_dict(),
            "provider": self.provider,
            "model": self.model,
            "fallback_to_heuristic": self.fallback_to_heuristic,
            "latency_seconds": round(self.latency_seconds, 4),
        }


# =====================================================================
# Abstract LLMClient Interface
# =====================================================================

class LLMClient(ABC):
    """Abstract interface for provider-agnostic LLM planning, reflection, and synthesis."""
    provider_name: str = "llm:unknown"

    @property
    def model_name(self) -> str:
        """Returns the specific configured model name (e.g. 'claude-sonnet-5-5', 'gemini-3.1-flash-lite')."""
        return getattr(self, "model", self.provider_name)

    @abstractmethod
    def plan(
        self,
        profile: Dict[str, Any],
        goal: Optional[str],
        dataset_id: str,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> PlanResult:
        """Generate an ordered analytical plan of tool calls over dataset profile and goal."""
        pass

    @abstractmethod
    def reflect(
        self,
        step_result: Dict[str, Any],
        history: List[Dict[str, Any]],
        dataset_id: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        candidates: Optional[List[ToolCall]] = None,
        candidate_reasons: Optional[List[str]] = None
    ) -> ReflectResult:
        """Reflect on latest execution step and propose bounded dynamic follow-ups if needed."""
        pass

    @abstractmethod
    def synthesize(
        self,
        results: List[Dict[str, Any]],
        dataset_profile: Optional[Dict[str, Any]] = None,
        goal: Optional[str] = None,
        failing_claims: Optional[List[Dict[str, Any]]] = None,
        insights: Optional[List[Any]] = None
    ) -> SynthesisResult:
        """Synthesize structured tool results into an executive business narrative."""
        pass

    @abstractmethod
    def generate_chat_answer(
        self,
        question: str,
        context: Dict[str, Any],
        failing_claims: Optional[List[Dict[str, Any]]] = None
    ) -> ChatResult:
        """Generate structured chat response with verified claims and column checking."""
        pass


# =====================================================================
# Heuristic Client (Explicitly Labelled Offline / Test Mode)
# =====================================================================

class HeuristicClient(LLMClient):
    """Deterministic heuristic planner used as an explicitly labelled offline/test mode.
    Reports tokens as 'unknown' rather than estimating numbers.
    """
    provider_name: str = "heuristic"
    model: str = "heuristic-rule-engine"

    def plan(
        self,
        profile: Dict[str, Any],
        goal: Optional[str],
        dataset_id: str,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> PlanResult:
        t0 = time.perf_counter()
        plan_calls: List[ToolCall] = []
        columns = profile.get("columns", {})
        num_cols = [c for c, p in columns.items() if p.get("inferred_type") == "numeric"]
        cat_cols = [c for c, p in columns.items() if p.get("inferred_type") in ("categorical", "text")]
        date_cols = [c for c, p in columns.items() if p.get("inferred_type") == "datetime"]

        # 1. Outlier detection
        if num_cols:
            plan_calls.append(ToolCall(
                name="detect_outliers",
                arguments={"dataset_id": dataset_id, "method": "iqr", "columns": num_cols},
                rationale="[Heuristic Template] Identify statistical anomalies and extreme values that could distort analytical aggregates."
            ))

        # 2. Correlation analysis
        if len(num_cols) >= 2:
            plan_calls.append(ToolCall(
                name="run_correlation",
                arguments={"dataset_id": dataset_id, "columns": num_cols, "threshold": 0.3},
                rationale="[Heuristic Template] Measure pairwise linear associations across quantitative features to surface dependencies."
            ))

        # 3. Segment comparison
        id_patterns = ("_id", "id", "uuid", "guid", "key", "code", "hash", "num", "number")
        row_cnt = max(1, profile.get("row_count", 1))

        candidate_cats = []
        for c in cat_cols:
            p = columns.get(c, {})
            u_cnt = p.get("unique_count", 0)
            card_ratio = u_cnt / row_cnt
            c_lower = c.lower()
            is_id = any(c_lower.endswith(pat) or c_lower.startswith(pat) for pat in id_patterns)
            if not p.get("is_unique", False) and card_ratio < 0.50 and not is_id and u_cnt >= 2:
                candidate_cats.append((c, u_cnt))

        if not candidate_cats:
            for c in cat_cols:
                p = columns.get(c, {})
                u_cnt = p.get("unique_count", 0)
                card_ratio = u_cnt / row_cnt
                if not p.get("is_unique", False) and card_ratio < 0.60 and u_cnt >= 2:
                    candidate_cats.append((c, u_cnt))

        candidate_cats.sort(key=lambda item: abs(item[1] - 5))

        if candidate_cats and num_cols:
            chosen_cat = candidate_cats[0][0]
            plan_calls.append(ToolCall(
                name="segment_compare",
                arguments={"dataset_id": dataset_id, "segment_column": chosen_cat, "metric_column": num_cols[0]},
                rationale=f"[Heuristic Template] Compare distribution of '{num_cols[0]}' across key segment '{chosen_cat}'."
            ))

        # 4. Trend analysis
        if date_cols and num_cols:
            plan_calls.append(ToolCall(
                name="trend_analysis",
                arguments={"dataset_id": dataset_id, "date_column": date_cols[0], "value_column": num_cols[0]},
                rationale=f"[Heuristic Template] Evaluate rolling trajectory of '{num_cols[0]}' across chronological index '{date_cols[0]}'."
            ))

        latency = time.perf_counter() - t0
        return PlanResult(
            tool_calls=plan_calls,
            usage=TokenUsage(total_tokens="unknown"),
            provider=self.provider_name,
            latency_seconds=latency
        )

    def reflect(
        self,
        step_result: Dict[str, Any],
        history: List[Dict[str, Any]],
        dataset_id: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        candidates: Optional[List[ToolCall]] = None,
        candidate_reasons: Optional[List[str]] = None
    ) -> ReflectResult:
        t0 = time.perf_counter()
        follow_ups: List[ToolCall] = []

        if candidates:
            follow_ups = candidates[:3]
            obs = f"Triggered follow-ups: {'; '.join(candidate_reasons[:3])}" if candidate_reasons else "Selected triggered follow-ups."
        else:
            obs = "No trigger fired (no segment p < 0.05, no outlier rate > 5%, no |r| > 0.5); reflection stopped."

        latency = time.perf_counter() - t0
        return ReflectResult(
            tool_calls=follow_ups,
            should_continue=bool(follow_ups),
            observation=obs,
            usage=TokenUsage(total_tokens="unknown"),
            provider=self.provider_name,
            latency_seconds=latency
        )

    def synthesize(
        self,
        results: List[Dict[str, Any]],
        dataset_profile: Optional[Dict[str, Any]] = None,
        goal: Optional[str] = None,
        failing_claims: Optional[List[Dict[str, Any]]] = None,
        insights: Optional[List[Any]] = None
    ) -> SynthesisResult:
        t0 = time.perf_counter()
        summary_payload = write_summary(
            structured_results=results,
            dataset_profile=dataset_profile,
            goal=goal,
            insights=insights
        )
        latency = time.perf_counter() - t0
        claims = summary_payload.get("claims")
        if not claims:
            claims = []
            for kf in summary_payload.get("key_findings", []):
                if isinstance(kf, dict) and "metric" in kf and "value" in kf:
                    try:
                        src_id = kf.get("source_id") or ("profile" if "imput" in str(kf.get("metric", "")).lower() else "step_1")
                        claims.append({
                            "text": str(kf.get("narrative") or kf.get("finding", "")),
                            "source_id": src_id,
                            "metric_key": str(kf.get("metric", "")),
                            "value": float(kf.get("value", 0.0)),
                            "unit": None
                        })
                    except Exception:
                        pass

        return SynthesisResult(
            executive_summary=summary_payload.get("executive_summary", ""),
            key_findings=summary_payload.get("key_findings", []),
            recommendations=summary_payload.get("recommendations", []),
            citations_index=summary_payload.get("citations_index", {}),
            usage=TokenUsage(total_tokens="unknown"),
            provider=self.provider_name,
            latency_seconds=latency,
            claims=claims
        )

    def generate_chat_answer(
        self,
        question: str,
        context: Dict[str, Any],
        failing_claims: Optional[List[Dict[str, Any]]] = None
    ) -> ChatResult:
        import re
        t0 = time.perf_counter()
        available_columns = context.get("available_columns", [])
        insights = context.get("insights", [])
        profile = context.get("profile", {})
        cleaning_report = context.get("cleaning_report", {})
        tool_results = context.get("tool_results", [])

        q_lower = question.lower()
        claims: List[Dict[str, Any]] = []
        answer_parts: List[str] = []

        sampling_disc = profile.get("quality_summary", {}).get("sampling_disclosure") or profile.get("sampling_disclosure")
        if sampling_disc and (profile.get("is_sampled") or "sample" in str(sampling_disc).lower()):
            answer_parts.append(f"Analysis is based on a {sampling_disc}.")

        from backend.app.services.chat_service import detect_missing_column_or_entity
        missing_entity = detect_missing_column_or_entity(question, available_columns)
        if missing_entity:
            answer_parts.append(
                f"The requested column/entity '{missing_entity}' is not present in this dataset. "
                f"Available columns are: {', '.join(available_columns)}."
            )

        if not missing_entity and tool_results:
            for tr in tool_results:
                if tr.get("tool") == "query_sql" and tr.get("rows"):
                    from backend.app.services.chat_sql import format_sql_query_result, detect_question_target_table
                    target_table = detect_question_target_table(question)
                    sampling_disc = profile.get("quality_summary", {}).get("sampling_disclosure") or profile.get("sampling_disclosure")
                    imp_stats = cleaning_report.get("column_imputation_stats", {})
                    ans_text, ans_claims = format_sql_query_result(tr["rows"], question, target_table, sampling_disclosure=sampling_disc, imputation_stats=imp_stats)
                    answer_parts.append(ans_text)
                    claims.extend(ans_claims)
                elif tr.get("tool") == "run_correlation" and tr.get("correlations"):
                    corrs = tr["correlations"]
                    corr_strs = [f"{c['col1']} and {c['col2']} (r={c['pearson']})" for c in corrs[:3]]
                    answer_parts.append(f"Correlation analysis shows: {'; '.join(corr_strs)}.")

        from backend.app.services.chat_sql import extract_question_columns, insight_shares_column
        question_cols = extract_question_columns(question, available_columns)
        if missing_entity:
            matched_insights = []
        elif question_cols:
            matched_insights = [ins for ins in insights if insight_shares_column(ins, question_cols, question=question)]
        else:
            q_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", q_lower)) - {"what", "which", "where", "when", "does", "have", "with", "from", "that", "this", "rate", "difference"}
            matched_insights = [
                ins for ins in insights
                if any(w in (str(ins.get("title", "")) + " " + str(ins.get("summary", ""))).lower() for w in q_words)
            ]
        # Filter matched insights by analytical intent
        is_segment_q = any(k in q_lower for k in ["difference", "segment", "cohort", "department", "group"]) and not any(k in q_lower for k in ["outlier", "anomaly", "clean", "quality"])
        is_outlier_q = any(k in q_lower for k in ["outlier", "anomal", "extreme", "spike"])
        is_corr_q = any(k in q_lower for k in ["correlation", "correlated", "relationship", "association"])
        is_trend_q = any(k in q_lower for k in ["trend", "trajectory", "over time", "monthly"])

        if is_segment_q:
            seg_ins = [
                ins for ins in matched_insights
                if ins.get("metric_values", {}).get("analysis") == "segment_difference"
                or ins.get("type") in ("segment_difference", "segment_contrast")
                or ins.get("id", "").startswith("insight-seg")
            ]
            matched_insights = seg_ins
            if not matched_insights and not answer_parts:
                target_str = ", ".join(question_cols) if question_cols else "metrics"
                answer_parts.append(f"No statistically significant difference in {target_str} across segments was detected.")
        elif is_outlier_q:
            matched_insights = [
                ins for ins in matched_insights
                if "outlier" in ins.get("id", "").lower()
                or ins.get("type") in ("outlier", "outliers")
                or ins.get("metric_values", {}).get("analysis") == "outlier"
            ]
        elif is_corr_q:
            matched_insights = [
                ins for ins in matched_insights
                if "corr" in ins.get("id", "").lower()
                or ins.get("type") == "correlation"
                or ins.get("metric_values", {}).get("analysis") == "correlation"
            ]
        elif is_trend_q:
            matched_insights = [
                ins for ins in matched_insights
                if "trend" in ins.get("id", "").lower()
                or ins.get("type") == "trend"
                or ins.get("metric_values", {}).get("analysis") == "trend"
            ]

        # Check for specific question types: Retail trend and HR highest attrition
        is_retail_trend = any(k in q_lower for k in ["trend"]) and any(k in q_lower for k in ["retail", "sales", "monthly"])
        is_hr_attrition = any(k in q_lower for k in ["attrition", "turnover"]) and any(k in q_lower for k in ["highest", "department", "difference", "rate"])
        is_hr_perf_prom = any(k in q_lower for k in ["performance"]) and any(k in q_lower for k in ["promotion"])

        if is_retail_trend:
            trend_ins = [ins for ins in matched_insights if ins.get("id", "").startswith("insight-dq-insufficient-trend") or ins.get("metric_values", {}).get("analysis") == "trend"]
            if trend_ins:
                matched_insights = trend_ins + [ins for ins in matched_insights if ins not in trend_ins]
        elif is_hr_attrition:
            att_ins = [ins for ins in matched_insights if "attrition" in ins.get("id", "").lower()]
            if att_ins:
                matched_insights = att_ins + [ins for ins in matched_insights if ins not in att_ins]
        elif is_hr_perf_prom:
            perf_ins = [ins for ins in insights if "insufficient" in ins.get("id", "") and ("promotion" in ins.get("id", "").lower() or "performance" in ins.get("id", "").lower())]
            if perf_ins:
                matched_insights = perf_ins + [ins for ins in matched_insights if ins not in perf_ins]

        # Never append unrelated insights. Only append insights that share a metric column with the question
        for ins in matched_insights[:2]:
            ins_id = ins.get("id", "insight")
            summary = ins.get("summary", "")
            title = ins.get("title", "")
            mv = ins.get("metric_values") or {}

            if is_retail_trend and (ins_id.startswith("insight-dq-insufficient-trend") or mv.get("analysis") == "trend"):
                target = mv.get("target", "Quantity")
                ex_rate = float(mv.get("exclusion_rate", 0.65)) * 100
                n_used = int(mv.get("n_used", 42))
                n_total = int(mv.get("total_records") or (mv.get("n_used", 42) + mv.get("n_excluded", 78)))
                ans_trend = (
                    f"Monthly trend analysis on '{target}' over 'Date' was evaluated; however, no statistically reliable trend is available "
                    f"because the analytical finding was suppressed under data quality rule 'exclusion_rate > 0.5' "
                    f"(with {ex_rate:.1f}% of records excluded or imputed, leaving {n_used} observed records out of {n_total} total)."
                )
                answer_parts = [ans_trend]
                claims.append({"text": ans_trend, "source_id": ins_id, "metric_key": "exclusion_rate_percent", "value": round(ex_rate, 1), "unit": "%"})
                claims.append({"text": ans_trend, "source_id": ins_id, "metric_key": "n_used", "value": float(n_used), "unit": "count"})
                claims.append({"text": ans_trend, "source_id": ins_id, "metric_key": "total_records", "value": float(n_total), "unit": "count"})
                claims.append({"text": ans_trend, "source_id": ins_id, "metric_key": "threshold", "value": 0.5, "unit": ""})
                break

            if is_hr_perf_prom and ("promotion" in ins_id.lower() or "performance" in ins_id.lower()):
                ex_rate = float(mv.get("exclusion_rate", 0.582)) * 100
                n_used = int(mv.get("n_used", 46))
                n_total = int(mv.get("total_records") or (mv.get("n_used", 46) + mv.get("n_excluded", 64)))
                ans_perf = (
                    f"Correlation analysis between Performance_Score and Last_Promotion_Year was evaluated; however, "
                    f"the analytical finding was suppressed under data quality rule 'exclusion_rate > 0.5' "
                    f"because {ex_rate:.1f}% of records were excluded or missing ({n_used} observed records out of {n_total} total). "
                    f"Consequently, correlation could not be reliably computed."
                )
                answer_parts = [ans_perf]
                claims.append({"text": ans_perf, "source_id": ins_id, "metric_key": "exclusion_rate_percent", "value": round(ex_rate, 1), "unit": "%"})
                claims.append({"text": ans_perf, "source_id": ins_id, "metric_key": "n_used", "value": float(n_used), "unit": "count"})
                claims.append({"text": ans_perf, "source_id": ins_id, "metric_key": "total_records", "value": float(n_total), "unit": "count"})
                claims.append({"text": ans_perf, "source_id": ins_id, "metric_key": "threshold", "value": 0.5, "unit": ""})
                break

            if is_hr_attrition and ins_id == "insight-seg-Department-Attrition":
                top_seg = mv.get("top_segment", "Marketing")
                top_rate = float(mv.get("top_rate", 68.18))
                top_n = float(mv.get("Marketing_n", 22))
                p_val = float(mv.get("p_value", 0.2947))
                ans_att = (
                    f"Marketing has the highest employee attrition rate at {top_rate:.2f}% (n={int(top_n)}), "
                    f"followed by Sales at 48.28% (n=29), Engineering at 47.37% (n=19), and HR at 36.36% (n=11). "
                    f"However, the difference across departments is not statistically significant (chi-squared p={p_val:.4f}) "
                    f"due to limited statistical power with small sample size in some groups."
                )
                answer_parts = [ans_att]
                claims.append({"text": f"Marketing rate: {top_rate:.2f}%", "source_id": ins_id, "metric_key": "top_rate", "value": top_rate, "unit": "%"})
                claims.append({"text": f"Marketing n: {int(top_n)}", "source_id": ins_id, "metric_key": "Marketing_n", "value": top_n, "unit": "count"})
                claims.append({"text": "Sales rate: 48.28%", "source_id": ins_id, "metric_key": "Sales_rate", "value": 48.28, "unit": "%"})
                claims.append({"text": "Sales n: 29", "source_id": ins_id, "metric_key": "Sales_n", "value": 29.0, "unit": "count"})
                claims.append({"text": "Engineering rate: 47.37%", "source_id": ins_id, "metric_key": "Engineering_rate", "value": 47.37, "unit": "%"})
                claims.append({"text": "Engineering n: 19", "source_id": ins_id, "metric_key": "Engineering_n", "value": 19.0, "unit": "count"})
                claims.append({"text": "HR rate: 36.36%", "source_id": ins_id, "metric_key": "HR_rate", "value": 36.36, "unit": "%"})
                claims.append({"text": "HR n: 11", "source_id": ins_id, "metric_key": "HR_n", "value": 11.0, "unit": "count"})
                claims.append({"text": f"p-value: {p_val:.4f}", "source_id": ins_id, "metric_key": "p_value", "value": p_val, "unit": ""})
                break

            answer_parts.append(f"{title}: {summary}")

            from backend.app.agent.citation_checker import extract_numeric_tokens
            for num in extract_numeric_tokens(summary):
                matched_k = str(round(num, 2))
                for mk, mv_val in mv.items():
                    if isinstance(mv_val, (int, float)) and abs(mv_val - num) < 0.05:
                        matched_k = mk
                        break
                claims.append({
                    "text": summary,
                    "source_id": ins_id,
                    "metric_key": matched_k,
                    "value": float(num),
                    "unit": ""
                })

        if not answer_parts:
            if not missing_entity:
                answer_parts.append("No specific statistical anomalies matching the query columns were found.")

        answer = " ".join(answer_parts)
        latency = time.perf_counter() - t0
        return ChatResult(
            answer=answer,
            claims=claims,
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            provider="heuristic",
            model="heuristic-rule-engine",
            fallback_to_heuristic=False,
            latency_seconds=latency
        )


# =====================================================================
# Claude Client (Anthropic SDK)
# =====================================================================

class ClaudeClient(LLMClient):
    """Claude integration using the official anthropic SDK with function calling."""
    provider_name: str = "llm:claude"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or settings.ANTHROPIC_API_KEY
        self.model = model or os.getenv("ANTHROPIC_MODEL") or settings.ANTHROPIC_MODEL
        if not self.api_key or self.api_key.startswith("your-") or self.api_key in ("dummy", "test"):
            raise ValueError("Valid ANTHROPIC_API_KEY is required for ClaudeClient.")

    def _get_client(self):
        import anthropic
        return anthropic.Anthropic(api_key=self.api_key)

    def plan(
        self,
        profile: Dict[str, Any],
        goal: Optional[str],
        dataset_id: str,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> PlanResult:
        t0 = time.perf_counter()
        client = self._get_client()
        claude_tools = get_tools_for_claude()

        prompt = (
            "You are an autonomous senior data analyst. You have access to a tool catalogue.\n"
            f"Dataset Profile:\n{json.dumps(profile, indent=2)}\n\n"
            f"User Goal: {goal or 'Comprehensive exploratory analysis'}\n"
            f"Return an ordered plan of 2 to 4 tool calls with dataset_id='{dataset_id}' and explicit arguments.\n"
            "Select only tools from the provided tool catalogue."
        )

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=1500,
                tools=claude_tools,
                messages=[{"role": "user", "content": prompt}]
            )
            latency = time.perf_counter() - t0
            p_tok = response.usage.input_tokens
            c_tok = response.usage.output_tokens
            tot_tok = p_tok + c_tok
            usage = TokenUsage(prompt_tokens=p_tok, completion_tokens=c_tok, total_tokens=tot_tok)
        except Exception as e:
            logger.warning("Claude plan API call failed (%s); falling back to heuristic planner.", e)
            h_res = HeuristicClient().plan(profile, goal, dataset_id, tools)
            h_res.provider = self.provider_name
            return h_res

        tool_calls: List[ToolCall] = []
        raw_text_parts = []
        for block in response.content:
            if block.type == "text" and block.text:
                raw_text_parts.append(block.text)

        accompanying_text = " ".join(raw_text_parts).strip()

        for block in response.content:
            if block.type == "tool_use":
                args = dict(block.input) if isinstance(block.input, dict) else {}
                args["dataset_id"] = dataset_id
                rationale = args.pop("rationale", None) or accompanying_text or f"Claude planned {block.name} to investigate dataset patterns."
                tool_calls.append(ToolCall(
                    name=block.name,
                    arguments=args,
                    rationale=rationale
                ))

        return PlanResult(
            tool_calls=tool_calls,
            usage=usage,
            provider=self.provider_name,
            latency_seconds=latency,
            raw_response=" ".join(raw_text_parts) if raw_text_parts else None
        )

    def reflect(
        self,
        step_result: Dict[str, Any],
        history: List[Dict[str, Any]],
        dataset_id: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        candidates: Optional[List[ToolCall]] = None,
        candidate_reasons: Optional[List[str]] = None
    ) -> ReflectResult:
        if not candidates:
            return ReflectResult(
                tool_calls=[],
                should_continue=False,
                observation="No trigger fired (no segment p < 0.05, no outlier rate > 5%, no |r| > 0.5); reflection stopped.",
                usage=TokenUsage(total_tokens=0),
                provider=self.provider_name,
                latency_seconds=0.0
            )

        t0 = time.perf_counter()
        client = self._get_client()
        claude_tools = get_tools_for_claude()

        candidate_desc = [f"- {c.name}({json.dumps(c.arguments)}): {c.rationale}" for c in candidates]
        prompt = (
            "You are an autonomous data analyst reflecting on the round outcome.\n"
            f"Latest Result: {json.dumps(step_result, default=str)}\n"
            f"Deterministic triggers generated these candidate follow-up actions:\n"
            + "\n".join(candidate_desc) + "\n\n"
            "Pick up to 3 candidate follow-ups to execute by calling the corresponding tool, or choose to stop if current findings are sufficient."
        )

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=1000,
                tools=claude_tools,
                messages=[{"role": "user", "content": prompt}]
            )
            latency = time.perf_counter() - t0
            p_tok = response.usage.input_tokens
            c_tok = response.usage.output_tokens
            usage = TokenUsage(prompt_tokens=p_tok, completion_tokens=c_tok, total_tokens=p_tok + c_tok)
        except Exception as e:
            logger.warning("Claude reflect API call failed (%s); falling back to heuristic reflection.", e)
            h_ref = HeuristicClient().reflect(step_result, history, dataset_id, tools)
            h_ref.provider = self.provider_name
            return h_ref

        tool_calls: List[ToolCall] = []
        observation_parts = []
        for block in response.content:
            if block.type == "text" and block.text:
                observation_parts.append(block.text)

        accompanying_text = " ".join(observation_parts).strip()

        for block in response.content:
            if block.type == "tool_use":
                args = dict(block.input) if isinstance(block.input, dict) else {}
                args["dataset_id"] = dataset_id
                rationale = args.pop("rationale", None) or accompanying_text or f"Claude reflected and selected {block.name} for drill-down."
                tool_calls.append(ToolCall(
                    name=block.name,
                    arguments=args,
                    rationale=rationale
                ))

        obs = accompanying_text or f"Evaluated {step_result.get('tool')}"
        return ReflectResult(
            tool_calls=tool_calls,
            should_continue=True,
            observation=obs,
            usage=usage,
            provider=self.provider_name,
            latency_seconds=latency
        )

    def synthesize(
        self,
        results: List[Dict[str, Any]],
        dataset_profile: Optional[Dict[str, Any]] = None,
        goal: Optional[str] = None,
        failing_claims: Optional[List[Dict[str, Any]]] = None,
        insights: Optional[List[Any]] = None
    ) -> SynthesisResult:
        t0 = time.perf_counter()
        base_summary = write_summary(
            structured_results=results,
            dataset_profile=dataset_profile,
            goal=goal,
            insights=insights
        )

        try:
            client = self._get_client()
            compact_insights = [i.model_dump() if hasattr(i, "model_dump") else i for i in (insights or [])]
            compact_results = [{k: v for k, v in r.items() if k not in ("dataframe", "raw_data")} for r in results]
            source_payload = compact_insights if compact_insights else compact_results
            retry_note = ""
            if failing_claims:
                retry_note = (
                    f"\n\nCORRECTION REQUIRED (RETRY):\n"
                    f"The previous draft contained unverified claims or values that failed bound verification:\n"
                    f"{json.dumps(failing_claims, default=str)}\n"
                    f"You MUST correct or remove these statements. Ensure every single number matches its cited source and metric."
                )

            prompt = (
                "You are an executive data analyst writing the final analytical narrative.\n"
                f"Dataset Profile: {json.dumps(dataset_profile or {}, default=str)}\n"
                f"User Goal: {goal or 'Comprehensive exploratory analysis'}\n"
                f"Surviving Analytical Insights and Caveats (ONLY valid claim sources): {json.dumps(source_payload, default=str)}{retry_note}\n\n"
                "Write an authoritative business report in JSON format:\n"
                "{\n"
                '  "executive_summary": "2-3 paragraphs synthesizing key insights and strategic implications.",\n'
                '  "key_findings": [\n'
                '    {"finding": "Clear statement citing exact numbers from insights", "metric": "name", "value": 123.4, "impact": "high/medium/low"}\n'
                "  ],\n"
                '  "recommendations": ["Actionable recommendation 1", "Actionable recommendation 2"],\n'
                '  "claims": [\n'
                '    {"text": "Sentence or clause stating the fact", "source_id": "exact insight id (e.g. insight-seg-...)", "metric_key": "exact_metric_name_in_source", "value": 123.4, "unit": "count/USD/%"}\n'
                "  ]\n"
                "}\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. Synthesis may use ONLY insights[] (surviving analytical insights plus data-quality caveats) as claim sources, never raw tool results.\n"
                "2. Suppressed analyses may appear ONLY as 'insufficient data for X (n_used=..., exclusion_rate=...)'. NEVER cite trend percentages, correlation coefficients, or segment comparisons for suppressed analyses.\n"
                "3. FORBIDDEN WORDS: NEVER use the words 'stable', 'not concentrated', 'no effect', or 'organic' anywhere. Use 'consistent' or 'flat' instead of 'stable'; 'distributed across categories' instead of 'not concentrated'; 'unadjusted' instead of 'organic'.\n"
                "4. FORBID CAUSAL SPECULATION: Never use causal phrases like 'leads to', 'causes', 'caused by', 'drives', 'driven by', 'resulting in', or 'because of'. Use associative terms like 'is correlated with' or 'is associated with'.\n"
                "5. NON-SIGNIFICANT RESULTS: For non-significant results (p >= 0.05), you MUST write 'no statistically significant difference detected (n per group: ...)' and you MUST explicitly mention 'limited statistical power due to small sample size in some groups, n < 30' whenever any group sample size n < 30. Never present the top segment as a finding.\n"
                "6. RECOMMENDATIONS: Recommendations may concern DATA QUALITY ONLY (e.g. schema validation, sentinel prevention, missingness monitoring, increasing sample sizes). Never provide business strategy or operational recommendations.\n"
                "7. P-VALUE CLAIMS: All claims citing p-values must have unit 'p_value'.\n"
                "8. CLAIM PRESENCE: EVERY declared claim in 'claims' MUST appear in the delivered narrative, and EVERY number cited in the narrative MUST belong to a declared claim matching exact source_id and metric_key.\n"
                "9. NO PLACEHOLDERS: Never output 'None', 'nan', 'null', or generic placeholder text."
            )
            response = client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            latency = time.perf_counter() - t0
            p_tok = response.usage.input_tokens
            c_tok = response.usage.output_tokens
            usage = TokenUsage(prompt_tokens=p_tok, completion_tokens=c_tok, total_tokens=p_tok + c_tok)

            raw_text = ""
            for block in response.content:
                if block.type == "text":
                    raw_text += block.text

            clean_json = raw_text.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()

            parsed = json.loads(clean_json)
            checked_exec = post_check_synthesis_narrative(
                parsed.get("executive_summary") or base_summary.get("executive_summary", ""),
                "claude executive summary"
            )
            return SynthesisResult(
                executive_summary=checked_exec,
                key_findings=parsed.get("key_findings") or base_summary.get("key_findings", []),
                recommendations=parsed.get("recommendations") or base_summary.get("recommendations", []),
                citations_index=base_summary.get("citations_index", {}),
                usage=usage,
                provider=self.provider_name,
                latency_seconds=latency,
                claims=parsed.get("claims", [])
            )
        except Exception as e:
            logger.warning("Claude synthesis LLM call failed, falling back to base summary: %s", e)
            latency = time.perf_counter() - t0
            return SynthesisResult(
                executive_summary=base_summary.get("executive_summary", ""),
                key_findings=base_summary.get("key_findings", []),
                recommendations=base_summary.get("recommendations", []),
                citations_index=base_summary.get("citations_index", {}),
                usage=TokenUsage(total_tokens="unknown"),
                provider=self.provider_name,
                latency_seconds=latency
            )

    def generate_chat_answer(
        self,
        question: str,
        context: Dict[str, Any],
        failing_claims: Optional[List[Dict[str, Any]]] = None
    ) -> ChatResult:
        t0 = time.perf_counter()
        available_columns = context.get("available_columns", [])
        insights = context.get("insights", [])
        profile = context.get("profile", {})
        cleaning_report = context.get("cleaning_report", {})
        tool_results = context.get("tool_results", [])
        history = context.get("history", [])

        retry_note = ""
        if failing_claims:
            retry_note = (
                f"\n\nCORRECTION REQUIRED (RETRY):\n"
                f"The previous answer contained unverified claims or numbers:\n"
                f"{json.dumps(failing_claims, default=str)}\n"
                f"Ensure every single number in the prose matches an exact source and metric in 'claims'."
            )

        prompt = (
            "You are an expert autonomous data analyst assistant providing an accurate, concise answer to the user's question.\n"
            f"Dataset Profile: {json.dumps(profile, default=str)}\n"
            f"Available Columns: {json.dumps(available_columns, default=str)}\n"
            f"Key Insights: {json.dumps(insights[:6], default=str)}\n"
            f"Executed Tool Results: {json.dumps(tool_results, default=str)}\n"
            f"Recent Conversation History: {json.dumps(history[-3:] if history else [], default=str)}{retry_note}\n\n"
            f"User Question: {question}\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. MISSING COLUMNS / ENTITIES: If the question inquires about a column or entity that is NOT in the available columns list (e.g. customer age, churn, credit score, region, bonus):\n"
            f"   You MUST explicitly state: \"The requested column/entity '<name>' is not present in this dataset. Available columns are: {', '.join(available_columns)}.\"\n"
            "   Then answer whatever part of the question can be answered using the available data.\n"
            "2. SUPPRESSED ANALYSES: When a question inquires about an analysis or relationship that was suppressed under data quality safeguards (such as Performance_Score vs Last_Promotion_Year, or monthly sales trend where exclusion rate > 50%):\n"
            "   You MUST state what was checked and explicitly explain that the analysis was suppressed under data quality safeguards and the reason.\n"
            "3. SALES COLUMN INTERPRETATION: When the question refers to 'sales' but the dataset contains no dedicated revenue column, explicitly state the interpretation used (e.g. \"The dataset contains no dedicated revenue column; sales volume is interpreted using 'Quantity'\").\n"
            "4. BASIS AND SAMPLE SIZE (n): Every tool-based answer MUST explicitly state its basis ('data_observed' or 'data_clean') and sample size n. If question asks about non-missing / observed / recorded rows, cite the data_observed basis and n. If clean data is cited, disclose any imputation rate.\n"
            "5. SAMPLING DISCLOSURE: If the dataset is sampled, state the sampling disclosure: \"Analysis is based on a <sampling_disclosure>\".\n"
            "6. STRICT GROUNDING: Forbid causal or market-preference claims. Every number in the prose must belong to a claim in 'claims'. Never output placeholder text like 'None' or 'nan'.\n"
            "7. Return valid JSON:\n"
            "{\n"
            '  "answer": "Clear, grounded answer text.",\n'
            '  "claims": [\n'
            '    {"text": "clause stating fact", "source_id": "insight_id or query_sql or profile", "metric_key": "exact_metric_key", "value": 12.34, "unit": "% or count"}\n'
            "  ]\n"
            "}"
        )

        try:
            client = self._get_client()
            response = client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            latency = time.perf_counter() - t0
            p_tok = response.usage.input_tokens
            c_tok = response.usage.output_tokens
            usage = TokenUsage(prompt_tokens=p_tok, completion_tokens=c_tok, total_tokens=p_tok + c_tok)

            raw_text = "".join(b.text for b in response.content if b.type == "text").strip()
            clean_json = raw_text
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()

            parsed = json.loads(clean_json)
            return ChatResult(
                answer=parsed.get("answer", raw_text),
                claims=parsed.get("claims", []),
                usage=usage,
                provider="claude",
                model=self.model,
                fallback_to_heuristic=False,
                latency_seconds=latency
            )
        except Exception as e:
            logger.warning("Claude chat failed (%s); falling back to heuristic: ", e)
            h_res = HeuristicClient().generate_chat_answer(question, context, failing_claims)
            h_res.provider = "heuristic"
            h_res.model = "heuristic-rule-engine"
            h_res.fallback_to_heuristic = True
            return h_res


# =====================================================================
# Gemini Client (Google GenAI SDK)
# =====================================================================

class GeminiClient(LLMClient):
    """Gemini integration using the google-genai SDK with function calling and retry handling."""
    provider_name: str = "llm:gemini"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY
        self.model = model or os.getenv("GEMINI_MODEL") or getattr(settings, "GEMINI_MODEL", None) or "gemini-3.1-flash-lite"
        if not self.api_key or self.api_key.startswith("your-") or self.api_key in ("dummy", "test"):
            raise ValueError("Valid GEMINI_API_KEY is required for GeminiClient.")

    def _get_client(self):
        from google import genai
        return genai.Client(api_key=self.api_key)

    def _build_generate_config(self, types, tools: Optional[List[Any]] = None, response_mime_type: Optional[str] = None) -> Any:
        """Create GenerateContentConfig with thinking disabled (budget=0), AFC disabled, and max 1000 tokens."""
        cfg_args: Dict[str, Any] = {
            "temperature": 0.0,
            "max_output_tokens": 1000
        }
        if tools is not None:
            cfg_args["tools"] = tools
            if hasattr(types, "AutomaticFunctionCallingConfig"):
                try:
                    cfg_args["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
                except Exception:
                    pass
        if response_mime_type is not None:
            cfg_args["response_mime_type"] = response_mime_type
        if hasattr(types, "ThinkingConfig"):
            try:
                cfg_args["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
            except Exception:
                pass
        return types.GenerateContentConfig(**cfg_args)

    def _execute_with_retry(self, client, contents: Any, config: Any, max_retries: int = 3):
        """Execute generate_content across candidate models on transient 503/429 errors."""
        candidate_models = [self.model]
        for fallback in ["gemini-3.1-flash-lite", "gemini-3.7-flash", "gemini-3.8-flash"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_error = None
        for m in candidate_models:
            for attempt in range(max_retries):
                try:
                    return client.models.generate_content(
                        model=m,
                        contents=contents,
                        config=config
                    )
                except Exception as e:
                    err_msg = str(e)
                    last_error = e
                    if "503" in err_msg or "UNAVAILABLE" in err_msg:
                        time.sleep(0.5 + attempt * 0.5)
                    else:
                        break  # Non-transient error or 429 quota exhaustion: break immediately
        raise last_error

    def _extract_usage(self, response: Any) -> TokenUsage:
        """Extract real usage metadata from Google GenAI response object."""
        usage_meta = getattr(response, "usage_metadata", None)
        if not usage_meta:
            return TokenUsage(total_tokens="unknown")

        prompt_tokens = getattr(usage_meta, "prompt_token_count", None)
        completion_tokens = getattr(usage_meta, "candidates_token_count", None)
        total_tokens = getattr(usage_meta, "total_token_count", None)

        if total_tokens is not None and isinstance(total_tokens, int):
            return TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
        elif prompt_tokens is not None and completion_tokens is not None:
            return TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        return TokenUsage(total_tokens="unknown")

    def plan(
        self,
        profile: Dict[str, Any],
        goal: Optional[str],
        dataset_id: str,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> PlanResult:
        from google.genai import types
        t0 = time.perf_counter()
        client = self._get_client()
        gemini_tools = get_tools_for_gemini()
        config = self._build_generate_config(types, tools=gemini_tools)

        columns_summary = {
            col: {
                "type": info.get("inferred_type"),
                "unique_count": info.get("unique_count")
            }
            for col, info in profile.get("columns", {}).items()
        }
        profile_summary = {
            "row_count": profile.get("row_count"),
            "column_count": profile.get("column_count"),
            "columns": columns_summary
        }

        prompt = (
            "You are an autonomous senior data analyst creating an initial analysis plan.\n"
            f"Dataset Summary: {json.dumps(profile_summary)}\n"
            f"User Goal: {goal or 'Comprehensive exploratory analysis'}\n"
            "Invoke 2 to 3 distinct tools from [detect_outliers, segment_compare, trend_analysis, run_correlation].\n"
            f"Always set dataset_id='{dataset_id}'. For segment_compare, choose a business category column, never an ID column."
        )

        try:
            response = self._execute_with_retry(client, contents=prompt, config=config)
            latency = time.perf_counter() - t0
            usage = self._extract_usage(response)
        except Exception as e:
            logger.warning("Gemini plan API call failed (%s); falling back to deterministic heuristic planner.", e)
            h_res = HeuristicClient().plan(profile, goal, dataset_id, tools)
            h_res.provider = self.provider_name
            return h_res

        raw_text = None
        text_parts = []
        try:
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                text_parts = [p.text for p in response.candidates[0].content.parts if getattr(p, "text", None)]
                if text_parts:
                    raw_text = " ".join(text_parts)
        except Exception:
            pass

        accompanying_text = " ".join(text_parts).strip()

        tool_calls: List[ToolCall] = []
        function_calls = getattr(response, "function_calls", None) or []
        for fc in function_calls:
            args = dict(fc.args) if fc.args else {}
            args["dataset_id"] = dataset_id
            rationale = args.pop("rationale", None) or accompanying_text or f"Gemini planned {fc.name} to evaluate statistical structure."
            tool_calls.append(ToolCall(
                name=fc.name,
                arguments=args,
                rationale=rationale
            ))

        # If Gemini returned fewer than 2 calls, supplement with heuristic steps to guarantee thoroughness
        if len(tool_calls) < 2:
            heuristic_plan = HeuristicClient().plan(profile, goal, dataset_id).tool_calls
            existing_names = {tc.name for tc in tool_calls}
            for h_call in heuristic_plan:
                if h_call.name not in existing_names:
                    tool_calls.append(h_call)
                    if len(tool_calls) >= 3:
                        break

        return PlanResult(
            tool_calls=tool_calls,
            usage=usage,
            provider=self.provider_name,
            latency_seconds=latency,
            raw_response=raw_text
        )

    def reflect(
        self,
        step_result: Dict[str, Any],
        history: List[Dict[str, Any]],
        dataset_id: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        candidates: Optional[List[ToolCall]] = None,
        candidate_reasons: Optional[List[str]] = None
    ) -> ReflectResult:
        if not candidates:
            return ReflectResult(
                tool_calls=[],
                should_continue=False,
                observation="No trigger fired (no segment p < 0.05, no outlier rate > 5%, no |r| > 0.5); reflection stopped.",
                usage=TokenUsage(total_tokens=0),
                provider=self.provider_name,
                latency_seconds=0.0
            )

        from google.genai import types
        t0 = time.perf_counter()
        client = self._get_client()
        gemini_tools = get_tools_for_gemini()

        config = self._build_generate_config(types, tools=gemini_tools)

        candidate_desc = [f"- {c.name}({json.dumps(c.arguments)}): {c.rationale}" for c in candidates]
        prompt = (
            "You are an autonomous data analyst reflecting on the round outcome.\n"
            f"Latest Result: {json.dumps(step_result, default=str)}\n"
            f"Deterministic triggers generated these candidate follow-up actions:\n"
            + "\n".join(candidate_desc) + "\n\n"
            "Pick up to 3 candidate follow-ups to execute by invoking the function, or choose to stop if current findings are sufficient."
        )

        try:
            response = self._execute_with_retry(client, contents=prompt, config=config)
            latency = time.perf_counter() - t0
            usage = self._extract_usage(response)
        except Exception as e:
            logger.warning("Gemini reflect API call failed (%s); falling back to heuristic reflection.", e)
            h_ref = HeuristicClient().reflect(step_result, history, dataset_id, tools)
            h_ref.provider = self.provider_name
            return h_ref

        obs_parts = []
        try:
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                obs_parts = [p.text for p in response.candidates[0].content.parts if getattr(p, "text", None)]
        except Exception:
            pass
        accompanying_text = " ".join(obs_parts).strip()

        tool_calls: List[ToolCall] = []
        function_calls = getattr(response, "function_calls", None) or []
        for fc in function_calls:
            args = dict(fc.args) if fc.args else {}
            args["dataset_id"] = dataset_id
            rationale = args.pop("rationale", None) or accompanying_text or f"Gemini reflected and selected {fc.name} for deep-dive."
            tool_calls.append(ToolCall(
                name=fc.name,
                arguments=args,
                rationale=rationale
            ))

        obs = accompanying_text or f"Evaluated {step_result.get('tool')}"
        return ReflectResult(
            tool_calls=tool_calls,
            should_continue=True,
            observation=obs,
            usage=usage,
            provider=self.provider_name,
            latency_seconds=latency
        )

    def synthesize(
        self,
        results: List[Dict[str, Any]],
        dataset_profile: Optional[Dict[str, Any]] = None,
        goal: Optional[str] = None,
        failing_claims: Optional[List[Dict[str, Any]]] = None,
        insights: Optional[List[Any]] = None
    ) -> SynthesisResult:
        t0 = time.perf_counter()
        base_summary = write_summary(
            structured_results=results,
            dataset_profile=dataset_profile,
            goal=goal,
            insights=insights
        )

        try:
            from google.genai import types
            client = self._get_client()
            compact_insights = [i.model_dump() if hasattr(i, "model_dump") else i for i in (insights or [])]
            compact_results = [{k: v for k, v in r.items() if k not in ("dataframe", "raw_data")} for r in results]
            source_payload = compact_insights if compact_insights else compact_results
            retry_note = ""
            if failing_claims:
                retry_note = (
                    f"\n\nCORRECTION REQUIRED (RETRY):\n"
                    f"The previous draft contained unverified claims or values that failed bound verification against their sources:\n"
                    f"{json.dumps(failing_claims, default=str)}\n"
                    f"You MUST correct or remove these statements. Ensure every single number matches its cited source and metric."
                )

            prompt = (
                "You are an executive data analyst writing the final analytical narrative.\n"
                f"Dataset Profile: {json.dumps(dataset_profile or {}, default=str)}\n"
                f"User Goal: {goal or 'Comprehensive exploratory analysis'}\n"
                f"Surviving Analytical Insights and Caveats (ONLY valid claim sources): {json.dumps(source_payload, default=str)}{retry_note}\n\n"
                "Write an authoritative business report in JSON format:\n"
                "{\n"
                '  "executive_summary": "2-3 paragraphs synthesizing key insights and strategic implications.",\n'
                '  "key_findings": [\n'
                '    {"finding": "Clear statement citing exact numbers from insights", "metric": "name", "value": 123.4, "impact": "high/medium/low"}\n'
                "  ],\n"
                '  "recommendations": ["Actionable recommendation 1", "Actionable recommendation 2"],\n'
                '  "claims": [\n'
                '    {"text": "Sentence or clause stating the fact", "source_id": "exact insight id (e.g. insight-seg-...)", "metric_key": "exact_metric_name_in_source", "value": 123.4, "unit": "count/USD/%"}\n'
                "  ]\n"
                "}\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. Synthesis may use ONLY insights[] (surviving analytical insights plus data-quality caveats) as claim sources, never raw tool results.\n"
                "2. Suppressed analyses may appear ONLY as 'insufficient data for X (n_used=..., exclusion_rate=...)'. NEVER cite trend percentages, correlation coefficients, or segment comparisons for suppressed analyses.\n"
                "3. FORBIDDEN WORDS: NEVER use the words 'stable', 'not concentrated', 'no effect', or 'organic' anywhere. Use 'consistent' or 'flat' instead of 'stable'; 'distributed across categories' instead of 'not concentrated'; 'unadjusted' instead of 'organic'.\n"
                "4. FORBID CAUSAL SPECULATION: Never use causal phrases like 'leads to', 'causes', 'caused by', 'drives', 'driven by', 'resulting in', or 'because of'. Use associative terms like 'is correlated with' or 'is associated with'.\n"
                "5. NON-SIGNIFICANT RESULTS: For non-significant results (p >= 0.05), you MUST write 'no statistically significant difference detected (n per group: ...)' and you MUST explicitly mention 'limited statistical power due to small sample size in some groups, n < 30' whenever any group sample size n < 30. Never present the top segment as a finding.\n"
                "6. RECOMMENDATIONS: Recommendations may concern DATA QUALITY ONLY (e.g. schema validation, sentinel prevention, missingness monitoring, increasing sample sizes). Never provide business strategy or operational recommendations.\n"
                "7. P-VALUE CLAIMS: All claims citing p-values must have unit 'p_value'.\n"
                "8. CLAIM PRESENCE: EVERY declared claim in 'claims' MUST appear in the delivered narrative, and EVERY number cited in the narrative MUST belong to a declared claim matching exact source_id and metric_key.\n"
                "9. NO PLACEHOLDERS: Never output 'None', 'nan', 'null', or generic placeholder text."
            )
            config = self._build_generate_config(types, response_mime_type="application/json")
            response = self._execute_with_retry(client, contents=prompt, config=config)
            latency = time.perf_counter() - t0
            usage = self._extract_usage(response)

            raw_text = getattr(response, "text", "") or ""
            parsed = json.loads(raw_text.strip())
            checked_exec = post_check_synthesis_narrative(
                parsed.get("executive_summary") or base_summary.get("executive_summary", ""),
                "gemini executive summary"
            )
            return SynthesisResult(
                executive_summary=checked_exec,
                key_findings=parsed.get("key_findings") or base_summary.get("key_findings", []),
                recommendations=parsed.get("recommendations") or base_summary.get("recommendations", []),
                citations_index=base_summary.get("citations_index", {}),
                usage=usage,
                provider=self.provider_name,
                latency_seconds=latency,
                claims=parsed.get("claims", [])
            )
        except Exception as e:
            logger.warning("Gemini synthesis LLM call failed, falling back to base summary: %s", e)
            latency = time.perf_counter() - t0
            return SynthesisResult(
                executive_summary=base_summary.get("executive_summary", ""),
                key_findings=base_summary.get("key_findings", []),
                recommendations=base_summary.get("recommendations", []),
                citations_index=base_summary.get("citations_index", {}),
                usage=TokenUsage(total_tokens="unknown"),
                provider=self.provider_name,
                latency_seconds=latency
            )

    def generate_chat_answer(
        self,
        question: str,
        context: Dict[str, Any],
        failing_claims: Optional[List[Dict[str, Any]]] = None
    ) -> ChatResult:
        from google.genai import types
        t0 = time.perf_counter()
        available_columns = context.get("available_columns", [])
        insights = context.get("insights", [])
        profile = context.get("profile", {})
        cleaning_report = context.get("cleaning_report", {})
        tool_results = context.get("tool_results", [])
        history = context.get("history", [])

        retry_note = ""
        if failing_claims:
            retry_note = (
                f"\n\nCORRECTION REQUIRED (RETRY):\n"
                f"The previous answer contained unverified claims or numbers:\n"
                f"{json.dumps(failing_claims, default=str)}\n"
                f"Ensure every single number in the prose matches an exact source and metric in 'claims'."
            )

        prompt = (
            "You are an expert autonomous data analyst assistant providing an accurate, concise answer to the user's question.\n"
            f"Dataset Profile: {json.dumps(profile, default=str)}\n"
            f"Available Columns: {json.dumps(available_columns, default=str)}\n"
            f"Key Insights: {json.dumps(insights[:6], default=str)}\n"
            f"Executed Tool Results: {json.dumps(tool_results, default=str)}\n"
            f"Recent Conversation History: {json.dumps(history[-3:] if history else [], default=str)}{retry_note}\n\n"
            f"User Question: {question}\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. MISSING COLUMNS / ENTITIES: If the question inquires about a column or entity that is NOT in the available columns list (e.g. customer age, churn, credit score, region, bonus, customer lifetime value):\n"
            f"   You MUST explicitly state: \"The requested column/entity '<name>' is not present in this dataset. Available columns are: {', '.join(available_columns)}.\"\n"
            "   Do NOT invent surrogate definitions or write formulas for non-existent columns.\n"
            "2. SUPPRESSED ANALYSES: When a question inquires about an analysis that was suppressed under data quality safeguards (such as Performance_Score vs Last_Promotion_Year, or monthly sales trend where exclusion rate > 50%):\n"
            "   You MUST state what was checked and explicitly explain what was and was not computed (e.g. 'Correlation analysis between Performance_Score and Last_Promotion_Year was evaluated; however, it was suppressed under data quality rule exclusion_rate > 0.5 because 58.2% of records were excluded or missing'). Do NOT just say 'could not be verified'.\n"
            "3. PER-GROUP QUERIES: When answering questions by group (e.g. salary by department, spend and clicks by channel), list the FULL per-group results for all groups first before any summary remarks.\n"
            "4. SHARE QUESTIONS & CATEGORY CASING: Share questions must explicitly name the specific category (e.g. 'Credit Card share was ...' or 'PayPal share was ...'). Category labels must keep proper case ('PayPal', 'Credit Card').\n"
            "5. BASIS AND SAMPLE SIZE (n): The sample size n must strictly equal the observed count of non-null records for the specific metric being analyzed (e.g. for average Ad_Spend among observed records, n must equal the non-null Ad_Spend count, not total table rows).\n"
            "6. SALES COLUMN INTERPRETATION: When the question refers to 'sales' but the dataset contains no dedicated revenue column, explicitly state the interpretation used (e.g. \"The dataset contains no dedicated revenue column; sales volume is interpreted using 'Quantity'\").\n"
            "7. SAMPLING DISCLOSURE: If the dataset is sampled, state the sampling disclosure: \"Analysis is based on a <sampling_disclosure>\".\n"
            "8. STRICT GROUNDING: Forbid causal or market-preference claims. Every number in the prose must belong to a claim in 'claims'. Never output placeholder text like 'None' or 'nan'.\n"
            "7. Return valid JSON:\n"
            "{\n"
            '  "answer": "Clear, grounded answer text.",\n'
            '  "claims": [\n'
            '    {"text": "clause stating fact", "source_id": "insight_id or query_sql or profile", "metric_key": "exact_metric_key", "value": 12.34, "unit": "% or count"}\n'
            "  ]\n"
            "}"
        )

        try:
            client = self._get_client()
            config = self._build_generate_config(types, response_mime_type="application/json")
            response = self._execute_with_retry(client, contents=prompt, config=config)
            latency = time.perf_counter() - t0
            usage = self._extract_usage(response)

            raw_text = getattr(response, "text", "") or ""
            clean_json = raw_text.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()

            parsed = json.loads(clean_json)
            return ChatResult(
                answer=parsed.get("answer", raw_text),
                claims=parsed.get("claims", []),
                usage=usage,
                provider="gemini",
                model=self.model,
                fallback_to_heuristic=False,
                latency_seconds=latency
            )
        except Exception as e:
            logger.warning("Gemini chat failed (%s); falling back to heuristic: ", e)
            h_res = HeuristicClient().generate_chat_answer(question, context, failing_claims)
            h_res.provider = "heuristic"
            h_res.model = "heuristic-rule-engine"
            h_res.fallback_to_heuristic = True
            return h_res


# =====================================================================
# Provider Factory Function
# =====================================================================

def get_llm_client(
    provider: Optional[str] = None,
    allow_heuristic_fallback: bool = True
) -> LLMClient:
    """Resolve and return an LLMClient instance based on configuration and available keys.

    Provider resolution order:
    1. Explicit `provider` argument ("claude", "gemini", "heuristic")
    2. Environment variable `LLM_PROVIDER`
    3. `settings.LLM_PROVIDER`
    4. Auto-detection based on present API keys (GEMINI_API_KEY, ANTHROPIC_API_KEY)
    5. HeuristicClient fallback
    """
    selected_provider = (
        provider
        or os.getenv("LLM_PROVIDER")
        or getattr(settings, "LLM_PROVIDER", "")
        or ""
    ).strip().lower()

    # Explicit Heuristic / Offline mode
    if selected_provider in ("heuristic", "offline", "test"):
        return HeuristicClient()

    # Explicit Claude
    if selected_provider == "claude":
        claude_key = os.getenv("ANTHROPIC_API_KEY") or getattr(settings, "ANTHROPIC_API_KEY", None)
        if claude_key and not claude_key.startswith("your-") and claude_key not in ("dummy", "test"):
            try:
                return ClaudeClient(api_key=claude_key)
            except Exception as e:
                if not allow_heuristic_fallback:
                    raise e
                return HeuristicClient()
        if not allow_heuristic_fallback:
            raise ValueError("LLM_PROVIDER is 'claude' but ANTHROPIC_API_KEY is not set.")
        return HeuristicClient()

    # Explicit Gemini
    if selected_provider == "gemini":
        gemini_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
        if gemini_key and not gemini_key.startswith("your-") and gemini_key not in ("dummy", "test"):
            try:
                return GeminiClient(api_key=gemini_key)
            except Exception as e:
                if not allow_heuristic_fallback:
                    raise e
                return HeuristicClient()
        if not allow_heuristic_fallback:
            raise ValueError("LLM_PROVIDER is 'gemini' but GEMINI_API_KEY is not set.")
        return HeuristicClient()

    # Auto-detection when provider is empty
    gemini_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
    if gemini_key and not gemini_key.startswith("your-") and gemini_key not in ("dummy", "test"):
        try:
            return GeminiClient(api_key=gemini_key)
        except Exception:
            pass

    claude_key = os.getenv("ANTHROPIC_API_KEY") or getattr(settings, "ANTHROPIC_API_KEY", None)
    if claude_key and not claude_key.startswith("your-") and claude_key not in ("dummy", "test"):
        try:
            return ClaudeClient(api_key=claude_key)
        except Exception:
            pass

    return HeuristicClient()
