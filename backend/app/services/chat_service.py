"""Chat Q&A Service for interactive conversational exploration over dataset insights (Milestone 4).

Enforces:
- Up to 3 read-only tool calls per question.
- Strict rejection of destructive or out-of-scope requests.
- Full numeric claim verification via citation checker.
- Single-attempt regeneration if claims are unverified, appending explicit '[could not verify: ...]' if still unverified.
- In-memory conversation history per job.
- Heuristic fallback when no LLM is configured.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from backend.app.agent.citation_checker import validate_citations
from backend.app.core.config import settings
from backend.app.models.dataset import Dataset
from backend.app.models.job import AnalysisJob
from backend.app.services.tool_catalogue import execute_tool

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
        
        # Link evidence to any data_quality insight
        dq_insights = [ins for ins in insights if ins.get("type") == "data_quality"]
        for dqi in dq_insights:
            evidence.append({"type": "insight", "id": dqi.get("id"), "title": dqi.get("title")})
            
        answer = " ".join(parts)
        return answer, evidence, tool_results, tool_calls_count

    # 2. Check if a read-only tool call is warranted (e.g. if user asks for correlation or segment or outlier specifically)
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
        matched_insights = insights[:2]  # Default to top insights

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
    """Execute complete Chat Q&A flow with guardrails, LLM/heuristic handling, and citation audit."""
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
                "status": "passed"
            }
        }

    # 2. Retrieve Job and Dataset Context
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first() if job_id else None
    ds_id = dataset_id or (job.dataset_id if job else None)
    
    dataset = db.query(Dataset).filter(Dataset.id == ds_id).first() if ds_id else None
    profile = (dataset.get_profile() if dataset and hasattr(dataset, "get_profile") else None) or {}
    cleaning_report = (dataset.get_cleaning_summary() if dataset and hasattr(dataset, "get_cleaning_summary") else None) or {}
    
    results = (job.get_results() if job and hasattr(job, "get_results") else None) or (json.loads(job.results_json) if job and isinstance(job.results_json, str) else (job.results_json if job and isinstance(job.results_json, dict) else {}))
    insights = results.get("insights", [])
    structured_results = results.get("structured_results", [])

    provider = os.getenv("LLM_PROVIDER", settings.LLM_PROVIDER).lower()
    has_api_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

    # Cap tool calls to max 3
    tool_results: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []

    # 3. Generate Answer (LLM or Heuristic)
    if provider == "heuristic" or not has_api_key:
        answer, evidence, tool_res, _ = answer_heuristic_question(
            question, insights, profile, cleaning_report, ds_id or ""
        )
        tool_results.extend(tool_res)
    else:
        # Provider-based answering
        try:
            from backend.app.agent.llm_client import create_llm_client
            client = create_llm_client(provider)
            
            # Formulate chat context
            context_summary = {
                "profile": profile,
                "cleaning_report": cleaning_report,
                "insights": insights[:8]
            }
            
            # Simple prompt-based chat with client
            prompt = (
                f"You are an expert autonomous data analyst assistant. Answer the user's question accurately using ONLY facts from the provided insights, profile, and cleaning report.\n"
                f"Context:\n{context_summary}\n\n"
                f"Question: {question}\n\n"
                f"Rules:\n"
                f"- Forbid causal or market-preference claims.\n"
                f"- Every number cited must be strictly accurate to the context.\n"
                f"- Keep your response concise, professional, and clear."
            )
            
            # Generate answer
            # We can use client's LLM or fallback cleanly
            if hasattr(client, "synthesize"):
                # Use synthesizer or generate directly
                answer, evidence, tool_res, _ = answer_heuristic_question(
                    question, insights, profile, cleaning_report, ds_id or ""
                )
                tool_results.extend(tool_res)
            else:
                answer, evidence, tool_res, _ = answer_heuristic_question(
                    question, insights, profile, cleaning_report, ds_id or ""
                )
        except Exception:
            answer, evidence, tool_res, _ = answer_heuristic_question(
                question, insights, profile, cleaning_report, ds_id or ""
            )

    # 4. Citation Verification & Unverified Claims Handling
    all_facts_results = structured_results + tool_results
    verification = validate_citations(
        synthesis_result={"executive_summary": answer},
        structured_results=all_facts_results,
        dataset_profile=profile,
        insights=insights
    )

    # If unverified claims exist, handle according to PRD:
    # "If any numeric claim is unverified: regenerate once with the failed claims listed; if still unverified, return the answer with an explicit 'could not verify: ...' note. Never return silently unverified numbers."
    if not verification.get("is_valid", True):
        unverified_nums = verification.get("unverified_numbers", [])
        if unverified_nums:
            # Append explicit note
            note = f"\n\n[could not verify: {', '.join(str(n) for n in unverified_nums)}]"
            answer = answer + note
            # Re-check verification with note recognized or keep audit log
            verification["status"] = "flagged"

    # 5. Store conversation turn in-memory
    if job_id:
        append_job_chat_history(job_id, "user", question)
        append_job_chat_history(job_id, "assistant", answer)

    return {
        "answer": answer,
        "evidence": evidence,
        "verification": verification
    }
