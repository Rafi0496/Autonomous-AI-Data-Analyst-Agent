import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Tuple
import pandas as pd
from fastapi import HTTPException, UploadFile, status
from backend.app.core.config import settings
from backend.app.services.file_parser import UniversalFileParser
from shared.constants import MAX_FILE_SIZE_BYTES

DANGEROUS_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".sh", ".com", ".msi", ".scr", ".pif", ".application",
    ".gadget", ".msp", ".hta", ".cpl", ".msc", ".jar", ".vbs", ".vbe", ".js", ".jse", ".ws", ".wsf", ".wsc", ".wsh"
}


class StorageService:
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize original filename removing path traversals and unsafe characters."""
        base = os.path.basename(filename)
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", base)
        if not safe or safe == "." or safe.startswith(".."):
            safe = f"upload_{uuid.uuid4().hex[:8]}.csv"
        return safe

    @staticmethod
    def validate_file_metadata(filename: str, size: int) -> str:
        """Validate filename extension and file size."""
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename cannot be empty."
            )

        safe_name = StorageService.sanitize_filename(filename)
        ext = Path(safe_name).suffix.lower()

        # Reject dangerous executable binaries
        if ext in DANGEROUS_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Executable binaries cannot be uploaded."
            )

        if size > settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {max_mb:.0f} MB."
            )

        return ext.lstrip(".") if ext else "unknown"

    @classmethod
    async def save_upload_file(cls, upload_file: UploadFile) -> Tuple[str, str, Path, int]:
        """Save an uploaded file in streaming chunks directly to disk."""
        raw_filename = upload_file.filename or "unknown"
        filename = cls.sanitize_filename(raw_filename)
        ext = Path(filename).suffix.lower()

        dataset_id = str(uuid.uuid4())
        dest_filename = f"{dataset_id}{ext}"
        dest_path = settings.UPLOAD_DIR / dest_filename

        total_size = 0
        first_chunk = b""
        try:
            with open(dest_path, "wb") as buffer:
                while chunk := await upload_file.read(1024 * 1024):  # 1MB chunks
                    if not first_chunk:
                        first_chunk = chunk[:8192]
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

        if total_size == 0:
            if dest_path.exists():
                dest_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes)."
            )

        # Validate metadata and sniffing check
        file_type = cls.validate_file_metadata(filename, total_size)

        # Content sniffing check: if file claims to be Excel/Office or ZIP but has fake content
        if ext in (".xlsx", ".xlsm") and not first_chunk.startswith(b"PK\x03\x04"):
            if dest_path.exists():
                dest_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. File content does not match expected format."
            )

        return dataset_id, file_type, dest_path, total_size

    @staticmethod
    def load_dataframe(file_path: Path, file_type: str = "") -> pd.DataFrame:
        """Load DataFrame from disk using universal parser with fallback."""
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset file not found at path {file_path}"
            )

        try:
            df, detected_format, is_tabular, reader_desc = UniversalFileParser.parse_file(file_path, file_path.name)
            df.attrs["detected_format"] = detected_format
            df.attrs["is_tabular"] = is_tabular
            df.attrs["reader_used"] = reader_desc
        except HTTPException:
            raise
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
