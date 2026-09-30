"""Data loader helper to retrieve DataFrames for tools by dataset_id or filename."""
from pathlib import Path
from typing import Any, Optional
import pandas as pd
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.dataset import Dataset
from backend.app.services.storage import StorageService

def _attach_mask_if_present(df: pd.DataFrame, file_path: Path) -> pd.DataFrame:
    """Attach companion boolean imputed mask and cleaning report to df.attrs if present on disk."""
    import json
    mask_candidate = file_path.with_name(f"{file_path.stem}_imputed_mask.csv")
    if mask_candidate.exists() and mask_candidate.is_file():
        try:
            mask_df = pd.read_csv(mask_candidate)
            df.attrs["imputed_mask"] = mask_df
        except Exception:
            pass

    report_candidate = file_path.with_name(f"{file_path.stem}_cleaning_report.json")
    if report_candidate.exists() and report_candidate.is_file():
        try:
            with open(report_candidate, "r", encoding="utf-8") as f:
                df.attrs["cleaning_report"] = json.load(f)
        except Exception:
            pass
    return df

def get_dataset_cleaning_report(df: pd.DataFrame, dataset_id: str) -> dict:
    """Retrieve cleaning report dictionary from df.attrs or on-disk companion file."""
    import json
    if "cleaning_report" in df.attrs and isinstance(df.attrs["cleaning_report"], dict):
        return df.attrs["cleaning_report"]
    stem = Path(dataset_id).stem
    candidates = [
        settings.PROCESSED_DIR / f"{stem}_cleaned_cleaning_report.json",
        settings.PROCESSED_DIR / f"{stem}_cleaning_report.json",
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file():
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    df.attrs["cleaning_report"] = data
                    return data
            except Exception:
                pass
    return {}

def get_column_imputed_mask(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Return a boolean Series indicating which rows of df[col] were imputed.
    Uses df.attrs['imputed_mask'] or indicator column fallback.
    """
    mask_df = df.attrs.get("imputed_mask")
    if isinstance(mask_df, pd.DataFrame) and col in mask_df.columns:
        return mask_df[col].astype(bool)
    indicator = f"_imputed_{col}"
    if indicator in df.columns:
        return df[indicator].astype(bool)
    return pd.Series(False, index=df.index)

def get_dataset_dataframe(dataset_id: Any, prefer_cleaned: bool = False) -> pd.DataFrame:
    """
    Resolve dataset by ID (UUID in DB) or filename (in data/samples or backend/tests/test_datasets),
    or return directly if already a DataFrame.
    When prefer_cleaned=True, returns the cleaned dataframe (with normalized casing/whitespace)
    so segment_compare and the orchestrator always operate on clean data.
    """
    if isinstance(dataset_id, pd.DataFrame):
        return dataset_id
    stem = Path(dataset_id).stem

    # 1. If prefer_cleaned, check processed dir first (only if companion mask also exists)
    if prefer_cleaned:
        for fname in [f"{stem}_cleaned.csv", f"{dataset_id}_cleaned.csv"]:
            candidate = settings.PROCESSED_DIR / fname
            mask_candidate = candidate.with_name(f"{candidate.stem}_imputed_mask.csv")
            if candidate.exists() and candidate.is_file() and mask_candidate.exists():
                df = StorageService.load_dataframe(candidate, "csv")
                return _attach_mask_if_present(df, candidate)

    # 2. Look up in Database
    db = SessionLocal()
    try:
        record = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if record:
            if prefer_cleaned and record.cleaned_file_path and Path(record.cleaned_file_path).exists():
                df = StorageService.load_dataframe(Path(record.cleaned_file_path), "csv")
                return _attach_mask_if_present(df, Path(record.cleaned_file_path))
            if record.file_path and Path(record.file_path).exists():
                return StorageService.load_dataframe(Path(record.file_path), record.file_type)
    finally:
        db.close()

    # 3. Check files in samples, uploads, and test_datasets
    for search_dir in [settings.UPLOAD_DIR, settings.SAMPLES_DIR, Path("backend/tests/test_datasets")]:
        for candidate in [search_dir / dataset_id, search_dir / f"{dataset_id}.csv", search_dir / f"{stem}.csv"]:
            if candidate.exists() and candidate.is_file():
                ext = candidate.suffix.lstrip(".").lower()
                df = StorageService.load_dataframe(candidate, ext)
                if prefer_cleaned:
                    from backend.app.services.cleaning import clean_data
                    from shared.schemas.dataset import DatasetCleaningOptions
                    cleaned_path = settings.PROCESSED_DIR / f"{stem}_cleaned.csv"
                    cleaned_df, _ = clean_data(
                        df=df,
                        dataset_id=stem,
                        output_path=cleaned_path,
                        options=DatasetCleaningOptions(drop_duplicates=True, strip_whitespace=True)
                    )
                    return cleaned_df
                return df

    # 4. Fallback check directly in processed dir if not found elsewhere
    for candidate in [settings.PROCESSED_DIR / dataset_id, settings.PROCESSED_DIR / f"{dataset_id}.csv"]:
        if candidate.exists() and candidate.is_file():
            df = StorageService.load_dataframe(candidate, "csv")
            return _attach_mask_if_present(df, candidate)

    raise ValueError(f"Dataset with ID or filename '{dataset_id}' could not be found.")
