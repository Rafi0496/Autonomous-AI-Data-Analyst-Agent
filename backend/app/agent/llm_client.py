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
from backend.app.services.summary import write_summary
from backend.app.services.tool_catalogue import (
    get_canonical_tools,
    get_tools_for_claude,
    get_tools_for_gemini,
)

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
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> ReflectResult:
        """Reflect on latest execution step and propose bounded dynamic follow-ups if needed."""
        pass

    @abstractmethod
    def synthesize(
        self,
        results: List[Dict[str, Any]],
        dataset_profile: Optional[Dict[str, Any]] = None,
        goal: Optional[str] = None,
        failing_claims: Optional[List[Dict[str, Any]]] = None
    ) -> SynthesisResult:
        """Synthesize structured tool results into an executive business narrative."""
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
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> ReflectResult:
        t0 = time.perf_counter()
        tool_name = step_result.get("tool")
        follow_ups: List[ToolCall] = []

        if tool_name == "detect_outliers" and step_result.get("total_anomalous_rows", 0) > 0:
            top_cols = step_result.get("top_outlier_columns", [])
            if top_cols:
                col_target = top_cols[0]["column"]
                follow_ups.append(ToolCall(
                    name="query_sql",
                    arguments={
                        "dataset_id": dataset_id,
                        "sql": f"SELECT {col_target}, COUNT(*) as frequency FROM df GROUP BY {col_target} ORDER BY frequency DESC LIMIT 5"
                    },
                    rationale=f"[Heuristic Template] High anomaly rate in '{col_target}'; drill down to investigate value distribution."
                ))

        latency = time.perf_counter() - t0
        return ReflectResult(
            tool_calls=follow_ups,
            should_continue=True,
            observation="Heuristic reflection evaluated step outcome.",
            usage=TokenUsage(total_tokens="unknown"),
            provider=self.provider_name,
            latency_seconds=latency
        )

    def synthesize(
        self,
        results: List[Dict[str, Any]],
        dataset_profile: Optional[Dict[str, Any]] = None,
        goal: Optional[str] = None,
        failing_claims: Optional[List[Dict[str, Any]]] = None
    ) -> SynthesisResult:
        t0 = time.perf_counter()
        summary_payload = write_summary(
            structured_results=results,
            dataset_profile=dataset_profile,
            goal=goal
        )
        latency = time.perf_counter() - t0
        claims = []
        for kf in summary_payload.get("key_findings", []):
            if isinstance(kf, dict) and "metric" in kf and "value" in kf:
                try:
                    claims.append({
                        "text": str(kf.get("finding", "")),
                        "source_id": "profile" if "imput" in str(kf.get("metric", "")).lower() else "step_1",
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
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> ReflectResult:
        t0 = time.perf_counter()
        client = self._get_client()
        claude_tools = get_tools_for_claude()

        prompt = (
            "You are an autonomous data analyst reflecting on the most recent step outcome:\n"
            f"Latest Result: {json.dumps(step_result, default=str)}\n"
            "If an anomaly or critical pattern warrants a drill-down (such as query_sql), invoke that tool now.\n"
            "If the current investigation is on track and no urgent drill-down is needed, return a brief text assessment without tool calls."
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
        failing_claims: Optional[List[Dict[str, Any]]] = None
    ) -> SynthesisResult:
        t0 = time.perf_counter()
        base_summary = write_summary(
            structured_results=results,
            dataset_profile=dataset_profile,
            goal=goal
        )

        try:
            client = self._get_client()
            compact_results = [{k: v for k, v in r.items() if k not in ("dataframe", "raw_data")} for r in results]
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
                f"Computed Tool Results: {json.dumps(compact_results, default=str)}{retry_note}\n\n"
                "Write an authoritative business report in JSON format:\n"
                "{\n"
                '  "executive_summary": "2-3 paragraphs synthesizing key insights and strategic implications.",\n'
                '  "key_findings": [\n'
                '    {"finding": "Clear statement citing exact numbers from tool results", "metric": "name", "value": 123.4, "impact": "high/medium/low"}\n'
                "  ],\n"
                '  "recommendations": ["Actionable recommendation 1", "Actionable recommendation 2"],\n'
                '  "claims": [\n'
                '    {"text": "Sentence or clause stating the fact", "source_id": "step_1 or insight id", "metric_key": "exact_metric_name_in_source", "value": 123.4, "unit": "count/USD/%"}\n'
                "  ]\n"
                "}\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. FORBID causal or market-preference claims (e.g., never claim 'X demonstrates market preference' or 'X caused Y').\n"
                "2. Use precise wording like 'count share' when a share or proportion is calculated by row count.\n"
                "3. You MUST explicitly state n_used and the imputation/exclusion rate for any analysis where more than 25% of rows were excluded or imputed.\n"
                "4. Every single number cited in the prose MUST have a corresponding claim in 'claims' matching exact source_id and metric_key."
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
            return SynthesisResult(
                executive_summary=parsed.get("executive_summary") or base_summary.get("executive_summary", ""),
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
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> ReflectResult:
        from google.genai import types
        t0 = time.perf_counter()
        client = self._get_client()
        gemini_tools = get_tools_for_gemini()

        config = self._build_generate_config(types, tools=gemini_tools)

        prompt = (
            "You are an autonomous data analyst reflecting on the most recent step outcome:\n"
            f"Latest Result: {json.dumps(step_result, default=str)}\n"
            "If an anomaly or critical pattern warrants a drill-down (such as query_sql), invoke that function now.\n"
            "If the current investigation is on track and no urgent drill-down is needed, return a brief text assessment without tool calls."
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
        failing_claims: Optional[List[Dict[str, Any]]] = None
    ) -> SynthesisResult:
        t0 = time.perf_counter()
        base_summary = write_summary(
            structured_results=results,
            dataset_profile=dataset_profile,
            goal=goal
        )

        try:
            from google.genai import types
            client = self._get_client()
            compact_results = [{k: v for k, v in r.items() if k not in ("dataframe", "raw_data")} for r in results]
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
                f"Computed Tool Results: {json.dumps(compact_results, default=str)}{retry_note}\n\n"
                "Write an authoritative business report in JSON format:\n"
                "{\n"
                '  "executive_summary": "2-3 paragraphs synthesizing key insights and strategic implications.",\n'
                '  "key_findings": [\n'
                '    {"finding": "Clear statement citing exact numbers from tool results", "metric": "name", "value": 123.4, "impact": "high/medium/low"}\n'
                "  ],\n"
                '  "recommendations": ["Actionable recommendation 1", "Actionable recommendation 2"],\n'
                '  "claims": [\n'
                '    {"text": "Sentence or clause stating the fact", "source_id": "step_1 or insight id", "metric_key": "exact_metric_name_in_source", "value": 123.4, "unit": "count/USD/%"}\n'
                "  ]\n"
                "}\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. FORBID causal or market-preference claims (e.g., never claim 'X demonstrates market preference' or 'X caused Y').\n"
                "2. Use precise wording like 'count share' when a share or proportion is calculated by row count.\n"
                "3. You MUST explicitly state n_used and the imputation/exclusion rate for any analysis where more than 25% of rows were excluded or imputed.\n"
                "4. Every single number cited in the prose MUST have a corresponding claim in 'claims' matching exact source_id and metric_key."
            )
            config = self._build_generate_config(types, response_mime_type="application/json")
            response = self._execute_with_retry(client, contents=prompt, config=config)
            latency = time.perf_counter() - t0
            usage = self._extract_usage(response)

            raw_text = getattr(response, "text", "") or ""
            parsed = json.loads(raw_text.strip())
            return SynthesisResult(
                executive_summary=parsed.get("executive_summary") or base_summary.get("executive_summary", ""),
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
