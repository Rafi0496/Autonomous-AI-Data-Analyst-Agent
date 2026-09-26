"""Unit tests for the Tool Catalogue against the 3 real messy benchmark datasets.

Tests:
- run_correlation()
- detect_outliers()
- segment_compare()
- trend_analysis()
- generate_chart()
- query_sql() (including security guardrail rejections)
- write_summary()
"""
import pytest
from backend.app.services.charts import generate_chart
from backend.app.services.correlation import run_correlation
from backend.app.services.outliers import detect_outliers
from backend.app.services.segmentation import segment_compare
from backend.app.services.sql_tool import query_sql
from backend.app.services.summary import write_summary
from backend.app.services.timeseries import trend_analysis

RETAIL_DATASET = "retail_sales_messy.csv"
HR_DATASET = "hr_attrition_messy.csv"
MKT_DATASET = "marketing_campaign_messy.csv"

# 1. CORRELATION TESTS
def test_correlation_retail():
    res = run_correlation(RETAIL_DATASET)
    assert res["status"] == "success"
    assert "Quantity" in res["columns_analyzed"]
    assert "correlation_matrix" in res

def test_correlation_marketing():
    res = run_correlation(MKT_DATASET, threshold=0.3)
    assert res["status"] == "success"
    assert len(res["columns_analyzed"]) >= 2
    assert "strong_relationships" in res
    assert isinstance(res["strong_relationships"], list)

# 2. OUTLIER TESTS
def test_detect_outliers_iqr():
    res = detect_outliers(RETAIL_DATASET, method="iqr")
    assert res["status"] == "success"
    assert res["total_anomalous_rows"] > 0
    assert "Quantity" in res["column_outliers"]
    q_info = res["column_outliers"]["Quantity"]
    assert q_info["outlier_count"] > 0
    assert "lower_bound" in q_info
    assert "upper_bound" in q_info

def test_detect_outliers_zscore_hr():
    res = detect_outliers(HR_DATASET, method="zscore")
    assert res["status"] == "success"
    assert "Age" in res["column_outliers"]
    age_info = res["column_outliers"]["Age"]
    assert age_info["outlier_count"] > 0  # Age 150 outlier detected

def test_detect_outliers_isolation_forest():
    res = detect_outliers(MKT_DATASET, method="isolation_forest")
    assert res["status"] == "success"
    assert res["total_anomalous_rows"] > 0

# 3. SEGMENT COMPARE TESTS
def test_segment_compare_retail():
    res = segment_compare(RETAIL_DATASET, segment_column="Category", metric_column="Unit_Price")
    assert res["status"] == "success"
    assert len(res["segments"]) > 1
    assert res["top_segment"] is not None
    assert res["bottom_segment"] is not None
    assert "relative_diff_ratio" not in res or res["top_vs_bottom_ratio"] is not None

def test_segment_compare_hr():
    res = segment_compare(HR_DATASET, segment_column="Department", metric_column="Annual_Salary")
    assert res["status"] == "success"
    assert len(res["segments"]) > 1
    assert "overall_mean" in res

def test_segment_compare_invalid_column():
    with pytest.raises(ValueError, match="not found in dataset"):
        segment_compare(RETAIL_DATASET, segment_column="NonExistentCol", metric_column="Unit_Price")

# 4. TREND ANALYSIS TESTS
def test_trend_analysis_retail():
    res = trend_analysis(RETAIL_DATASET, date_column="Date", value_column="Unit_Price")
    assert res["status"] == "success"
    assert res["overall_trend"] in ["upward", "downward", "stable"]
    assert "timeline" in res
    assert len(res["timeline"]) > 0
    assert "peak_period" in res

def test_trend_analysis_marketing():
    res = trend_analysis(MKT_DATASET, date_column="Date", value_column="Ad_Spend")
    assert res["status"] == "success"
    assert res["timespan_days"] >= 0

# 5. GENERATE CHART TESTS
def test_generate_chart_specs():
    corr_res = run_correlation(MKT_DATASET)
    heatmap_spec = generate_chart("correlation", corr_res)
    assert heatmap_spec["status"] == "success"
    assert heatmap_spec["spec"]["data"][0]["type"] == "heatmap"

    seg_res = segment_compare(HR_DATASET, segment_column="Department", metric_column="Annual_Salary")
    bar_spec = generate_chart("segment_compare", seg_res)
    assert bar_spec["status"] == "success"
    assert bar_spec["spec"]["data"][0]["type"] == "bar"

    trend_res = trend_analysis(RETAIL_DATASET, date_column="Date", value_column="Unit_Price")
    line_spec = generate_chart("trend", trend_res)
    assert line_spec["status"] == "success"
    assert line_spec["spec"]["data"][0]["type"] == "scatter"

# 6. SQL QUERY & SECURITY GUARDRAILS TESTS
def test_query_sql_valid():
    res = query_sql(RETAIL_DATASET, "SELECT Product, COUNT(*) as cnt, AVG(Quantity) as avg_qty FROM df GROUP BY Product")
    assert res["status"] == "success"
    assert res["row_count"] > 0
    assert "Product" in res["columns"]

def test_query_sql_security_drop_rejected():
    with pytest.raises(ValueError, match="Forbidden SQL keyword"):
        query_sql(RETAIL_DATASET, "DROP TABLE df")

def test_query_sql_security_insert_rejected():
    with pytest.raises(ValueError, match="Forbidden SQL keyword"):
        query_sql(RETAIL_DATASET, "INSERT INTO df VALUES (1, 2, 3)")

def test_query_sql_security_semicolon_chain_rejected():
    with pytest.raises(ValueError, match="Multi-statement SQL queries are prohibited"):
        query_sql(RETAIL_DATASET, "SELECT * FROM df; DROP TABLE df")

def test_query_sql_security_path_traversal_rejected():
    with pytest.raises(ValueError, match="External filesystem access"):
        query_sql(RETAIL_DATASET, "SELECT * FROM read_csv('../secrets.txt')")

# 7. WRITE SUMMARY TESTS
def test_write_summary_synthesis():
    c_res = run_correlation(MKT_DATASET)
    o_res = detect_outliers(RETAIL_DATASET)
    s_res = segment_compare(HR_DATASET, segment_column="Department", metric_column="Annual_Salary")
    
    summary = write_summary(
        structured_results=[c_res, o_res, s_res],
        dataset_profile={"row_count": 126, "column_count": 9, "quality_summary": {"quality_score": 98.5, "duplicate_rows": 6}}
    )
    assert summary["status"] == "success"
    assert len(summary["key_findings"]) >= 3
    assert len(summary["citations_index"]) > 0
    assert "126" in summary["citations_index"]
