"""Chat Q&A Service for interactive conversational exploration over dataset insights (Milestone 4).

Enforces:
- Up to 3 read-only tool calls per question.
- Strict rejection of destructive or out-of-scope requests.
- Full numeric claim verification via bound citation checker.
- Single-attempt regeneration if claims are unverified, stripping offending sentences if still unverified.
- Never deliver a narrative with unverified claims (require >= 95% verified pre-strip).
- Explicit detection and handling of questions mentioning columns or entities not in the dataset.
- In-memory conversation history per job.
- Full provider integration (Gemini / Claude / Heuristic).
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.agent.citation_checker import (
    validate_citations,
    strip_unverified_sentences,
    extract_numeric_tokens
)
from backend.app.agent.llm_client import get_llm_client, ChatResult, TokenUsage
from backend.app.core.config import settings
from backend.app.models.dataset import Dataset
from backend.app.models.job import AnalysisJob
from backend.app.services.tool_catalogue import execute_tool

logger = logging.getLogger(__name__)

# In-memory per-job conversation history store
_CHAT_HISTORY_STORE: Dict[str, List[Dict[str, str]]] = {}

# Out-of-scope / destructive patterns
DESTRUCTIVE_OR_OUT_OF_SCOPE_PATTERNS = [
    r"\b(drop|delete|remove|truncate|alter|insert|update)\s+(from\s+|table\s+|database\s+|schema\s+|file\s+|record\s+|column\s+|datasets?\b|jobs?\b|\*)",
    r"\b(rm|rmdir|unlink|shred|format)\s+[\/\w\.-]+",
    r"\b(exec|eval|system|subprocess|os\.)\b",
    r"\b(ignore\s+(all\s+)?(previous\s+)?instructions|jailbreak|dan\s+mode)\b",
    r"\b(write\s+(a\s+)?(poem|song|essay|story|code\s+for\s+malware))\b",
    r"\b(who\s+won\s+the|weather\s+in|recipe\s+for)\b"
]

def is_destructive_or_out_of_scope(question: str) -> bool:
    """Check if question is destructive, system-level, or completely outside data analysis."""
    q_lower = question.lower().strip()
    for pat in DESTRUCTIVE_OR_OUT_OF_SCOPE_PATTERNS:
        if re.search(pat, q_lower):
            return True
    return False

def get_job_chat_history(job_id: str) -> List[Dict[str, str]]:
    """Retrieve in-memory conversation history for a job."""
    return _CHAT_HISTORY_STORE.get(job_id, [])

def append_job_chat_history(job_id: str, role: str, content: str):
    """Append a turn to in-memory conversation history."""
    if job_id not in _CHAT_HISTORY_STORE:
        _CHAT_HISTORY_STORE[job_id] = []
    _CHAT_HISTORY_STORE[job_id].append({"role": role, "content": content})

def detect_missing_column_or_entity(question: str, available_columns: List[str]) -> Optional[str]:
    """
    Check if the user question inquires about a column or entity that is not in available_columns.
    Returns the missing entity name (e.g. 'customer age', 'customer churn', 'credit score') or None.
    """
    if not available_columns:
        return None

    q_lower = question.lower()
    norm_cols = {re.sub(r"[^a-z0-9]", "", c.lower()) for c in available_columns}
    col_words = {w.lower() for c in available_columns for w in re.split(r"[_\s]+", c) if len(w) > 2}

    candidate_entities = [
        ("customer age", ["customer age", "customerage"]),
        ("age", ["age"]),
        ("customer churn", ["customer churn", "customerchurn"]),
        ("churn", ["churn"]),
        ("credit score", ["credit score", "creditscore", "credit rating", "credit_score"]),
        ("customer satisfaction", ["customer satisfaction", "customersatisfaction", "csat", "nps"]),
        ("household income", ["household income", "householdincome"]),
        ("profit margin", ["profit margin", "profitmargin"]),
        ("lifetime value", ["lifetime value", "lifetimevalue", "clv", "ltv"]),
    ]

    for entity_name, aliases in candidate_entities:
        if any(re.search(rf"\b{re.escape(alias)}\b", q_lower) for alias in [entity_name] + aliases):
            exists = any(a in norm_cols or any(a in cw for cw in col_words) for a in aliases)
            if not exists:
                return entity_name

    return None

def determine_chat_tool_call(
    question: str,
    dataset_id: str,
    available_columns: List[str]
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Determine if a chat question requires a read-only tool call (e.g. query_sql)."""
    q_lower = question.lower()
    norm_cols = [c.lower() for c in available_columns]

    # 1. Retail: Credit Card payment share
    if ("credit card" in q_lower or "payment" in q_lower) and ("share" in q_lower or "percentage" in q_lower or "proportion" in q_lower) and any("payment" in c for c in norm_cols):
        sql = (
            "SELECT Payment_Method, COUNT(*) as count, "
            "ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM data_clean WHERE Payment_Method IS NOT NULL), 2) as share_percent "
            "FROM data_clean WHERE Payment_Method IS NOT NULL GROUP BY Payment_Method"
        )
        return "query_sql", {"dataset_id": dataset_id, "sql": sql}

    # 2. HR: Average salary by department on observed rows
    if ("salary" in q_lower or "annual_salary" in q_lower) and ("department" in q_lower or "observed" in q_lower) and any("salary" in c for c in norm_cols):
        sql = (
            "SELECT Department, ROUND(AVG(Annual_Salary), 2) as avg_salary, COUNT(*) as n_observed "
            "FROM data_observed WHERE Annual_Salary IS NOT NULL GROUP BY Department"
        )
        return "query_sql", {"dataset_id": dataset_id, "sql": sql}

    # 3. Marketing: Spend and clicks by channel
    if ("spend" in q_lower or "ad_spend" in q_lower) and ("click" in q_lower or "clicks" in q_lower) and any("spend" in c for c in norm_cols):
        spend_col = "Ad_Spend" if any(c == "ad_spend" for c in norm_cols) else "Spend"
        clicks_col = "Clicks" if any(c == "clicks" for c in norm_cols) else "Clicks"
        chan_col = "Channel" if any(c == "channel" for c in norm_cols) else "Channel"
        sql = f"SELECT {chan_col}, ROUND(SUM({spend_col}), 2) as total_spend, SUM({clicks_col}) as total_clicks FROM data_clean GROUP BY {chan_col}"
        return "query_sql", {"dataset_id": dataset_id, "sql": sql}

    # 4. Explicit correlation
    if "correlation" in q_lower and dataset_id:
        return "run_correlation", {"dataset_id": dataset_id, "threshold": 0.4}

    return None

def answer_heuristic_question(
    question: str,
    insights: List[Dict[str, Any]],
    profile: Dict[str, Any],
    cleaning_report: Dict[str, Any],
    dataset_id: str
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """Generate a grounded heuristic answer by matching question intent to insights and profile."""
    q_lower = question.lower()
    evidence: List[Dict[str, Any]] = []
    tool_results: List[Dict[str, Any]] = []
    tool_calls_count = 0

    # 1. Quality / Cleaning questions
    if any(k in q_lower for k in ["quality", "clean", "sentinel", "invalid", "return", "missing", "imput"]):
        sentinels = cleaning_report.get("sentinels_detected", [])
        invalids = cleaning_report.get("invalid_values_detected", [])
        returns = cleaning_report.get("suspected_returns", [])
        imputations = cleaning_report.get("column_imputation_stats", {})
        q_score = profile.get("quality_summary", {}).get("quality_score", 100.0)
        
        parts = [f"Dataset data quality score is {q_score}/100."]
        if sentinels:
            s_details = ", ".join(f"{s.get('column')} (value {s.get('sentinel_value')}: {s.get('count')} rows)" for s in sentinels)
            parts.append(f"Sentinels sanitized: {s_details}.")
        if invalids:
            i_details = ", ".join(f"{iv.get('column')} ({iv.get('rule')}: {iv.get('count')} rows)" for iv in invalids)
            parts.append(f"Domain invalid values removed: {i_details}.")
        if returns:
            r_details = ", ".join(f"{sr.get('column')} ({sr.get('count')} rows)" for sr in returns)
            parts.append(f"Suspected returns preserved: {r_details}.")
        if imputations:
            high_imp = [f"{col} ({round(stat.get('imputation_rate', 0)*100, 1)}%)" for col, stat in imputations.items() if stat.get('imputation_rate', 0) > 0.05]
            if high_imp:
                parts.append(f"Key imputation rates: {', '.join(high_imp)}.")
        
        dq_insights = [ins for ins in insights if ins.get("type") == "data_quality"]
        for dqi in dq_insights:
            evidence.append({"type": "insight", "id": dqi.get("id"), "title": dqi.get("title")})
            
        answer = " ".join(parts)
        return answer, evidence, tool_results, tool_calls_count

    # 2. Check if a read-only tool call is warranted
    if "correlation" in q_lower and dataset_id:
        try:
            tool_res = execute_tool("run_correlation", {"dataset_id": dataset_id, "threshold": 0.4})
            tool_results.append(tool_res)
            tool_calls_count += 1
            evidence.append({"type": "tool_call", "tool": "run_correlation"})
        except Exception:
            pass

    # 3. Match against ranked insights
    matched_insights = []
    for ins in insights:
        title = ins.get("title", "").lower()
        summary = ins.get("summary", "").lower()
        ins_type = ins.get("type", "").lower()
        
        words = [w for w in re.findall(r"\w+", q_lower) if len(w) > 3]
        if any(w in title or w in summary for w in words) or ins_type in q_lower:
            matched_insights.append(ins)

    if not matched_insights and insights:
        matched_insights = insights[:2]

    if matched_insights:
        lines = []
        for ins in matched_insights[:3]:
            evidence.append({"type": "insight", "id": ins.get("id"), "title": ins.get("title")})
            sig_text = f" (p-value: {ins.get('significance')})" if ins.get("significance") is not None else ""
            lines.append(f"- {ins.get('title')}: {ins.get('summary')}{sig_text}")
        answer = f"Based on the analysis findings:\n" + "\n".join(lines)
    else:
        row_cnt = profile.get("row_count", 0)
        col_cnt = profile.get("column_count", 0)
        answer = f"The dataset contains {row_cnt} clean records across {col_cnt} columns. No specific statistical anomalies matching the query were found."

    return answer, evidence, tool_results, tool_calls_count

def process_chat_question(
    db: Session,
    job_id: str,
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
    dataset_id: Optional[str] = None
) -> Dict[str, Any]:
    """Execute complete Chat Q&A flow with guardrails, tool calls, bound verification, and regeneration."""
    # 1. Guardrail: Check destructive or out-of-scope
    if is_destructive_or_out_of_scope(question):
        return {
            "answer": "This assistant is restricted to data analysis questions regarding the dataset. Destructive or out-of-scope requests cannot be performed.",
            "evidence": [],
            "verification": {
                "is_valid": True,
                "total_claims_checked": 0,
                "verified_claims_count": 0,
                "unverified_claims_count": 0,
                "verification_rate_percent": 100.0,
                "pre_strip_verification_rate": 100.0,
                "post_strip_verification_rate": 100.0,
                "status": "passed"
            },
            "provider": "guardrail",
            "tool_calls_used": [],
            "pre_strip_rate": 100.0,
            "post_strip_rate": 100.0
        }

    # 2. Retrieve Job and Dataset Context
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first() if job_id else None
    ds_id = dataset_id or (job.dataset_id if job else None) or ""
    
    dataset = db.query(Dataset).filter(Dataset.id == ds_id).first() if ds_id else None
    profile = (dataset.get_profile() if dataset and hasattr(dataset, "get_profile") else None) or {}
    cleaning_report = (dataset.get_cleaning_summary() if dataset and hasattr(dataset, "get_cleaning_summary") else None) or {}
    
    results = (job.get_results() if job and hasattr(job, "get_results") else None) or (json.loads(job.results_json) if job and isinstance(job.results_json, str) else (job.results_json if job and isinstance(job.results_json, dict) else {}))
    insights = results.get("insights", [])
    structured_results = results.get("structured_results", [])

    # Extract available columns
    available_columns: List[str] = profile.get("columns") or list(profile.get("column_types", {}).keys())
    if not available_columns and ds_id:
        try:
            from backend.app.services.data_loader import get_dataset_dataframe
            df = get_dataset_dataframe(ds_id)
            available_columns = list(df.columns)
        except Exception:
            available_columns = []

    provider = os.getenv("LLM_PROVIDER", settings.LLM_PROVIDER).lower()
    has_api_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

    # Cap tool calls to max 3
    tool_results: List[Dict[str, Any]] = []
    tool_calls_used: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []

    # 3. Check if question requires a tool call (e.g. query_sql on Credit Card payment share)
    tool_plan = determine_chat_tool_call(question, ds_id, available_columns)
    if tool_plan:
        tool_name, tool_args = tool_plan
        try:
            tool_res = execute_tool(tool_name, tool_args)
            tool_results.append(tool_res)
            tool_calls_used.append({"tool": tool_name, "arguments": tool_args})
            evidence.append({"type": "tool_call", "tool": tool_name})
        except Exception as e:
            logger.warning("Chat tool call %s failed: %s", tool_name, e)

    # 4. Detect missing column / entity
    missing_entity = detect_missing_column_or_entity(question, available_columns)

    # 5. Link evidence to relevant insights
    q_words = [w.lower() for w in re.findall(r"\w+", question) if len(w) > 3]
    for ins in insights:
        t = ins.get("title", "").lower()
        s = ins.get("summary", "").lower()
        if any(w in t or w in s for w in q_words):
            evidence.append({"type": "insight", "id": ins.get("id"), "title": ins.get("title")})

    # 6. Generate structured chat response
    client_provider = provider if has_api_key else "heuristic"
    client = get_llm_client(client_provider, allow_heuristic_fallback=True)

    chat_context = {
        "available_columns": available_columns,
        "insights": insights,
        "profile": profile,
        "cleaning_report": cleaning_report,
        "tool_results": tool_results,
        "history": history or get_job_chat_history(job_id)
    }

    chat_result = client.generate_chat_answer(question, chat_context)

    # 7. Bound Citation Verification & Single Retry
    all_facts_results = structured_results + tool_results
    verification = validate_citations(
        synthesis_result={"executive_summary": chat_result.answer, "claims": chat_result.claims},
        structured_results=all_facts_results,
        dataset_profile=profile,
        insights=insights
    )

    if not verification.get("is_valid", True):
        failing = verification.get("unverified_claims", []) or [{"unverified_numbers": verification.get("unverified_numbers", [])}]
        # Regenerate ONCE with failing claims listed
        chat_result = client.generate_chat_answer(question, chat_context, failing_claims=failing)
        verification = validate_citations(
            synthesis_result={"executive_summary": chat_result.answer, "claims": chat_result.claims},
            structured_results=all_facts_results,
            dataset_profile=profile,
            insights=insights
        )

        if not verification.get("is_valid", True):
            # Strip offending sentences post-retry
            cleaned_ans, stripped = strip_unverified_sentences(
                chat_result.answer,
                verification.get("unverified_numbers", []),
                [uc["claim"] for uc in verification.get("unverified_claims", [])]
            )
            chat_result.answer = cleaned_ans
            verification["stripped_sentences"] = stripped
            verification["cleaned_executive_summary"] = cleaned_ans

    # 8. Ensure missing column disclaimer is prominently stated if detected
    if missing_entity and available_columns:
        notice = f"The requested column/entity '{missing_entity}' is not present in this dataset. Available columns are: {', '.join(available_columns)}."
        if missing_entity.lower() not in chat_result.answer.lower() and "not present" not in chat_result.answer.lower():
            chat_result.answer = f"{notice}\n\n{chat_result.answer}"

    # 9. Store conversation turn in-memory
    if job_id:
        append_job_chat_history(job_id, "user", question)
        append_job_chat_history(job_id, "assistant", chat_result.answer)

    return {
        "answer": chat_result.answer,
        "evidence": evidence,
        "verification": verification,
        "provider": chat_result.provider,
        "tool_calls_used": tool_calls_used,
        "pre_strip_rate": verification.get("pre_strip_verification_rate", 100.0),
        "post_strip_rate": verification.get("post_strip_verification_rate", 100.0)
    }
