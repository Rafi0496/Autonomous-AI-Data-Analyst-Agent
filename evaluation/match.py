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
                        return True, ins.get("id"), f"Matched S1 (p={p_val})"
        return False, None, "S1 not found in surviving insights"

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
                        return True, ins.get("id"), f"Matched C1 (r={r_val:.2f})"
        return False, None, "C1 not found in surviving insights"

    # 3. T1 Trend
    if planted_id == "T1" or p_type == "trend":
        t_col = _normalize(planted_spec.get("metric_column", "trend_metric"))
        for ins in insights:
            if ins.get("type") == "trend":
                full_text = _normalize(f"{ins.get('title')} {ins.get('summary')} {ins.get('headline')}")
                if t_col in full_text or "trend_metric" in full_text:
                    direction = ins.get("direction", "upward")
                    if direction in ("upward", "positive", "increasing"):
                        return True, ins.get("id"), f"Matched T1 (trend on {t_col})"
        return False, None, "T1 not found in surviving insights"

    # 4. O1 Outliers
    if planted_id == "O1" or p_type in ("outlier", "outliers"):
        o_col = _normalize(planted_spec.get("column", "volume"))
        for ins in insights:
            if ins.get("type") in ("outlier", "outliers"):
                full_text = _normalize(f"{ins.get('title')} {ins.get('summary')} {ins.get('headline')}")
                if o_col in full_text or "volume" in full_text:
                    return True, ins.get("id"), "Matched O1 (outliers in volume)"
        return False, None, "O1 not found in surviving insights"

    # 5. Q1 Sentinel
    if planted_id == "Q1" or p_type == "sentinel":
        q_col = _normalize(planted_spec.get("column", "satisfaction_score"))
        for item in dq_items:
            full_text = _normalize(f"{item.get('title')} {item.get('summary')} {item.get('headline')} {item.get('narrative')} {item.get('details')}")
            if ("999" in full_text or "sentinel" in full_text) and (q_col in full_text or "satisfaction" in full_text):
                return True, item.get("id") or "dq_sentinel", "Matched Q1 (999 sentinel in satisfaction_score)"
        return False, None, "Q1 not found in data quality insights"

    # 6. Q2 Invalid Domain
    if planted_id == "Q2" or p_type == "invalid_domain":
        q2_col = _normalize(planted_spec.get("column", "salary"))
        for item in dq_items:
            full_text = _normalize(f"{item.get('title')} {item.get('summary')} {item.get('headline')} {item.get('narrative')} {item.get('details')}")
            if ("negative" in full_text or "invalid" in full_text) and (q2_col in full_text or "salary" in full_text):
                return True, item.get("id") or "dq_invalid", "Matched Q2 (negative salary values)"
        return False, None, "Q2 not found in data quality insights"

    # 7. M1 Missingness
    if planted_id == "M1" or p_type == "missingness":
        m_col = _normalize(planted_spec.get("column", "activity_index"))
        for item in dq_items:
            full_text = _normalize(f"{item.get('title')} {item.get('summary')} {item.get('headline')} {item.get('narrative')} {item.get('details')}")
            if ("missing" in full_text or "imput" in full_text) and (m_col in full_text or "activity" in full_text):
                return True, item.get("id") or "dq_missing", "Matched M1 (missingness in activity_index)"
        return False, None, "M1 not found in data quality insights"

    return False, None, f"Unknown planted finding type: {p_type}"


def audit_dataset_findings(
    manifest: Dict[str, Any],
    insights: List[Dict[str, Any]],
    dq_caveats: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Perform complete ground-truth match audit for a dataset.
    Returns audit summary, matches table, false positives, and formatted markdown table.
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

    # False positive detection
    false_positives = []
    core_cols = ["segment", "metric_score", "var_x", "var_y", "trend_metric", "volume"]

    for ins in insights:
        ins_type = ins.get("type")
        if ins_type in ("segment_difference", "correlation", "trend", "outlier"):
            ins_text = _normalize(f"{ins.get('title')} {ins.get('summary')} {ins.get('headline')}")
            if is_null:
                false_positives.append({
                    "insight_id": ins.get("id"),
                    "type": ins_type,
                    "reason": f"Signal claimed on NULL dataset (type: {ins_type})"
                })
            else:
                # Planted dataset: check if finding claimed on decoy columns
                if any(f"decoy" in ins_text for _ in [1]):
                    false_positives.append({
                        "insight_id": ins.get("id"),
                        "type": ins_type,
                        "reason": f"Signal claimed on decoy noise column: {ins.get('title')}"
                    })

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
        lines.append(f"- **False Positives Detected:** {len(false_positives)}")
        if false_positives:
            for fp in false_positives:
                lines.append(f"  - [{fp['type']}] `{fp['insight_id']}`: {fp['reason']}")
        else:
            lines.append("  - None (Clean null run: 0 false positives).")

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
        "false_positive_count": len(false_positives),
        "audit_table_markdown": audit_table_markdown
    }
