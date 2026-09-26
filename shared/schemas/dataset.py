"""Data schemas for dataset management and API requests/responses."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from shared.constants import DatasetStatus, FileType, MissingValueStrategy

class DatasetCleaningOptions(BaseModel):
    drop_duplicates: bool = True
    missing_num_strategy: MissingValueStrategy = MissingValueStrategy.AUTO  # auto uses median for skewed, mean otherwise
    missing_cat_strategy: MissingValueStrategy = MissingValueStrategy.AUTO  # auto uses mode or "Unknown"
    missing_threshold_drop_col: float = Field(default=0.8, ge=0.0, le=1.0) # drop col if >80% missing
    coerce_dates: bool = True
    strip_whitespace: bool = True
    remove_constant_columns: bool = True

class CleaningStepLog(BaseModel):
    step: str
    description: str
    affected_columns: List[str] = Field(default_factory=list)
    rows_affected: int = 0

class DatasetCleaningResult(BaseModel):
    dataset_id: str
    original_row_count: int
    cleaned_row_count: int
    original_col_count: int
    cleaned_col_count: int
    dropped_columns: List[str] = Field(default_factory=list)
    type_conversions: Dict[str, str] = Field(default_factory=dict)
    missing_values_imputed: Dict[str, int] = Field(default_factory=dict)
    duplicates_removed: int = 0
    logs: List[CleaningStepLog] = Field(default_factory=list)
    cleaned_file_path: str

class FileUploadResponse(BaseModel):
    dataset_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    row_count: int
    column_count: int
    status: DatasetStatus
    message: str
    upload_timestamp: str

class DatasetListItem(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    status: DatasetStatus
    created_at: str
    updated_at: str
