"""Unit and component tests for Reflex frontend app, routes, and AppState."""
import sys
from pathlib import Path
import pytest

# Add frontend to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from frontend.frontend import app
from frontend.state import AppState

def test_reflex_app_routes():
    """Verify that all Phase 1-3 pages are properly registered in Reflex app."""
    routes = list(app._unevaluated_pages.keys())
    
    assert "index" in routes or "/" in routes
    assert "upload" in routes
    assert "dashboard" in routes
    assert "chat" in routes
    assert "reports" in routes
    assert "settings" in routes

def test_app_state_profile_parsing():
    """Verify AppState._parse_profile correctly updates reactive state variables."""
    state = AppState(_reflex_internal_init=True)
    sample_profile_payload = {
        "dataset_id": "test_ds_123",
        "row_count": 120,
        "column_count": 5,
        "memory_usage_bytes": 1048576,  # 1 MB
        "quality_summary": {
            "quality_score": 88.5,
            "duplicate_rows": 4,
            "missing_percentage": 2.5,
            "warnings": ["Detected 4 duplicate rows."]
        },
        "columns": {
            "salary": {
                "inferred_type": "numeric",
                "null_percentage": 1.2,
                "unique_count": 105,
                "stats": {"mean": 75000, "min": 30000, "max": 180000},
                "warnings": []
            }
        }
    }
    
    state._parse_profile(sample_profile_payload)
    
    assert state.has_profile is True
    assert state.row_count == 120
    assert state.column_count == 5
    assert state.memory_mb == 1.0
    assert state.quality_score == 88.5
    assert state.duplicate_rows == 4
    assert len(state.quality_warnings) == 1
    assert len(state.column_profiles) == 1
    assert state.column_profiles[0]["name"] == "salary"
    assert state.column_profiles[0]["type"] == "numeric"
    assert state.column_profiles[0]["warnings"] == "Clean"
