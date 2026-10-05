"""Tests for Milestone 7: OpenAPI Contract and API Documentation Validation."""
import json
from pathlib import Path
import pytest
from backend.app.main import app

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
OPENAPI_JSON_PATH = DOCS_DIR / "openapi.json"
API_MD_PATH = DOCS_DIR / "API.md"

def test_openapi_json_exists():
    """Verify docs/openapi.json and docs/API.md exist and are non-empty."""
    assert OPENAPI_JSON_PATH.exists(), "docs/openapi.json must exist in repository"
    assert OPENAPI_JSON_PATH.stat().st_size > 0, "docs/openapi.json must not be empty"
    assert API_MD_PATH.exists(), "docs/API.md must exist in repository"
    assert API_MD_PATH.stat().st_size > 0, "docs/API.md must not be empty"

def test_live_openapi_matches_committed_contract():
    """
    Test fails if the live FastAPI OpenAPI schema differs from docs/openapi.json.
    Ensures that any API route, model, or parameter changes update docs/openapi.json.
    """
    live_schema = app.openapi()
    
    with open(OPENAPI_JSON_PATH, "r", encoding="utf-8") as f:
        committed_schema = json.load(f)

    # Compare paths
    live_paths = set(live_schema.get("paths", {}).keys())
    committed_paths = set(committed_schema.get("paths", {}).keys())
    
    assert live_paths == committed_paths, (
        f"API paths differ!\n"
        f"Added in live: {live_paths - committed_paths}\n"
        f"Removed from live: {committed_paths - live_paths}"
    )

    # Compare full schema JSON representations
    live_json = json.dumps(live_schema, indent=2, sort_keys=True)
    committed_json = json.dumps(committed_schema, indent=2, sort_keys=True)

    assert live_json == committed_json, (
        "Live FastAPI OpenAPI schema differs from docs/openapi.json! "
        "Run 'python scripts/generate_api_contract.py' to update docs/openapi.json and docs/API.md."
    )

def test_api_markdown_contains_core_contract_elements():
    """Verify docs/API.md documents job lifecycle, error schemas, insights, and workflows."""
    content = API_MD_PATH.read_text(encoding="utf-8")

    # Verify standard error schema documented
    assert "Standard Error Response Schema" in content
    assert "HTTP_401_UNAUTHORIZED" in content
    assert "HTTP_403_FORBIDDEN" in content

    # Verify job lifecycle fields documented
    assert "Job Lifecycle Fields & State Machine" in content
    assert "`status`" in content
    assert "`phase`" in content
    assert "`current_step`" in content
    assert "`tokens_used`" in content
    assert "`token_budget`" in content

    # Verify insights payload documented
    assert "Insights Payload Specification" in content
    assert "analytical_insights" in content
    assert "data_quality_insights" in content
    assert "suppressed_insights" in content

    # Verify chat and report workflows documented
    assert "Chat & Report Workflows" in content
    assert "/api/v1/chat" in content
    assert "/api/v1/reports" in content
