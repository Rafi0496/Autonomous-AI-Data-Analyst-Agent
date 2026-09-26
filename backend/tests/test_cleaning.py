"""Unit tests for the clean_data() pipeline run against 3 real messy datasets."""
from pathlib import Path
import pandas as pd
import pytest
from backend.app.services.cleaning import clean_data
from shared.schemas.dataset import DatasetCleaningOptions

def test_clean_retail_sales(sample_datasets_dir: Path):
    """Test cleaning on messy retail dataset with duplicates, currency strings, and missing values."""
    file_path = sample_datasets_dir / "retail_sales_messy.csv"
    assert file_path.exists(), f"Sample dataset not found at {file_path}"
    
    df = pd.read_csv(file_path)
    orig_rows, orig_cols = df.shape
    assert orig_rows > 0

    cleaned_df, result = clean_data(
        df=df,
        dataset_id="test_retail",
        options=DatasetCleaningOptions(drop_duplicates=True, strip_whitespace=True)
    )

    # 1. Duplicates must be removed
    assert result.duplicates_removed > 0
    assert len(cleaned_df) < orig_rows
    assert len(cleaned_df) == orig_rows - result.duplicates_removed

    # 2. Currency strings in 'Unit_Price' should be converted to numeric float
    assert pd.api.types.is_numeric_dtype(cleaned_df["Unit_Price"])
    assert cleaned_df["Unit_Price"].isnull().sum() == 0  # Imputed

    # 3. Leading/trailing whitespace in strings should be stripped
    for val in cleaned_df["Category"].dropna():
        assert val == val.strip()

    # 4. Logs must document steps
    assert len(result.logs) > 0
    assert any(log.step == "remove_duplicates" for log in result.logs)
    assert any(log.step == "impute_numeric_nulls" for log in result.logs)

def test_clean_hr_attrition(sample_datasets_dir: Path):
    """Test cleaning on messy HR dataset with mixed salaries, outliers, and duplicates."""
    file_path = sample_datasets_dir / "hr_attrition_messy.csv"
    assert file_path.exists()
    
    df = pd.read_csv(file_path)
    orig_rows = len(df)
    
    cleaned_df, result = clean_data(
        df=df,
        dataset_id="test_hr",
        options=DatasetCleaningOptions(drop_duplicates=True)
    )

    # Duplicates removed
    assert result.duplicates_removed > 0
    # Annual salary coerced to numeric
    assert pd.api.types.is_numeric_dtype(cleaned_df["Annual_Salary"])
    assert cleaned_df["Annual_Salary"].isnull().sum() == 0
    # Age nulls imputed
    assert cleaned_df["Age"].isnull().sum() == 0

def test_clean_marketing_campaign(sample_datasets_dir: Path):
    """Test cleaning on marketing campaign dataset with currency spend, zero/null impressions."""
    file_path = sample_datasets_dir / "marketing_campaign_messy.csv"
    assert file_path.exists()
    
    df = pd.read_csv(file_path)
    cleaned_df, result = clean_data(
        df=df,
        dataset_id="test_mkt",
        options=DatasetCleaningOptions(drop_duplicates=True)
    )

    # Ad spend numeric
    assert pd.api.types.is_numeric_dtype(cleaned_df["Ad_Spend"])
    assert cleaned_df["Ad_Spend"].isnull().sum() == 0
    # Impressions & Clicks nulls imputed
    assert cleaned_df["Impressions"].isnull().sum() == 0
    assert cleaned_df["Clicks"].isnull().sum() == 0

def test_clean_data_custom_options():
    """Test that custom cleaning options are respected."""
    data = {
        "Col A ": [" x ", " y ", " x ", " x "],
        "Col B": [10.0, None, 10.0, 10.0],
        "Constant": [1, 1, 1, 1]
    }
    df = pd.DataFrame(data)
    
    # Run with drop_duplicates=False, remove_constant_columns=True
    cleaned_df, result = clean_data(
        df=df,
        dataset_id="custom_opt",
        options=DatasetCleaningOptions(drop_duplicates=False, remove_constant_columns=True)
    )
    
    assert result.duplicates_removed == 0
    assert "Constant" in result.dropped_columns
    assert "Constant" not in cleaned_df.columns
    assert "Col A" in cleaned_df.columns  # Header stripped
