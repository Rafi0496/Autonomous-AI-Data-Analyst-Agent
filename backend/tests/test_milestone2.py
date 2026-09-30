"""Tests for Phase 3 Milestone 2: Chart Specifications & Matplotlib Headless Rendering."""
import pytest
from pathlib import Path
from typing import Dict, Any

from backend.app.services.chart_render import render_chart_to_png
from backend.app.services.insights import generate_insights
from shared.schemas.insight import Insight


def test_chart_spec_selection_per_insight_type():
    # 1. Segment difference -> bar chart
    seg_result = {
        "tool": "segment_compare",
        "segment_column": "Department",
        "metric_column": "Salary",
        "segments": [
            {"segment": "Engineering", "mean": 95000.0, "std": 12000.0},
            {"segment": "Sales", "mean": 75000.0, "std": 8000.0},
            {"segment": "HR", "mean": 65000.0, "std": 6000.0}
        ],
        "top_segment": {"segment": "Engineering", "median": 95000.0},
        "bottom_segment": {"segment": "HR", "median": 65000.0},
        "ratio": 1.46,
        "n_used": 110,
        "n_excluded_imputed": 10,
        "anova_p_value": 0.002
    }

    # 2. Correlation with 3+ columns -> heatmap; pairwise -> scatter
    corr_multi_result = {
        "tool": "run_correlation",
        "columns_analyzed": ["Ad_Spend", "Impressions", "Clicks", "Conversions"],
        "correlation_matrix": {
            "Ad_Spend": {"Ad_Spend": 1.0, "Impressions": 0.85, "Clicks": 0.72, "Conversions": 0.65},
            "Impressions": {"Ad_Spend": 0.85, "Impressions": 1.0, "Clicks": 0.91, "Conversions": 0.78},
            "Clicks": {"Ad_Spend": 0.72, "Impressions": 0.91, "Clicks": 1.0, "Conversions": 0.88},
            "Conversions": {"Ad_Spend": 0.65, "Impressions": 0.78, "Clicks": 0.88, "Conversions": 1.0}
        },
        "strong_relationships": [
            {"column_x": "Impressions", "column_y": "Clicks", "correlation": 0.91, "strength": "very strong"}
        ],
        "n_used": 100,
        "n_excluded_imputed": 5
    }

    # 3. Trend -> line chart
    trend_result = {
        "tool": "trend_analysis",
        "value_column": "Revenue",
        "date_column": "Date",
        "overall_trend": "upward",
        "percentage_change": 42.5,
        "timeline": [
            {"date": "2023-01", "value": 10000.0, "rolling_avg": 10000.0},
            {"date": "2023-02", "value": 12000.0, "rolling_avg": 11000.0},
            {"date": "2023-03", "value": 14250.0, "rolling_avg": 12083.3}
        ],
        "peak_period": {"date": "2023-03", "value": 14250.0},
        "n_used": 12,
        "n_excluded_imputed": 0
    }

    # 4. Outlier -> box or histogram
    outlier_result = {
        "tool": "detect_outliers",
        "total_anomalous_rows": 15,
        "overall_anomaly_rate_percent": 12.5,
        "top_outlier_columns": [{"column": "Quantity", "count": 15}],
        "column_outliers": {
            "Quantity": {
                "q1": 10.0,
                "median": 15.0,
                "q3": 25.0,
                "sample_outlier_values": [999.0, 999.0, 999.0]
            }
        },
        "n_rows_used": 120,
        "n_excluded_imputed": 0
    }

    # 5. Data Quality -> horizontal bar of imputation rates
    dataset_profile = {
        "row_count": 100,
        "cleaned_row_count": 90,
        "column_imputation_stats": {
            "Annual_Salary": {"imputation_rate": 0.464, "imputed_count": 51},
            "Age": {"imputation_rate": 0.291, "imputed_count": 32},
            "Tenure": {"imputation_rate": 0.182, "imputed_count": 20}
        },
        "sentinels_detected": [{"column": "Quantity", "sentinel_value": 999.0, "count": 15}]
    }

    insights = generate_insights(
        structured_results=[seg_result, corr_multi_result, trend_result, outlier_result],
        dataset_profile=dataset_profile
    )

    types_found = {ins.type: ins for ins in insights}
    assert "segment_difference" in types_found
    assert "correlation" in types_found
    assert "trend" in types_found
    assert "outlier" in types_found
    assert "data_quality" in types_found

    # Verify chart_type selections
    seg_spec = types_found["segment_difference"].chart_spec
    assert seg_spec is not None
    assert seg_spec["chart_type"] == "bar"
    assert len(seg_spec["data"]) == 3

    corr_spec = types_found["correlation"].chart_spec
    assert corr_spec is not None
    assert corr_spec["chart_type"] in ("heatmap", "scatter")

    trend_spec = types_found["trend"].chart_spec
    assert trend_spec is not None
    assert trend_spec["chart_type"] == "line"
    assert len(trend_spec["data"]) == 3

    outlier_spec = types_found["outlier"].chart_spec
    assert outlier_spec is not None
    assert outlier_spec["chart_type"] in ("box", "histogram")

    dq_spec = types_found["data_quality"].chart_spec
    assert dq_spec is not None
    assert dq_spec["chart_type"] == "bar"
    assert dq_spec.get("orientation") == "horizontal"


def test_every_spec_renders_to_non_empty_png(tmp_path: Path):
    specs = [
        # Bar vertical with error bars
        {
            "chart_type": "bar",
            "orientation": "vertical",
            "title": "Mean Salary by Department",
            "x_label": "Department",
            "y_label": "Salary ($)",
            "data": [
                {"label": "Engineering", "value": 95000.0, "error": 5000.0},
                {"label": "Sales", "value": 75000.0, "error": 4000.0},
                {"label": "Marketing", "value": 68000.0, "error": 3000.0}
            ]
        },
        # Bar horizontal
        {
            "chart_type": "bar",
            "orientation": "horizontal",
            "title": "Missing Value Imputation Rate (%)",
            "x_label": "Imputation Rate (%)",
            "y_label": "Column",
            "data": [
                {"label": "Salary", "value": 46.4},
                {"label": "Age", "value": 29.1},
                {"label": "Tenure", "value": 18.2}
            ]
        },
        # Line chart with rolling average
        {
            "chart_type": "line",
            "title": "Revenue Trajectory",
            "x_label": "Period",
            "y_label": "Revenue",
            "data": [
                {"x": "Jan", "y": 100.0, "rolling": 100.0},
                {"x": "Feb", "y": 120.0, "rolling": 110.0},
                {"x": "Mar", "y": 140.0, "rolling": 120.0},
                {"x": "Apr", "y": 135.0, "rolling": 123.7}
            ]
        },
        # Scatter chart
        {
            "chart_type": "scatter",
            "title": "Ad Spend vs Conversions",
            "x_label": "Ad Spend ($)",
            "y_label": "Conversions",
            "data": [
                {"x": 100.0, "y": 10.0},
                {"x": 200.0, "y": 22.0},
                {"x": 300.0, "y": 28.0},
                {"x": 400.0, "y": 45.0}
            ]
        },
        # Heatmap
        {
            "chart_type": "heatmap",
            "title": "Feature Correlation",
            "x_label": "Features",
            "y_label": "Features",
            "data": {
                "columns": ["A", "B", "C"],
                "matrix": [
                    [1.0, 0.75, 0.45],
                    [0.75, 1.0, 0.60],
                    [0.45, 0.60, 1.0]
                ]
            }
        },
        # Box plot
        {
            "chart_type": "box",
            "title": "Outlier Boxplot",
            "x_label": "Quantity",
            "y_label": "Values",
            "data": [
                {
                    "label": "Quantity",
                    "q1": 10.0,
                    "median": 15.0,
                    "q3": 25.0,
                    "outliers": [999.0]
                }
            ]
        },
        # Histogram
        {
            "chart_type": "histogram",
            "title": "Distribution Frequency",
            "x_label": "Bins",
            "y_label": "Frequency",
            "data": [
                {"bin": "0-20", "count": 12},
                {"bin": "20-40", "count": 45},
                {"bin": "40-60", "count": 30}
            ]
        }
    ]

    for idx, spec in enumerate(specs):
        out_file = tmp_path / f"test_chart_{idx}.png"
        png_bytes = render_chart_to_png(spec, output_path=out_file)
        
        # Check non-empty bytes
        assert isinstance(png_bytes, bytes)
        assert len(png_bytes) > 1000
        # Check PNG header magic bytes \x89PNG
        assert png_bytes[:4] == b"\x89PNG"
        # Check file was written
        assert out_file.exists()
        assert out_file.stat().st_size > 1000
