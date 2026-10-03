"""Tests for Phase 4 Scale Handling and Sampling Strategy (Plan §8.7)."""
import io
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.app.core.config import settings
from backend.app.main import app
from backend.app.services.cleaning import clean_data

client = TestClient(app)

def test_max_row_count_limit_rejection(monkeypatch):
    # Set limit temporarily low for testing
    monkeypatch.setattr(settings, "MAX_ROW_COUNT_LIMIT", 500)

    # 1. Direct clean_data rejection
    big_df = pd.DataFrame({
        "ID": range(600),
        "Sales": np.random.rand(600)
    })
    with pytest.raises(ValueError) as excinfo:
        clean_data(df=big_df, dataset_id="too_big")
    assert "exceeds maximum supported row count" in str(excinfo.value)
    assert "500" in str(excinfo.value)

    # 2. Upload endpoint rejection
    csv_bytes = big_df.to_csv(index=False).encode("utf-8")
    res = client.post(
        "/api/v1/upload",
        files={"file": ("too_big.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert res.status_code == 400
    assert "exceeds maximum supported row count" in res.json()["detail"]

def test_sampling_strategy_for_large_datasets(monkeypatch, tmp_path):
    # Configure threshold and sample size for testing
    monkeypatch.setattr(settings, "SAMPLE_THRESHOLD_ROWS", 300)
    monkeypatch.setattr(settings, "SAMPLE_SIZE_ROWS", 100)

    # Create dataset exceeding threshold
    df = pd.DataFrame({
        "Category": ["Electronics", "Clothing", "Home"] * 150,  # 450 rows
        "Amount": np.random.uniform(10, 500, 450),
        "Rating": np.random.choice([1, 2, 3, 4, 5], 450)
    })
    assert len(df) == 450

    output_path = tmp_path / "sampled_cleaned.csv"
    cleaned_df, result = clean_data(
        df=df,
        dataset_id="test_sampling_ds",
        output_path=output_path
    )

    # Assertions
    assert result.is_sampled is True
    assert result.population_row_count == 450
    assert result.cleaned_row_count <= 100
    assert result.sampling_rate == pytest.approx(100 / 450, rel=0.05)
    assert len(cleaned_df) <= 100

    # Verify log entry
    sample_log = next((l for l in result.logs if l.step == "scale_sampling"), None)
    assert sample_log is not None
    assert "Extracted a representative random sample" in sample_log.description
    assert "sampling rate" in sample_log.description
