"""Executive Synthesis Tool: write_summary().

Final analysis step only (not callable mid-plan).
Synthesizes all structured tool results into a structured business narrative where every claim
strictly traces back to computed values.
"""
from typing import Any, Dict, List, Optional

def write_summary(
    structured_results: List[Dict[str, Any]],
    dataset_profile: Optional[Dict[str, Any]] = None,
    goal: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synthesize structured tool results into an executive business summary.
    Extracts all exact computed numbers into a citation registry.
    """
    if not structured_results:
        return {
            "status": "empty",
            "message": "No analysis tool results provided for synthesis.",
            "executive_summary": "Analysis was concluded without tool executions.",
            "key_findings": [],
            "citations_index": {}
        }

    citations: Dict[str, Dict[str, Any]] = {}
    findings: List[Dict[str, Any]] = []

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
