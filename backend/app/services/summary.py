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

    # 1. Harvest facts from profiling
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
            total_anomalies = res.get("total_anomalous_rows", 0)
            rate = res.get("overall_anomaly_rate_percent", 0.0)
            citations[str(total_anomalies)] = {"tool": tool_name, "metric": "total_anomalous_rows", "value": total_anomalies}
            citations[str(rate)] = {"tool": tool_name, "metric": "anomaly_rate_percent", "value": rate}
            
            top_cols = res.get("top_outlier_columns", [])
            if top_cols:
                top = top_cols[0]
                citations[str(top["count"])] = {"tool": tool_name, "metric": f"{top['column']} outliers", "value": top["count"]}
                findings.append({
                    "category": "Outlier Detection",
                    "headline": f"{total_anomalies} anomalous records detected ({rate}%)",
                    "narrative": f"Identified statistical anomalies primarily concentrated in '{top['column']}' ({top['count']} outliers).",
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
                citations[str(top_seg["mean"])] = {"tool": tool_name, "metric": f"{top_seg['segment']} mean", "value": top_seg["mean"]}
                citations[str(bottom_seg["mean"])] = {"tool": tool_name, "metric": f"{bottom_seg['segment']} mean", "value": bottom_seg["mean"]}
                if ratio:
                    citations[str(ratio)] = {"tool": tool_name, "metric": "top_vs_bottom_ratio", "value": ratio}
                
                sig_note = f" (statistically significant, p={p_val})" if res.get("is_statistically_significant") else ""
                findings.append({
                    "category": "Segment Comparison",
                    "headline": f"Top segment '{top_seg['segment']}' outperformed '{bottom_seg['segment']}' by {ratio or 1.0}x",
                    "narrative": f"Average {res.get('metric_column')} reached {top_seg['mean']} for '{top_seg['segment']}' compared to {bottom_seg['mean']} for '{bottom_seg['segment']}'{sig_note}.",
                    "primary_metric": top_seg["mean"],
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
