"""Chart generation tool: generate_chart().

Generates declarative Plotly chart specifications (dict) for interactive rendering via rx.plotly.
Returns a JSON-compatible dictionary specification, NOT an image.
"""
from typing import Any, Dict, List, Optional

def generate_chart(
    result_type: str,
    data: Dict[str, Any],
    title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate an interactive Plotly chart specification based on analysis tool results.
    Supported result_types: 'correlation', 'trend', 'segment_compare', 'outlier', 'bar', 'line', 'scatter', 'heatmap'.
    """
    chart_type = result_type.lower()
    
    # Common dark-mode layout template
    base_layout = {
        "title": {"text": title or "Analysis Visualization", "font": {"color": "#f8fafc", "size": 16}},
        "paper_bgcolor": "rgba(15, 23, 42, 0.0)",
        "plot_bgcolor": "rgba(15, 23, 42, 0.0)",
        "font": {"color": "#94a3b8", "family": "Inter, sans-serif"},
        "margin": {"l": 50, "r": 30, "t": 50, "b": 50},
        "xaxis": {
            "gridcolor": "rgba(255, 255, 255, 0.06)",
            "linecolor": "rgba(255, 255, 255, 0.1)",
            "tickfont": {"color": "#94a3b8"}
        },
        "yaxis": {
            "gridcolor": "rgba(255, 255, 255, 0.06)",
            "linecolor": "rgba(255, 255, 255, 0.1)",
            "tickfont": {"color": "#94a3b8"}
        },
        "legend": {"font": {"color": "#f1f5f9"}}
    }

    # 1. CORRELATION / HEATMAP
    if chart_type in ("correlation", "heatmap"):
        matrix = data.get("correlation_matrix", {})
        cols = list(matrix.keys())
        if not cols and "columns_analyzed" in data:
            cols = data["columns_analyzed"]
            
        z_vals = []
        for r_col in cols:
            row = []
            for c_col in cols:
                val = matrix.get(r_col, {}).get(c_col, 0.0)
                row.append(val)
            z_vals.append(row)

        plot_data = [
            {
                "type": "heatmap",
                "x": cols,
                "y": cols,
                "z": z_vals,
                "colorscale": "Viridis",
                "zmin": -1.0,
                "zmax": 1.0,
                "colorbar": {"title": "Correlation (r)", "tickfont": {"color": "#94a3b8"}}
            }
        ]
        layout = {**base_layout, "title": {"text": title or "Correlation Heatmap Matrix"}}

    # 2. TREND / LINE
    elif chart_type in ("trend", "line", "trend_analysis"):
        timeline = data.get("timeline", [])
        dates = [pt["date"] for pt in timeline]
        values = [pt["value"] for pt in timeline]
        rolling = [pt["rolling_avg"] for pt in timeline if "rolling_avg" in pt]
        
        plot_data = [
            {
                "type": "scatter",
                "mode": "lines+markers",
                "name": data.get("value_column", "Observed"),
                "x": dates,
                "y": values,
                "line": {"color": "#6366f1", "width": 2},
                "marker": {"size": 6, "color": "#818cf8"}
            }
        ]
        
        if len(rolling) == len(dates):
            plot_data.append({
                "type": "scatter",
                "mode": "lines",
                "name": "Rolling Average",
                "x": dates,
                "y": rolling,
                "line": {"color": "#f59e0b", "width": 2, "dash": "dot"}
            })
            
        layout = {
            **base_layout,
            "title": {"text": title or f"Trend: {data.get('value_column', 'Metric')} over Time"}
        }

    # 3. SEGMENT_COMPARE / BAR
    elif chart_type in ("segment_compare", "bar"):
        segments = data.get("segments", [])
        seg_names = [s["segment"] for s in segments]
        means = [s["mean"] for s in segments]
        
        plot_data = [
            {
                "type": "bar",
                "x": seg_names,
                "y": means,
                "marker": {
                    "color": "#6366f1",
                    "line": {"color": "#818cf8", "width": 1}
                },
                "name": f"Mean {data.get('metric_column', 'Metric')}"
            }
        ]
        layout = {
            **base_layout,
            "title": {"text": title or f"Segment Comparison: {data.get('metric_column', '')} by {data.get('segment_column', '')}"}
        }

    # 4. OUTLIER / SCATTER
    elif chart_type in ("outlier", "scatter", "detect_outliers"):
        cols = list(data.get("column_outliers", {}).keys())
        primary_col = cols[0] if cols else "Value"
        col_info = data.get("column_outliers", {}).get(primary_col, {})
        
        samples = col_info.get("sample_outlier_values", [])
        plot_data = [
            {
                "type": "scatter",
                "mode": "markers",
                "name": "Outliers Detected",
                "x": list(range(len(samples))),
                "y": samples,
                "marker": {"color": "#ef4444", "size": 10, "symbol": "diamond"}
            }
        ]
        
        layout = {
            **base_layout,
            "title": {"text": title or f"Outlier Distribution: {primary_col}"}
        }

    else:
        # Generic fallback
        plot_data = data.get("data", [])
        layout = {**base_layout, "title": {"text": title or "Visualization"}}

    return {
        "status": "success",
        "chart_type": chart_type,
        "spec": {
            "data": plot_data,
            "layout": layout
        }
    }
