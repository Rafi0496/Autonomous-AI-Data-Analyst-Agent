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
from typing import Any, Dict, List, Optional
import uuid
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
    confidence: str
) -> float:
    """Compute deterministic impact score between 0.0 and 1.0."""
    total = n_used + n_excluded
    coverage = (n_used / total) if total > 0 else 1.0

    if insight_type == "data_quality":
        severity = min(1.0, (n_excluded / max(1, total)) * 1.5)
        return round(max(0.1, min(0.95, 0.35 + 0.65 * severity)), 4)

    base_effect = min(1.0, abs(effect_size)) if effect_size is not None else 0.5
    sig_mult = 1.0 if (significance is None or significance <= 0.05) else 0.4
    conf_mult = {"high": 1.0, "medium": 0.8, "low": 0.6}.get(confidence, 0.8)

    raw_score = (base_effect * 0.40) + (sig_mult * 0.30) + (coverage * 0.15) + (conf_mult * 0.15)
    if significance is not None and significance > 0.05:
        raw_score *= 0.55
    return round(max(0.05, min(1.0, raw_score)), 4)

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
    total_rows = dataset_profile.get("row_count", 100) if dataset_profile else 100
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
        t_name = res.get("tool", "")
        step_num = find_step(t_name)

        # Segment Difference
        if t_name == "segment_compare":
            seg_col = res.get("segment_column", "Segment")
            met_col = res.get("metric_column", "Metric")
            n_used = res.get("n_used", cleaned_rows)
            n_excluded = res.get("n_excluded_imputed", 0)
            ex_rate = round(n_excluded / max(1, n_used + n_excluded), 4)
            conf = determine_confidence(n_used, ex_rate)
            p_val = res.get("anova_p_value")
            top_seg = res.get("top_segment", {})
            bot_seg = res.get("bottom_segment", {})
            ratio = res.get("top_vs_bottom_ratio", 1.0)
            effect = round(abs(ratio - 1.0), 4) if ratio else 0.2

            is_significant = (p_val is not None and p_val <= 0.05)
            if p_val is not None and not is_significant:
                title = f"No significant difference in {met_col} across {seg_col}"
                summary = (
                    f"ANOVA test shows no statistically significant variance in {met_col} "
                    f"across {seg_col} categories (p={p_val:.4f}, n_used={n_used}). "
                    f"{top_seg.get('segment')} recorded {top_seg.get('median')} vs {bot_seg.get('median')} for {bot_seg.get('segment')}."
                )
            else:
                title = f"Variance in {met_col} across {seg_col}"
                p_text = f" (p={p_val:.4f})" if p_val is not None else ""
                summary = (
                    f"{top_seg.get('segment')} recorded the highest {met_col} (median {top_seg.get('median')}) "
                    f"compared to {bot_seg.get('segment')} (median {bot_seg.get('median')}), a {ratio:.2f}x differential{p_text}."
                )

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
                    "top_segment": top_seg.get("segment"),
                    "top_median": top_seg.get("median"),
                    "bottom_segment": bot_seg.get("segment"),
                    "bottom_median": bot_seg.get("median"),
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
            n_used = res.get("n_used", cleaned_rows)
            n_excluded = res.get("n_excluded_imputed", 0)
            ex_rate = round(n_excluded / max(1, n_used + n_excluded), 4)
            conf = determine_confidence(n_used, ex_rate)

            rel_list = res.get("strong_relationships") or []
            if not rel_list and res.get("highest_correlation"):
                rel_list = [res["highest_correlation"]]

            for rel in rel_list[:2]:
                cx, cy = rel["column_x"], rel["column_y"]
                r_val = rel["correlation"]
                p_val = rel.get("p_value")
                eff = round(abs(r_val), 4)
                is_sig = (p_val is None or p_val <= 0.05)
                
                title = f"{rel.get('strength', 'Statistical').capitalize()} relationship between {cx} and {cy}"
                summary = (
                    f"A correlation coefficient of r={r_val:.4f} was observed between {cx} and {cy} "
                    f"across {n_used} observations (exclusion rate {ex_rate*100:.1f}%)."
                )
                score = compute_impact_score("correlation", eff, p_val, n_used, n_excluded, conf)
                cavs = build_caveats(n_used, ex_rate, p_val)
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
                    metric_values={"column_x": cx, "column_y": cy, "correlation": r_val, "sample_size": n_used},
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

        # Trend Analysis
        elif t_name == "trend_analysis":
            n_used = res.get("n_used", cleaned_rows)
            n_excluded = res.get("n_excluded_imputed", 0)
            ex_rate = round(n_excluded / max(1, n_used + n_excluded), 4)
            conf = determine_confidence(n_used, ex_rate)
            direction = res.get("overall_trend", "stable")
            pct = res.get("percentage_change", 0.0)
            eff = round(abs(pct) / 100.0, 4)
            val_col = res.get("value_column", "Metric")
            date_col = res.get("date_column", "Date")
            peak = res.get("peak_period", {})

            title = f"{direction.capitalize()} trajectory in {val_col} ({pct:+.1f}%)"
            summary = (
                f"{val_col} followed an overall {direction} trajectory with {pct:+.1f}% change "
                f"across {n_used} time intervals, reaching peak {peak.get('value')} on {peak.get('date')}."
            )
            score = compute_impact_score("trend", eff, None, n_used, n_excluded, conf)
            cavs = build_caveats(n_used, ex_rate, None)
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
                    "timeline": res.get("timeline", [])
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

        # Outliers
        elif t_name == "detect_outliers":
            n_used = res.get("n_rows_used", cleaned_rows)
            n_excluded = res.get("n_excluded_imputed", 0)
            ex_rate = round(n_excluded / max(1, n_used + n_excluded), 4)
            conf = determine_confidence(n_used, ex_rate)
            anom_cnt = res.get("total_anomalous_rows", res.get("anomaly_count", 0))
            anom_rate = res.get("overall_anomaly_rate_percent", res.get("anomaly_rate_percent", 0.0))
            eff = round(anom_rate / 100.0, 4)
            top_cols = res.get("top_outlier_columns") or []
            top_col_name = top_cols[0]["column"] if top_cols else "features"

            title = f"{anom_cnt} statistical outliers identified ({anom_rate:.1f}%)"
            summary = (
                f"Identified {anom_cnt} anomalous rows ({anom_rate:.1f}% anomaly rate) across {n_used} records, "
                f"predominantly concentrated in column '{top_col_name}'."
            )
            score = compute_impact_score("outlier", eff, None, n_used, n_excluded, conf)
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
        ex_rate = round(cnt / max(1, cleaned_rows + cnt), 4)
        conf = determine_confidence(cleaned_rows, ex_rate)
        score = compute_impact_score("data_quality", None, None, cleaned_rows, cnt, conf)
        c_spec = build_chart_spec_for_data_quality(cl_report, highlight_col=col)
        candidates.append(Insight(
            id=f"insight-dq-sentinel-{col}",
            type="data_quality",
            title=f"Placeholder sentinel values sanitized in {col}",
            summary=f"Detected and sanitized {cnt} placeholder sentinel values ({val}) in column '{col}' prior to imputation.",
            metric_values={"column": col, "sentinel_value": val, "count": cnt},
            evidence_step=None,
            significance=None,
            effect_size=round(cnt / max(1, total_rows), 4),
            n_used=cleaned_rows,
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
        ex_rate = round(cnt / max(1, cleaned_rows + cnt), 4)
        conf = determine_confidence(cleaned_rows, ex_rate)
        score = compute_impact_score("data_quality", None, None, cleaned_rows, cnt, conf)
        c_spec = build_chart_spec_for_data_quality(cl_report, highlight_col=col)
        candidates.append(Insight(
            id=f"insight-dq-invalid-{col}",
            type="data_quality",
            title=f"Invalid domain values sanitized in {col}",
            summary=f"Identified and sanitized {cnt} invalid values in column '{col}' violating {rule} prior to imputation.",
            metric_values={"column": col, "rule": rule, "count": cnt},
            evidence_step=None,
            significance=None,
            effect_size=round(cnt / max(1, total_rows), 4),
            n_used=cleaned_rows,
            n_excluded=cnt,
            exclusion_rate=ex_rate,
            confidence=conf,
            caveats=[f"{cnt} invalid entries converted to NaN and imputed."],
            chart_spec=c_spec,
            impact_score=score
        ))

    # C: Suspected Returns
    for sr in cl_report.get("suspected_returns", []):
        col = sr.get("column")
        cnt = sr.get("count", 0)
        c_spec = build_chart_spec_for_data_quality(cl_report, highlight_col=col)
        candidates.append(Insight(
            id=f"insight-dq-returns-{col}",
            type="data_quality",
            title=f"Suspected transaction returns in {col}",
            summary=f"Identified {cnt} negative entries in '{col}' flagged as suspected customer returns and preserved in dataset.",
            metric_values={"column": col, "count": cnt},
            evidence_step=None,
            significance=None,
            effect_size=round(cnt / max(1, total_rows), 4),
            n_used=cleaned_rows,
            n_excluded=0,
            exclusion_rate=0.0,
            confidence="high",
            caveats=["Negative values preserved to reflect transaction return dynamics."],
            chart_spec=c_spec,
            impact_score=0.45
        ))

    # D: Suspected Repeated Extremes
    for sre in cl_report.get("suspected_repeated_extremes", []):
        col = sre.get("column")
        val = sre.get("value")
        cnt = sre.get("count", 0)
        c_spec = build_chart_spec_for_data_quality(cl_report, highlight_col=col)
        candidates.append(Insight(
            id=f"insight-dq-extremes-{col}",
            type="data_quality",
            title=f"Repeated extreme values in {col}",
            summary=f"Identified {cnt} occurrences of repeated value {val} in column '{col}' outside 3x IQR fence; preserved as valid extremes.",
            metric_values={"column": col, "value": val, "count": cnt},
            evidence_step=None,
            significance=None,
            effect_size=round(cnt / max(1, total_rows), 4),
            n_used=cleaned_rows,
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
            conf = determine_confidence(cleaned_rows, imp_rate)
            score = compute_impact_score("data_quality", imp_rate, None, cleaned_rows, imp_cnt, conf)
            c_spec = build_chart_spec_for_data_quality(cl_report, highlight_col=col)
            candidates.append(Insight(
                id=f"insight-dq-imputation-{col}",
                type="data_quality",
                title=f"Elevated imputation rate in {col} ({imp_rate * 100:.1f}%)",
                summary=f"Column '{col}' required {imp_rate * 100:.1f}% imputation ({imp_cnt} missing entries imputed).",
                metric_values={"column": col, "imputed_count": imp_cnt, "imputation_rate": imp_rate},
                evidence_step=None,
                significance=None,
                effect_size=imp_rate,
                n_used=cleaned_rows - imp_cnt,
                n_excluded=imp_cnt,
                exclusion_rate=imp_rate,
                confidence=conf,
                caveats=[f"Substantial proportion ({imp_rate * 100:.1f}%) of values were deterministically imputed."],
                chart_spec=c_spec,
                impact_score=score
            ))

    # 3. Deduplicate near-identical insights
    seen_keys = set()
    deduped: List[Insight] = []
    for ins in candidates:
        key = (ins.type, ins.metric_values.get("segment_column"), ins.metric_values.get("metric_column"),
               ins.metric_values.get("column_x"), ins.metric_values.get("column_y"), ins.metric_values.get("column"))
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(ins)

    # 4. Sort by impact_score descending and cap at 8
    deduped.sort(key=lambda x: -x.impact_score)
    return deduped[:8]
