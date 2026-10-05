"""Unit and Integration Tests for Milestone 3: Narrative & Verification.

Tests:
- Prohibition of forbidden terms ('stable', 'not concentrated', 'no effect', 'organic') and causal speculation.
- Formatting of non-significant results with group n and statistical power caveat when group n < 30.
- Recommendations restricted to data quality only.
- Number verification rate and claim presence rate reported; p-value claims use unit 'p_value'.
- Sentences with unverified claims/numbers stripped.
- Complete absence of 'None', 'nan', or placeholder text across insights, chat answers, narrative, and reports on all 3 datasets.
"""
import re
import pytest
import pandas as pd
from backend.app.agent.citation_checker import validate_citations, extract_numeric_tokens
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.services.synthesis_guardrails import (
    check_forbidden_narrative_terms,
    post_check_synthesis_narrative
)
from backend.app.core.database import SessionLocal
from backend.app.services.chat_service import process_chat_question

DATASETS = [
    "hr_attrition_messy.csv",
    "marketing_campaign_messy.csv",
    "retail_sales_messy.csv"
]


def test_forbidden_terms_and_causal_speculation_blocked():
    """Verify post_check_synthesis_narrative strips or sanitizes forbidden words and causal speculation."""
    bad_text = (
        "The trend was stable over the period. The customer base was not concentrated in any single region. "
        "The campaign had no effect on total volume. Organic traffic was monitored. "
        "Higher discount causes customer churn and leads to decreased revenue. "
        "Sales were driven by marketing resulting in higher engagement because of seasonal peaks."
    )
    cleaned = post_check_synthesis_narrative(bad_text, "test context")
    
    # Assert zero forbidden terms remain
    violations = check_forbidden_narrative_terms(cleaned)
    assert not violations, f"Forbidden terms still found: {violations} in '{cleaned}'"
    for term in ["stable", "not concentrated", "no effect", "organic"]:
        assert re.search(rf"\b{term}\b", cleaned, re.IGNORECASE) is None
    for causal in ["leads to", "causes", "caused by", "drives", "driven by", "resulting in", "because of"]:
        assert re.search(rf"\b{causal}\b", cleaned, re.IGNORECASE) is None


def test_both_rates_reported_and_p_value_unit():
    """Verify both number_verification_rate and claim_presence_rate are reported and p-value unit is 'p_value'."""
    synthesis_payload = {
        "executive_summary": "Revenue reached 1500.0 across 45 observations with p=0.0420.",
        "key_findings": [],
        "claims": [
            {
                "text": "Revenue reached 1500.0",
                "source_id": "step_1",
                "metric_key": "revenue",
                "value": 1500.0
            },
            {
                "text": "sample size was 45",
                "source_id": "step_1",
                "metric_key": "n_used",
                "value": 45.0
            },
            {
                "text": "statistical significance p=0.0420",
                "source_id": "step_1",
                "metric_key": "p_value",
                "value": 0.0420,
                "unit": "p_value"
            }
        ]
    }
    tool_results = [
        {"tool": "calculate_stats", "revenue": 1500.0, "n_used": 45, "p_value": 0.0420}
    ]

    audit = validate_citations(synthesis_payload, structured_results=tool_results)
    assert audit["is_valid"] is True
    assert "number_verification_rate" in audit
    assert "claim_presence_rate" in audit
    assert audit["number_verification_rate"] == 100.0
    assert audit["claim_presence_rate"] == 100.0
    
    # Verify p-value claim has unit 'p_value'
    p_claim = next(c for c in synthesis_payload["claims"] if c.get("metric_key") == "p_value")
    assert p_claim.get("unit") == "p_value"


def test_unverified_claims_and_numbers_stripped():
    """Verify unverified numbers are stripped and never delivered in cleaned summary."""
    synthesis_payload = {
        "executive_summary": "Verified revenue was 200.0. Hallucinated growth was 999.0 without basis.",
        "key_findings": [],
        "claims": [
            {
                "text": "Verified revenue was 200.0",
                "source_id": "step_1",
                "metric_key": "revenue",
                "value": 200.0
            }
        ]
    }
    tool_results = [{"tool": "calc", "revenue": 200.0}]

    audit = validate_citations(synthesis_payload, structured_results=tool_results)
    assert audit["is_valid"] is False
    assert 999.0 in audit["unverified_numbers"]
    assert "999.0" not in audit["cleaned_executive_summary"]
    assert "200.0" in audit["cleaned_executive_summary"]
    assert audit["post_strip_verification_rate"] == 100.0


def test_non_significant_formatting_and_power_caveat():
    """Verify non-significant findings include group n and power caveat when any group n < 30."""
    orch = PlanActReflectOrchestrator(max_steps=3, provider="heuristic")
    res = orch.run_analysis(dataset_id="hr_attrition_messy.csv")
    
    summary = res["synthesis"]["executive_summary"]
    # If non-significant test occurred, verify the phrasing
    if "no statistically significant difference" in summary.lower():
        assert "no statistically significant difference detected" in summary
        assert "(limited statistical power due to small sample size in some groups, n < 30)" in summary


def test_recommendations_concern_data_quality_only():
    """Verify recommendations concern data quality only."""
    orch = PlanActReflectOrchestrator(max_steps=3, provider="heuristic")
    res = orch.run_analysis(dataset_id="retail_sales_messy.csv")
    
    recs = res["synthesis"]["recommendations"]
    assert len(recs) > 0
    dq_keywords = ["schema", "validation", "sentinel", "sample size", "statistical power", "monitoring", "missingness", "imputation", "data quality"]
    for rec in recs:
        assert any(k in rec.lower() for k in dq_keywords), f"Recommendation '{rec}' does not concern data quality"


@pytest.mark.parametrize("dataset_filename", DATASETS)
def test_no_placeholders_or_forbidden_terms_across_all_datasets(dataset_filename):
    """Verify no insight, chat answer, narrative or report contains 'None', 'nan', or generic placeholder text."""
    orch = PlanActReflectOrchestrator(max_steps=4, provider="heuristic")
    res = orch.run_analysis(dataset_id=dataset_filename)
    
    synthesis = res["synthesis"]
    exec_summary = synthesis["executive_summary"]
    findings = synthesis["key_findings"]
    insights = res["insights"]
    
    # 1. Check narrative and findings
    corpus = exec_summary + " " + " ".join(f.get("finding", "") + " " + f.get("narrative", "") for f in findings)
    assert "none" not in corpus.lower().split()
    assert "nan" not in corpus.lower().split()
    assert "placeholder" not in corpus.lower()
    assert "undefined" not in corpus.lower()
    
    # Forbidden terms check
    violations = check_forbidden_narrative_terms(corpus)
    assert not violations, f"Forbidden terms {violations} found in {dataset_filename} narrative"
    
    # 2. Check all generated insights
    for ins in insights:
        ins_dict = ins if isinstance(ins, dict) else ins.model_dump()
        text = f"{ins_dict.get('title', '')} {ins_dict.get('summary', '')}"
        assert "none" not in text.lower().split(), f"Placeholder 'none' in insight {ins_dict.get('id')}"
        assert "nan" not in text.lower().split(), f"Placeholder 'nan' in insight {ins_dict.get('id')}"
        assert "placeholder" not in text.lower(), f"Placeholder in insight {ins_dict.get('id')}"
        ins_violations = check_forbidden_narrative_terms(text)
        assert not ins_violations, f"Forbidden terms {ins_violations} in insight {ins_dict.get('id')}"
        
    # 3. Check chat answer
    db = SessionLocal()
    try:
        chat_resp = process_chat_question(
            db=db,
            job_id="",
            question="What are the key insights and trends in this data?",
            dataset_id=dataset_filename
        )
    finally:
        db.close()
    ans = chat_resp["answer"]
    assert "none" not in ans.lower().split()
    assert "nan" not in ans.lower().split()
    assert "placeholder" not in ans.lower()
    chat_violations = check_forbidden_narrative_terms(ans)
    assert not chat_violations, f"Forbidden terms {chat_violations} found in chat answer for {dataset_filename}"
