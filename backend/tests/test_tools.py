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
import pandas as pd
import pytest
from backend.app.services.charts import generate_chart
from backend.app.services.correlation import run_correlation
from backend.app.services.outliers import detect_outliers
from backend.app.services.segmentation import segment_compare
from backend.app.services.sql_tool import query_sql
from backend.app.services.summary import write_summary
from backend.app.services.timeseries import STABILITY_THRESHOLD_PCT, trend_analysis

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
    # Note: Phase 2 sentinel cleaning replaced extreme Quantity=999 sentinels with median.
    # We pass threshold=1.0 to detect non-sentinel volume outliers in the cleaned dataset.
    res = detect_outliers(RETAIL_DATASET, method="iqr", threshold=1.0)
    assert res["status"] == "success"
    assert res["total_anomalous_rows"] > 0
    assert "Quantity" in res["column_outliers"]
    q_info = res["column_outliers"]["Quantity"]
    assert q_info["outlier_count"] > 0
    assert "lower_bound" in q_info
    assert "upper_bound" in q_info

def test_detect_outliers_zscore_hr():
    # With z_threshold=3.0 and Phase 2 domain validity rules cleaning Age=150 as invalid,
    # cleaned Age has no outliers exceeding 3 standard deviations.
    res = detect_outliers(HR_DATASET, method="zscore")
    assert res["status"] == "success"
    assert "Age" in res["column_outliers"]
    age_info = res["column_outliers"]["Age"]
    assert age_info["outlier_count"] == 0  # Age 150 handled as domain-invalid value prior to imputation
    assert age_info["z_threshold"] == 3.0

def test_detect_outliers_zscore_custom_threshold():
    # Verify custom z-score threshold parameter is respected when specified by caller
    res = detect_outliers(MKT_DATASET, method="zscore", threshold=2.0)
    assert res["status"] == "success"
    assert "Clicks" in res["column_outliers"]
    assert res["column_outliers"]["Clicks"]["outlier_count"] > 0
    assert res["column_outliers"]["Clicks"]["z_threshold"] == 2.0

def test_detect_outliers_isolation_forest():
    try:
        res = detect_outliers(MKT_DATASET, method="isolation_forest")
    except ImportError as e:
        pytest.skip(f"sklearn native DLL blocked by Application Control policy: {e}")
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

def test_segment_compare_rejects_high_cardinality_id():
    """Assert segment_compare rejects columns with high cardinality or identifier names."""
    with pytest.raises(ValueError, match="resembles a unique record identifier|unique identifier|high cardinality"):
        segment_compare(RETAIL_DATASET, segment_column="Transaction_ID", metric_column="Unit_Price")

def test_segment_compare_deprioritizes_id_in_heuristic_planner():
    """Assert the orchestrator's heuristic planner deprioritizes/excludes ID columns."""
    from backend.app.agent.orchestrator import PlanActReflectOrchestrator
    from backend.app.services.data_loader import get_dataset_dataframe
    from backend.app.services.profiling import profile_dataset
    df = get_dataset_dataframe(RETAIL_DATASET)
    profile = profile_dataset(df, dataset_id=RETAIL_DATASET).model_dump()
    orchestrator = PlanActReflectOrchestrator()
    plan = orchestrator._generate_heuristic_plan(profile, RETAIL_DATASET)
    seg_step = next(s for s in plan if s["tool"] == "segment_compare")
    assert seg_step["arguments"]["segment_column"] not in ["Transaction_ID", "Customer_ID"]
    assert seg_step["arguments"]["segment_column"] in ["Category", "Region", "Payment_Method", "Product"]

def test_imputation_exclusion():
    """Assert segment_compare on HR attrition produces distinct segment medians and reports n_used/n_excluded_imputed."""
    res = segment_compare(HR_DATASET, segment_column="Department", metric_column="Annual_Salary")
    assert res["status"] == "success"
    assert "n_used" in res
    assert "n_excluded_imputed" in res
    assert res["n_used"] > 0
    assert res["n_excluded_imputed"] > 0
    # Segment medians must not all be identical (no longer flattened by global imputation)
    medians = [s["median"] for s in res["segments"]]
    assert len(set(medians)) > 1, f"Segment medians are flat/identical: {medians}"

def test_outlier_denominator():
    """Assert detect_outliers reports correct n_rows_used, anomaly_count, and anomaly_rate_percent using clean denominator."""
    res = detect_outliers(RETAIL_DATASET, method="iqr")
    assert res["status"] == "success"
    assert "n_rows_used" in res
    assert "anomaly_count" in res
    assert "anomaly_rate_percent" in res
    assert res["n_rows_used"] > 0
    expected_rate = round((res["anomaly_count"] / res["n_rows_used"]) * 100, 2)
    assert abs(res["anomaly_rate_percent"] - expected_rate) < 1e-4

# 4. TREND ANALYSIS TESTS
def test_trend_analysis_retail():
    res = trend_analysis(RETAIL_DATASET, date_column="Date", value_column="Unit_Price")
    assert res["status"] == "success"
    assert res["overall_trend"] in ["upward", "downward", "stable"]
    assert "timeline" in res
    assert len(res["timeline"]) > 0
    assert "peak_period" in res

def test_trend_analysis_stability_threshold(monkeypatch):
    """Assert trend_analysis labels a downward drop as downward and only labels stable when within STABILITY_THRESHOLD_PCT."""
    # 1. Retail dataset has a downward drop (-20.5%), must be classified as 'downward', NOT 'stable'
    res_retail = trend_analysis(RETAIL_DATASET, date_column="Date", value_column="Unit_Price")
    assert res_retail["percentage_change"] <= -STABILITY_THRESHOLD_PCT
    assert res_retail["overall_trend"] == "downward"
    assert res_retail["overall_trend"] != "stable"

    # 2. Synthetic series within threshold (+2.0% change < 5.0% threshold) must be 'stable'
    df_stable = pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=10, freq="D"),
        "Value": [100.0, 101.0, 99.5, 100.5, 101.2, 100.8, 101.5, 100.2, 101.8, 102.0]
    })
    monkeypatch.setattr("backend.app.services.timeseries.get_dataset_dataframe", lambda ds_id, **kw: df_stable)
    res_stable = trend_analysis("dummy_ds", date_column="Date", value_column="Value")
    assert abs(res_stable["percentage_change"]) < STABILITY_THRESHOLD_PCT
    assert res_stable["overall_trend"] == "stable"

    # 3. Synthetic series with -40% drop must be 'downward'
    df_drop = pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=10, freq="D"),
        "Value": [100.0, 95.0, 90.0, 85.0, 80.0, 75.0, 70.0, 65.0, 62.0, 60.0]
    })
    monkeypatch.setattr("backend.app.services.timeseries.get_dataset_dataframe", lambda ds_id, **kw: df_drop)
    res_drop = trend_analysis("dummy_ds", date_column="Date", value_column="Value")
    assert res_drop["percentage_change"] == -40.0
    assert res_drop["overall_trend"] == "downward"

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
    o_res = detect_outliers(RETAIL_DATASET, threshold=1.0)
    s_res = segment_compare(HR_DATASET, segment_column="Department", metric_column="Annual_Salary")
    
    summary = write_summary(
        structured_results=[c_res, o_res, s_res],
        dataset_profile={"row_count": 126, "column_count": 9, "quality_summary": {"quality_score": 98.5, "duplicate_rows": 6}}
    )
    assert summary["status"] == "success"
    assert len(summary["key_findings"]) >= 3
    assert len(summary["citations_index"]) > 0
    assert "126" in summary["citations_index"]
