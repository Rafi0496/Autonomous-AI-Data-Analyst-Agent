"""Integration and API tests for file upload, validation, cleaning, and profiling."""
import io
import pytest
from fastapi import status

def test_health_check(client):
    """Test API health endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

def test_upload_valid_csv(client):
    """Test uploading a valid CSV file."""
    csv_content = "id,name,age\n1,Alice,30\n2,Bob,25\n3,Charlie,35\n"
    file = io.BytesIO(csv_content.encode("utf-8"))
    
    response = client.post(
        "/api/v1/upload",
        files={"file": ("test_users.csv", file, "text/csv")}
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["filename"] == "test_users.csv"
    assert data["row_count"] == 3
    assert data["column_count"] == 3
    assert data["status"] == "uploaded"
    assert "dataset_id" in data

def test_upload_invalid_extension(client):
    """Test rejecting unsupported file format."""
    content = "malicious payload"
    file = io.BytesIO(content.encode("utf-8"))
    
    response = client.post(
        "/api/v1/upload",
        files={"file": ("malicious.exe", file, "application/octet-stream")}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported file format" in response.json()["detail"]

def test_upload_malformed_csv(client):
    """Test error on malformed/empty CSV."""
    file = io.BytesIO(b"")
    response = client.post(
        "/api/v1/upload",
        files={"file": ("empty.csv", file, "text/csv")}
    )
    assert response.status_code in (422, status.HTTP_400_BAD_REQUEST)

def test_dataset_pipeline_lifecycle(client):
    """Test full dataset lifecycle: upload -> preview -> clean -> profile -> retrieve profile."""
    csv_content = (
        "cust_id,revenue,signup_date\n"
        "C01,$100.50,2025-01-01\n"
        "C02,$250.00,2025-01-02\n"
        "C01,$100.50,2025-01-01\n" # Duplicate row
        "C03,,2025-01-04\n"         # Missing revenue
    )
    file = io.BytesIO(csv_content.encode("utf-8"))
    
    # 1. Upload
    up_res = client.post(
        "/api/v1/upload",
        files={"file": ("customers.csv", file, "text/csv")}
    )
    assert up_res.status_code == status.HTTP_201_CREATED
    dataset_id = up_res.json()["dataset_id"]

    # 2. Preview original
    prev_res = client.get(f"/api/v1/datasets/{dataset_id}/preview?use_cleaned=false")
    assert prev_res.status_code == status.HTTP_200_OK
    assert prev_res.json()["total_rows"] == 4

    # 3. Clean
    clean_res = client.post(f"/api/v1/datasets/{dataset_id}/clean")
    assert clean_res.status_code == status.HTTP_200_OK
    clean_data = clean_res.json()
    assert clean_data["duplicates_removed"] == 1
    assert clean_data["cleaned_row_count"] == 3
    assert "revenue" in clean_data["type_conversions"]

    # 4. Profile
    prof_res = client.post(f"/api/v1/datasets/{dataset_id}/profile")
    assert prof_res.status_code == status.HTTP_200_OK
    prof_data = prof_res.json()
    assert prof_data["row_count"] == 3
    assert "revenue" in prof_data["columns"]
    assert prof_data["columns"]["revenue"]["inferred_type"] == "numeric"

    # 5. Get Cached Profile
    get_prof = client.get(f"/api/v1/datasets/{dataset_id}/profile")
    assert get_prof.status_code == status.HTTP_200_OK
    assert get_prof.json()["dataset_id"] == dataset_id
