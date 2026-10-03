"""State management for the Reflex frontend application (Phases 1-3)."""
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
import reflex as rx

API_BASE_URL = os.getenv("API_URL", "http://127.0.0.1:8000/api/v1")

from pydantic import BaseModel

class ChartSpecModel(BaseModel):
    chart_type: str = "bar"
    title: str = ""
    x_label: str = ""
    y_label: str = ""
    x_key: str = "category"
    y_key: str = "value"
    data: List[Dict[str, Any]] = []

class InsightModel(BaseModel):
    id: str = ""
    type: str = ""
    title: str = ""
    summary: str = ""
    significance: Optional[float] = None
    effect_size: Optional[float] = None
    n_used: int = 0
    n_excluded: int = 0
    exclusion_rate: float = 0.0
    confidence: str = "high"
    caveats: List[str] = []
    impact_score: float = 0.0
    chart_spec: Optional[ChartSpecModel] = None

class RunLogStepModel(BaseModel):
    step: int = 0
    tool: str = ""
    rationale: str = ""
    model: str = ""
    tool_time_ms: float = 0.0
    llm_latency_ms: float = 0.0
    tokens: int = 0

class EvidenceItemModel(BaseModel):
    type: str = "insight"
    id: str = ""
    title: str = ""
    tool: str = ""

class ChatMessageModel(BaseModel):
    role: str = "user"
    content: str = ""
    evidence: List[EvidenceItemModel] = []
    verification_is_valid: bool = True
    verification_summary: str = ""

class ReportItemModel(BaseModel):
    report_id: str = ""
    job_id: str = ""
    dataset_name: str = ""
    format: str = "pdf"
    filename: str = ""
    created_at: str = ""
    download_url: str = ""

class AppState(rx.State):
    """Global reactive state managing datasets, profiling, agent execution, dashboard, and chat."""
    
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
    is_analyzing: bool = False
    is_polling: bool = False
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
    
    # Cleaning Report Data
    has_cleaning_report: bool = False
    sentinels_list: List[Dict[str, Any]] = []
    invalid_values_list: List[Dict[str, Any]] = []
    suspected_returns_list: List[Dict[str, Any]] = []
    suspected_extremes_list: List[Dict[str, Any]] = []
    imputation_stats_list: List[Dict[str, Any]] = []
    
    # Data Preview
    preview_columns: List[str] = []
    preview_rows: List[Dict[str, Any]] = []

    # Agent Execution & Progress Polling
    active_job_id: str = ""
    analysis_goal: str = "Perform comprehensive exploratory analysis across all segments, correlations, and anomalies."
    job_status: str = "idle"  # idle, running, completed, budget_tripped, failed
    job_phase: str = "queued"  # queued, profiling, planning, execution, reflection, synthesis, completed
    job_current_step: int = 0
    job_current_step_name: str = "Ready"
    job_total_steps: int = 0
    job_elapsed_seconds: float = 0.0
    job_tokens_used: str = "0"
    job_step_limit: int = 5
    job_token_budget: int = 15000
    job_run_log: List[RunLogStepModel] = []

    # Analysis Results & Explainability
    job_synthesis: Dict[str, Any] = {}
    job_executive_summary: str = ""
    job_key_findings: List[Dict[str, Any]] = []
    job_recommendations: List[str] = []
    job_insights: List[InsightModel] = []
    job_analytical_insights: List[InsightModel] = []
    job_data_quality_insights: List[InsightModel] = []
    job_chart_specs: List[Dict[str, Any]] = []
    job_verification: Dict[str, Any] = {}
    verification_verified_count: int = 0
    verification_total_count: int = 0
    verification_rate: float = 100.0
    verification_is_valid: bool = True

    # Settings / System Info
    active_provider: str = os.getenv("LLM_PROVIDER", "gemini")
    active_model: str = "gemini-2.5-flash" if os.getenv("LLM_PROVIDER", "gemini") == "gemini" else "claude-3-7-sonnet-20250219"
    step_budget_setting: int = 5
    token_budget_setting: int = 15000

    # Chat Q&A (Milestone 4)
    chat_messages: List[ChatMessageModel] = []
    chat_input: str = ""
    is_chatting: bool = False
    suggested_questions: List[str] = [
        "What are the top statistical findings?",
        "What data quality issues were sanitized?",
        "Which segments showed the highest differences?"
    ]

    # Report Export (Milestone 5)
    is_generating_report: bool = False
    report_download_url: str = ""
    past_reports: List[ReportItemModel] = []

    async def fetch_reports(self):
        """Fetch list of past generated reports from backend."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{API_BASE_URL}/reports")
                if res.status_code == 200:
                    raw = res.json()
                    self.past_reports = [ReportItemModel(**r) for r in raw]
        except Exception:
            pass

    async def generate_report(self, fmt: str = "pdf"):
        """Trigger report generation for active job or selected dataset."""
        if not self.active_job_id:
            self.error_message = "No completed analysis job found. Please run an analysis job first."
            return
            
        self.is_generating_report = True
        self.error_message = ""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(f"{API_BASE_URL}/jobs/{self.active_job_id}/report?format={fmt}")
                if res.status_code == 200:
                    data = res.json()
                    self.report_download_url = data.get("download_url", "")
                    await self.fetch_reports()
                else:
                    self.error_message = f"Report generation failed: {res.text}"
        except Exception as e:
            self.error_message = f"Error generating report: {str(e)}"
        finally:
            self.is_generating_report = False

    async def generate_pdf(self):
        await self.generate_report("pdf")

    async def generate_docx(self):
        await self.generate_report("docx")

    def set_active_tab(self, tab: str):
        self.active_tab = tab

    def set_analysis_goal(self, goal: str):
        self.analysis_goal = goal

    def set_chat_input(self, val: str):
        self.chat_input = val

    async def fetch_datasets(self):
        """Fetch list of all datasets from backend."""
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
        """Select active dataset and load its preview, profile, and cleaning report."""
        self.selected_dataset_id = dataset_id
        for d in self.datasets:
            if d.get("id") == dataset_id:
                self.selected_dataset_name = d.get("filename", "Dataset")
                break

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

                # 2. Profile
                prof_res = await client.get(f"{API_BASE_URL}/datasets/{dataset_id}/profile")
                if prof_res.status_code == 200:
                    self._parse_profile(prof_res.json())
                else:
                    self.has_profile = False

                # 3. Cleaning Report
                cl_res = await client.get(f"{API_BASE_URL}/datasets/{dataset_id}/cleaning-report")
                if cl_res.status_code == 200 and cl_res.json():
                    self._parse_cleaning_report(cl_res.json())
                else:
                    self.has_cleaning_report = False
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

    def _parse_cleaning_report(self, data: Dict[str, Any]):
        """Parse cleaning report (sentinels, invalid values, returns, imputation)."""
        self.has_cleaning_report = True
        self.sentinels_list = [
            {"column": s.get("column"), "value": s.get("sentinel_value"), "count": s.get("count", 0)}
            for s in data.get("sentinels_detected", [])
        ]
        self.invalid_values_list = [
            {"column": iv.get("column"), "rule": iv.get("rule", "domain_validity"), "count": iv.get("count", 0)}
            for iv in data.get("invalid_values_detected", [])
        ]
        self.suspected_returns_list = [
            {"column": sr.get("column"), "count": sr.get("count", 0), "desc": sr.get("description", "Kept in dataset")}
            for sr in data.get("suspected_returns", [])
        ]
        self.suspected_extremes_list = [
            {"column": se.get("column"), "value": se.get("value"), "count": se.get("count", 0)}
            for se in data.get("suspected_repeated_extremes", [])
        ]
        imp_stats = []
        for col, s in data.get("column_imputation_stats", {}).items():
            rate = s.get("imputation_rate", 0.0)
            if rate > 0:
                imp_stats.append({
                    "column": col,
                    "count": s.get("imputed_count", 0),
                    "rate": f"{rate * 100:.1f}%",
                    "rate_num": round(rate * 100, 1),
                    "strategy": s.get("strategy", "median")
                })
        imp_stats.sort(key=lambda x: -x["rate_num"])
        self.imputation_stats_list = imp_stats

    async def run_cleaning(self):
        """Trigger dataset cleaning endpoint and refresh profile & cleaning report."""
        if not self.selected_dataset_id:
            return
        self.is_cleaning = True
        self.error_message = ""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(f"{API_BASE_URL}/datasets/{self.selected_dataset_id}/clean")
                if res.status_code == 200:
                    await self.select_dataset(self.selected_dataset_id)
                    self.status_message = "Dataset cleaned and normalized successfully."
                else:
                    self.error_message = f"Cleaning failed: {res.text}"
        except Exception as e:
            self.error_message = f"Cleaning error: {str(e)}"
        finally:
            self.is_cleaning = False

    async def run_profiling(self):
        """Trigger dataset profiling endpoint and refresh profile."""
        if not self.selected_dataset_id:
            return
        self.is_profiling = True
        self.error_message = ""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(f"{API_BASE_URL}/datasets/{self.selected_dataset_id}/profile")
                if res.status_code == 200:
                    self._parse_profile(res.json())
                    self.status_message = "Dataset profiled successfully."
                else:
                    self.error_message = f"Profiling failed: {res.text}"
        except Exception as e:
            self.error_message = f"Profiling error: {str(e)}"
        finally:
            self.is_profiling = False

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
                        self.status_message = f"Uploaded {filename}! Running profiling & cleaning..."
                        
                        # Clean and profile
                        await client.post(f"{API_BASE_URL}/datasets/{dataset_id}/clean")
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
                    
                    # Clean and profile
                    await client.post(f"{API_BASE_URL}/datasets/{dataset_id}/clean")
                    prof_res = await client.post(f"{API_BASE_URL}/datasets/{dataset_id}/profile")
                    if prof_res.status_code == 200:
                        self._parse_profile(prof_res.json())
                        
                    self.status_message = f"Sample {sample_name} loaded and prepared successfully!"
                    await self.fetch_datasets()
                    await self.select_dataset(dataset_id)
                else:
                    self.error_message = f"Upload failed: {res.text}"
        except Exception as e:
            self.error_message = f"Failed to load sample: {str(e)}"

    async def start_analysis(self):
        """Submit analysis job to backend and initiate background polling."""
        if not self.selected_dataset_id:
            self.error_message = "Please select or upload a dataset before starting analysis."
            return
            
        self.is_analyzing = True
        self.is_polling = True
        self.error_message = ""
        self.job_status = "running"
        self.job_phase = "planning"
        self.job_current_step = 0
        self.job_current_step_name = "Submitting job..."
        self.status_message = "Dispatching autonomous analysis agent..."

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                payload = {
                    "dataset_id": self.selected_dataset_id,
                    "goal": self.analysis_goal,
                    "max_steps": self.step_budget_setting,
                    "token_budget": self.token_budget_setting
                }
                res = await client.post(f"{API_BASE_URL}/jobs", json=payload)
                if res.status_code in (200, 202):
                    data = res.json()
                    self.active_job_id = data["job_id"]
                    self.job_current_step_name = data.get("current_step_name", "Planning analysis")
                    return [AppState.poll_job_progress, rx.redirect("/dashboard")]
                else:
                    self.error_message = f"Failed to start analysis: {res.text}"
                    self.is_analyzing = False
                    self.is_polling = False
        except Exception as e:
            self.error_message = f"Error starting analysis: {str(e)}"
            self.is_analyzing = False
            self.is_polling = False

    @rx.event(background=True)
    async def poll_job_progress(self):
        """Poll job status every 2s using Reflex background task."""
        async with self:
            job_id = self.active_job_id
            if not job_id:
                return
            self.is_polling = True

        while True:
            await asyncio.sleep(2.0)
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.get(f"{API_BASE_URL}/jobs/{job_id}")
                    if res.status_code == 200:
                        data = res.json()
                        st = data.get("status", "")
                        ph = data.get("phase", "")
                        step = data.get("current_step", 0)
                        step_name = data.get("current_step_name", "")
                        tot = data.get("total_steps", 0)
                        elapsed = data.get("execution_time_seconds", 0)
                        tokens = data.get("tokens_used", 0)
                        
                        async with self:
                            self.job_status = st
                            self.job_phase = ph
                            self.job_current_step = step
                            self.job_current_step_name = step_name
                            self.job_total_steps = tot
                            self.job_elapsed_seconds = elapsed
                            self.job_tokens_used = str(tokens)

                        if st in ("completed", "budget_tripped", "failed"):
                            async with self:
                                self.is_polling = False
                                self.is_analyzing = False
                                res_obj = data.get("results") or {}
                                synth = res_obj.get("synthesis") or {}
                                self.job_synthesis = synth
                                self.job_executive_summary = synth.get("executive_summary", "")
                                self.job_key_findings = synth.get("key_findings", [])
                                raw_insights = res_obj.get("insights") or []
                                parsed_insights = []
                                for ins in raw_insights:
                                    cs = ins.get("chart_spec")
                                    cs_obj = None
                                    if cs and isinstance(cs, dict):
                                        cs_obj = ChartSpecModel(
                                            chart_type=str(cs.get("chart_type", "bar")),
                                            title=str(cs.get("title", "")),
                                            x_label=str(cs.get("x_label", "")),
                                            y_label=str(cs.get("y_label", "")),
                                            x_key=str(cs.get("x_key", "category")),
                                            y_key=str(cs.get("y_key", "value")),
                                            data=cs.get("data", [])
                                        )
                                    parsed_insights.append(InsightModel(
                                        id=str(ins.get("id", "")),
                                        type=str(ins.get("type", "insight")),
                                        title=str(ins.get("title", "")),
                                        summary=str(ins.get("summary", "")),
                                        significance=ins.get("significance"),
                                        effect_size=ins.get("effect_size"),
                                        n_used=int(ins.get("n_used", 0)),
                                        n_excluded=int(ins.get("n_excluded", 0)),
                                        exclusion_rate=float(ins.get("exclusion_rate", 0.0)),
                                        confidence=str(ins.get("confidence", "high")),
                                        caveats=ins.get("caveats", []) or [],
                                        impact_score=float(ins.get("impact_score", 0.0)),
                                        chart_spec=cs_obj
                                    ))
                                self.job_insights = parsed_insights
                                self.job_analytical_insights = [i for i in parsed_insights if i.type != "data_quality"][:6]
                                self.job_data_quality_insights = [i for i in parsed_insights if i.type == "data_quality"][:4]
                                self.job_chart_specs = res_obj.get("chart_specifications") or []
                                
                                ver = data.get("verification") or {}
                                self.job_verification = ver
                                self.verification_verified_count = ver.get("verified_claims_count", 0)
                                self.verification_total_count = ver.get("total_claims_checked", 0)
                                self.verification_rate = ver.get("verification_rate_percent", 100.0)
                                self.verification_is_valid = ver.get("is_valid", True)
                                
                                # Generate suggested questions from top insights
                                if self.job_insights:
                                    self.suggested_questions = [
                                        f"Can you explain the {ins.type}: '{ins.title}'?"
                                        for ins in self.job_insights[:3]
                                    ]

                            # Fetch complete run log
                            log_res = await client.get(f"{API_BASE_URL}/jobs/{job_id}/logs")
                            if log_res.status_code == 200:
                                raw_log = log_res.json().get("run_log", [])
                                parsed_log = []
                                for entry in raw_log:
                                    parsed_log.append(RunLogStepModel(
                                        step=int(entry.get("step", 0)),
                                        tool=str(entry.get("tool", "")),
                                        rationale=str(entry.get("rationale", "")),
                                        model=str(entry.get("model", "")),
                                        tool_time_ms=float(entry.get("tool_time_ms", 0.0)),
                                        llm_latency_ms=float(entry.get("llm_latency_ms", 0.0)),
                                        tokens=int(entry.get("tokens", 0))
                                    ))
                                async with self:
                                    self.job_run_log = parsed_log
                            return
            except Exception:
                pass

    async def ensure_dashboard_data(self):
        """Ensure dashboard has populated data by loading latest completed job or insights if empty."""
        if self.job_insights:
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{API_BASE_URL}/jobs?limit=5")
                if res.status_code == 200:
                    jobs = res.json()
                    completed_jobs = [j for j in jobs if j.get("status") in ("completed", "budget_tripped") and j.get("results")]
                    if completed_jobs:
                        latest = completed_jobs[0]
                        self.active_job_id = latest["job_id"]
                        self.selected_dataset_id = latest["dataset_id"]
                        res_obj = latest.get("results") or {}
                        raw_insights = res_obj.get("insights") or []
                        parsed_insights = []
                        for ins in raw_insights:
                            cs = ins.get("chart_spec")
                            cs_obj = None
                            if cs and isinstance(cs, dict):
                                cs_obj = ChartSpecModel(
                                    chart_type=str(cs.get("chart_type", "bar")),
                                    title=str(cs.get("title", "")),
                                    x_label=str(cs.get("x_label", "")),
                                    y_label=str(cs.get("y_label", "")),
                                    x_key=str(cs.get("x_key", "category")),
                                    y_key=str(cs.get("y_key", "value")),
                                    data=cs.get("data", [])
                                )
                            parsed_insights.append(InsightModel(
                                id=str(ins.get("id", "")),
                                type=str(ins.get("type", "insight")),
                                title=str(ins.get("title", "")),
                                summary=str(ins.get("summary", "")),
                                significance=ins.get("significance"),
                                effect_size=ins.get("effect_size"),
                                n_used=int(ins.get("n_used", 0)),
                                n_excluded=int(ins.get("n_excluded", 0)),
                                exclusion_rate=float(ins.get("exclusion_rate", 0.0)),
                                confidence=str(ins.get("confidence", "high")),
                                caveats=ins.get("caveats", []) or [],
                                impact_score=float(ins.get("impact_score", 0.0)),
                                chart_spec=cs_obj
                            ))
                        self.job_insights = parsed_insights
                        self.job_analytical_insights = [i for i in parsed_insights if i.type != "data_quality"][:6]
                        self.job_data_quality_insights = [i for i in parsed_insights if i.type == "data_quality"][:4]
                        self.job_chart_specs = res_obj.get("chart_specifications") or []
                        synth = res_obj.get("synthesis") or {}
                        self.job_synthesis = synth
                        self.job_executive_summary = synth.get("executive_summary", "")
                        self.job_key_findings = synth.get("key_findings", [])
                        self.job_recommendations = synth.get("recommendations", [])
                        ver = latest.get("verification") or {}
                        self.job_verification = ver
                        self.verification_verified_count = ver.get("verified_claims_count", 0)
                        self.verification_total_count = ver.get("total_claims_checked", 0)
                        self.verification_rate = ver.get("verification_rate_percent", 100.0)
                        self.verification_is_valid = ver.get("is_valid", True)
                        self.job_status = "completed"
        except Exception as e:
            print("ensure_dashboard_data error:", e)

    async def on_load_dashboard(self):
        """Unified on_load event for dashboard and chat."""
        await self.fetch_datasets()
        await self.ensure_dashboard_data()

    async def on_load_reports(self):
        """Unified on_load event for reports."""
        await self.fetch_datasets()
        await self.fetch_reports()

    def clear_chat(self):
        """Reset conversation message history."""
        self.chat_messages = []

    async def ask_suggested(self, q: str):
        """Ask a suggested question directly."""
        self.chat_input = q
        await self.send_chat_message()

    async def send_chat_message(self):
        """Send Q&A prompt to /chat endpoint (Milestone 4)."""
        prompt = self.chat_input.strip()
        if not prompt:
            return

        self.chat_input = ""
        self.is_chatting = True
        self.chat_messages.append(ChatMessageModel(
            role="user",
            content=prompt,
            evidence=[]
        ))

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "job_id": self.active_job_id,
                    "dataset_id": self.selected_dataset_id,
                    "question": prompt,
                    "history": [{"role": m.role, "content": m.content} for m in self.chat_messages[:-1]]
                }
                res = await client.post(f"{API_BASE_URL}/chat", json=payload)
                if res.status_code == 200:
                    ans_data = res.json()
                    raw_ev = ans_data.get("evidence", [])
                    ev_list = []
                    for e in raw_ev:
                        ev_list.append(EvidenceItemModel(
                            type=str(e.get("type", "insight")),
                            id=str(e.get("id", "")),
                            title=str(e.get("title", e.get("tool", ""))),
                            tool=str(e.get("tool", ""))
                        ))
                    ver = ans_data.get("verification", {})
                    is_val = ver.get("is_valid", True)
                    checked = ver.get("total_claims_checked", 0)
                    ver_sum = f"{ver.get('verified_claims_count', 0)}/{checked} claims verified" if checked > 0 else "Fact-aligned"
                    self.chat_messages.append(ChatMessageModel(
                        role="assistant",
                        content=ans_data.get("answer", "No response generated."),
                        evidence=ev_list,
                        verification_is_valid=is_val,
                        verification_summary=ver_sum
                    ))
                else:
                    self.chat_messages.append(ChatMessageModel(
                        role="assistant",
                        content=f"Error: Unable to get response from analyst engine ({res.status_code}).",
                        evidence=[],
                        verification_is_valid=False,
                        verification_summary="Error"
                    ))
        except Exception as e:
            self.chat_messages.append(ChatMessageModel(
                role="assistant",
                content=f"Request failed: {str(e)}",
                evidence=[],
                verification_is_valid=False,
                verification_summary="Exception"
            ))
        finally:
            self.is_chatting = False
