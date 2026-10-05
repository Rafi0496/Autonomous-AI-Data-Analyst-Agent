"""Deterministic Follow-Up Candidate Generator (Milestone 4).

Computes candidate follow-up actions deterministically after each round based on 3 triggers:
1. Segment p < 0.05:
   Drill down by a second categorical column or multi-dimensional group-by.
2. Outlier rate > 5% in a column:
   Inspect that column distribution and extreme values.
3. |r| > 0.5:
   Check the correlated pair across categories of a segment column.

If no trigger fires, returns an empty list (does not force follow-ups).
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from backend.app.agent.llm_client import ToolCall


def compute_candidate_follow_ups(
    executed_results: List[Dict[str, Any]],
    profile: Dict[str, Any],
    dataset_id: str,
    existing_tools_run: Optional[Set[str]] = None
) -> Tuple[List[ToolCall], List[str]]:
    """
    Inspect executed results from the round and compute candidate follow-ups deterministically.
    Returns:
        candidate_tool_calls: List[ToolCall] (up to available candidates)
        trigger_reasons: List[str] (explanation for each candidate trigger)
    """
    candidates: List[ToolCall] = []
    reasons: List[str] = []
    existing_tools_run = existing_tools_run or set()

    # Extract available columns and types from profile
    columns_info = profile.get("columns", {})
    col_types = profile.get("column_types", {})
    total_records = profile.get("row_count") or profile.get("cleaned_row_count") or 100

    id_patterns = ("id", "code", "key", "number", "txn", "phone", "email")

    categorical_cols = []
    numeric_cols = []
    for c, info in columns_info.items():
        c_low = c.lower()
        t = info.get("inferred_type") or info.get("type") or col_types.get(c, "")
        u_cnt = info.get("unique_count", 0)
        is_id = any(c_low == p or c_low.endswith(f"_{p}") or c_low.startswith(f"{p}_") for p in id_patterns)
        
        if t in ("categorical", "string", "text", "boolean") or (t == "numeric" and 2 <= u_cnt <= 10):
            if not is_id and 2 <= u_cnt <= 50:
                categorical_cols.append(c)
        elif t in ("numeric", "float", "integer"):
            if not is_id and u_cnt > 5:
                numeric_cols.append(c)

    # -------------------------------------------------------------
    # TRIGGER 1: Segment p < 0.05 -> drill down by second categorical
    # -------------------------------------------------------------
    for res in executed_results:
        t_name = res.get("tool")
        if t_name in ("segment_compare", "run_segmentation"):
            p_val = res.get("p_value")
            if p_val is None:
                p_val = res.get("significance")
            
            if p_val is not None and isinstance(p_val, (int, float)) and p_val < 0.05:
                seg_col = res.get("segment_column") or res.get("segment") or ""
                met_col = res.get("metric_column") or res.get("metric") or ""
                
                # Find a second categorical column
                second_cats = [c for c in categorical_cols if c != seg_col]
                if second_cats and met_col:
                    second_cat = second_cats[0]
                    sql = (
                        f"SELECT {seg_col}, {second_cat}, COUNT(*) as n, "
                        f"ROUND(AVG({met_col}), 2) as avg_{met_col} "
                        f"FROM data_clean GROUP BY {seg_col}, {second_cat} "
                        f"ORDER BY n DESC LIMIT 10"
                    )
                    reason = f"segment p={p_val:.4f} < 0.05 for '{met_col}' across '{seg_col}' -> drill down by '{second_cat}'"
                    reasons.append(reason)
                    candidates.append(ToolCall(
                        name="query_sql",
                        arguments={"dataset_id": dataset_id, "sql": sql},
                        rationale=f"Significant difference (p={p_val:.4f} < 0.05) in {met_col} across {seg_col}; drill down with second categorical dimension '{second_cat}'."
                    ))

    # -------------------------------------------------------------
    # TRIGGER 2: Outlier rate > 5% in a column -> inspect that column
    # -------------------------------------------------------------
    for res in executed_results:
        t_name = res.get("tool")
        if t_name == "detect_outliers":
            n_tot = res.get("total_records") or total_records or 1
            # Check top_outlier_columns
            top_cols = res.get("top_outlier_columns", [])
            if not top_cols and res.get("total_anomalous_rows", 0) > 0 and res.get("column"):
                top_cols = [{"column": res.get("column"), "count": res.get("total_anomalous_rows")}]
                
            for col_entry in top_cols:
                col_name = col_entry.get("column")
                cnt = col_entry.get("count") or col_entry.get("anomalous_rows", 0)
                rate = col_entry.get("outlier_rate") or (cnt / n_tot if n_tot > 0 else 0)
                
                if rate > 0.05 and col_name:
                    sql = (
                        f"SELECT {col_name}, COUNT(*) as frequency "
                        f"FROM data_clean GROUP BY {col_name} "
                        f"ORDER BY frequency DESC LIMIT 10"
                    )
                    reason = f"outlier rate {rate*100:.1f}% > 5% in column '{col_name}' -> inspect column"
                    reasons.append(reason)
                    candidates.append(ToolCall(
                        name="query_sql",
                        arguments={"dataset_id": dataset_id, "sql": sql},
                        rationale=f"Column '{col_name}' exhibited an outlier rate of {rate*100:.1f}% (> 5%); inspect distribution and frequency of extreme values."
                    ))

    # -------------------------------------------------------------
    # TRIGGER 3: |r| > 0.5 -> check pair by segment
    # -------------------------------------------------------------
    for res in executed_results:
        t_name = res.get("tool")
        if t_name == "run_correlation":
            corr_val = res.get("correlation")
            pairs = []
            if corr_val is not None and isinstance(corr_val, (int, float)):
                c1 = res.get("column1") or res.get("col1")
                c2 = res.get("column2") or res.get("col2")
                if c1 and c2:
                    pairs.append((c1, c2, float(corr_val)))
                    
            for p in res.get("top_correlations", []):
                c1 = p.get("col1") or p.get("column1")
                c2 = p.get("col2") or p.get("column2")
                r = p.get("r") or p.get("correlation", 0.0)
                if c1 and c2:
                    pairs.append((c1, c2, float(r)))

            for c1, c2, r_val in pairs:
                if abs(r_val) > 0.5:
                    if categorical_cols:
                        seg_col = categorical_cols[0]
                        sql = (
                            f"SELECT {seg_col}, COUNT(*) as n, "
                            f"ROUND(AVG({c1}), 2) as avg_{c1}, "
                            f"ROUND(AVG({c2}), 2) as avg_{c2} "
                            f"FROM data_clean GROUP BY {seg_col} "
                            f"ORDER BY n DESC LIMIT 10"
                        )
                        reason = f"|r|={abs(r_val):.2f} > 0.5 between '{c1}' and '{c2}' -> check pair by segment '{seg_col}'"
                        reasons.append(reason)
                        candidates.append(ToolCall(
                            name="query_sql",
                            arguments={"dataset_id": dataset_id, "sql": sql},
                            rationale=f"Strong correlation |r|={abs(r_val):.2f} > 0.5 between '{c1}' and '{c2}'; examine paired values across '{seg_col}' categories."
                        ))

    # Deduplicate candidates by tool + arguments
    unique_candidates: List[ToolCall] = []
    unique_reasons: List[str] = []
    seen_calls: Set[str] = set()

    for tc, r_text in zip(candidates, reasons):
        call_key = f"{tc.name}_{tc.arguments.get('sql', '')}_{tc.arguments.get('metric_column', '')}"
        if call_key not in seen_calls:
            seen_calls.add(call_key)
            unique_candidates.append(tc)
            unique_reasons.append(r_text)

    return unique_candidates, unique_reasons
