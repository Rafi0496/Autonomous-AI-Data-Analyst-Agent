from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_optional_current_user
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.dataset import Dataset
from backend.app.models.user import User
from backend.app.services.cleaning import clean_data
from backend.app.services.profiling import profile_dataset
from backend.app.services.storage import StorageService
from shared.constants import DatasetStatus
from shared.schemas.dataset import (
    DatasetCleaningOptions,
    DatasetCleaningResult,
    DatasetListItem
)
from shared.schemas.profile import DatasetProfile

router = APIRouter()

def check_dataset_access(dataset: Dataset, current_user: Optional[User]):
    """Verify that current_user has access to private dataset, allowing shared public/demo datasets."""
    if not settings.ALLOW_ANONYMOUS and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )
    if dataset.user_id and (not current_user or dataset.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this dataset."
        )

@router.get("", response_model=List[DatasetListItem])
def list_datasets(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """List datasets scoped to current authenticated user or public/demo datasets."""
    if not settings.ALLOW_ANONYMOUS and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )
    query = db.query(Dataset)
    if current_user:
        query = query.filter((Dataset.user_id == current_user.id) | (Dataset.user_id == None))
    else:
        query = query.filter(Dataset.user_id == None)

        
    datasets = query.order_by(Dataset.created_at.desc()).offset(skip).limit(limit).all()
    return [
        DatasetListItem(
            id=d.id,
            filename=d.filename,
            file_type=d.file_type,
            file_size_bytes=d.file_size_bytes,
            row_count=d.row_count,
            column_count=d.column_count,
            status=DatasetStatus(d.status),
            created_at=d.created_at.isoformat(),
            updated_at=d.updated_at.isoformat()
        )
        for d in datasets
    ]

@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Get metadata for a specific dataset."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID {dataset_id} not found."
        )
    check_dataset_access(dataset, current_user)
    return {
        "id": dataset.id,
        "filename": dataset.filename,
        "file_type": dataset.file_type,
        "file_size_bytes": dataset.file_size_bytes,
        "row_count": dataset.row_count,
        "column_count": dataset.column_count,
        "status": dataset.status,
        "has_cleaned_version": bool(dataset.cleaned_file_path),
        "has_profile": bool(dataset.profile_json),
        "cleaning_summary": dataset.get_cleaning_summary(),
        "created_at": dataset.created_at.isoformat(),
        "updated_at": dataset.updated_at.isoformat()
    }

@router.post("/{dataset_id}/clean", response_model=DatasetCleaningResult)
def clean_dataset_endpoint(
    dataset_id: str,
    options: Optional[DatasetCleaningOptions] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Execute the data cleaning pipeline on the specified dataset."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID {dataset_id} not found."
        )
    check_dataset_access(dataset, current_user)

    file_path = Path(dataset.file_path)
    df = StorageService.load_dataframe(file_path, dataset.file_type)

    cleaned_filename = f"{dataset.id}_cleaned.csv"
    cleaned_path = settings.PROCESSED_DIR / cleaned_filename

    cleaned_df, cleaning_result = clean_data(
        df=df,
        dataset_id=dataset_id,
        output_path=cleaned_path,
        options=options or DatasetCleaningOptions()
    )

    # Update DB record with dimensions and scale sampling metadata (Plan §8.7)
    dataset.cleaned_file_path = str(cleaned_path)
    dataset.row_count = len(cleaned_df)
    dataset.column_count = len(cleaned_df.columns)
    dataset.status = DatasetStatus.CLEANED.value
    dataset.is_sampled = cleaning_result.is_sampled
    dataset.original_row_count = cleaning_result.population_row_count
    dataset.sampling_rate = cleaning_result.sampling_rate
    dataset.set_cleaning_summary(cleaning_result.model_dump())
    db.commit()

    return cleaning_result

@router.post("/{dataset_id}/profile", response_model=DatasetProfile)
def profile_dataset_endpoint(
    dataset_id: str,
    use_cleaned: bool = Query(default=True, description="Whether to profile cleaned data if available"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Generate a comprehensive deterministic statistical profile for the dataset."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID {dataset_id} not found."
        )
    check_dataset_access(dataset, current_user)

    # Choose cleaned file if requested and present
    if use_cleaned and dataset.cleaned_file_path and Path(dataset.cleaned_file_path).exists():
        target_path = Path(dataset.cleaned_file_path)
        target_type = "csv"
    else:
        target_path = Path(dataset.file_path)
        target_type = dataset.file_type

    df = StorageService.load_dataframe(target_path, target_type)
    profile = profile_dataset(df, dataset_id=dataset_id)

    # Cache profile in DB
    dataset.set_profile(profile.model_dump())
    dataset.status = DatasetStatus.PROFILED.value
    db.commit()

    return profile

@router.get("/{dataset_id}/profile", response_model=DatasetProfile)
def get_dataset_profile(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Retrieve pre-computed profile for the dataset."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID {dataset_id} not found."
        )
    check_dataset_access(dataset, current_user)
    profile_data = dataset.get_profile()
    if not profile_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile has not been generated yet for dataset {dataset_id}. Call POST /{dataset_id}/profile first."
        )
    return DatasetProfile(**profile_data)

@router.get("/{dataset_id}/preview")
def get_dataset_preview(
    dataset_id: str,
    rows: int = Query(default=10, ge=1, le=100),
    use_cleaned: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Retrieve head preview of the dataset rows and columns."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID {dataset_id} not found."
        )
    check_dataset_access(dataset, current_user)

    if use_cleaned and dataset.cleaned_file_path and Path(dataset.cleaned_file_path).exists():
        target_path = Path(dataset.cleaned_file_path)
        target_type = "csv"
        is_cleaned = True
    else:
        target_path = Path(dataset.file_path)
        target_type = dataset.file_type
        is_cleaned = False

    df = StorageService.load_dataframe(target_path, target_type)
    sample_df = df.head(rows)
    # Replace NaN with None for valid JSON serialization
    sample_records = sample_df.replace({float('nan'): None}).to_dict(orient="records")

    return {
        "dataset_id": dataset_id,
        "is_cleaned": is_cleaned,
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "columns": list(df.columns),
        "rows": sample_records
    }

@router.get("/{dataset_id}/cleaning-report")
def get_dataset_cleaning_report_endpoint(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Retrieve full cleaning report (sentinels, invalid values, returns, imputation)."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID {dataset_id} not found."
        )
    check_dataset_access(dataset, current_user)
    summary = dataset.get_cleaning_summary()
    if not summary:
        import json
        report_file = settings.PROCESSED_DIR / f"{dataset_id}_cleaned_cleaning_report.json"
        if report_file.exists():
            try:
                with open(report_file, "r", encoding="utf-8") as f:
                    summary = json.load(f)
            except Exception:
                pass
    return summary or {}
