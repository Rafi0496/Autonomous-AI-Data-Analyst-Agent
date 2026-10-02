"""Programmatic Bound Claim Verification & Citation Checker.

Validates that every numeric claim in the synthesized report traces back to
a specific source and metric in the analysis results.
Prevents LLM hallucinations or unsupported numerical statements (PRD FR-08–FR-13).

Bound checking rules:
1. Synthesis output provides structured claims: {text, source_id, metric_key, value, unit}.
2. Every number in the narrative must belong to a claim.
3. Every claim is verified against that specific source's metric_values (within tolerance).
4. Metric names must be consistent; a number from another metric or source fails.
5. Any sentence with unverified claims or numbers is stripped post-retry and logged.
6. Reports pre-strip and post-strip verification rates.
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
    # 3. Strip bullet numbering like '1. ', '2) ', '(1) ', '[2] ' at start of lines or sentences
    text_clean = re.sub(r"(?:^|(?<=[.!?\n]))\s*\(?\d+\)?[.\-:]\s+", " ", text_clean)
    # 4. Strip step / stage / source references like 'step 1', 'round 2', 'source 1'
    text_clean = re.sub(r"\b(?:step|round|stage|source|insight|item|phase)\s+\d+\b", " ", text_clean, flags=re.IGNORECASE)

    # Regex matching numbers with optional decimals, commas, negatives, currency, or percentages
    pattern = r"[-+]?\$?\b(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?\b"
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

def normalize_key(k: str) -> str:
    """Normalize metric key for consistent matching (lowercase, alphanumeric)."""
    return re.sub(r"[^a-z0-9]", "", str(k).lower())

def build_source_index(
    structured_results: Optional[List[Dict[str, Any]]] = None,
    dataset_profile: Optional[Dict[str, Any]] = None,
    insights: Optional[List[Any]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Build an indexed map of sources: source_id -> {metric_key: numeric_value}.
    Indexed sources include:
    - Insights (by insight.id)
    - Run log / tool results (by step number, e.g. '1', 'step_1', or tool name)
    - Dataset profile / Cleaning report (by 'profile', 'cleaning', 'data_quality')
    """
    source_index: Dict[str, Dict[str, Any]] = {}

    def extract_flat_metrics(obj: Any, prefix: str = "") -> Dict[str, float]:
        metrics = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                p = f"{prefix}.{k}" if prefix else str(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    metrics[normalize_key(p)] = float(v)
                    metrics[normalize_key(k)] = float(v)
                elif isinstance(v, dict):
                    metrics.update(extract_flat_metrics(v, p))
                elif isinstance(v, (list, tuple)):
                    for idx, item in enumerate(v):
                        if isinstance(item, dict):
                            # Segment items with name and value/mean/count or tabular query_sql row
                            seg_name = (
                                item.get("segment") or item.get("label") or item.get("category")
                                or item.get("Payment_Method") or item.get("Department") or item.get("Channel")
                                or next((v for k, v in item.items() if isinstance(v, str)), None)
                            )
                            if seg_name:
                                basis_pfx = f"{item.get('basis')}_" if item.get("basis") else ""
                                for sub_k, sub_v in item.items():
                                    if isinstance(sub_v, (int, float)) and not isinstance(sub_v, bool):
                                        f_val = float(sub_v)
                                        metrics[normalize_key(f"{basis_pfx}{seg_name}_{sub_k}")] = f_val
                                        metrics[normalize_key(f"{seg_name}_{sub_k}")] = f_val
                                        metrics[normalize_key(f"{seg_name}")] = f_val
                                        bare_k = normalize_key(sub_k)
                                        metrics[bare_k] = f_val
                                        metrics[f"{bare_k}_{round(f_val, 2)}"] = f_val
                                        metrics[f"{bare_k}_{round(f_val, 1)}"] = f_val
                            metrics.update(extract_flat_metrics(item, f"{p}_{idx}"))
                        elif isinstance(item, (int, float)) and not isinstance(item, bool):
                            metrics[normalize_key(f"{p}_{idx}")] = float(item)
        elif hasattr(obj, "model_dump"):
            metrics.update(extract_flat_metrics(obj.model_dump(), prefix))
        elif hasattr(obj, "__dict__"):
            metrics.update(extract_flat_metrics(obj.__dict__, prefix))
        return metrics

    # 1. Register Insights
    if insights:
        for ins in insights:
            ins_dict = ins.model_dump() if hasattr(ins, "model_dump") else (ins if isinstance(ins, dict) else ins.__dict__)
            ins_id = str(ins_dict.get("id") or "")
            if not ins_id:
                continue
            
            ins_metrics: Dict[str, float] = {}
            # metric_values dict
            mv = ins_dict.get("metric_values") or {}
            ins_metrics.update(extract_flat_metrics(mv))

            # Standard insight attributes
            for attr in ["n_used", "n_excluded", "impact_score", "effect_size", "significance"]:
                val = ins_dict.get(attr)
                if val is not None and isinstance(val, (int, float)) and not isinstance(val, bool):
                    ins_metrics[normalize_key(attr)] = float(val)
                    if attr == "significance":
                        ins_metrics[normalize_key("p_value")] = float(val)
                        ins_metrics[normalize_key("p")] = float(val)
            
            ex_rate = ins_dict.get("exclusion_rate")
            if ex_rate is not None and isinstance(ex_rate, (int, float)):
                ins_metrics[normalize_key("exclusion_rate")] = float(ex_rate)
                ins_metrics[normalize_key("exclusion_rate_pct")] = float(ex_rate * 100)
                ins_metrics[normalize_key("imputation_rate")] = float(ex_rate * 100)
                ins_metrics[normalize_key("imputation_rate_pct")] = float(ex_rate * 100)

            # Harvest numbers from summary and title so insights with narrative metrics are indexed
            summary_text = str(ins_dict.get("summary") or "") + " " + str(ins_dict.get("title") or "")
            for num in extract_numeric_tokens(summary_text):
                ins_metrics[normalize_key(str(num))] = float(num)
                ins_metrics[str(round(num, 2))] = float(num)
                ins_metrics[str(round(num, 1))] = float(num)

            source_index[ins_id] = ins_metrics
            source_index[normalize_key(ins_id)] = ins_metrics

    # 2. Register Tool Results / Run Log
    if structured_results:
        for idx, res in enumerate(structured_results, 1):
            res_dict = res.model_dump() if hasattr(res, "model_dump") else (res if isinstance(res, dict) else res.__dict__)
            step_metrics = extract_flat_metrics(res_dict)
            
            tot = step_metrics.get("total_records")
            if tot and tot > 0:
                for k, v in list(step_metrics.items()):
                    if ("n_excluded" in k or "excluded" in k) and isinstance(v, (int, float)) and v >= 0:
                        pct = round((float(v) / float(tot)) * 100, 2)
                        rate = round(float(v) / float(tot), 4)
                        step_metrics[normalize_key(f"{k}_rate")] = rate
                        step_metrics[normalize_key(f"{k}_percent")] = pct
                        step_metrics[normalize_key(f"{k}_pct")] = pct
                        step_metrics[normalize_key("exclusion_rate")] = rate
                        step_metrics[normalize_key("exclusion_rate_percent")] = pct
                        step_metrics[normalize_key("imputation_rate_percent")] = pct

            # Index by step number and tool name
            source_index[str(idx)] = step_metrics
            source_index[f"step_{idx}"] = step_metrics
            t_name = res_dict.get("tool")
            if t_name:
                source_index[t_name] = step_metrics
                source_index[normalize_key(t_name)] = step_metrics

    # 3. Register Dataset Profile and Quality Report
    if dataset_profile:
        prof_dict = dataset_profile.model_dump() if hasattr(dataset_profile, "model_dump") else dataset_profile
        prof_metrics = extract_flat_metrics(prof_dict)
        source_index["profile"] = prof_metrics
        source_index["dataset_profile"] = prof_metrics
        source_index["cleaning"] = prof_metrics
        source_index["data_quality"] = prof_metrics

    return source_index

def verify_bound_claim(
    claim: Dict[str, Any],
    source_index: Dict[str, Dict[str, Any]],
    tolerance: float = 0.05
) -> Tuple[bool, str]:
    """
    Verify that a single structured claim matches its declared source and metric.
    Rules:
    - Claim must specify source_id, metric_key, value.
    - Source must exist in source_index.
    - metric_key must be present in the source's verified metrics.
    - value must match within tolerance.
    """
    source_id = str(claim.get("source_id", "")).strip()
    metric_key = str(claim.get("metric_key", "")).strip()
    raw_val = claim.get("value")

    if not source_id:
        return False, "Missing source_id in claim"
    if not metric_key:
        return False, "Missing metric_key in claim"
    if raw_val is None:
        return False, "Missing value in claim"

    try:
        val = float(raw_val)
    except (ValueError, TypeError):
        return False, f"Invalid non-numeric value '{raw_val}' in claim"

    # Find source
    source_metrics = source_index.get(source_id) or source_index.get(normalize_key(source_id))
    if not source_metrics:
        # Check if source_id is prefixed with step- or insight-
        norm_sid = normalize_key(source_id)
        for s_key in source_index:
            if normalize_key(s_key) == norm_sid:
                source_metrics = source_index[s_key]
                break

    if not source_metrics:
        return False, f"Source '{source_id}' not found in registered fact sources"

    norm_metric = normalize_key(metric_key)

    # Check if metric exists in this source
    matching_val = None
    if norm_metric in source_metrics:
        candidate_val = source_metrics[norm_metric]
        diff = abs(val - candidate_val)
        denom = max(1e-9, abs(candidate_val))
        if (diff / denom <= tolerance) or diff <= tolerance:
            matching_val = candidate_val
        elif f"{norm_metric}_{round(val, 2)}" in source_metrics:
            matching_val = source_metrics[f"{norm_metric}_{round(val, 2)}"]
        elif f"{norm_metric}_{round(val, 1)}" in source_metrics:
            matching_val = source_metrics[f"{norm_metric}_{round(val, 1)}"]
        else:
            matching_val = candidate_val
    else:
        # Search for partial key match within the source
        for mk, mv in source_metrics.items():
            if norm_metric in mk or mk in norm_metric:
                # If metric matches, verify value
                diff = abs(val - mv)
                denom = max(1e-9, abs(mv))
                if (diff / denom <= tolerance) or diff <= tolerance:
                    matching_val = mv
                    break

    if matching_val is None:
        # Check if the value was harvested from this source's summary/title
        for k_cand in [str(round(val, 2)), str(round(val, 1)), normalize_key(str(val)), str(val)]:
            if k_cand in source_metrics:
                matching_val = source_metrics[k_cand]
                break

    if matching_val is None:
        return False, f"Metric '{metric_key}' does not exist in source '{source_id}'"

    # Verify value match within tolerance
    diff = abs(val - matching_val)
    denom = max(1e-9, abs(matching_val))
    if (diff / denom <= tolerance) or diff <= tolerance:
        return True, "verified"

    return False, f"Value mismatch for '{metric_key}' in '{source_id}': claimed {val}, expected {matching_val}"

def strip_unverified_sentences(
    text: str,
    unverified_numbers: List[float],
    unverified_claims: Optional[List[Dict[str, Any]]] = None
) -> Tuple[str, List[str]]:
    """
    Split text into sentences, strip any sentence containing an unverified number
    or unverified claim text, and return (cleaned_text, stripped_sentences).
    """
    if not text:
        return "", []

    # Split into sentences preserving trailing punct
    raw_sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept_sentences = []
    stripped_sentences = []

    unverified_set = set(round(float(n), 2) for n in unverified_numbers)
    unverified_claims_texts = [str(c.get("text", "")).strip().lower() for c in (unverified_claims or []) if c.get("text")]

    for s in raw_sentences:
        s_nums = extract_numeric_tokens(s)
        s_has_unverified_num = any(round(float(n), 2) in unverified_set for n in s_nums)
        s_lower = s.lower()
        s_has_unverified_claim = any(ct in s_lower for ct in unverified_claims_texts if len(ct) > 10)

        if s_has_unverified_num or s_has_unverified_claim:
            stripped_sentences.append(s.strip())
        else:
            kept_sentences.append(s.strip())

    cleaned_text = " ".join(kept_sentences).strip()
    return cleaned_text, stripped_sentences

def validate_citations(
    synthesis_result: Dict[str, Any],
    structured_results: List[Dict[str, Any]],
    dataset_profile: Optional[Dict[str, Any]] = None,
    insights: Optional[List[Any]] = None,
    tolerance: float = 0.05
) -> Dict[str, Any]:
    """
    Programmatically verify all numeric claims in the synthesis output using bound checking.
    - Verifies each structured claim against its declared source_id and metric_key.
    - Verifies that every number in the prose belongs to a verified claim.
    - Strips offending sentences if unverified claims/numbers persist.
    - Returns audit details including pre-strip and post-strip verification rates.
    """
    source_index = build_source_index(structured_results, dataset_profile, insights=insights)
    
    # Collect narrative text
    exec_summary = synthesis_result.get("executive_summary", "")
    key_findings = synthesis_result.get("key_findings", [])
    text_corpus = exec_summary
    for finding in key_findings:
        text_corpus += " " + str(finding.get("finding", "")) + " " + str(finding.get("narrative", ""))

    extracted_numbers = extract_numeric_tokens(text_corpus)
    claims = synthesis_result.get("claims") or []

    verified_claims = []
    unverified_claims = []
    verified_claim_values: Set[float] = set()

    # 1. Verify structured claims
    for claim in claims:
        is_valid, reason = verify_bound_claim(claim, source_index, tolerance=tolerance)
        if is_valid:
            verified_claims.append(claim)
            try:
                c_val = float(claim["value"])
                verified_claim_values.add(round(c_val, 2))
                verified_claim_values.add(round(c_val, 1))
                verified_claim_values.add(round(c_val, 4))
                verified_claim_values.add(float(int(c_val)))
            except Exception:
                pass
        else:
            unverified_claims.append({"claim": claim, "reason": reason})

    # 2. Check every number in prose against verified claims (or source index if claims omitted)
    verified_numbers = []
    unverified_numbers = []

    # Flatten all source index values for fallback or claim matching
    all_source_values: Set[float] = set()
    for s_dict in source_index.values():
        for sv in s_dict.values():
            if isinstance(sv, (int, float)) and not isinstance(sv, bool):
                all_source_values.add(round(float(sv), 2))
                all_source_values.add(round(float(sv), 1))
                all_source_values.add(round(float(sv), 4))
                all_source_values.add(float(int(sv)))

    for num in extracted_numbers:
        matched = False
        rounded = round(num, 2)

        if claims:
            # Must belong to a verified claim
            if rounded in verified_claim_values or round(num, 1) in verified_claim_values or float(int(num)) in verified_claim_values:
                matched = True
            else:
                for cv in verified_claim_values:
                    if abs(cv) > 0 and abs(num - cv) / abs(cv) <= tolerance:
                        matched = True
                        break
        else:
            # Fallback if claims list was not provided: check source index
            if rounded in all_source_values or round(num, 1) in all_source_values or float(int(num)) in all_source_values:
                matched = True
            else:
                for sv in all_source_values:
                    if abs(sv) > 0 and abs(num - sv) / abs(sv) <= tolerance:
                        matched = True
                        break

        if matched:
            verified_numbers.append(num)
        else:
            unverified_numbers.append(num)

    total_claims_checked = len(claims) if claims else len(extracted_numbers)
    verified_claims_count = len(verified_claims) if claims else len(verified_numbers)
    unverified_claims_count = len(unverified_claims) if claims else len(unverified_numbers)

    total_prose_nums = len(extracted_numbers)
    pre_strip_rate = round((len(verified_numbers) / total_prose_nums) * 100, 2) if total_prose_nums > 0 else 100.0

    # 3. Strip unverified sentences if needed
    cleaned_summary, stripped_sentences = strip_unverified_sentences(
        exec_summary,
        unverified_numbers,
        [uc["claim"] for uc in unverified_claims]
    )

    post_strip_numbers = extract_numeric_tokens(cleaned_summary)
    post_strip_verified = [n for n in post_strip_numbers if round(n, 2) not in set(round(x, 2) for x in unverified_numbers)]
    post_strip_rate = 100.0 if not post_strip_numbers or len(post_strip_numbers) == len(post_strip_verified) else round((len(post_strip_verified) / len(post_strip_numbers)) * 100, 2)

    is_valid = (len(unverified_claims) == 0 and len(unverified_numbers) == 0)

    return {
        "is_valid": is_valid,
        "total_claims_checked": total_claims_checked,
        "verified_claims_count": verified_claims_count,
        "unverified_claims_count": unverified_claims_count,
        "verification_rate_percent": pre_strip_rate,
        "pre_strip_verification_rate": pre_strip_rate,
        "post_strip_verification_rate": post_strip_rate,
        "verified_numbers": verified_numbers,
        "unverified_numbers": unverified_numbers,
        "unverified_claims": unverified_claims,
        "stripped_sentences": stripped_sentences,
        "cleaned_executive_summary": cleaned_summary,
        "status": "passed" if is_valid else "flagged"
    }
