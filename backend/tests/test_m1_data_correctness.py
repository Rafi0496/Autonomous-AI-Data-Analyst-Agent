"""Targeted tests for Milestone 1: Data Correctness.

Tests:
a) Data quality score computed on RAW data (missingness, invalid and sentinel rate, duplicates, imputation share)
   with cleaned score as a separate field; HR visibly scores low.
b) Imputation policy: never impute identifier-like columns, date columns, or categorical columns used as segments;
   numeric imputation keeps its companion mask.
c) Sampling disclosure: when dataset sampled (>25,000 rows), insights, narrative, chat and reports state
   'random sample of N of M rows (seed S)' with fixed seed.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from backend.app.core.config import settings
from backend.app.services.cleaning import clean_data
from backend.app.services.profiling import profile_dataset
from backend.app.services.insights import generate_insights
from backend.app.services.summary import write_summary
from shared.schemas.dataset import DatasetCleaningOptions


def test_m1_raw_vs_cleaned_quality_scores(sample_datasets_dir: Path):
    """Test raw vs cleaned quality score calculation across 3 sample datasets."""
    hr_path = sample_datasets_dir / "hr_attrition_messy.csv"
    mkt_path = sample_datasets_dir / "marketing_campaign_messy.csv"
    retail_path = sample_datasets_dir / "retail_sales_messy.csv"

    # 1. HR Attrition: 46% salary missing/invalid, 31 negative salaries, 18 impossible ages
    df_hr = pd.read_csv(hr_path)
    clean_hr, res_hr = clean_data(df_hr, "hr_test")
    
    assert res_hr.raw_quality_score is not None
    assert res_hr.cleaned_quality_score is not None
    # HR must visibly score low
    assert res_hr.raw_quality_score < 60.0, f"HR raw score {res_hr.raw_quality_score} was expected to score < 60.0"
    assert res_hr.cleaned_quality_score > res_hr.raw_quality_score

    prof_hr = profile_dataset(clean_hr, "hr_test")
    assert prof_hr.quality_summary.quality_score == res_hr.raw_quality_score
    assert prof_hr.quality_summary.raw_quality_score == res_hr.raw_quality_score
    assert prof_hr.quality_summary.cleaned_quality_score == res_hr.cleaned_quality_score

    # 2. Marketing Campaign
    df_mkt = pd.read_csv(mkt_path)
    clean_mkt, res_mkt = clean_data(df_mkt, "mkt_test")
    assert res_mkt.raw_quality_score > res_hr.raw_quality_score
    assert res_mkt.cleaned_quality_score >= res_mkt.raw_quality_score

    # 3. Retail Sales
    df_retail = pd.read_csv(retail_path)
    clean_retail, res_retail = clean_data(df_retail, "retail_test")
    assert res_retail.raw_quality_score > res_hr.raw_quality_score
    assert res_retail.cleaned_quality_score >= res_retail.raw_quality_score


def test_m1_imputation_policy(sample_datasets_dir: Path):
    """Assert never impute identifier-like columns, date columns, or categorical columns used as segments."""
    # HR dataset
    df_hr = pd.read_csv(sample_datasets_dir / "hr_attrition_messy.csv")
    clean_hr, res_hr = clean_data(df_hr, "hr_test")

    # Categorical segments must NOT be imputed
    assert res_hr.column_imputation_stats["Department"]["imputation_skipped"] is True
    assert res_hr.column_imputation_stats["Department"]["imputed_count"] == 0
    assert res_hr.column_imputation_stats["Gender"]["imputation_skipped"] is True
    assert res_hr.column_imputation_stats["Attrition"]["imputation_skipped"] is True
    
    # Date column must NOT be imputed
    assert res_hr.column_imputation_stats["Last_Promotion_Year"]["imputation_skipped"] is True
    assert res_hr.column_imputation_stats["Last_Promotion_Year"]["skip_reason"] == "date_column"

    # Numeric metrics MUST be imputed and tracked with mask
    assert res_hr.column_imputation_stats["Annual_Salary"]["imputation_skipped"] is False
    assert res_hr.column_imputation_stats["Annual_Salary"]["imputed_count"] > 0
    assert res_hr.column_imputation_stats["Age"]["imputation_skipped"] is False
    assert res_hr.column_imputation_stats["Age"]["imputed_count"] > 0
    
    mask = clean_hr.attrs["imputed_mask"]
    assert mask["Annual_Salary"].sum() > 0
    assert mask["Age"].sum() > 0

    # Retail dataset: Customer_ID is an identifier, Region and Payment_Method are segments, Date is a date
    df_retail = pd.read_csv(sample_datasets_dir / "retail_sales_messy.csv")
    clean_retail, res_retail = clean_data(df_retail, "retail_test")
    assert res_retail.column_imputation_stats["Customer_ID"]["imputation_skipped"] is True
    assert res_retail.column_imputation_stats["Customer_ID"]["skip_reason"] == "identifier_column"
    assert res_retail.column_imputation_stats["Region"]["imputation_skipped"] is True
    assert res_retail.column_imputation_stats["Payment_Method"]["imputation_skipped"] is True
    assert res_retail.column_imputation_stats["Quantity"]["imputed_count"] > 0

    # Marketing dataset: Channel and Target_Audience are segments, Date is a date
    df_mkt = pd.read_csv(sample_datasets_dir / "marketing_campaign_messy.csv")
    clean_mkt, res_mkt = clean_data(df_mkt, "mkt_test")
    assert res_mkt.column_imputation_stats["Channel"]["imputation_skipped"] is True
    assert res_mkt.column_imputation_stats["Target_Audience"]["imputation_skipped"] is True
    assert res_mkt.column_imputation_stats["Date"]["imputation_skipped"] is True
    assert res_mkt.column_imputation_stats["Ad_Spend"]["imputed_count"] > 0


def test_m1_sampling_disclosure_synthetic():
    """Test sampling disclosure with synthetic dataset of >25,000 rows."""
    n_rows = 26_000
    df_large = pd.DataFrame({
        "id": range(n_rows),
        "department": np.random.choice(["Sales", "Engineering", "Marketing", "HR"], size=n_rows),
        "salary": np.random.normal(75000, 15000, size=n_rows),
        "performance": np.random.choice([1, 2, 3, 4, 5], size=n_rows)
    })
    assert len(df_large) > 25000

    clean_large, res_large = clean_data(df_large, "synthetic_large")
    assert res_large.is_sampled is True
    assert res_large.population_row_count == 26000
    assert res_large.sample_row_count == 10000
    assert res_large.sampling_seed == 42
    expected_disclosure = "random sample of 10,000 of 26,000 rows (seed 42)"
    assert expected_disclosure in res_large.sampling_disclosure

    # Test propagation to profile
    prof = profile_dataset(clean_large, "synthetic_large")
    assert prof.quality_summary.sampling_disclosure is not None
    assert expected_disclosure in prof.quality_summary.sampling_disclosure

    # Test propagation to executive summary narrative
    prof_dict = prof.model_dump()
    summary = write_summary(
        structured_results=[],
        dataset_profile=prof_dict,
        insights=[]
    )
    assert expected_disclosure in summary["executive_summary"]
