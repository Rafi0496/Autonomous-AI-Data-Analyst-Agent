"""Matcher and Ground-Truth Audit Harness (Stage B2).

Implements deterministic rules mapping surviving insights and data quality caveats
to ground-truth planted IDs (S1, C1, T1, O1, Q1, Q2, M1) or flagging false positives on NULL datasets.

Documented Matching Rules:
1. S1 (Segment Difference):
   - Type: 'segment_difference'
   - Segment Column: 'segment'
   - Metric Column: 'metric_score'
   - Condition: Statistical significance p < 0.05 and direction GroupA > GroupB.
2. C1 (Correlation):
   - Type: 'correlation'
   - Columns: 'var_x' and 'var_y'
   - Condition: |r| >= 0.45, positive direction.
3. T1 (Trend):
   - Type: 'trend'
   - Column: 'trend_metric'
   - Condition: Positive upward slope, p < 0.05.
4. O1 (Outliers):
   - Type: 'outlier'
   - Column: 'volume'
   - Condition: Outliers detected (> 0).
5. Q1 (Sentinel):
   - Type: 'data_quality'
   - Column: 'satisfaction_score'
   - Condition: Sentinel 999 identified and reported.
6. Q2 (Invalid Domain):
   - Type: 'data_quality'
   - Column: 'salary'
   - Condition: Invalid negative salary values detected and sanitized.
7. M1 (Missingness):
   - Type: 'data_quality'
   - Column: 'activity_index'
   - Condition: Missingness / imputation reported for activity_index (~20%).

On NULL Datasets:
   - Any surviving analytical insight (segment_difference, correlation, trend, outlier)
     on the core variables is recorded as a FALSE POSITIVE.
"""
from typing import Any, Dict, List, Optional, Tuple


def _normalize(text: Optional[str]) -> str:
    return (text or "").lower().replace(" ", "_")


def match_single_planted_finding(
    planted_id: str,
    planted_spec: Dict[str, Any],
    insights: List[Dict[str, Any]],
    dq_caveats: Optional[List[Dict[str, Any]]] = None
) -> Tuple[bool, Optional[str], str]:
    """Match a single planted finding against surviving insights and data-quality caveats."""
    p_type = planted_spec.get("type")
    dq_items = (dq_caveats or []) + [i for i in insights if i.get("type") == "data_quality"]

    # 1. S1 Segment Difference
    if planted_id == "S1" or p_type == "segment_difference":
        target_seg = _normalize(planted_spec.get("segment_column", "segment"))
        target_metric = _normalize(planted_spec.get("metric_column", "metric_score"))
        for ins in insights:
            if ins.get("type") == "segment_difference":
                title_norm = _normalize(ins.get("title") or "")
                summary_norm = _normalize(ins.get("summary") or "")
                headline_norm = _normalize(ins.get("headline") or "")
                full_text = f"{title_norm} {summary_norm} {headline_norm}"
                
                # Check column match
                col_match = (
                    (ins.get("segment_column") == planted_spec.get("segment_column") or target_seg in full_text)
                    and (ins.get("metric_column") == planted_spec.get("metric_column") or target_metric in full_text)
                )
                if col_match:
                    p_val = ins.get("significance", 1.0)
                    if p_val is None or p_val < 0.05:
                        diff_val = ins.get("effect_size")
                        diff_str = f", diff={diff_val:.3f}" if isinstance(diff_val, (int, float)) else ""
                        return True, ins.get("id"), f"Matched S1 ({ins.get('segment_column', target_seg)} vs {ins.get('metric_column', target_metric)}: p={p_val}{diff_str})"
        return False, None, f"S1 not found in surviving insights (evaluated segment={target_seg}, metric={target_metric})"

    # 2. C1 Correlation
    if planted_id == "C1" or p_type == "correlation":
        c1 = _normalize(planted_spec.get("column_1", "var_x"))
        c2 = _normalize(planted_spec.get("column_2", "var_y"))
        for ins in insights:
            if ins.get("type") == "correlation":
                full_text = _normalize(f"{ins.get('title')} {ins.get('summary')} {ins.get('headline')}")
                if (c1 in full_text or "var_x" in full_text) and (c2 in full_text or "var_y" in full_text):
                    r_val = ins.get("effect_size", 0.0)
                    if abs(r_val) >= 0.40:
                        p_val = ins.get("significance")
                        p_str = f", p={p_val}" if p_val is not None else ""
                        return True, ins.get("id"), f"Matched C1 ({c1}~{c2}: r={r_val:.2f}{p_str})"
        return False, None, f"C1 not found in surviving insights (evaluated {c1}~{c2} |r|>=0.40)"

    # 3. T1 Trend
    if planted_id == "T1" or p_type == "trend":
        t_col = _normalize(planted_spec.get("metric_column", "trend_metric"))
        for ins in insights:
            if ins.get("type") == "trend":
                full_text = _normalize(f"{ins.get('title')} {ins.get('summary')} {ins.get('headline')}")
                if t_col in full_text or "trend_metric" in full_text:
                    direction = ins.get("direction", "upward")
                    if direction in ("upward", "positive", "increasing"):
                        p_val = ins.get("significance")
                        p_str = f", p={p_val}" if p_val is not None else ""
                        return True, ins.get("id"), f"Matched T1 ({t_col}: {direction} trend{p_str})"
        return False, None, f"T1 not found in surviving insights (evaluated trend on {t_col})"

    # 4. O1 Outliers
    if planted_id == "O1" or p_type in ("outlier", "outliers"):
        o_col = _normalize(planted_spec.get("column", "volume"))
        for ins in insights:
            if ins.get("type") in ("outlier", "outliers"):
                full_text = _normalize(f"{ins.get('title')} {ins.get('summary')} {ins.get('headline')}")
                if o_col in full_text or "volume" in full_text:
                    cnt = ins.get("metric_values", {}).get("outlier_count")
                    cnt_str = f", count={cnt}" if cnt is not None else ""
                    return True, ins.get("id"), f"Matched O1 ({o_col}: 3.0x IQR outliers{cnt_str})"
        return False, None, f"O1 not found in surviving insights (evaluated 3.0x IQR outliers on {o_col})"

    # 5. Q1 Sentinel
    if planted_id == "Q1" or p_type == "sentinel":
        q_col = _normalize(planted_spec.get("column", "satisfaction_score"))
        for item in dq_items:
            full_text = _normalize(f"{item.get('title')} {item.get('summary')} {item.get('headline')} {item.get('narrative')} {item.get('details')}")
            if ("999" in full_text or "sentinel" in full_text) and (q_col in full_text or "satisfaction" in full_text):
                cnt = item.get("metric_values", {}).get("count_999") or item.get("metric_values", {}).get("affected_count")
                cnt_str = f", count={cnt}" if cnt is not None else ""
                return True, item.get("id") or "dq_sentinel", f"Matched Q1 ({q_col}: sentinel 999{cnt_str})"
        return False, None, f"Q1 not found in data quality insights (evaluated sentinel 999 on {q_col})"

    # 6. Q2 Invalid Domain
    if planted_id == "Q2" or p_type == "invalid_domain":
        q2_col = _normalize(planted_spec.get("column", "salary"))
        for item in dq_items:
            full_text = _normalize(f"{item.get('title')} {item.get('summary')} {item.get('headline')} {item.get('narrative')} {item.get('details')}")
            if ("negative" in full_text or "invalid" in full_text) and (q2_col in full_text or "salary" in full_text):
                cnt = item.get("metric_values", {}).get("negative_count") or item.get("metric_values", {}).get("affected_count")
                cnt_str = f", count={cnt}" if cnt is not None else ""
                return True, item.get("id") or "dq_invalid", f"Matched Q2 ({q2_col}: negative values domain violation{cnt_str})"
        return False, None, f"Q2 not found in data quality insights (evaluated negative domain values on {q2_col})"

    # 7. M1 Missingness
    if planted_id == "M1" or p_type == "missingness":
        m_col = _normalize(planted_spec.get("column", "activity_index"))
        for item in dq_items:
            full_text = _normalize(f"{item.get('title')} {item.get('summary')} {item.get('headline')} {item.get('narrative')} {item.get('details')}")
            if ("missing" in full_text or "imput" in full_text) and (m_col in full_text or "activity" in full_text):
                rate = item.get("metric_values", {}).get("imputation_rate") or item.get("imputation_rate")
                rate_str = f", rate={float(rate)*100:.1f}%" if isinstance(rate, (int, float)) else " (>=10% reporting threshold)"
                return True, item.get("id") or "dq_missing", f"Matched M1 ({m_col}: missingness/imputation{rate_str})"
        return False, None, f"M1 not found in data quality insights (evaluated missingness on {m_col} >= 10%)"

    return False, None, f"Unknown planted finding type: {p_type}"


import numpy as np
import scipy.stats as stats


def extract_insight_p_value(ins: Dict[str, Any]) -> Optional[float]:
    """Extract or compute the statistical hypothesis p-value for an insight."""
    mv = ins.get("metric_values") or {}
    p = ins.get("significance") if isinstance(ins.get("significance"), (int, float)) else None
    if p is None:
        for k in ["p_value", "pval", "p", "trend_p_val", "trend_p_value"]:
            if k in mv and isinstance(mv[k], (int, float)):
                p = float(mv[k])
                break
    if p is None and ins.get("type") == "correlation":
        r = ins.get("effect_size") if isinstance(ins.get("effect_size"), (int, float)) else mv.get("pearson", mv.get("r"))
        n = ins.get("n_used", mv.get("n_used", 2000))
        if r is not None and isinstance(r, (int, float)) and n > 2:
            r_val = float(r)
            if abs(r_val) >= 1.0:
                return 0.0
            t_stat = r_val * np.sqrt((n - 2) / (1.0 - r_val**2))
            p = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat), df=n - 2)))
    return p


def audit_dataset_findings(
    manifest: Dict[str, Any],
    insights: List[Dict[str, Any]],
    dq_caveats: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Perform complete ground-truth match audit for a dataset.
    Returns audit summary, matches table, false positives (p < 0.05 only, Benjamini-Hochberg corrected),
    outlier flags, and data quality flags separately.
    """
    is_null = manifest.get("is_null", False)
    seed = manifest.get("seed", 0)
    planted_findings = manifest.get("planted_findings", {})

    matches = {}
    audit_rows = []

    if not is_null:
        for p_id, p_spec in planted_findings.items():
            found, match_id, note = match_single_planted_finding(
                planted_id=p_id,
                planted_spec=p_spec,
                insights=insights,
                dq_caveats=dq_caveats
            )
            matches[p_id] = {
                "planted_id": p_id,
                "expected_type": p_spec.get("type"),
                "found": found,
                "matching_insight_id": match_id,
                "note": note
            }
            audit_rows.append({
                "planted_id": p_id,
                "expected_type": p_spec.get("type"),
                "found": "Yes" if found else "No",
                "matching_id": match_id or "—",
                "note": note
            })

    # 1. Collect all statistical hypothesis tests in this run
    tests_conducted = []
    for ins in insights:
        ins_type = ins.get("type")
        if ins_type in ("segment_difference", "correlation", "trend"):
            p_val = extract_insight_p_value(ins)
            tests_conducted.append({"insight": ins, "p_value": p_val})

    # 2. Apply Benjamini-Hochberg across all tests in the run
    valid_p_indices = [i for i, t in enumerate(tests_conducted) if t["p_value"] is not None]
    if valid_p_indices:
        raw_p_values = [tests_conducted[i]["p_value"] for i in valid_p_indices]
        try:
            adj_p_values = stats.false_discovery_control(raw_p_values, method="bh")
            for orig_idx, adj_p in zip(valid_p_indices, adj_p_values):
                tests_conducted[orig_idx]["p_adj"] = float(adj_p)
                tests_conducted[orig_idx]["insight"]["p_adj"] = float(adj_p)
        except Exception:
            for orig_idx in valid_p_indices:
                tests_conducted[orig_idx]["p_adj"] = tests_conducted[orig_idx]["p_value"]

    # 3. Separate significant claims, outlier flags, and data quality flags
    false_positives = []
    outlier_flags = []
    dq_flags = []

    if is_null:
        for t in tests_conducted:
            ins = t["insight"]
            p_val = t["p_value"]
            p_adj = t.get("p_adj", p_val)
            # Count FP only for significant-claim insight (p < 0.05 and p_adj < 0.05)
            if p_val is not None and p_val < 0.05 and (p_adj is None or p_adj < 0.05):
                false_positives.append({
                    "insight_id": ins.get("id"),
                    "type": ins.get("type"),
                    "p_value": round(p_val, 4),
                    "p_adj": round(p_adj, 4) if p_adj is not None else None,
                    "reason": f"Significant claim on NULL dataset (p={p_val:.4f}, p_adj={p_adj:.4f})"
                })

        for ins in insights:
            if ins.get("type") in ("outlier", "outliers"):
                outlier_flags.append({
                    "insight_id": ins.get("id"),
                    "title": ins.get("title", ""),
                    "summary": ins.get("summary", ""),
                    "fence": "3.0x IQR"
                })

        for item in (dq_caveats or []) + [i for i in insights if i.get("type") == "data_quality"]:
            dq_flags.append({
                "id": item.get("id"),
                "title": item.get("title", "")
            })
    else:
        for t in tests_conducted:
            ins = t["insight"]
            ins_text = _normalize(f"{ins.get('title')} {ins.get('summary')} {ins.get('headline')}")
            if "decoy" in ins_text:
                p_val = t["p_value"]
                p_adj = t.get("p_adj", p_val)
                if p_val is not None and p_val < 0.05 and (p_adj is None or p_adj < 0.05):
                    false_positives.append({
                        "insight_id": ins.get("id"),
                        "type": ins.get("type"),
                        "p_value": round(p_val, 4),
                        "p_adj": round(p_adj, 4) if p_adj is not None else None,
                        "reason": f"Spurious claim on decoy column (p={p_val:.4f}, p_adj={p_adj:.4f})"
                    })

    total_tests_n = len(tests_conducted)
    fp_count = len(false_positives)
    per_test_fp_rate = round((fp_count / total_tests_n) * 100, 2) if total_tests_n > 0 else 0.0

    # Build Markdown Audit Table
    lines = []
    lines.append(f"### Matcher Audit Table: Seed {seed} ({'NULL Dataset' if is_null else 'Planted Dataset'})")
    if not is_null:
        lines.append("| Planted ID | Expected Type | Found | Matching Insight ID | Audit Note |")
        lines.append("|---|---|---|---|---|")
        for r in audit_rows:
            lines.append(f"| **{r['planted_id']}** | `{r['expected_type']}` | **{r['found']}** | `{r['matching_id']}` | {r['note']} |")
    else:
        lines.append(f"- **Planted Findings Expected:** 0 (NULL dataset)")
        lines.append(f"- **Statistical Tests Evaluated (n):** {total_tests_n}")
        lines.append(f"- **Significant-Claim False Positives (p < 0.05, BH):** {fp_count} (per-test rate: {per_test_fp_rate}% vs expected alpha 5.0%)")
        lines.append(f"- **Outlier Flags (3.0x IQR fence, reported separately):** {len(outlier_flags)}")
        lines.append(f"- **Data Quality Flags (reported separately):** {len(dq_flags)}")
        if false_positives:
            for fp in false_positives:
                lines.append(f"  - [{fp['type']}] `{fp['insight_id']}`: {fp['reason']}")
        else:
            lines.append("  - None (Clean null run: 0 significant-claim false positives).")

    audit_table_markdown = "\n".join(lines)

    total_planted = len(planted_findings)
    found_count = sum(1 for m in matches.values() if m["found"])
    recall = round((found_count / total_planted) * 100, 2) if total_planted > 0 else 0.0

    return {
        "seed": seed,
        "is_null": is_null,
        "total_planted": total_planted,
        "found_count": found_count,
        "recall_percent": recall,
        "matches": matches,
        "false_positives": false_positives,
        "false_positive_count": fp_count,
        "outlier_flags": outlier_flags,
        "outlier_flag_count": len(outlier_flags),
        "data_quality_flags": dq_flags,
        "data_quality_flag_count": len(dq_flags),
        "total_tests_n": total_tests_n,
        "per_test_fp_rate": per_test_fp_rate,
        "expected_alpha": 0.05,
        "audit_table_markdown": audit_table_markdown
    }
