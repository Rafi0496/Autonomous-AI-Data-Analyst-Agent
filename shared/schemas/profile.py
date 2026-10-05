"""Data schemas for dataset profiling and quality summaries."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ColumnProfile(BaseModel):
    name: str
    original_dtype: str
    inferred_type: str  # numeric, categorical, datetime, boolean, text
    null_count: int
    null_percentage: float
    unique_count: int
    is_unique: bool
    sample_values: List[Any] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)

class DataQualitySummary(BaseModel):
    total_cells: int
    missing_cells: int
    missing_percentage: float
    duplicate_rows: int
    duplicate_percentage: float
    quality_score: float  # 0 to 100 (computed on RAW data)
    raw_quality_score: Optional[float] = None
    cleaned_quality_score: Optional[float] = None
    sampling_disclosure: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)

class DatasetProfile(BaseModel):
    dataset_id: str
    row_count: int
    column_count: int
    memory_usage_bytes: int
    columns: Dict[str, ColumnProfile]
    quality_summary: DataQualitySummary
    created_at: str
