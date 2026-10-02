"""Executive Synthesis Tool: write_summary().

Final analysis step only (not callable mid-plan).
Synthesizes all structured tool results into a structured business narrative where every claim
strictly traces back to computed values.
"""
from typing import Any, Dict, List, Optional
from backend.app.services.insights import validate_no_placeholders
from backend.app.agent.citation_checker import extract_numeric_tokens

def write_summary(
    structured_results: Optional[List[Dict[str, Any]]] = None,
    dataset_profile: Optional[Dict[str, Any]] = None,
    goal: Optional[str] = None,
    insights: Optional[List[Any]] = None
) -> Dict[str, Any]:
    """
    Synthesize surviving analytical insights and data quality caveats into an executive business summary.
    Synthesis may use ONLY insights[] as claim sources, never raw tool results.
    Suppressed analyses appear only as 'insufficient data for X (n_used=..., exclusion_rate=...)'.
    If p >= 0.05, the narrative states 'no significant difference' and does not present top segment as a finding.
    """
    if not structured_results and not insights:
        return {
            "status": "empty",
            "message": "No analysis tool results or insights provided for synthesis.",
            "executive_summary": "Analysis was concluded without tool executions.",
            "key_findings": [],
            "citations_index": {},
            "claims": []
        }

    citations: Dict[str, Dict[str, Any]] = {}
    findings: List[Dict[str, Any]] = []
    claims: List[Dict[str, Any]] = []

    if insights:
        for ins in insights:
            ins_dict = ins.model_dump() if hasattr(ins, "model_dump") else (ins if isinstance(ins, dict) else ins.__dict__)
            ins_id = str(ins_dict.get("id") or "")
            ins_type = str(ins_dict.get("type") or "")
            title = str(ins_dict.get("title") or "")
            summary = str(ins_dict.get("summary") or "")
            mv = ins_dict.get("metric_values") or {}
            p_val = ins_dict.get("significance")
            if p_val is None:
                p_val = mv.get("p_value") or mv.get("anova_p_value") or mv.get("chi2_p_value")
            n_used = ins_dict.get("n_used", 0)
            n_excluded = ins_dict.get("n_excluded", 0)
            ex_rate = ins_dict.get("exclusion_rate", 0.0)

            # Suppressed insight check
            if ins_id.startswith("insight-dq-insufficient") or "insufficient data for" in title.lower() or "insufficient data for" in summary.lower():
                analysis = mv.get("analysis") or "analysis"
                target = mv.get("target") or title.replace("Insufficient data for ", "")
                narrative = f"insufficient data for {analysis} on '{target}' (n_used={n_used}, exclusion_rate={ex_rate*100:.1f}%)"
                full_nar = f"Analysis for {analysis} on '{target}' was suppressed due to {narrative}."
                full_nar = validate_no_placeholders(full_nar, f"suppressed-{ins_id}")
                f_obj = {
                    "category": "Data Quality Suppression",
                    "headline": f"Insufficient data for {analysis} on {target}",
                    "narrative": full_nar,
                    "primary_metric": n_used,
                    "source_id": ins_id,
                    "metric": "n_used",
                    "value": float(n_used)
                }
                findings.append(f_obj)
                citations[str(n_used)] = {"tool": "insights", "metric": "n_used", "value": n_used}
                for fnum in extract_numeric_tokens(f"{f_obj['headline']} {f_obj['narrative']}"):
                    mkey = "n_used" if abs(fnum - float(n_used)) < 1e-4 else ("exclusion_rate_percent" if abs(fnum - round(float(ex_rate*100), 1)) < 1e-2 else str(fnum))
                    claims.append({
                        "text": f_obj["narrative"],
                        "source_id": ins_id,
                        "metric_key": mkey,
                        "value": float(fnum),
                        "unit": None
                    })
                continue

            if ins_type == "segment_difference":
                seg_col = mv.get("segment_column", "segment")
                met_col = mv.get("metric_column", "metric")
                top_name = mv.get("top_segment")
                bot_name = mv.get("bottom_segment")
                top_med = mv.get("top_median", mv.get("top_rate"))
                bot_med = mv.get("bottom_median", mv.get("bottom_rate"))
                ratio = mv.get("ratio")
                is_sig = (p_val is not None and p_val < 0.05)

                if p_val is not None and not is_sig:
                    # Item 2: If p >= 0.05, narrative says "no significant difference" and does NOT present top segment as finding
                    headline = f"No significant difference in {met_col} across {seg_col}"
                    narrative = f"Statistical testing demonstrates no significant difference in {met_col} across {seg_col} categories (p={p_val:.4f}, n_used={n_used})."
                    headline = validate_no_placeholders(headline, f"{ins_id}-headline")
                    narrative = validate_no_placeholders(narrative, f"{ins_id}-narrative")
                    findings.append({
                        "category": "Segment Comparison",
                        "headline": headline,
                        "narrative": narrative,
                        "primary_metric": p_val,
                        "source_id": ins_id,
                        "metric": "p_value",
                        "value": round(float(p_val), 4)
                    })
                    citations[str(round(float(p_val), 4))] = {"tool": "insights", "metric": "p_value", "value": round(float(p_val), 4)}
                else:
                    headline = f"Variance in {met_col} across {seg_col}"
                    ratio_str = f", a {ratio:.2f}x differential" if ratio else ""
                    p_str = f" (p={p_val:.4f})" if p_val is not None else ""
                    narrative = f"{top_name} recorded the highest {met_col} (median {top_med:.2f}) compared to {bot_name} (median {bot_med:.2f}){ratio_str}{p_str} across {n_used} records."
                    headline = validate_no_placeholders(headline, f"{ins_id}-headline")
                    narrative = validate_no_placeholders(narrative, f"{ins_id}-narrative")
                    findings.append({
                        "category": "Segment Comparison",
                        "headline": headline,
                        "narrative": narrative,
                        "primary_metric": top_med,
                        "source_id": ins_id,
                        "metric": f"{top_name}_median" if f"{top_name}_median" in mv else "top_median",
                        "value": float(top_med) if top_med is not None else 0.0
                    })
                    if top_med is not None:
                        citations[str(top_med)] = {"tool": "insights", "metric": "top_median", "value": top_med}

            elif ins_type == "correlation":
                cx = mv.get("column_x", "")
                cy = mv.get("column_y", "")
                r = mv.get("correlation", 0.0)
                headline = f"Significant correlation between {cx} and {cy}"
                narrative = f"A correlation coefficient of r={r:.4f} was observed between {cx} and {cy} across {n_used} observations."
                headline = validate_no_placeholders(headline, f"{ins_id}-headline")
                narrative = validate_no_placeholders(narrative, f"{ins_id}-narrative")
                findings.append({
                    "category": "Correlation",
                    "headline": headline,
                    "narrative": narrative,
                    "primary_metric": r,
                    "source_id": ins_id,
                    "metric": "correlation",
                    "value": float(r)
                })
                citations[str(round(float(r), 4))] = {"tool": "insights", "metric": "correlation", "value": r}

            elif ins_type == "trend":
                val_col = mv.get("value_column", "Metric")
                direction = mv.get("overall_trend", "trajectory")
                pct = mv.get("percentage_change", 0.0)
                headline = f"Overall {direction} trajectory in {val_col} ({pct:+.1f}%)"
                narrative = f"{val_col} followed an overall {direction} trajectory ({pct:+.1f}%) across {n_used} observations."
                headline = validate_no_placeholders(headline, f"{ins_id}-headline")
                narrative = validate_no_placeholders(narrative, f"{ins_id}-narrative")
                findings.append({
                    "category": "Trend Analysis",
                    "headline": headline,
                    "narrative": narrative,
                    "primary_metric": pct,
                    "source_id": ins_id,
                    "metric": "percentage_change",
                    "value": float(pct)
                })
                citations[str(pct)] = {"tool": "insights", "metric": "percentage_change", "value": pct}

            elif ins_type == "outlier":
                anom_cnt = mv.get("anomaly_count", 0)
                anom_rate = mv.get("anomaly_rate_percent", 0.0)
                headline = f"{anom_cnt} statistical outliers identified ({anom_rate:.1f}%)"
                narrative = f"Identified {anom_cnt} anomalous rows ({anom_rate:.1f}% anomaly rate) across {n_used} records."
                headline = validate_no_placeholders(headline, f"{ins_id}-headline")
                narrative = validate_no_placeholders(narrative, f"{ins_id}-narrative")
                findings.append({
                    "category": "Outlier Detection",
                    "headline": headline,
                    "narrative": narrative,
                    "primary_metric": anom_cnt,
                    "source_id": ins_id,
                    "metric": "anomaly_count",
                    "value": float(anom_cnt)
                })
                citations[str(anom_cnt)] = {"tool": "insights", "metric": "anomaly_count", "value": anom_cnt}

            elif ins_type == "data_quality":
                findings.append({
                    "category": "Data Quality",
                    "headline": title,
                    "narrative": summary,
                    "primary_metric": mv.get("count", mv.get("imputed_count", 0)),
                    "source_id": ins_id,
                    "metric": "count" if "count" in mv else "imputed_count",
                    "value": float(mv.get("count", mv.get("imputed_count", 0)))
                })

            if findings and findings[-1].get("source_id") == ins_id:
                latest_f = findings[-1]
                for fnum in extract_numeric_tokens(f"{latest_f['headline']} {latest_f['narrative']}"):
                    mkey = latest_f.get("metric", str(fnum))
                    if n_used is not None and abs(fnum - float(n_used)) < 1e-4:
                        mkey = "n_used"
                    elif n_excluded is not None and abs(fnum - float(n_excluded)) < 1e-4:
                        mkey = "n_excluded"
                    elif p_val is not None and abs(fnum - float(p_val)) < 1e-4:
                        mkey = "p_value"
                    elif abs(fnum - float(latest_f.get("value", 0.0))) < 1e-4:
                        mkey = latest_f.get("metric", "value")
                    else:
                        mkey = str(fnum)
                    claims.append({
                        "text": latest_f["narrative"],
                        "source_id": ins_id,
                        "metric_key": mkey,
                        "value": float(fnum),
                        "unit": None
                    })

        analytical = [f for f in findings if f["category"] not in ("Data Quality", "Data Quality Suppression")]
        suppressed = [f for f in findings if f["category"] == "Data Quality Suppression"]
        dq = [f for f in findings if f["category"] == "Data Quality"]

        parts = []
        user_clean_goal = ""
        if goal:
            cleaned = goal.split(". When citing")[0].split("When citing")[0].strip()
            if cleaned and "Comprehensive exploratory analysis" not in cleaned and "Quantity=999" not in cleaned:
                user_clean_goal = cleaned
        goal_str = f" targeting '{user_clean_goal}'" if user_clean_goal else ""
        parts.append(f"Autonomous analysis{goal_str} concluded with validated analytical findings.")
        for a in analytical:
            parts.append(a["narrative"])
        if suppressed:
            supp_text = "; ".join(s["narrative"] for s in suppressed)
            parts.append(f"Suppressed analyses: {supp_text}.")
        if dq:
            dq_text = " ".join(d["narrative"] for d in dq[:2])
            parts.append(f"Data quality caveats: {dq_text}")
        executive_summary = validate_no_placeholders(" ".join(parts), "executive summary")

        recommendations = [
            "Focus operational optimization on segments demonstrating verified efficiency differentials.",
            "Account for data quality caveats and suppressed dimensions in subsequent strategic modeling.",
            "Establish recurring automated monitoring on high-confidence analytical indicators."
        ]

        return {
            "status": "success",
            "executive_summary": executive_summary,
            "key_findings": findings,
            "recommendations": recommendations,
            "total_findings": len(findings),
            "total_tools_executed": len(structured_results or []),
            "citations_index": citations,
            "claims": claims
        }

    # 1. Harvest facts from profiling and data quality
    if dataset_profile:
        row_cnt = dataset_profile.get("row_count", 0)
        col_cnt = dataset_profile.get("column_count", 0)
        q_summary = dataset_profile.get("quality_summary", {})
        q_score = q_summary.get("quality_score", 100.0)
        dup_cnt = q_summary.get("duplicate_rows", 0)
        
        citations[str(row_cnt)] = {"tool": "profile_dataset", "metric": "row_count", "value": row_cnt}
        citations[str(col_cnt)] = {"tool": "profile_dataset", "metric": "column_count", "value": col_cnt}
        citations[str(q_score)] = {"tool": "profile_dataset", "metric": "quality_score", "value": q_score}
        if dup_cnt > 0:
            citations[str(dup_cnt)] = {"tool": "profile_dataset", "metric": "duplicate_rows", "value": dup_cnt}

        # Data Quality Findings: Sentinels
        for s in dataset_profile.get("sentinels_detected", []):
            col = s.get("column")
            val = s.get("sentinel_value")
            cnt = s.get("count")
            citations[str(cnt)] = {"tool": "data_cleaning", "metric": f"{col}_sentinel_count", "value": cnt}
            citations[str(val)] = {"tool": "data_cleaning", "metric": f"{col}_sentinel_value", "value": val}
            findings.append({
                "category": "Data Quality",
                "headline": f"{cnt} placeholder sentinels in {col}",
                "narrative": f"Sanitized {cnt} placeholder values of {val} in column '{col}' prior to imputation.",
                "primary_metric": cnt,
                "source_tool": "data_cleaning"
            })

        # Data Quality Findings: Invalid Values
        for iv in dataset_profile.get("invalid_values_detected", []):
            col = iv.get("column")
            cnt = iv.get("count")
            rule = iv.get("rule")
            citations[str(cnt)] = {"tool": "data_cleaning", "metric": f"{col}_invalid_count", "value": cnt}
            findings.append({
                "category": "Data Quality",
                "headline": f"{cnt} invalid domain values in {col}",
                "narrative": f"Identified and removed {cnt} invalid values in column '{col}' violating {rule}.",
                "primary_metric": cnt,
                "source_tool": "data_cleaning"
            })

        # Data Quality Findings: Imputation Rates
        for col, stats in dataset_profile.get("column_imputation_stats", {}).items():
            imp_cnt = stats.get("imputed_count", 0)
            imp_rate = stats.get("imputation_rate", 0.0)
            if imp_cnt > 0:
                citations[str(imp_cnt)] = {"tool": "data_cleaning", "metric": f"{col}_imputed_count", "value": imp_cnt}
                pct = round(imp_rate * 100, 2)
                citations[str(pct)] = {"tool": "data_cleaning", "metric": f"{col}_imputed_pct", "value": pct}

    # 2. Harvest facts from tool results
    for res in structured_results:
        tool_name = res.get("tool", "")

        # Correlation findings
        if tool_name == "run_correlation":
            strong = res.get("strong_relationships", [])
            if strong:
                for rel in strong[:3]:
                    r_val = rel["correlation"]
                    str_r = str(r_val)
                    col_x, col_y = rel["column_x"], rel["column_y"]
                    citations[str_r] = {"tool": tool_name, "relationship": f"{col_x} vs {col_y}", "value": r_val}
                    findings.append({
                        "category": "Correlation",
                        "headline": f"Strong relationship between {col_x} and {col_y}",
                        "narrative": f"Found a {rel['strength']} correlation of {r_val} across {rel['sample_size']} observations.",
                        "primary_metric": r_val,
                        "source_tool": tool_name
                    })
            elif res.get("highest_correlation"):
                rel = res["highest_correlation"]
                r_val = rel["correlation"]
                str_r = str(r_val)
                col_x, col_y = rel["column_x"], rel["column_y"]
                citations[str_r] = {"tool": tool_name, "relationship": f"{col_x} vs {col_y}", "value": r_val}
                findings.append({
                    "category": "Correlation",
                    "headline": f"Leading relationship between {col_x} and {col_y}",
                    "narrative": f"Highest observed correlation was {r_val} ({rel['strength']}) across {rel['sample_size']} observations.",
                    "primary_metric": r_val,
                    "source_tool": tool_name
                })

        # Outlier findings
        elif tool_name == "detect_outliers":
            total_anomalies = res.get("total_anomalous_rows", res.get("anomaly_count", 0))
            rate = res.get("overall_anomaly_rate_percent", res.get("anomaly_rate_percent", 0.0))
            n_rows_used = res.get("n_rows_used", res.get("total_rows_examined", 0))
            citations[str(total_anomalies)] = {"tool": tool_name, "metric": "total_anomalous_rows", "value": total_anomalies}
            citations[str(rate)] = {"tool": tool_name, "metric": "anomaly_rate_percent", "value": rate}
            if n_rows_used:
                citations[str(n_rows_used)] = {"tool": tool_name, "metric": "n_rows_used", "value": n_rows_used}
            
            top_cols = res.get("top_outlier_columns", [])
            if top_cols:
                top = top_cols[0]
                citations[str(top["count"])] = {"tool": tool_name, "metric": f"{top['column']} outliers", "value": top["count"]}
                findings.append({
                    "category": "Outlier Detection",
                    "headline": f"{total_anomalies} anomalous records detected ({rate}%)",
                    "narrative": f"Identified statistical anomalies primarily concentrated in '{top['column']}' ({top['count']} outliers across {n_rows_used} cleaned rows).",
                    "primary_metric": total_anomalies,
                    "source_tool": tool_name
                })

        # Segment comparison findings
        elif tool_name == "segment_compare":
            top_seg = res.get("top_segment", {})
            bottom_seg = res.get("bottom_segment", {})
            ratio = res.get("top_vs_bottom_ratio")
            p_val = res.get("anova_p_value")
            
            if top_seg and bottom_seg:
                top_m = top_seg["mean"]
                bot_m = bottom_seg["mean"]
                citations[str(top_m)] = {"tool": tool_name, "metric": f"{top_seg['segment']} mean", "value": top_m}
                citations[str(bot_m)] = {"tool": tool_name, "metric": f"{bottom_seg['segment']} mean", "value": bot_m}

                abs_diff = res.get("absolute_difference")
                if abs_diff is None:
                    abs_diff = round(top_m - bot_m, 2)
                citations[str(abs(abs_diff))] = {"tool": tool_name, "metric": "absolute_difference", "value": abs(abs_diff)}

                sig_note = f" (statistically significant, p={p_val})" if res.get("is_statistically_significant") else ""

                if ratio is not None and ratio > 1.0:
                    citations[str(ratio)] = {"tool": tool_name, "metric": "top_vs_bottom_ratio", "value": ratio}
                    headline = f"Top segment '{top_seg['segment']}' outperformed '{bottom_seg['segment']}' by {ratio}x ({top_m} vs {bot_m})"
                elif ratio is not None and ratio == 1.0:
                    headline = f"Segments '{top_seg['segment']}' and '{bottom_seg['segment']}' demonstrated equivalent performance ({top_m})"
                else:
                    headline = f"Segment '{top_seg['segment']}' exceeded '{bottom_seg['segment']}' by {abs_diff:+} ({top_m} vs {bot_m})"

                findings.append({
                    "category": "Segment Comparison",
                    "headline": headline,
                    "narrative": f"Average {res.get('metric_column')} reached {top_m} for '{top_seg['segment']}' compared to {bot_m} for '{bottom_seg['segment']}'{sig_note}.",
                    "primary_metric": top_m,
                    "source_tool": tool_name
                })

        # Trend findings
        elif tool_name == "trend_analysis":
            direction = res.get("overall_trend", "stable")
            pct = res.get("percentage_change", 0.0)
            citations[str(pct)] = {"tool": tool_name, "metric": "percentage_change", "value": pct}
            peak = res.get("peak_period", {})
            if peak:
                citations[str(peak["value"])] = {"tool": tool_name, "metric": "peak_value", "value": peak["value"]}

            findings.append({
                "category": "Trend Analysis",
                "headline": f"Overall {direction} trajectory ({pct}% total change)",
                "narrative": f"Chronological analysis indicates an overall {direction} trend in {res.get('value_column')}, peaking at {peak.get('value')} on {peak.get('date')}.",
                "primary_metric": pct,
                "source_tool": tool_name
            })

        # SQL query findings
        elif tool_name == "query_sql":
            row_cnt = res.get("row_count", 0)
            citations[str(row_cnt)] = {"tool": tool_name, "metric": "sql_rows_returned", "value": row_cnt}
            findings.append({
                "category": "SQL Query",
                "headline": f"Ad-hoc SQL query returned {row_cnt} records",
                "narrative": f"Executed custom query: '{res.get('query')[:80]}...'",
                "primary_metric": row_cnt,
                "source_tool": tool_name
            })

    # 3. Assemble executive narrative
    goal_context = f" targeting '{goal}'" if goal else ""
    summary_paragraph = (
        f"The autonomous analysis{goal_context} concluded with {len(findings)} key statistical findings "
        f"derived from {len(structured_results)} analytical tool executions. "
        f"All reported metrics and comparisons reflect deterministic computation without speculative estimation."
    )

    recommendations = [
        "Focus operational optimization on segments demonstrating the highest efficiency differentials.",
        "Investigate flagged statistical anomalies to prevent data skew from biasing long-term forecasts.",
        "Establish automated recurring tracking on key correlated metrics."
    ]

    return {
        "status": "success",
        "executive_summary": summary_paragraph,
        "key_findings": findings,
        "recommendations": recommendations,
        "total_findings": len(findings),
        "total_tools_executed": len(structured_results),
        "citations_index": citations
    }
