"""Data loader helper to retrieve DataFrames for tools by dataset_id or filename."""
from pathlib import Path
from typing import Optional
import pandas as pd
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.dataset import Dataset
from backend.app.services.storage import StorageService

def get_dataset_dataframe(dataset_id: str, prefer_cleaned: bool = True) -> pd.DataFrame:
    """
    Resolve dataset by ID (UUID in DB) or filename (in data/samples or backend/tests/test_datasets).
    Returns a pandas DataFrame.
    """
    # 1. Check if dataset_id matches a file path directly in samples
    for search_dir in [settings.SAMPLES_DIR, settings.UPLOAD_DIR, settings.PROCESSED_DIR, Path("backend/tests/test_datasets")]:
        candidate = search_dir / dataset_id
        if candidate.exists() and candidate.is_file():
            ext = candidate.suffix.lstrip(".").lower()
            return StorageService.load_dataframe(candidate, ext)
        
        # Also check with .csv suffix if omitted
        candidate_csv = search_dir / f"{dataset_id}.csv"
        if candidate_csv.exists() and candidate_csv.is_file():
            return StorageService.load_dataframe(candidate_csv, "csv")

    # 2. Look up in Database
    db = SessionLocal()
    try:
        record = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if record:
            if prefer_cleaned and record.cleaned_file_path and Path(record.cleaned_file_path).exists():
                return StorageService.load_dataframe(Path(record.cleaned_file_path), "csv")
            return StorageService.load_dataframe(Path(record.file_path), record.file_type)
    finally:
        db.close()

    raise ValueError(f"Dataset with ID or filename '{dataset_id}' could not be found.")
