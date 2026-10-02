"""Targeted tests for Chat Hardening (Item 7).

Verifies:
1. Questions mentioning non-existent columns/entities explicitly state the missing column/entity and list available columns.
2. Questions requiring tool calls execute query_sql or run_correlation with proper evidence and results.
3. Bound citation verification runs on chat answers and enforces accurate numbers.
"""
import pytest
from backend.app.services.chat_service import (
    detect_missing_column_or_entity,
    determine_chat_tool_call,
    process_chat_question
)
from backend.app.core.database import SessionLocal
from backend.app.models.dataset import Dataset
from backend.app.models.job import AnalysisJob
from backend.app.services.data_loader import get_dataset_dataframe

def test_missing_column_detection():
    # 1. Retail dataset lacks customer age
    retail_cols = ["Transaction_ID", "Date", "Customer_ID", "Product", "Category", "Region", "Quantity", "Unit_Price", "Payment_Method"]
    missing_1 = detect_missing_column_or_entity("What is the average customer age across store regions?", retail_cols)
    assert missing_1 == "customer age"

    # 2. HR dataset lacks customer churn
    hr_cols = ["Employee_ID", "Age", "Gender", "Department", "Annual_Salary", "Tenure_Years", "Satisfaction_Level", "Performance_Score", "Attrition", "Last_Promotion_Year"]
    missing_2 = detect_missing_column_or_entity("How does customer churn correlate with employee satisfaction?", hr_cols)
    assert missing_2 == "customer churn"

    # 3. Marketing dataset lacks credit score
    mkt_cols = ["Campaign_ID", "Date", "Channel", "Ad_Spend", "Impressions", "Clicks", "Conversions", "Target_Audience"]
    missing_3 = detect_missing_column_or_entity("What is the average customer credit score across marketing channels?", mkt_cols)
    assert missing_3 == "credit score"

    # 4. Valid column query returns None
    assert detect_missing_column_or_entity("What is the breakdown of conversions by channel?", mkt_cols) is None

def test_chat_tool_call_determination():
    # Retail payment method share
    retail_cols = ["Transaction_ID", "Date", "Customer_ID", "Product", "Category", "Region", "Quantity", "Unit_Price", "Payment_Method"]
    tool_name, tool_args = determine_chat_tool_call(
        "What is the share of Credit Card payments among non-missing payment method rows?",
        "retail_sales_messy.csv",
        retail_cols
    )
    assert tool_name == "query_sql"
    assert "Payment_Method" in tool_args["sql"]
    assert "data_clean" in tool_args["sql"]

    # HR observed salary by department
    hr_cols = ["Employee_ID", "Age", "Gender", "Department", "Annual_Salary", "Tenure_Years", "Satisfaction_Level", "Performance_Score", "Attrition"]
    tool_name_hr, tool_args_hr = determine_chat_tool_call(
        "What is the average annual salary by department among observed non-missing records?",
        "hr_attrition_messy.csv",
        hr_cols
    )
    assert tool_name_hr == "query_sql"
    assert "data_observed" in tool_args_hr["sql"]
    assert "Department" in tool_args_hr["sql"]

    # Marketing spend and clicks by channel
    mkt_cols = ["Campaign_ID", "Date", "Channel", "Ad_Spend", "Impressions", "Clicks", "Conversions"]
    tool_name_mkt, tool_args_mkt = determine_chat_tool_call(
        "What is the total ad spend and total clicks by channel?",
        "marketing_campaign_messy.csv",
        mkt_cols
    )
    assert tool_name_mkt == "query_sql"
    assert "Channel" in tool_args_mkt["sql"]
    assert "data_clean" in tool_args_mkt["sql"]

def test_chat_process_missing_column_and_tool_call(monkeypatch):
    """Test full chat execution with missing column notice and tool calling."""
    monkeypatch.setenv("LLM_PROVIDER", "heuristic")
    db = SessionLocal()
    
    # Process question with missing column
    res_missing = process_chat_question(
        db=db,
        job_id="",
        question="What is the average customer age across branches?",
        dataset_id="retail_sales_messy.csv"
    )
    assert "The requested column/entity 'customer age' is not present in this dataset" in res_missing["answer"]
    assert "Transaction_ID" in res_missing["answer"]
    assert res_missing["verification"]["is_valid"] is True

    # Process question with tool call (Retail Credit Card share)
    res_tool = process_chat_question(
        db=db,
        job_id="",
        question="What is the share of Credit Card payments among non-missing payment method rows?",
        dataset_id="retail_sales_messy.csv"
    )
    assert len(res_tool["tool_calls_used"]) == 1
    assert res_tool["tool_calls_used"][0]["tool"] == "query_sql"
    assert "data_observed" in res_tool["answer"]
    assert "48.96" in res_tool["answer"]
    assert "59.17" in res_tool["answer"]
    assert "24" in res_tool["answer"]
    assert "imputed" in res_tool["answer"].lower()
    assert res_tool["verification"]["is_valid"] is True
    assert res_tool["verification"]["post_strip_verification_rate"] == 100.0

    # Process question: Which channel has the highest conversion rate?
    mkt_cols = ["Campaign_ID", "Date", "Channel", "Ad_Spend", "Impressions", "Clicks", "Conversions"]
    res_conv = process_chat_question(
        db=db,
        job_id="",
        question="Which channel has the highest conversion rate?",
        dataset_id="marketing_campaign_messy.csv"
    )
    assert len(res_conv["tool_calls_used"]) == 1
    assert res_conv["tool_calls_used"][0]["tool"] == "query_sql"
    assert "Email" in res_conv["answer"]
    assert "8.97" in res_conv["answer"]
    assert "data_observed" in res_conv["answer"]
    assert res_conv["verification"]["is_valid"] is True
    assert res_conv["verification"]["post_strip_verification_rate"] == 100.0
