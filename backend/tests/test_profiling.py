"""Unit tests for the profile_dataset() pipeline run against 3 real messy datasets."""
from pathlib import Path
import pandas as pd
import pytest
from backend.app.services.profiling import profile_dataset

def test_profile_retail_sales(sample_datasets_dir: Path):
    """Test data profiling on retail sales dataset."""
    file_path = sample_datasets_dir / "retail_sales_messy.csv"
    assert file_path.exists()
    
    df = pd.read_csv(file_path)
    profile = profile_dataset(df, dataset_id="retail_prof")

    assert profile.row_count == len(df)
    assert profile.column_count == len(df.columns)
    assert profile.memory_usage_bytes > 0
    assert "Quantity" in profile.columns

    qty_prof = profile.columns["Quantity"]
    assert qty_prof.inferred_type == "numeric"
    assert "min" in qty_prof.stats
    assert "max" in qty_prof.stats
    assert "outliers_count" in qty_prof.stats

    # Quality summary checks
    assert profile.quality_summary.duplicate_rows > 0
    assert profile.quality_summary.missing_cells > 0
    assert 0.0 <= profile.quality_summary.quality_score <= 100.0
    assert len(profile.quality_summary.warnings) > 0

def test_profile_hr_attrition(sample_datasets_dir: Path):
    """Test data profiling on HR attrition dataset."""
    file_path = sample_datasets_dir / "hr_attrition_messy.csv"
    assert file_path.exists()
    
    df = pd.read_csv(file_path)
    profile = profile_dataset(df, dataset_id="hr_prof")

    assert profile.row_count == len(df)
    assert "Department" in profile.columns
    dept_prof = profile.columns["Department"]
    assert dept_prof.inferred_type in ["categorical", "text"]
    assert len(dept_prof.stats.get("top_values", [])) > 0

def test_profile_marketing_campaign(sample_datasets_dir: Path):
    """Test data profiling on marketing campaign dataset."""
    file_path = sample_datasets_dir / "marketing_campaign_messy.csv"
    assert file_path.exists()
    
    df = pd.read_csv(file_path)
    profile = profile_dataset(df, dataset_id="mkt_prof")

    assert profile.row_count == len(df)
    assert "Impressions" in profile.columns
    imp_prof = profile.columns["Impressions"]
    assert imp_prof.inferred_type == "numeric"

def test_profile_edge_cases():
    """Test edge cases: empty-like dataframe, single row, all nulls."""
    df_edge = pd.DataFrame({
        "all_null": [None, None, None],
        "single_val": [5, 5, 5],
        "binary": [True, False, True]
    })
    profile = profile_dataset(df_edge, dataset_id="edge_test")
    
    assert profile.columns["all_null"].null_count == 3
    assert profile.columns["all_null"].null_percentage == 100.0
    assert profile.columns["single_val"].unique_count == 1
    assert profile.columns["binary"].inferred_type == "boolean"
    assert profile.quality_summary.quality_score < 100.0
