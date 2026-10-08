"""Targeted tests for Milestone 2: Chat Correctness.

Tests:
a) Replaced question-specific logic with general SQL generator against data_clean / data_observed.
   Tool results bound to claims; answer built from tool results + only insights sharing a column.
b) "non-missing / observed / recorded" questions query data_observed; otherwise data_clean.
   Every tool answer states basis and n matching the queried table.
c) If all claims are stripped, states answer could not be verified and displays query result.
d) UNSEEN paraphrased questions per dataset verified against direct pandas computation:
   - HR: "average annual salary by department among observed records"
   - Marketing: "total ad spend and total clicks by channel"
   - Retail: "number of transactions per region"
   - HR: "how many employees per department"
"""
import re
from pathlib import Path
import pandas as pd
import pytest

from backend.app.core.database import SessionLocal
from backend.app.services.data_loader import get_dataset_dataframe, get_column_imputed_mask
from backend.app.services.chat_service import (
    process_chat_question,
    determine_chat_tool_call,
    detect_missing_column_or_entity,
)
from backend.app.services.chat_sql import (
    generate_sql_for_question,
    detect_question_target_table,
    format_sql_query_result,
    extract_question_columns,
    insight_shares_column,
)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_unseen_questions_pandas_verification(db_session, monkeypatch):
    """Test 4 unseen paraphrased questions and assert numbers match direct pandas computation."""
    monkeypatch.setenv("LLM_PROVIDER", "heuristic")

    # 1. HR: "average annual salary by department among observed records" -> data_observed
    hr_clean = get_dataset_dataframe("hr_attrition_messy.csv", prefer_cleaned=True)
    mask = get_column_imputed_mask(hr_clean, "Annual_Salary")
    hr_obs = hr_clean[~mask] if mask.any() else hr_clean
    hr_obs = hr_obs[hr_obs["Annual_Salary"].notna() & hr_obs["Department"].notna()]
    expected_hr_salaries = hr_obs.groupby("Department")["Annual_Salary"].mean().round(2).to_dict()

    res1 = process_chat_question(
        db=db_session,
        job_id="",
        question="average annual salary by department among observed records",
        dataset_id="hr_attrition_messy.csv"
    )
    assert "data_observed" in res1["answer"]
    assert f"n={len(hr_obs)}" in res1["answer"]
    for dept, exp_salary in expected_hr_salaries.items():
        assert f"{exp_salary:,.2f}" in res1["answer"] or f"{exp_salary:.2f}" in res1["answer"]
    assert res1["verification"]["is_valid"] is True

    # 2. Marketing: "total ad spend and total clicks by channel" -> defaults to data_observed (numeric aggregates)
    mkt_clean = get_dataset_dataframe("marketing_campaign_messy.csv", prefer_cleaned=True)
    mask_sp = get_column_imputed_mask(mkt_clean, "Ad_Spend")
    mask_cl = get_column_imputed_mask(mkt_clean, "Clicks")
    mkt_obs = mkt_clean[~mask_sp & ~mask_cl] if (mask_sp.any() or mask_cl.any()) else mkt_clean
    mkt_valid = mkt_obs[mkt_obs["Channel"].notna() & mkt_obs["Ad_Spend"].notna() & mkt_obs["Clicks"].notna()]
    expected_spend = mkt_valid.groupby("Channel")["Ad_Spend"].sum().round(2).to_dict()
    expected_clicks = mkt_valid.groupby("Channel")["Clicks"].sum().round(2).to_dict()

    res2 = process_chat_question(
        db=db_session,
        job_id="",
        question="total ad spend and total clicks by channel",
        dataset_id="marketing_campaign_messy.csv"
    )
    assert "data_observed" in res2["answer"]
    assert f"n={len(mkt_valid)}" in res2["answer"]
    for ch, exp_sp in expected_spend.items():
        assert f"{exp_sp:,.2f}" in res2["answer"] or f"{exp_sp:.2f}" in res2["answer"]
    for ch, exp_cl in expected_clicks.items():
        assert f"{exp_cl:,.2f}" in res2["answer"] or f"{exp_cl:.2f}" in res2["answer"]
    assert res2["verification"]["is_valid"] is True

    # 3. Retail: "number of transactions per region" -> data_clean
    retail_clean = get_dataset_dataframe("retail_sales_messy.csv", prefer_cleaned=True)
    expected_region_counts = retail_clean["Region"].value_counts().to_dict()

    res3 = process_chat_question(
        db=db_session,
        job_id="",
        question="number of transactions per region",
        dataset_id="retail_sales_messy.csv"
    )
    retail_valid = retail_clean[retail_clean["Region"].notna()]
    assert f"n={len(retail_valid)}" in res3["answer"]
    for reg, exp_count in expected_region_counts.items():
        assert f"{reg}: transaction count was {exp_count}" in res3["answer"] or f"{exp_count}" in res3["answer"]
    assert res3["verification"]["is_valid"] is True

    # 4. HR: "how many employees per department" -> data_clean
    expected_hr_counts = hr_clean["Department"].value_counts().to_dict()

    res4 = process_chat_question(
        db=db_session,
        job_id="",
        question="how many employees per department",
        dataset_id="hr_attrition_messy.csv"
    )
    hr_valid = hr_clean[hr_clean["Department"].notna()]
    assert f"n={len(hr_valid)}" in res4["answer"]
    for dept, exp_cnt in expected_hr_counts.items():
        assert f"{dept}: employee count was {exp_cnt}" in res4["answer"]
    assert res4["verification"]["is_valid"] is True


def test_old_9_questions_execution(db_session, monkeypatch):
    """Test all old 9 demo questions execute cleanly and verify numeric citations."""
    monkeypatch.setenv("LLM_PROVIDER", "heuristic")

    old_9_questions = [
        # Retail
        ("retail_sales_messy.csv", "What is the overall trend in monthly retail sales and is it statistically significant?"),
        ("retail_sales_messy.csv", "What is the share of Credit Card payments among non-missing payment method rows?"),
        ("retail_sales_messy.csv", "What is the average customer age across the different retail store regions?"),
        # HR
        ("hr_attrition_messy.csv", "Which department has the highest employee attrition rate and is the difference statistically significant?"),
        ("hr_attrition_messy.csv", "What is the average annual salary by department among observed non-missing records?"),
        ("hr_attrition_messy.csv", "How does customer churn correlate with employee satisfaction levels?"),
        # Marketing
        ("marketing_campaign_messy.csv", "Which marketing channel delivers the highest conversion rate?"),
        ("marketing_campaign_messy.csv", "What is the total ad spend and total clicks by marketing channel?"),
        ("marketing_campaign_messy.csv", "What is the average customer credit score across the different marketing channels?")
    ]

    for ds, q in old_9_questions:
        res = process_chat_question(db=db_session, job_id="", question=q, dataset_id=ds)
        assert res["answer"] is not None
        assert len(res["answer"]) > 10
        assert res["verification"]["is_valid"] is True
        assert "None" not in res["answer"]
        assert "nan" not in res["answer"].lower()


def test_no_unrelated_insights_appended():
    """Verify that insights not sharing a column with the question are never appended."""
    retail_cols = ["Transaction_ID", "Date", "Customer_ID", "Product", "Category", "Region", "Quantity", "Unit_Price", "Payment_Method"]
    q = "What is the breakdown of Payment_Method?"
    q_cols = extract_question_columns(q, retail_cols)
    assert "Payment_Method" in q_cols

    unrelated_insight = {
        "id": "ins_1",
        "title": "High Quantity Outliers",
        "summary": "Large quantities detected in East region.",
        "columns": ["Quantity", "Region"]
    }
    assert not insight_shares_column(unrelated_insight, q_cols)

    related_insight = {
        "id": "ins_2",
        "title": "Credit Card Payment Dominance",
        "summary": "Credit card is the most common payment method.",
        "columns": ["Payment_Method"]
    }
    assert insight_shares_column(related_insight, q_cols)


def test_stripped_claims_fallback(db_session, monkeypatch):
    """Test that if claims are stripped, the answer states it could not be verified and displays query results."""
    from backend.app.agent.llm_client import ChatResult, TokenUsage

    class HallucinatingClient:
        provider_name = "hallucinating_test"
        def generate_chat_answer(self, question, context, failing_claims=None):
            # Returns completely unverified claim numbers that fail verification
            return ChatResult(
                answer="There were 999999 fictitious widgets sold.",
                claims=[{"text": "999999 widgets", "source_id": "query_sql", "metric_key": "widgets", "value": 999999.0, "unit": "count"}],
                usage=TokenUsage(total_tokens="0"),
                provider="hallucinating_test",
                latency_seconds=0.1
            )

    monkeypatch.setattr("backend.app.services.chat_service.get_llm_client", lambda *args, **kwargs: HallucinatingClient())

    res = process_chat_question(
        db=db_session,
        job_id="",
        question="number of transactions per region",
        dataset_id="retail_sales_messy.csv"
    )
    # The hallucinated sentence should be stripped, falling back to verified query results
    assert "could not be verified" in res["answer"].lower()
    assert "999999" not in res["answer"]
    assert "Query result from" in res["answer"] or "data_clean" in res["answer"]


def test_insight_shares_metric_column_strictness():
    """Verify that an insight is included only if it shares the question's METRIC column."""
    hr_cols = ["Employee_ID", "Age", "Gender", "Department", "Annual_Salary", "Tenure_Years", "Satisfaction_Level", "Performance_Score", "Attrition"]
    q_att = "Which department has the highest employee attrition rate and is the difference statistically significant?"
    q_cols = extract_question_columns(q_att, hr_cols)

    salary_insight = {
        "id": "insight-seg-Department-Annual_Salary",
        "title": "Difference in Annual_Salary across Department",
        "summary": "Average salary varies across departments.",
        "metric_values": {"segment_column": "Department", "metric_column": "Annual_Salary"},
        "columns": ["Department", "Annual_Salary"]
    }
    # Sharing only Department (segment column) must NOT match
    assert not insight_shares_column(salary_insight, q_cols, question=q_att)

    attrition_insight = {
        "id": "insight-seg-Department-Attrition",
        "title": "Difference in Attrition across Department",
        "summary": "Attrition rate varies across departments.",
        "metric_values": {"segment_column": "Department", "metric_column": "Attrition"},
        "columns": ["Department", "Attrition"]
    }
    # Sharing Attrition (metric column) MUST match
    assert insight_shares_column(attrition_insight, q_cols, question=q_att)


def test_a3_retail_trend_and_hr_highest_attrition(db_session, monkeypatch):
    """Verify A3 direct answers for Retail trend (suppression explanation) and HR attrition (Marketing highest + significance caveat)."""
    monkeypatch.setenv("LLM_PROVIDER", "heuristic")

    # Retail trend: says what was checked and why no trend is available (suppressed rule exclusion_rate > 0.5)
    res_retail = process_chat_question(
        db=db_session,
        job_id="",
        question="What is the overall trend in monthly retail sales and is it statistically significant?",
        dataset_id="retail_sales_messy.csv"
    )
    ans_retail = res_retail["answer"]
    assert "Quantity" in ans_retail
    assert "Date" in ans_retail or "monthly" in ans_retail.lower()
    assert "exclusion_rate > 0.5" in ans_retail
    assert "65.0" in ans_retail
    assert "42" in ans_retail
    assert "120" in ans_retail
    assert res_retail["verification"]["is_valid"] is True

    # HR highest attrition: names Marketing, rate 68.18%, n=22, significance caveat p=0.2947
    res_hr = process_chat_question(
        db=db_session,
        job_id="",
        question="Which department has the highest employee attrition rate and is the difference statistically significant?",
        dataset_id="hr_attrition_messy.csv"
    )
    ans_hr = res_hr["answer"]
    assert "Marketing" in ans_hr
    assert "68.18" in ans_hr
    assert "22" in ans_hr
    assert "0.2947" in ans_hr
    assert "not statistically significant" in ans_hr.lower()
    assert res_hr["verification"]["is_valid"] is True

