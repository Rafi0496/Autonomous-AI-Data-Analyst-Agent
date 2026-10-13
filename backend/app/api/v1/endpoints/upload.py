"""File upload API endpoint with validation, streaming storage, and background processing."""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_optional_current_user
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal, get_db
from backend.app.models.dataset import Dataset
from backend.app.models.user import User
from backend.app.services.cleaning import clean_data
from backend.app.services.profiling import profile_dataset
from backend.app.services.storage import StorageService
from shared.constants import DatasetStatus
from shared.schemas.dataset import DatasetCleaningOptions, FileUploadResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def run_background_pipeline(dataset_id: str):
    """Background task to clean and profile dataset without blocking the client upload connection."""
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            return

        dataset.status = DatasetStatus.PROCESSING.value
        db.commit()

        # 1. Clean
        df = StorageService.load_dataframe(Path(dataset.file_path), dataset.file_type)
        cleaned_path = settings.PROCESSED_DIR / f"{dataset.id}_cleaned.csv"
        cleaned_df, cleaning_summary = clean_data(
            df=df,
            dataset_id=dataset.id,
            output_path=cleaned_path,
            options=DatasetCleaningOptions(drop_duplicates=True, strip_whitespace=True)
        )
        dataset.cleaned_file_path = str(cleaned_path)
        dataset.set_cleaning_summary(cleaning_summary)
        dataset.status = DatasetStatus.CLEANED.value
        db.commit()

        # 2. Profile
        prof = profile_dataset(cleaned_df, dataset_id=dataset.id)
        dataset.set_profile(prof)
        dataset.status = DatasetStatus.READY.value
        db.commit()
    except Exception as e:
        logger.warning("Background pipeline execution error for %s: %s", dataset_id, e)
    finally:
        db.close()


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Upload a dataset in any file format.
    Streams chunks directly to disk, validates structure, parses dimensions,
    and returns 201 immediately while triggering background cleaning and profiling.
    """
    if not settings.ALLOW_ANONYMOUS and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file was uploaded."
        )

    # Save to disk with chunked stream and size validation
    dataset_id, file_type, file_path, total_size = await StorageService.save_upload_file(file)

    # Parse dataset to verify it is valid and extract row/col counts
    try:
        df = StorageService.load_dataframe(file_path, file_type)
        row_count, col_count = df.shape
    except HTTPException:
        # Clean up file on parse failure
        if file_path.exists():
            file_path.unlink()
        raise

    # Scale check: Max row count limit (Plan §8.7)
    if row_count > settings.MAX_ROW_COUNT_LIMIT:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset exceeds maximum supported row count for v1 ({settings.MAX_ROW_COUNT_LIMIT:,} rows). Provided dataset has {row_count:,} rows."
        )

    safe_filename = StorageService.sanitize_filename(file.filename)
    reader_used = df.attrs.get("reader_used", "Universal file parser")
    is_tabular = df.attrs.get("is_tabular", True)

    # Store metadata in DB (isolated per user if authenticated)
    dataset_record = Dataset(
        id=dataset_id,
        user_id=current_user.id if current_user else None,
        filename=safe_filename,
        file_type=file_type,
        file_path=str(file_path),
        file_size_bytes=total_size,
        row_count=row_count,
        column_count=col_count,
        status=DatasetStatus.UPLOADED.value if is_tabular else DatasetStatus.NON_TABULAR.value
    )

    db.add(dataset_record)
    db.commit()
    db.refresh(dataset_record)

    # Trigger background cleaning and profiling
    if is_tabular:
        background_tasks.add_task(run_background_pipeline, dataset_record.id)

    msg = f"Successfully uploaded and validated {file.filename} ({row_count} rows, {col_count} columns via {reader_used})."
    if not is_tabular:
        msg = f"We received your file but could not find tabular data in it. {reader_used}"

    return FileUploadResponse(
        dataset_id=dataset_record.id,
        filename=dataset_record.filename,
        file_type=dataset_record.file_type,
        file_size_bytes=dataset_record.file_size_bytes,
        row_count=dataset_record.row_count,
        column_count=dataset_record.column_count,
        status=DatasetStatus(dataset_record.status),
        message=msg,
        upload_timestamp=dataset_record.created_at.isoformat()
    )
