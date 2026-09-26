"""Storage and file ingestion service for uploaded datasets."""
import os
import shutil
import uuid
from pathlib import Path
from typing import Tuple
import pandas as pd
from fastapi import HTTPException, UploadFile, status
from backend.app.core.config import settings
from shared.constants import MAX_FILE_SIZE_BYTES

class StorageService:
    @staticmethod
    def validate_file_metadata(filename: str, size: int) -> str:
        """Validate filename extension and file size."""
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename cannot be empty."
            )
            
        ext = Path(filename).suffix.lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )
            
        if size > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {max_mb:.0f} MB."
            )
            
        return ext.lstrip(".")

    @classmethod
    async def save_upload_file(cls, upload_file: UploadFile) -> Tuple[str, str, Path, int]:
        """Save an uploaded file to the upload directory and validate its content."""
        filename = upload_file.filename or "unknown"
        ext = Path(filename).suffix.lower()
        
        # Read file chunks and measure size
        dataset_id = str(uuid.uuid4())
        dest_filename = f"{dataset_id}{ext}"
        dest_path = settings.UPLOAD_DIR / dest_filename
        
        total_size = 0
        try:
            with open(dest_path, "wb") as buffer:
                while chunk := await upload_file.read(1024 * 1024):  # 1MB chunks
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE_BYTES:
                        buffer.close()
                        if dest_path.exists():
                            dest_path.unlink()
                        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File exceeds maximum allowed size of {max_mb:.0f} MB."
                        )
                    buffer.write(chunk)
        except HTTPException:
            raise
        except Exception as e:
            if dest_path.exists():
                dest_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save uploaded file: {str(e)}"
            )

        # Validate file content structure
        file_type = cls.validate_file_metadata(filename, total_size)
        return dataset_id, file_type, dest_path, total_size

    @staticmethod
    def load_dataframe(file_path: Path, file_type: str) -> pd.DataFrame:
        """Load DataFrame from disk with robust error handling for malformed files."""
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset file not found at path {file_path}"
            )
            
        try:
            if file_type == "csv":
                try:
                    df = pd.read_csv(file_path, encoding="utf-8")
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, encoding="latin1")
            elif file_type in ("xlsx", "xls"):
                df = pd.read_excel(file_path)
            elif file_type == "json":
                df = pd.read_json(file_path)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file type: {file_type}"
                )
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Malformed or corrupt dataset file. Parser error: {str(e)}"
            )
            
        if df.empty:
            raise HTTPException(
                status_code=422,
                detail="Dataset is empty (contains 0 rows or columns)."
            )
            
        return df

    @staticmethod
    def save_dataframe(df: pd.DataFrame, dest_path: Path):
        """Save DataFrame as CSV."""
        df.to_csv(dest_path, index=False)
