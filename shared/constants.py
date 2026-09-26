"""Shared constants across backend, agent, and Reflex frontend."""
from enum import Enum

class FileType(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"
    XLS = "xls"
    JSON = "json"

class DatasetStatus(str, Enum):
    UPLOADED = "uploaded"
    CLEANED = "cleaned"
    PROFILED = "profiled"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    ERROR = "error"

class MissingValueStrategy(str, Enum):
    AUTO = "auto"
    DROP = "drop"
    MEAN = "mean"
    MEDIAN = "median"
    MODE = "mode"
    CONSTANT = "constant"

# Maximum file upload size: 50MB for V1
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
MAX_ROW_COUNT_DEFAULT = 100_000
SAMPLE_ROW_THRESHOLD = 50_000
