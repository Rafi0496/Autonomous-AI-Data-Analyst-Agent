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


# =========================================================================
# Cross-Dataset Casing Validation Tests
# =========================================================================

_DATASETS = [
    ("retail_sales_messy.csv", "test_retail"),
    ("hr_attrition_messy.csv", "test_hr"),
    ("marketing_campaign_messy.csv", "test_mkt"),
]


def _get_categorical_cols(df: pd.DataFrame) -> list:
    """Return low-cardinality string columns (likely categorical)."""
    cats = []
    for c in df.columns:
        if df[c].dtype == "object" or str(df[c].dtype).startswith("str") or str(df[c].dtype).startswith("string"):
            if df[c].nunique(dropna=True) < len(df) * 0.50:
                cats.append(c)
    return cats


@pytest.mark.parametrize("filename,ds_id", _DATASETS)
def test_no_case_duplicates_after_cleaning(sample_datasets_dir: Path, filename: str, ds_id: str):
    """After clean_data(), no categorical column should have two values differing only by case/whitespace."""
    file_path = sample_datasets_dir / filename
    assert file_path.exists(), f"Dataset not found: {file_path}"

    df = pd.read_csv(file_path)
    cleaned_df, _result = clean_data(
        df=df,
        dataset_id=ds_id,
        options=DatasetCleaningOptions(drop_duplicates=True, strip_whitespace=True)
    )

    violations = []
    for col in _get_categorical_cols(cleaned_df):
        values = cleaned_df[col].dropna().unique().tolist()
        lower_map: dict = {}
        for v in values:
            key = str(v).strip().lower()
            if key in lower_map and lower_map[key] != str(v):
                violations.append(f"{col}: '{lower_map[key]}' vs '{v}'")
            else:
                lower_map[key] = str(v)

    assert violations == [], (
        f"Categorical columns in {filename} have case-duplicate values after cleaning:\n"
        + "\n".join(violations)
    )


def test_electronics_casing_bug_fixed(sample_datasets_dir: Path):
    """Regression test: 'Electronics' and 'electronics' must collapse after cleaning."""
    file_path = sample_datasets_dir / "retail_sales_messy.csv"
    assert file_path.exists()

    df = pd.read_csv(file_path)
    cleaned_df, result = clean_data(
        df=df,
        dataset_id="test_retail_casing",
        options=DatasetCleaningOptions(drop_duplicates=True, strip_whitespace=True)
    )

    categories = cleaned_df["Category"].dropna().unique().tolist()
    lower_cats = [c.lower() for c in categories]
    assert len(lower_cats) == len(set(lower_cats)), (
        f"Case-duplicate categories still exist: {categories}"
    )
    # Verify the normalization step was logged
    assert any(log.step == "normalize_categorical_casing" for log in result.logs)


def test_canonical_casing(sample_datasets_dir: Path):
    """Assert canonical-form selection preserves acronyms and brand names (HR, LinkedIn, Google Ads)."""
    # 1. Direct synthetic series test
    synthetic_df = pd.DataFrame({
        "dept": ["HR", "HR", "Hr", "Engineering", "engineering"],
        "channel": ["LinkedIn", "linkedin", "LinkedIn", "Google Ads", "google ads"],
        "val": [1, 2, 3, 4, 5]
    })
    cleaned_syn, _ = clean_data(synthetic_df, dataset_id="syn_case")
    assert "HR" in cleaned_syn["dept"].values
    assert "Hr" not in cleaned_syn["dept"].values
    assert "LinkedIn" in cleaned_syn["channel"].values
    assert "Linkedin" not in cleaned_syn["channel"].values
    assert "Google Ads" in cleaned_syn["channel"].values

    # 2. Check across real messy datasets that all expected labels are present
    hr_df = pd.read_csv(sample_datasets_dir / "hr_attrition_messy.csv")
    cleaned_hr, _ = clean_data(hr_df, dataset_id="hr_clean")
    hr_depts = set(cleaned_hr["Department"].dropna().unique().tolist())
    assert {"Engineering", "HR", "Marketing", "Sales"}.issubset(hr_depts)
    assert "Hr" not in hr_depts
    assert "engineering" not in hr_depts
    assert "marketing" not in hr_depts
    assert "sales" not in hr_depts

    retail_df = pd.read_csv(sample_datasets_dir / "retail_sales_messy.csv")
    cleaned_retail, _ = clean_data(retail_df, dataset_id="retail_clean")
    retail_cats = set(cleaned_retail["Category"].dropna().unique().tolist())
    assert {"Accessories", "Electronics", "Office Supplies"}.issubset(retail_cats)

    mkt_df = pd.read_csv(sample_datasets_dir / "marketing_campaign_messy.csv")
    cleaned_mkt, _ = clean_data(mkt_df, dataset_id="mkt_clean")
    mkt_channels = set(cleaned_mkt["Channel"].dropna().unique().tolist())
    assert {"LinkedIn", "Google Ads", "Email", "Facebook", "Instagram"}.issubset(mkt_channels)
    assert "Linkedin" not in mkt_channels
    assert "google ads" not in mkt_channels


def test_domain_validity_rules(sample_datasets_dir: Path):
    """Assert negative business metrics and invalid ages are sanitized to NaN before imputation."""
    hr_df = pd.read_csv(sample_datasets_dir / "hr_attrition_messy.csv")
    assert (hr_df["Age"] > 100).sum() > 0
    raw_salaries = pd.to_numeric(hr_df["Annual_Salary"].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce")
    assert (raw_salaries < 0).sum() > 0

    cleaned_hr, result = clean_data(hr_df, dataset_id="hr_domain_val")
    # Verify Age=150 is removed and treated as invalid (not outlier or sentinel)
    assert (cleaned_hr["Age"] > 100).sum() == 0
    assert (cleaned_hr["Age"] < 0).sum() == 0
    age_rule = next((r for r in result.invalid_values_detected if r["column"] == "Age"), None)
    assert age_rule is not None
    assert age_rule["count"] == 18

    # Verify negative salary in Sales is converted and imputed
    assert (cleaned_hr["Annual_Salary"] < 0).sum() == 0
    sales_salaries = cleaned_hr.loc[cleaned_hr["Department"] == "Sales", "Annual_Salary"]
    assert (sales_salaries < 0).sum() == 0
    assert sales_salaries.min() > 0
    sal_rule = next((r for r in result.invalid_values_detected if r["column"] == "Annual_Salary"), None)
    assert sal_rule is not None
    assert sal_rule["count"] >= 1


def test_sentinel_detection(sample_datasets_dir: Path):
    """Assert Quantity=999 in retail sales is detected as sentinel and replaced prior to median imputation."""
    retail_df = pd.read_csv(sample_datasets_dir / "retail_sales_messy.csv")
    assert (retail_df["Quantity"] == 999).sum() >= 3

    cleaned_df, result = clean_data(retail_df, dataset_id="retail_sentinel")
    assert (cleaned_df["Quantity"] == 999).sum() == 0
    assert cleaned_df["Quantity"].max() <= 20.0
    sentinel_entry = next((s for s in result.sentinels_detected if s["column"] == "Quantity"), None)
    assert sentinel_entry is not None
    assert sentinel_entry["sentinel_value"] == 999.0
    assert sentinel_entry["count"] >= 3
    assert "Quantity" in result.column_imputation_stats
    assert result.column_imputation_stats["Quantity"]["imputed_count"] > 0

