"""File upload API endpoint with validation and database registration."""
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.dataset import Dataset
from backend.app.services.storage import StorageService
from shared.constants import DatasetStatus
from shared.schemas.dataset import FileUploadResponse

router = APIRouter()

@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a dataset file (CSV, XLSX, XLS, JSON).
    Validates file format, limits file size, parses dimensions, and stores record.
    """
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

    # Store metadata in DB
    dataset_record = Dataset(
        id=dataset_id,
        filename=file.filename,
        file_type=file_type,
        file_path=str(file_path),
        file_size_bytes=total_size,
        row_count=row_count,
        column_count=col_count,
        status=DatasetStatus.UPLOADED.value
    )
    db.add(dataset_record)
    db.commit()
    db.refresh(dataset_record)

    return FileUploadResponse(
        dataset_id=dataset_record.id,
        filename=dataset_record.filename,
        file_type=dataset_record.file_type,
        file_size_bytes=dataset_record.file_size_bytes,
        row_count=dataset_record.row_count,
        column_count=dataset_record.column_count,
        status=DatasetStatus(dataset_record.status),
        message=f"Successfully uploaded and validated {file.filename} ({row_count} rows, {col_count} columns).",
        upload_timestamp=dataset_record.created_at.isoformat()
    )
