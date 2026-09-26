"""State management for the Reflex frontend application."""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
import reflex as rx

API_BASE_URL = os.getenv("API_URL", "http://127.0.0.1:8000/api/v1")

class AppState(rx.State):
    """Global state managing datasets, upload lifecycle, profiling, and navigation."""
    
    # Navigation
    active_tab: str = "upload"
    
    # Dataset Registry
    datasets: List[Dict[str, Any]] = []
    selected_dataset_id: str = ""
    selected_dataset_name: str = "No dataset selected"
    
    # Status flags
    is_loading: bool = False
    is_uploading: bool = False
    is_cleaning: bool = False
    is_profiling: bool = False
    status_message: str = ""
    error_message: str = ""
    
    # Profile & Quality Data
    has_profile: bool = False
    quality_score: float = 0.0
    row_count: int = 0
    column_count: int = 0
    memory_mb: float = 0.0
    duplicate_rows: int = 0
    missing_percentage: float = 0.0
    quality_warnings: List[str] = []
    column_profiles: List[Dict[str, Any]] = []
    
    # Data Preview
    preview_columns: List[str] = []
    preview_rows: List[Dict[str, Any]] = []

    def set_active_tab(self, tab: str):
        self.active_tab = tab

    async def fetch_datasets(self):
        """Fetch list of all datasets from the FastAPI backend."""
        self.is_loading = True
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{API_BASE_URL}/datasets")
                if res.status_code == 200:
                    self.datasets = res.json()
                    if self.datasets and not self.selected_dataset_id:
                        await self.select_dataset(self.datasets[0]["id"])
        except Exception as e:
            self.error_message = f"Unable to reach backend: {str(e)}"
        finally:
            self.is_loading = False

    async def select_dataset(self, dataset_id: str):
        """Select active dataset and load its preview & profile."""
        self.selected_dataset_id = dataset_id
        for d in self.datasets:
            if d.get("id") == dataset_id:
                self.selected_dataset_name = d.get("filename", "Dataset")
                break

        # Fetch preview
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 1. Preview
                p_res = await client.get(f"{API_BASE_URL}/datasets/{dataset_id}/preview?rows=8")
                if p_res.status_code == 200:
                    data = p_res.json()
                    self.preview_columns = data.get("columns", [])
                    self.preview_rows = data.get("rows", [])
                    self.row_count = data.get("total_rows", 0)
                    self.column_count = data.get("total_columns", 0)

                # 2. Check for Profile
                prof_res = await client.get(f"{API_BASE_URL}/datasets/{dataset_id}/profile")
                if prof_res.status_code == 200:
                    self._parse_profile(prof_res.json())
                else:
                    self.has_profile = False
        except Exception as e:
            self.error_message = f"Failed loading dataset details: {str(e)}"

    def _parse_profile(self, data: Dict[str, Any]):
        """Parse raw profile JSON into reactive state fields."""
        self.has_profile = True
        self.row_count = data.get("row_count", 0)
        self.column_count = data.get("column_count", 0)
        self.memory_mb = round(data.get("memory_usage_bytes", 0) / (1024 * 1024), 2)
        
        q_summary = data.get("quality_summary", {})
        self.quality_score = q_summary.get("quality_score", 0.0)
        self.duplicate_rows = q_summary.get("duplicate_rows", 0)
        self.missing_percentage = q_summary.get("missing_percentage", 0.0)
        self.quality_warnings = q_summary.get("warnings", [])
        
        raw_cols = data.get("columns", {})
        col_list = []
        for name, col_info in raw_cols.items():
            stats = col_info.get("stats", {})
            stat_summary = ""
            if "mean" in stats:
                stat_summary = f"Mean: {stats['mean']}, Min: {stats['min']}, Max: {stats['max']}"
            elif "top_values" in stats and stats["top_values"]:
                top = stats["top_values"][0]
                stat_summary = f"Top: {top.get('value')} ({top.get('count')})"
                
            col_list.append({
                "name": name,
                "type": col_info.get("inferred_type", "unknown"),
                "null_pct": f"{col_info.get('null_percentage', 0.0)}%",
                "unique": col_info.get("unique_count", 0),
                "summary": stat_summary,
                "warnings": ", ".join(col_info.get("warnings", [])) or "Clean"
            })
        self.column_profiles = col_list

    async def handle_upload(self, files: List[rx.UploadFile]):
        """Upload file via rx.upload component directly to FastAPI."""
        if not files:
            self.error_message = "No file selected."
            return
            
        self.is_uploading = True
        self.error_message = ""
        self.status_message = "Uploading and validating dataset..."

        for file in files:
            upload_data = await file.read()
            filename = file.filename
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    files_payload = {"file": (filename, upload_data, "multipart/form-data")}
                    res = await client.post(f"{API_BASE_URL}/upload", files=files_payload)
                    
                    if res.status_code == 201:
                        data = res.json()
                        dataset_id = data["dataset_id"]
                        self.status_message = f"Uploaded {filename}! Running profiling pipeline..."
                        
                        # Automatically profile dataset
                        prof_res = await client.post(f"{API_BASE_URL}/datasets/{dataset_id}/profile")
                        if prof_res.status_code == 200:
                            self._parse_profile(prof_res.json())
                            
                        self.status_message = f"Dataset {filename} ready for analysis!"
                        await self.fetch_datasets()
                        await self.select_dataset(dataset_id)
                    else:
                        err = res.json().get("detail", "Upload failed.")
                        self.error_message = f"Upload error: {err}"
            except Exception as e:
                self.error_message = f"Error during upload: {str(e)}"
            finally:
                self.is_uploading = False

    async def load_sample(self, sample_name: str):
        """Quick load one of the 3 pre-built messy datasets."""
        self.status_message = f"Loading sample: {sample_name}..."
        self.error_message = ""
        
        sample_path = Path("data/samples") / sample_name
        if not sample_path.exists():
            self.error_message = f"Sample dataset {sample_name} not found."
            return
            
        try:
            with open(sample_path, "rb") as f:
                content = f.read()
                
            async with httpx.AsyncClient(timeout=30.0) as client:
                files_payload = {"file": (sample_name, content, "text/csv")}
                res = await client.post(f"{API_BASE_URL}/upload", files=files_payload)
                
                if res.status_code == 201:
                    data = res.json()
                    dataset_id = data["dataset_id"]
                    
                    # Run profiling
                    prof_res = await client.post(f"{API_BASE_URL}/datasets/{dataset_id}/profile")
                    if prof_res.status_code == 200:
                        self._parse_profile(prof_res.json())
                        
                    self.status_message = f"Sample {sample_name} loaded and profiled successfully!"
                    await self.fetch_datasets()
                    await self.select_dataset(dataset_id)
                else:
                    self.error_message = f"Upload failed: {res.text}"
        except Exception as e:
            self.error_message = f"Failed to load sample: {str(e)}"

    async def run_cleaning(self):
        """Trigger deterministic cleaning on current dataset."""
        if not self.selected_dataset_id:
            self.error_message = "Please select a dataset first."
            return
            
        self.is_cleaning = True
        self.status_message = "Running cleaning pipeline: handling nulls, formatting currency, deduplicating..."
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(f"{API_BASE_URL}/datasets/{self.selected_dataset_id}/clean")
                if res.status_code == 200:
                    clean_res = res.json()
                    # Re-profile cleaned data
                    prof_res = await client.post(f"{API_BASE_URL}/datasets/{self.selected_dataset_id}/profile?use_cleaned=true")
                    if prof_res.status_code == 200:
                        self._parse_profile(prof_res.json())
                    
                    # Refresh preview
                    await self.select_dataset(self.selected_dataset_id)
                    self.status_message = (
                        f"Cleaned! Removed {clean_res.get('duplicates_removed', 0)} duplicates, "
                        f"imputed {sum(clean_res.get('missing_values_imputed', {}).values())} missing values."
                    )
                else:
                    self.error_message = f"Cleaning failed: {res.text}"
        except Exception as e:
            self.error_message = f"Cleaning error: {str(e)}"
        finally:
            self.is_cleaning = False

    async def run_profiling(self):
        """Trigger re-profiling on current dataset."""
        if not self.selected_dataset_id:
            return
        self.is_profiling = True
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                prof_res = await client.post(f"{API_BASE_URL}/datasets/{self.selected_dataset_id}/profile")
                if prof_res.status_code == 200:
                    self._parse_profile(prof_res.json())
                    self.status_message = "Profile re-computed successfully."
        except Exception as e:
            self.error_message = f"Profiling error: {str(e)}"
        finally:
            self.is_profiling = False
