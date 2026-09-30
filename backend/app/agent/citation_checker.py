"""Programmatic Claim Verification & Citation Checker.

Validates that every numeric claim in the synthesized report traces back to
an actual computed tool result in the analysis run log.
Prevents LLM hallucinations or unsupported numerical statements (PRD FR-08–FR-13).
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

def extract_numeric_tokens(text: str) -> List[float]:
    """
    Extract numbers from narrative text (handles floats, ints, currency, percentages).
    Ignores dates (YYYY-MM-DD), hyphenated IDs (e.g. TXN-1003), and year indicators.
    """
    # 1. Strip date patterns (e.g. 2025-03-23, 03/23/2025)
    text_clean = re.sub(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", " ", text)
    text_clean = re.sub(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", " ", text_clean)
    # 2. Strip hyphenated codes/IDs like TXN-1003, CUST-102
    text_clean = re.sub(r"\b[A-Za-z0-9]+-\d+\b", " ", text_clean)

    # Regex matching numbers with optional decimals, commas, negatives, currency, or percentages
    pattern = r"[-+]?\$?\b\d{1,3}(?:,\d{3})*(?:\.\d+)?%?\b"
    matches = re.findall(pattern, text_clean)
    numbers = []
    
    for raw in matches:
        clean = raw.replace("$", "").replace("%", "").replace(",", "")
        try:
            val = float(clean)
            # Skip years from false flagging
            if val in [2020, 2021, 2022, 2023, 2024, 2025, 2026]:
                continue
            numbers.append(val)
        except ValueError:
            continue
            
    return numbers

def build_fact_pool(
    structured_results: List[Dict[str, Any]],
    dataset_profile: Optional[Dict[str, Any]] = None,
    insights: Optional[List[Any]] = None
) -> Set[float]:
    """Extract all computed numerical values across all tools and insights into a set of known facts."""
    fact_pool = set()

    def add_num(val):
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            fact_pool.add(round(float(val), 2))
            fact_pool.add(round(float(val), 1))
            fact_pool.add(round(float(val), 4))
            fact_pool.add(float(int(val)))

    def harvest_obj(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                harvest_obj(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                harvest_obj(item)
        elif hasattr(obj, "model_dump"):
            harvest_obj(obj.model_dump())
        elif hasattr(obj, "__dict__"):
            harvest_obj(obj.__dict__)
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            add_num(obj)

    if dataset_profile:
        add_num(dataset_profile.get("row_count"))
        add_num(dataset_profile.get("cleaned_row_count"))
        add_num(dataset_profile.get("n_rows_used"))
        add_num(dataset_profile.get("column_count"))
        q = dataset_profile.get("quality_summary", {})
        add_num(q.get("quality_score"))
        add_num(q.get("duplicate_rows"))
        add_num(q.get("missing_percentage"))

        # Harvest Data Quality Facts
        for s in dataset_profile.get("sentinels_detected", []):
            add_num(s.get("count"))
            add_num(s.get("sentinel_value"))
        for iv in dataset_profile.get("invalid_values_detected", []):
            add_num(iv.get("count"))
        for sr in dataset_profile.get("suspected_returns", []):
            add_num(sr.get("count"))
        for re_item in dataset_profile.get("suspected_repeated_extremes", []):
            add_num(re_item.get("count"))
            add_num(re_item.get("value"))
        for col, stats in dataset_profile.get("column_imputation_stats", {}).items():
            add_num(stats.get("imputed_count"))
            imp_rate = stats.get("imputation_rate")
            if imp_rate is not None:
                add_num(round(imp_rate * 100, 2))
                add_num(round(imp_rate * 100, 1))
                add_num(round(imp_rate, 4))
        for col, cnt in dataset_profile.get("missing_values_imputed", {}).items():
            add_num(cnt)

        # Harvest embedded insights if present in profile
        if "insights" in dataset_profile:
            harvest_obj(dataset_profile["insights"])

    if insights:
        harvest_obj(insights)

    for res in structured_results:
        harvest_obj(res)

    return fact_pool

def validate_citations(
    synthesis_result: Dict[str, Any],
    structured_results: List[Dict[str, Any]],
    dataset_profile: Optional[Dict[str, Any]] = None,
    insights: Optional[List[Any]] = None,
    tolerance: float = 0.05
) -> Dict[str, Any]:
    """
    Programmatically verify all numeric claims in the synthesis output.
    Returns audit details with verified and unverified claims.
    Accepts every numeric value in insights as a verified fact source.
    """
    fact_pool = build_fact_pool(structured_results, dataset_profile, insights=insights)
    
    # Collect all narrative text to check
    text_corpus = synthesis_result.get("executive_summary", "")
    for finding in synthesis_result.get("key_findings", []):
        text_corpus += " " + finding.get("headline", "") + " " + finding.get("narrative", "")

    extracted_numbers = extract_numeric_tokens(text_corpus)
    verified = []
    unverified = []

    for num in extracted_numbers:
        # Check exact or near match within tolerance
        matched = False
        rounded_num = round(num, 2)
        if rounded_num in fact_pool or round(num, 1) in fact_pool or round(num, 4) in fact_pool or float(int(num)) in fact_pool:
            matched = True
        else:
            for fact in fact_pool:
                if abs(fact) > 0 and abs(num - fact) / abs(fact) <= tolerance:
                    matched = True
                    break
                    
        if matched:
            verified.append(num)
        else:
            unverified.append(num)

    total = len(extracted_numbers)
    rate = round((len(verified) / total) * 100, 2) if total > 0 else 100.0

    return {
        "is_valid": len(unverified) == 0,
        "total_claims_checked": total,
        "verified_claims_count": len(verified),
        "unverified_claims_count": len(unverified),
        "verification_rate_percent": rate,
        "verified_numbers": verified,
        "unverified_numbers": unverified,
        "status": "passed" if len(unverified) == 0 else "flagged"
    }
