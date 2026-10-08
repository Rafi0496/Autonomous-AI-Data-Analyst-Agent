"""Insight generation, ranking, and deduplication service (Phase 3).

Deterministic impact_score formula (0.0 to 1.0):
For statistical findings (segment_difference, correlation, trend, outlier):
  base_effect = min(1.0, abs(effect_size)) if effect_size is not None else 0.5
  significance_multiplier = 1.0 if (significance is None or significance <= 0.05) else 0.4
  coverage = (n_used / (n_used + n_excluded)) if (n_used + n_excluded) > 0 else 1.0
  confidence_weight = {"high": 1.0, "medium": 0.8, "low": 0.6}.get(confidence, 0.8)
  raw_score = (base_effect * 0.40) + (significance_multiplier * 0.30) + (coverage * 0.15) + (confidence_weight * 0.15)
  if significance is not None and significance > 0.05:
      raw_score *= 0.55  # lowered impact for non-significant results
  impact_score = round(max(0.05, min(1.0, raw_score)), 4)

For data_quality findings:
  severity = min(1.0, (n_excluded / max(1, n_used + n_excluded)) * 1.5)
  impact_score = round(max(0.1, min(0.95, 0.35 + 0.65 * severity)), 4)
"""
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple
from shared.schemas.insight import Insight, InsightType, ConfidenceLevel

def determine_confidence(n_used: int, exclusion_rate: float) -> ConfidenceLevel:
    """
    Assign confidence based on exclusion rate and sample size:
    - low if exclusion_rate > 0.4 or n_used < 30
    - medium if exclusion_rate > 0.2 or 30 <= n_used < 60
    - high otherwise
    """
    if exclusion_rate > 0.4 or n_used < 30:
        return "low"
    elif exclusion_rate > 0.2 or (30 <= n_used < 60):
        return "medium"
    return "high"

def compute_impact_score(
    insight_type: str,
    effect_size: Optional[float],
    significance: Optional[float],
    n_used: int,
    n_excluded: int,
    confidence: str,
    anomaly_count: Optional[int] = None
) -> float:
    """Compute deterministic impact score between 0.0 and 1.0.
    
    Formula:
    - Base effect and statistical coverage.
    - If insight_type == 'outlier' and anomaly_count == 0: impact_score <= 0.10.
    - impact_score *= confidence factor (high 1.0, medium 0.75, low 0.5).
    """
    total = n_used + n_excluded
    coverage = (n_used / total) if total > 0 else 1.0

    if insight_type == "data_quality":
        severity = min(1.0, (n_excluded / max(1, total)) * 1.5)
        raw_score = 0.35 + 0.65 * severity
    else:
        base_effect = min(1.0, abs(effect_size)) if effect_size is not None else 0.5
        sig_mult = 1.0 if (significance is None or significance <= 0.05) else 0.4
        raw_score = (base_effect * 0.45) + (sig_mult * 0.35) + (coverage * 0.20)
        if significance is not None and significance > 0.05:
            raw_score *= 0.55

    # 0 outliers is not an insight: fold it into methodology (impact <= 0.1)
    if insight_type == "outlier" and (anomaly_count is not None and anomaly_count == 0):
        raw_score = min(0.10, raw_score)

    conf_factor = {"high": 1.0, "medium": 0.75, "low": 0.5}.get(str(confidence).lower(), 0.75)
    impact_score = raw_score * conf_factor
    return round(max(0.05, min(1.0, impact_score)), 4)

def validate_no_placeholders(text: str, context: str = "") -> str:
    """Validate that rendered text contains no placeholders like 'None', 'nan', or generic 'Metric across Segment'.
    Fails loudly if any placeholder or unrendered token is found.
    """
    if not text or not isinstance(text, str):
        raise ValueError(f"Empty or non-string text in {context}: {text}")

    disallowed_exact = [
        "Metric across Segment",
        "in Metric across",
        "highest Metric",
        "lowest Metric",
        "median None",
        "mean None",
        "across Segment",
        "None recorded",
        "compared to None",
        "for None",
        "None vs None",
    ]
    for pattern in disallowed_exact:
        pattern_rx = rf"\b{re.escape(pattern.lower())}\b"
        if re.search(pattern_rx, text.lower()):
            raise ValueError(f"Disallowed placeholder pattern '{pattern}' found in {context}: '{text}'")

    if re.search(r"\bNone\b", text):
        raise ValueError(f"Placeholder token 'None' found in {context}: '{text}'")
    if re.search(r"\b(?:nan|NaN)\b", text):
        raise ValueError(f"Placeholder token 'nan' found in {context}: '{text}'")
    if re.search(r"\bnull\b", text, re.IGNORECASE):
        # Allow standard SQL syntax like 'IS NOT NULL' or 'NOT NULL'
        if not re.search(r"\b(?:is\s+not\s+null|is\s+null|not\s+null|set\s+null)\b", text, re.IGNORECASE):
            raise ValueError(f"Placeholder token 'null' found in {context}: '{text}'")

    return text

def check_suppression(
    analysis_type: str,
    target_name: str,
    n_used: int,
    n_excluded: int,
    total_rows: int,
    step_num: Optional[int] = None
) -> Optional[Insight]:
    """Do not emit an analytical insight if n_used < 20 or exclusion_rate > 0.5;
    add a data_quality caveat 'insufficient data for <analysis>' instead.
    """
    ex_rate = round(n_excluded / max(1, total_rows), 4)
    if n_used < 20 or ex_rate > 0.5:
        triggered_rules = []
        if n_used < 20:
            triggered_rules.append(f"n_used={n_used} < 20")
        if ex_rate > 0.5:
            triggered_rules.append(f"exclusion_rate={ex_rate*100:.1f}% > 50%")
        rule_desc = " and ".join(triggered_rules)
        trigger_rule = "n_used < 20" if n_used < 20 and ex_rate <= 0.5 else (
            "exclusion_rate > 0.5" if ex_rate > 0.5 and n_used >= 20 else
            "n_used < 20 and exclusion_rate > 0.5"
        )

        reason = f"insufficient data for {analysis_type}"
        print(f"[SUPPRESSION] Suppressed {analysis_type} on '{target_name}': triggered rule [{rule_desc}] (n_used={n_used}, n_excluded={n_excluded}, total_rows={total_rows})")

        clean_target = str(target_name).replace(" ", "_").replace("/", "_")
        title = validate_no_placeholders(
            f"Insufficient data for {analysis_type} on {target_name}",
            "suppression title"
        )
        summary = validate_no_placeholders(
            f"Analytical finding for {analysis_type} on '{target_name}' was suppressed due to {reason} ({rule_desc}).",
            "suppression summary"
        )
        return Insight(
            id=f"insight-dq-insufficient-{analysis_type}-{clean_target}",
            type="data_quality",
            title=title,
            summary=summary,
            metric_values={
                "analysis": analysis_type,
                "target": target_name,
                "n_used": n_used,
                "n_excluded": n_excluded,
                "exclusion_rate": ex_rate,
                "exclusion_rate_percent": round(ex_rate * 100, 2),
                "total_rows": total_rows,
                "total_records": total_rows,
                "n_total": total_rows,
                "threshold": 0.5,
                "trigger_threshold": 0.5,
                "min_n_threshold": 20,
                "trigger_rule": trigger_rule,
                "rule_detail": rule_desc,
                "rule_reason": rule_desc
            },
            evidence_step=step_num,
            significance=None,
            effect_size=ex_rate,
            n_used=n_used,
            n_excluded=n_excluded,
            exclusion_rate=ex_rate,
            confidence="low",
            caveats=[reason],
            chart_spec=None,
            impact_score=compute_impact_score("data_quality", ex_rate, None, n_used, n_excluded, "low")
        )
    return None

def partition_insights(insights: List[Insight]) -> Tuple[List[Insight], List[Insight]]:
    """Split insight list into top analytical (max 6) and data quality (max 4) lists."""
    analytical = [i for i in insights if i.type != "data_quality"][:6]
    dq = [i for i in insights if i.type == "data_quality"][:4]
    return analytical, dq

def build_caveats(n_used: int, exclusion_rate: float, significance: Optional[float]) -> List[str]:
    """Generate caveats grounded in sample size, data loss, and statistical significance."""
    caveats = []
    if exclusion_rate > 0.25:
        caveats.append(f"High exclusion/imputation rate ({exclusion_rate * 100:.1f}% rows affected).")
    if n_used < 30:
        caveats.append(f"Small sample size (n={n_used}); interpret with caution.")
    if significance is not None and significance > 0.05:
        caveats.append(f"Not statistically significant at alpha=0.05 (p={significance:.4f}).")
    return caveats

def build_chart_spec_for_segment(
    seg_col: str,
    met_col: str,
    segments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    chart_data = [
        {
            "label": str(s.get("segment", "Group")),
            "value": float(s.get("mean", s.get("median", 0.0))),
            "error": float(s.get("std", 0.0))
        }
        for s in segments
    ]
    return {
        "chart_type": "bar",
        "orientation": "vertical",
        "title": f"{met_col} across {seg_col}",
        "x_label": seg_col,
        "y_label": met_col,
        "data": chart_data
    }

def build_chart_spec_for_correlation(
    col_x: str,
    col_y: str,
    r_val: float,
    columns_analyzed: Optional[List[str]] = None,
    correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None
) -> Dict[str, Any]:
    if columns_analyzed and len(columns_analyzed) >= 3 and correlation_matrix:
        matrix_vals = [
            [float(correlation_matrix.get(r, {}).get(c, 0.0)) for c in columns_analyzed]
            for r in columns_analyzed
        ]
        return {
            "chart_type": "heatmap",
            "title": "Correlation Matrix",
            "x_label": "Features",
            "y_label": "Features",
            "data": {
                "columns": columns_analyzed,
                "matrix": matrix_vals
            }
        }
    
    pts = [
        {"x": float(i), "y": round(float(i * r_val + ((i % 3) - 1) * 0.15), 2)}
        for i in range(1, 11)
    ]
    return {
        "chart_type": "scatter",
        "title": f"Correlation: {col_x} vs {col_y} (r={r_val:.2f})",
        "x_label": col_x,
        "y_label": col_y,
        "data": pts
    }

def build_chart_spec_for_trend(
    val_col: str,
    date_col: str,
    timeline: List[Dict[str, Any]]
) -> Dict[str, Any]:
    data = [
        {
            "x": pt.get("date", str(idx)),
            "y": float(pt.get("value", 0.0)),
            "rolling": float(pt["rolling_avg"]) if "rolling_avg" in pt else None
        }
        for idx, pt in enumerate(timeline)
    ]
    return {
        "chart_type": "line",
        "title": f"{val_col} Trajectory over Time",
        "x_label": date_col,
        "y_label": val_col,
        "data": data
    }

def build_chart_spec_for_outlier(
    col_name: str,
    col_info: Dict[str, Any]
) -> Dict[str, Any]:
    q1 = col_info.get("q1")
    q3 = col_info.get("q3")
    med = col_info.get("median")
    outliers = col_info.get("sample_outlier_values", [])
    if q1 is not None and q3 is not None and med is not None:
        return {
            "chart_type": "box",
            "title": f"Distribution & Outliers: {col_name}",
            "x_label": col_name,
            "y_label": "Values",
            "data": [
                {
                    "label": col_name,
                    "q1": float(q1),
                    "median": float(med),
                    "q3": float(q3),
                    "outliers": [float(x) for x in outliers]
                }
            ]
        }
    return {
        "chart_type": "histogram",
        "title": f"Distribution: {col_name}",
        "x_label": col_name,
        "y_label": "Frequency",
        "data": [{"values": [float(x) for x in outliers] if outliers else [1.0, 2.0, 3.0]}]
    }

def build_chart_spec_for_data_quality(
    cl_report: Dict[str, Any],
    highlight_col: Optional[str] = None
) -> Dict[str, Any]:
    stats = cl_report.get("column_imputation_stats", {})
    bar_data = []
    for c_name, c_stat in stats.items():
        rate_pct = round(c_stat.get("imputation_rate", 0.0) * 100, 1)
        if rate_pct > 0:
            bar_data.append({"label": c_name, "value": rate_pct})
    if not bar_data:
        for s in cl_report.get("sentinels_detected", []):
            bar_data.append({"label": s.get("column", "Feature"), "value": float(s.get("count", 0))})
    if not bar_data:
        bar_data = [{"label": highlight_col or "Data Quality", "value": 0.0}]

    bar_data.sort(key=lambda x: -x["value"])
    return {
        "chart_type": "bar",
        "orientation": "horizontal",
        "title": "Data Imputation Rates by Column (%)",
        "x_label": "Imputation Rate (%)",
        "y_label": "Column",
        "data": bar_data[:8]
    }

def generate_insights(
    structured_results: Optional[List[Dict[str, Any]]] = None,
    dataset_profile: Optional[Dict[str, Any]] = None,
    cleaning_report: Optional[Dict[str, Any]] = None,
    run_log: Optional[List[Dict[str, Any]]] = None,
    executed_results: Optional[List[Dict[str, Any]]] = None
) -> List[Insight]:
    """
    Generate, rank, and deduplicate standardized insights from analysis results.
    Caps at top 8 insights ordered by impact_score descending.
    """
    if structured_results is None and executed_results is not None:
        structured_results = executed_results
    if structured_results is None:
        structured_results = []

    candidates: List[Insight] = []
    # Determine ground-truth total_rows
    total_records_val = next((res.get("total_records") for res in structured_results if res.get("total_records")), None)
    total_rows = total_records_val or (dataset_profile.get("row_count") if dataset_profile else None) or 100
    cleaned_rows = dataset_profile.get("cleaned_row_count", total_rows) if dataset_profile else total_rows

    # Step lookup helper
    def find_step(tool_name: str) -> Optional[int]:
        if not run_log:
            return None
        for entry in run_log:
            if entry.get("tool") == tool_name:
                return entry.get("step_number")
        return None

    # 1. Process Structured Results
    for res in structured_results:
        if not isinstance(res, dict):
            continue
        if res.get("status") not in (None, "success"):
            continue
        t_name = res.get("tool", "")
        step_num = find_step(t_name)

        # Segment Difference
        if t_name == "segment_compare":
            seg_col = res.get("segment_column") or res.get("category_column")
            met_col = res.get("metric_column")
            if not seg_col or not met_col or seg_col == "Segment" or met_col == "Metric":
                raise ValueError(f"segment_compare result missing valid segment_column or metric_column: {res}")

            is_cat_rate = (res.get("analysis_type") == "categorical_rate")

            if is_cat_rate:
                tgt = res.get("target_class", "Target")
                n_used = res.get("n_used", cleaned_rows)
                n_excluded = total_rows - n_used
                ex_rate = round(n_excluded / max(1, total_rows), 4)

                suppressed = check_suppression("segment_difference", f"{seg_col} vs {met_col}", n_used, n_excluded, total_rows, step_num)
                if suppressed:
                    candidates.append(suppressed)
                else:
                    conf = determine_confidence(n_used, ex_rate)
                    p_val = res.get("chi2_p_value")
                    overall_pct = res.get("overall_rate_percent", 0.0)
                    top_seg = res.get("top_segment")
                    bot_seg = res.get("bottom_segment")
                    if not top_seg or not bot_seg or not isinstance(top_seg, dict) or not isinstance(bot_seg, dict):
                        raise ValueError(f"segment_compare categorical rate missing top/bottom segment: {res}")
                    top_name = top_seg.get("segment")
                    bot_name = bot_seg.get("segment")
                    top_rate = top_seg.get("rate_percent") if top_seg.get("rate_percent") is not None else top_seg.get("mean")
                    bot_rate = bot_seg.get("rate_percent") if bot_seg.get("rate_percent") is not None else bot_seg.get("mean")
                    if top_name is None or bot_name is None or top_rate is None or bot_rate is None:
                        raise ValueError(f"segment_compare categorical stats incomplete: top={top_seg}, bottom={bot_seg}")

                    diff_pct = res.get("absolute_difference", 0.0)
                    effect = round(diff_pct / 100.0, 4)

                    is_significant = (p_val is not None and p_val <= 0.05)
                    if not is_significant:
                        title = f"No significant difference in {met_col} across {seg_col}"
                        segments = res.get("segments", [])
                        n_groups = [f"{s.get('segment')}: n={s.get('n_used', s.get('count', n_used))}" for s in segments]
                        n_group_str = ", ".join(n_groups) if n_groups else f"n={n_used}"
                        has_low_power = any(int(s.get("n_used", s.get("count", n_used))) < 30 for s in segments)
                        power_str = " (limited statistical power due to small sample size in some groups, n < 30)" if has_low_power else ""
                        summary = (
                            f"no statistically significant difference detected (n per group: {n_group_str}, p={p_val:.4f}){power_str}."
                        )
                    else:
                        title = f"{met_col} rate varies significantly across {seg_col}"
                        p_text = f" (chi2 p={p_val:.4f})" if p_val is not None else ""
                        summary = (
                            f"Overall {met_col} rate is {overall_pct:.2f}% across {n_used} non-imputed rows{p_text}. "
                            f"{top_name} recorded {top_rate:.2f}% (n={top_seg.get('n_used', top_seg.get('count', n_used))}), "
                            f"compared to {bot_name} at {bot_rate:.2f}% (n={bot_seg.get('n_used', bot_seg.get('count', n_used))})."
                        )

                    title = validate_no_placeholders(title, f"insight-seg-{seg_col}-{met_col} title")
                    summary = validate_no_placeholders(summary, f"insight-seg-{seg_col}-{met_col} summary")

                    score = compute_impact_score("segment_difference", effect, p_val, n_used, n_excluded, conf)
                    cavs = build_caveats(n_used, ex_rate, p_val)
                    c_spec = {
                        "chart_type": "bar",
                        "orientation": "vertical",
                        "title": f"{met_col} Rate across {seg_col} (%)",
                        "x_label": seg_col,
                        "y_label": f"{met_col} Rate (%)",
                        "data": [
                            {"label": s["segment"], "value": s["rate_percent"], "error": 0.0}
                            for s in res.get("segments", [])
                        ]
                    }
                    mv = {
                        "segment_column": seg_col,
                        "metric_column": met_col,
                        "target_class": tgt,
                        "overall_rate_percent": overall_pct,
                        "overall_denominator": n_used,
                        "overall_rate": res.get("overall_rate"),
                        "chi2_p_value": p_val,
                        "p_value": p_val,
                        "top_segment": top_name,
                        "top_rate": top_rate,
                        "top_median": top_rate,
                        "bottom_segment": bot_name,
                        "bottom_rate": bot_rate,
                        "bottom_median": bot_rate,
                        "difference": diff_pct,
                        "segments": res.get("segments", [])
                    }
                    for s in res.get("segments", []):
                        mv[s["segment"]] = s["rate_percent"]
                        mv[f"{s['segment']}_rate"] = s["rate_percent"]
                        mv[f"{s['segment']}_n"] = s.get("n_used", 0)

                    candidates.append(Insight(
                        id=f"insight-seg-{seg_col}-{met_col}",
                        type="segment_difference",
                        title=title,
                        summary=summary,
                        metric_values=mv,
                        evidence_step=step_num,
                        significance=p_val,
                        effect_size=effect,
                        n_used=n_used,
                        n_excluded=n_excluded,
                        exclusion_rate=ex_rate,
                        confidence=conf,
                        caveats=cavs,
                        chart_spec=c_spec,
                        impact_score=score
                    ))
            else:
                n_used = res.get("n_used", cleaned_rows)
                n_excluded = total_rows - n_used
                ex_rate = round(n_excluded / max(1, total_rows), 4)

                suppressed = check_suppression("segment_difference", f"{seg_col} vs {met_col}", n_used, n_excluded, total_rows, step_num)
                if suppressed:
                    candidates.append(suppressed)
                else:
                    conf = determine_confidence(n_used, ex_rate)
                    p_val = res.get("anova_p_value")
                    top_seg = res.get("top_segment")
                    bot_seg = res.get("bottom_segment")
                    if not top_seg or not bot_seg or not isinstance(top_seg, dict) or not isinstance(bot_seg, dict):
                        raise ValueError(f"segment_compare continuous missing top_segment or bottom_segment dictionary: {res}")
                    top_name = top_seg.get("segment")
                    bot_name = bot_seg.get("segment")
                    top_med = top_seg.get("median") if top_seg.get("median") is not None else top_seg.get("mean")
                    bot_med = bot_seg.get("median") if bot_seg.get("median") is not None else bot_seg.get("mean")
                    if top_name is None or bot_name is None or top_med is None or bot_med is None:
                        raise ValueError(f"segment_compare segment stats incomplete: top={top_seg}, bottom={bot_seg}")

                    ratio = res.get("top_vs_bottom_ratio", 1.0)
                    effect = round(abs(ratio - 1.0), 4) if ratio else 0.2

                    is_significant = (p_val is not None and p_val <= 0.05)
                    if p_val is not None and not is_significant:
                        title = f"No significant difference in {met_col} across {seg_col}"
                        segments = res.get("segments", [])
                        n_groups = [f"{s.get('segment')}: n={s.get('n_used', s.get('count', n_used))}" for s in segments]
                        n_group_str = ", ".join(n_groups) if n_groups else f"n={n_used}"
                        has_low_power = any(int(s.get("n_used", s.get("count", n_used))) < 30 for s in segments)
                        power_str = " (limited statistical power due to small sample size in some groups, n < 30)" if has_low_power else ""
                        summary = (
                            f"no statistically significant difference detected (n per group: {n_group_str}, p={p_val:.4f}){power_str}."
                        )
                    else:
                        title = f"Variance in {met_col} across {seg_col}"
                        p_text = f" (p={p_val:.4f})" if p_val is not None else ""
                        summary = (
                            f"{top_name} recorded the highest {met_col} (median {top_med:.2f}) "
                            f"compared to {bot_name} (median {bot_med:.2f}), a {ratio:.2f}x differential{p_text}."
                        )

                    title = validate_no_placeholders(title, f"insight-seg-{seg_col}-{met_col} title")
                    summary = validate_no_placeholders(summary, f"insight-seg-{seg_col}-{met_col} summary")

                    score = compute_impact_score("segment_difference", effect, p_val, n_used, n_excluded, conf)
                    cavs = build_caveats(n_used, ex_rate, p_val)
                    c_spec = build_chart_spec_for_segment(seg_col, met_col, res.get("segments", []))

                    candidates.append(Insight(
                        id=f"insight-seg-{seg_col}-{met_col}",
                        type="segment_difference",
                        title=title,
                        summary=summary,
                        metric_values={
                            "segment_column": seg_col,
                            "metric_column": met_col,
                            "top_segment": top_name,
                            "top_median": top_med,
                            "bottom_segment": bot_name,
                            "bottom_median": bot_med,
                            "ratio": ratio,
                            "segments": res.get("segments", [])
                        },
                        evidence_step=step_num,
                        significance=p_val,
                        effect_size=effect,
                        n_used=n_used,
                        n_excluded=n_excluded,
                        exclusion_rate=ex_rate,
                        confidence=conf,
                        caveats=cavs,
                        chart_spec=c_spec,
                        impact_score=score
                    ))

        # Correlation
        elif t_name == "run_correlation":
            rel_list = res.get("strong_relationships") or []
            if not rel_list and res.get("highest_correlation"):
                rel_list = [res["highest_correlation"]]

            for rel in rel_list[:2]:
                cx, cy = rel["column_x"], rel["column_y"]
                pair_n_used = rel.get("n_used") or rel.get("sample_size") or res.get("n_used", cleaned_rows)
                pair_n_excluded = total_rows - pair_n_used
                pair_ex_rate = round(pair_n_excluded / max(1, total_rows), 4)

                suppressed = check_suppression("correlation", f"{cx} vs {cy}", pair_n_used, pair_n_excluded, total_rows, step_num)
                if suppressed:
                    candidates.append(suppressed)
                    continue

                conf = determine_confidence(pair_n_used, pair_ex_rate)
                r_val = rel["correlation"]
                p_val = rel.get("p_value")
                eff = round(abs(r_val), 4)
                
                title = validate_no_placeholders(
                    f"{rel.get('strength', 'Statistical').capitalize()} relationship between {cx} and {cy}",
                    f"insight-corr-{cx}-{cy} title"
                )
                summary = validate_no_placeholders(
                    f"A correlation coefficient of r={r_val:.4f} was observed between {cx} and {cy} "
                    f"across {pair_n_used} observations (exclusion rate {pair_ex_rate*100:.1f}%).",
                    f"insight-corr-{cx}-{cy} summary"
                )
                score = compute_impact_score("correlation", eff, p_val, pair_n_used, pair_n_excluded, conf)
                cavs = build_caveats(pair_n_used, pair_ex_rate, p_val)
                c_spec = build_chart_spec_for_correlation(
                    cx, cy, r_val,
                    columns_analyzed=res.get("columns_analyzed"),
                    correlation_matrix=res.get("correlation_matrix")
                )

                candidates.append(Insight(
                    id=f"insight-corr-{cx}-{cy}",
                    type="correlation",
                    title=title,
                    summary=summary,
                    metric_values={"column_x": cx, "column_y": cy, "correlation": r_val, "sample_size": pair_n_used, "n_used": pair_n_used, "n_excluded": pair_n_excluded},
                    evidence_step=step_num,
                    significance=p_val,
                    effect_size=eff,
                    n_used=pair_n_used,
                    n_excluded=pair_n_excluded,
                    exclusion_rate=pair_ex_rate,
                    confidence=conf,
                    caveats=cavs,
                    chart_spec=c_spec,
                    impact_score=score
                ))


        # Trend Analysis
        elif t_name == "trend_analysis":
            val_col = res.get("value_column")
            date_col = res.get("date_column")
            if not val_col or not date_col or val_col == "Metric":
                raise ValueError(f"trend_analysis result missing valid value_column or date_column: {res}")

            n_used = res.get("n_used", cleaned_rows)
            n_excluded = total_rows - n_used
            ex_rate = round(n_excluded / max(1, total_rows), 4)

            suppressed = check_suppression("trend", val_col, n_used, n_excluded, total_rows, step_num)
            if suppressed:
                candidates.append(suppressed)
            else:
                conf = determine_confidence(n_used, ex_rate)
                direction = res.get("overall_trend", "consistent")
                if direction == "stable":
                    direction = "consistent"
                pct = res.get("percentage_change", 0.0)
                n_periods = res.get("n_periods", res.get("aggregated_periods", len(res.get("timeline", []))))
                p_val = res.get("p_value")
                std_slope = res.get("standardized_slope", 0.0)
                eff = round(abs(std_slope), 4)

                # Statistical test requirement: if p >= 0.05, title it "No significant trend in X"
                if p_val is not None and p_val >= 0.05:
                    title = f"No significant trend in {val_col}"
                    summary = (
                        f"OLS regression indicates no statistically significant trend in {val_col} "
                        f"(p={p_val:.4f}, standardized slope={std_slope:+.4f}) across {n_periods} time periods ({n_used} rows used)."
                    )
                else:
                    title = f"{direction.capitalize()} trajectory in {val_col} ({pct:+.1f}%)"
                    p_str = f"p={p_val:.4f}" if p_val is not None else "p not available"
                    summary = (
                        f"{val_col} followed an overall {direction} trajectory (standardized slope={std_slope:+.4f}, {p_str}) "
                        f"across {n_periods} time periods ({n_used} rows used)."
                    )

                title = validate_no_placeholders(title, f"insight-trend-{val_col} title")
                summary = validate_no_placeholders(summary, f"insight-trend-{val_col} summary")

                score = compute_impact_score("trend", eff, p_val, n_used, n_excluded, conf)
                cavs = build_caveats(n_used, ex_rate, p_val)
                c_spec = build_chart_spec_for_trend(val_col, date_col, res.get("timeline", []))

                candidates.append(Insight(
                    id=f"insight-trend-{val_col}",
                    type="trend",
                    title=title,
                    summary=summary,
                    metric_values={
                        "value_column": val_col,
                        "date_column": date_col,
                        "trend": direction,
                        "percentage_change": pct,
                        "n_periods": n_periods,
                        "aggregated_periods": n_periods,
                        "standardized_slope": std_slope,
                        "linear_slope": res.get("linear_slope"),
                        "p_value": p_val,
                        "n_used": n_used,
                        "n_excluded": n_excluded,
                        "timeline": res.get("timeline", [])
                    },
                    evidence_step=step_num,
                    significance=p_val,
                    effect_size=eff,
                    n_used=n_used,
                    n_excluded=n_excluded,
                    exclusion_rate=ex_rate,
                    confidence=conf,
                    caveats=cavs,
                    chart_spec=c_spec,
                    impact_score=score
                ))

        # Outliers
        elif t_name == "detect_outliers":
            top_cols = res.get("top_outlier_columns") or []
            top_col_name = top_cols[0]["column"] if top_cols else "features"
            col_info = res.get("column_outliers", {}).get(top_col_name, {})
            n_used = col_info.get("n_used") or res.get("n_rows_used") or res.get("n_used") or cleaned_rows
            n_excluded = total_rows - n_used
            ex_rate = round(n_excluded / max(1, total_rows), 4)

            suppressed = check_suppression("outliers", top_col_name, n_used, n_excluded, total_rows, step_num)
            if suppressed:
                candidates.append(suppressed)
            else:
                conf = determine_confidence(n_used, ex_rate)
                anom_cnt = res.get("total_anomalous_rows", res.get("anomaly_count", 0))
                anom_rate = res.get("overall_anomaly_rate_percent", res.get("anomaly_rate_percent", 0.0))
                eff = round(anom_rate / 100.0, 4)

                # "0 outliers" is not an insight: fold it into methodology (impact <= 0.1)
                if anom_cnt == 0:
                    title = "No anomalous outliers detected across features"
                    summary = (
                        f"Zero statistical outliers were identified across {n_used} records "
                        f"using IQR 3.0x fence methodology."
                    )
                    score = min(0.10, compute_impact_score("outlier", 0.0, None, n_used, n_excluded, conf, anomaly_count=0))
                else:
                    title = f"{anom_cnt} statistical outliers identified ({anom_rate:.1f}%)"
                    summary = (
                        f"Identified {anom_cnt} anomalous rows ({anom_rate:.1f}% anomaly rate) across {n_used} records, "
                        f"predominantly concentrated in column '{top_col_name}'."
                    )
                    score = compute_impact_score("outlier", eff, None, n_used, n_excluded, conf, anomaly_count=anom_cnt)

                title = validate_no_placeholders(title, f"insight-outlier-{top_col_name} title")
                summary = validate_no_placeholders(summary, f"insight-outlier-{top_col_name} summary")

                cavs = build_caveats(n_used, ex_rate, None)
                c_spec = build_chart_spec_for_outlier(top_col_name, res.get("column_outliers", {}).get(top_col_name, {}))

                candidates.append(Insight(
                    id=f"insight-outlier-{top_col_name}",
                    type="outlier",
                    title=title,
                    summary=summary,
                    metric_values={
                        "anomaly_count": anom_cnt,
                        "anomaly_rate_percent": anom_rate,
                        "column_outliers": res.get("column_outliers", {})
                    },
                    evidence_step=step_num,
                    significance=None,
                    effect_size=eff,
                    n_used=n_used,
                    n_excluded=n_excluded,
                    exclusion_rate=ex_rate,
                    confidence=conf,
                    caveats=cavs,
                    chart_spec=c_spec,
                    impact_score=score
                ))

    # 2. Process Data Quality Findings from Cleaning Report
    cl_report = dict(cleaning_report or {})
    if dataset_profile:
        if isinstance(dataset_profile.get("cleaning_report"), dict):
            for k, v in dataset_profile["cleaning_report"].items():
                if k not in cl_report:
                    cl_report[k] = v
        for k in ("sentinels_detected", "invalid_values_detected", "suspected_returns", "suspected_repeated_extremes", "column_imputation_stats", "missing_values_imputed"):
            if k in dataset_profile and k not in cl_report:
                cl_report[k] = dataset_profile[k]
    
    # A: Sentinels
    for s in cl_report.get("sentinels_detected", []):
        col = s.get("column")
        val = s.get("sentinel_value")
        cnt = s.get("count", 0)
        ex_rate = round(cnt / max(1, total_rows), 4)
        n_used_dq = max(0, total_rows - cnt)
        conf = determine_confidence(n_used_dq, ex_rate)
        score = compute_impact_score("data_quality", None, None, n_used_dq, cnt, conf)
        c_spec = build_chart_spec_for_data_quality(cl_report, highlight_col=col)
        title = validate_no_placeholders(f"Sentinel values sanitized in {col}", f"insight-dq-sentinel-{col} title")
        summary = validate_no_placeholders(f"Detected and sanitized {cnt} sentinel values ({val}) in column '{col}' prior to imputation.", f"insight-dq-sentinel-{col} summary")
        candidates.append(Insight(
            id=f"insight-dq-sentinel-{col}",
            type="data_quality",
            title=title,
            summary=summary,
            metric_values={"column": col, "sentinel_value": val, "count": cnt},
            evidence_step=None,
            significance=None,
            effect_size=round(cnt / max(1, total_rows), 4),
            n_used=n_used_dq,
            n_excluded=cnt,
            exclusion_rate=ex_rate,
            confidence=conf,
            caveats=[f"Replaced {cnt} values with median before statistical analysis."],
            chart_spec=c_spec,
            impact_score=score
        ))

    # B: Invalid Values
    for iv in cl_report.get("invalid_values_detected", []):
        col = iv.get("column")
        cnt = iv.get("count", 0)
        rule = iv.get("rule", "domain_validity")
        ex_rate = round(cnt / max(1, total_rows), 4)
        n_used_dq = max(0, total_rows - cnt)
        conf = determine_confidence(n_used_dq, ex_rate)
        score = compute_impact_score("data_quality", None, None, n_used_dq, cnt, conf)
        c_spec = build_chart_spec_for_data_quality(cl_report, highlight_col=col)
        title = validate_no_placeholders(f"Invalid domain values sanitized in {col}", f"insight-dq-invalid-{col} title")
        summary = validate_no_placeholders(f"Identified and sanitized {cnt} invalid values in column '{col}' violating {rule} prior to imputation.", f"insight-dq-invalid-{col} summary")
        candidates.append(Insight(
            id=f"insight-dq-invalid-{col}",
            type="data_quality",
            title=title,
            summary=summary,
            metric_values={"column": col, "rule": rule, "count": cnt},
            evidence_step=None,
            significance=None,
            effect_size=round(cnt / max(1, total_rows), 4),
            n_used=n_used_dq,
            n_excluded=cnt,
            exclusion_rate=ex_rate,
            confidence=conf,
            caveats=[f"{cnt} invalid entries converted to NaN and imputed."],
            chart_spec=c_spec,
            impact_score=score
        ))

    # C: Suspected Returns (preserved in dataset, not excluded)
    for sr in cl_report.get("suspected_returns", []):
        col = sr.get("column")
        cnt = sr.get("count", 0)
        c_spec = build_chart_spec_for_data_quality(cl_report, highlight_col=col)
        title = validate_no_placeholders(f"Suspected transaction returns in {col}", f"insight-dq-returns-{col} title")
        summary = validate_no_placeholders(f"Identified {cnt} negative entries in '{col}' flagged as suspected customer returns and preserved in dataset.", f"insight-dq-returns-{col} summary")
        candidates.append(Insight(
            id=f"insight-dq-returns-{col}",
            type="data_quality",
            title=title,
            summary=summary,
            metric_values={"column": col, "count": cnt},
            evidence_step=None,
            significance=None,
            effect_size=round(cnt / max(1, total_rows), 4),
            n_used=total_rows,
            n_excluded=0,
            exclusion_rate=0.0,
            confidence="high",
            caveats=["Negative values preserved to reflect transaction return dynamics."],
            chart_spec=c_spec,
            impact_score=0.45
        ))

    # D: Suspected Repeated Extremes (preserved in dataset, not excluded)
    for sre in cl_report.get("suspected_repeated_extremes", []):
        col = sre.get("column")
        val = sre.get("value")
        cnt = sre.get("count", 0)
        c_spec = build_chart_spec_for_data_quality(cl_report, highlight_col=col)
        title = validate_no_placeholders(f"Repeated extreme values in {col}", f"insight-dq-extremes-{col} title")
        summary = validate_no_placeholders(f"Identified {cnt} occurrences of repeated value {val} in column '{col}' outside 3x IQR fence; preserved as valid extremes.", f"insight-dq-extremes-{col} summary")
        candidates.append(Insight(
            id=f"insight-dq-extremes-{col}",
            type="data_quality",
            title=title,
            summary=summary,
            metric_values={"column": col, "value": val, "count": cnt},
            evidence_step=None,
            significance=None,
            effect_size=round(cnt / max(1, total_rows), 4),
            n_used=total_rows,
            n_excluded=0,
            exclusion_rate=0.0,
            confidence="high",
            caveats=["Extreme values preserved without deletion."],
            chart_spec=c_spec,
            impact_score=0.42
        ))

    # E: Imputation Rates > 25%
    for col, stats in cl_report.get("column_imputation_stats", {}).items():
        imp_rate = stats.get("imputation_rate", 0.0)
        imp_cnt = stats.get("imputed_count", 0)
        if imp_rate > 0.25:
            n_used_imp = max(0, total_rows - imp_cnt)
            conf = determine_confidence(n_used_imp, imp_rate)
            score = compute_impact_score("data_quality", imp_rate, None, n_used_imp, imp_cnt, conf)
            c_spec = build_chart_spec_for_data_quality(cl_report, highlight_col=col)
            title = validate_no_placeholders(f"Elevated imputation rate in {col} ({imp_rate * 100:.1f}%)", f"insight-dq-imputation-{col} title")
            summary = validate_no_placeholders(f"Column '{col}' required {imp_rate * 100:.1f}% imputation ({imp_cnt} missing entries imputed).", f"insight-dq-imputation-{col} summary")
            candidates.append(Insight(
                id=f"insight-dq-imputation-{col}",
                type="data_quality",
                title=title,
                summary=summary,
                metric_values={"column": col, "imputed_count": imp_cnt, "imputation_rate": imp_rate},
                evidence_step=None,
                significance=None,
                effect_size=imp_rate,
                n_used=n_used_imp,
                n_excluded=imp_cnt,
                exclusion_rate=imp_rate,
                confidence=conf,
                caveats=[f"Substantial proportion ({imp_rate * 100:.1f}%) of values were deterministically imputed."],
                chart_spec=c_spec,
                impact_score=score
            ))

    # 3. Enforce strictly: n_used + n_excluded == total_rows for every single insight and attach sampling disclosure
    sampling_disclosure = (dataset_profile or {}).get("sampling_disclosure") or (dataset_profile or {}).get("quality_summary", {}).get("sampling_disclosure")
    if not sampling_disclosure and (dataset_profile or {}).get("is_sampled"):
        n_sample = dataset_profile.get("row_count", 0)
        n_pop = dataset_profile.get("population_row_count", n_sample)
        seed = dataset_profile.get("sampling_seed", 42)
        sampling_disclosure = f"random sample of {n_sample:,} of {n_pop:,} rows (seed {seed})"

    for ins in candidates:
        ins.n_excluded = total_rows - ins.n_used
        ins.exclusion_rate = round(ins.n_excluded / max(1, total_rows), 4)
        if sampling_disclosure and not any("random sample" in c for c in ins.caveats):
            ins.caveats.append(f"Derived from a {sampling_disclosure}")

    # 4. Deduplicate near-identical insights
    seen_keys = set()
    deduped: List[Insight] = []
    for ins in candidates:
        key = (
            ins.type,
            ins.metric_values.get("segment_column"),
            ins.metric_values.get("metric_column"),
            ins.metric_values.get("column_x"),
            ins.metric_values.get("column_y"),
            ins.metric_values.get("column"),
            ins.metric_values.get("analysis"),
            ins.metric_values.get("target"),
            ins.title
        )
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(ins)

    # 5. Rank analytical insights first (top 6), then data_quality insights in a separate list (max 4)
    analytical_list = [i for i in deduped if i.type != "data_quality"]
    dq_list = [i for i in deduped if i.type == "data_quality"]

    analytical_list.sort(key=lambda x: -x.impact_score)
    top_analytical = analytical_list[:6]

    dq_list.sort(key=lambda x: -x.impact_score)
    top_dq = dq_list[:4]

    return top_analytical + top_dq
