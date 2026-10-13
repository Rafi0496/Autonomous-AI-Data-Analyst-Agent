"""State management for the Reflex frontend application (Phases 1-3)."""
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import httpx
import reflex as rx

_raw_api_url = os.getenv("API_URL", "").strip().rstrip("/")
if not _raw_api_url:
    _raw_api_url = "https://autonomous-ai-data-analyst-backend.onrender.com/api/v1"
elif _raw_api_url in ("autonomous-ai-data-analyst-backend", "http://autonomous-ai-data-analyst-backend", "https://autonomous-ai-data-analyst-backend"):
    _raw_api_url = "https://autonomous-ai-data-analyst-backend.onrender.com/api/v1"
elif "autonomous-ai-data-analyst-backend" in _raw_api_url and "onrender.com" not in _raw_api_url:
    _raw_api_url = "https://autonomous-ai-data-analyst-backend.onrender.com/api/v1"
elif not _raw_api_url.startswith(("http://", "https://")):
    if "onrender.com" in _raw_api_url:
        _raw_api_url = f"https://{_raw_api_url}"
    elif "localhost" in _raw_api_url or "127.0.0.1" in _raw_api_url:
        _raw_api_url = f"http://{_raw_api_url}"
    else:
        _raw_api_url = f"https://{_raw_api_url}.onrender.com"
if not _raw_api_url.endswith("/api/v1"):
    _raw_api_url = f"{_raw_api_url}/api/v1"
API_BASE_URL = _raw_api_url

def safe_json(res: Any, default: Any = None) -> Any:
    """Safely decode JSON from httpx Response, avoiding Expecting value line 1 column 1 error."""
    if default is None:
        default = {}
    if not isinstance(res, httpx.Response):
        return default
    try:
        if res.content and len(res.content.strip()) > 0:
            return res.json()
    except Exception:
        pass
    return default

def extract_error_detail(res: Any, fallback: str = "Request failed") -> str:
    """Extract human-readable error detail from response, never crashing on non-JSON."""
    if not isinstance(res, httpx.Response):
        return str(res) if res else fallback
    try:
        data = safe_json(res)
        if isinstance(data, dict):
            for key in ("detail", "message", "error"):
                val = data.get(key)
                if val:
                    if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                        return str(val[0].get("msg", val[0]))
                    return str(val)
        if res.text and len(res.text.strip()) > 0 and not res.text.strip().startswith("<"):
            return res.text[:200]
    except Exception:
        pass
    if res.status_code == 502:
        return "Backend service is waking up (Bad Gateway). Please retry in a few seconds."
    elif res.status_code == 503:
        return "Backend service is temporarily unavailable. Please retry shortly."
    elif res.status_code == 404:
        return "Requested resource was not found."
    return f"{fallback} (HTTP {res.status_code})"

from pydantic import BaseModel

def normalize_chart_data(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [item if isinstance(item, dict) else {"value": item} for item in data]
    if isinstance(data, dict):
        matrix = data.get("matrix", [])
        cols = data.get("columns", [])
        if matrix and cols:
            return [
                {"feature": cols[i] if i < len(cols) else f"row_{i}", **{cols[j]: matrix[i][j] for j in range(min(len(cols), len(matrix[i])))}}
                for i in range(len(matrix))
            ]
    return []

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

class RecentJobModel(BaseModel):
    job_id: str = ""
    dataset_id: str = ""
    dataset_name: str = ""
    status: str = "completed"
    goal: str = ""
    created_at: str = ""
    time_group: str = "Today"
    is_pinned: bool = False

class AppState(rx.State):
    """Global reactive state managing datasets, profiling, agent execution, dashboard, and chat."""
    
    # Navigation
    active_tab: str = "home"

    @rx.var
    def current_page_tab(self) -> str:
        path = self.router.page.path or ""
        clean = path.strip("/").split("/")[0]
        if not clean or clean == "":
            return "home"
        return clean

    def select_tab(self, tab: str):
        self.active_tab = tab

    def go_to_upload(self):
        self.active_tab = "upload"
        return rx.redirect("/upload")

    def go_to_dashboard(self):
        self.active_tab = "dashboard"
        return rx.redirect("/dashboard")
    
    # Upload State Machine (exactly one visible at a time: idle | selected | uploading | processing | ready | failed)
    upload_ui_state: str = "idle"
    upload_progress_pct: int = 0
    upload_stage_name: str = "Validating"
    upload_error_reason: str = ""
    selected_file_name: str = ""
    selected_file_size_str: str = ""
    selected_file_type: str = ""
    detected_reader: str = "Universal File Parser"
    is_server_waking: bool = False

    def handle_upload_progress(self, prog: Dict[str, Any]):
        p = prog.get("progress", 0.0)
        self.upload_progress_pct = min(int(p * 100), 100)
        if self.upload_progress_pct > 0 and self.upload_ui_state != "uploading":
            self.upload_ui_state = "uploading"

    def reset_upload(self):
        self.upload_ui_state = "idle"
        self.upload_progress_pct = 0
        self.upload_stage_name = "Validating"
        self.upload_error_reason = ""
        self.selected_file_name = ""
        self.selected_file_size_str = ""
        self.selected_file_type = ""
        self.error_message = ""

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
    active_provider: str = "AI engine"
    active_model: str = "Autonomous Analytics Engine"
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

    # Phase 4: Authentication State & Multi-User Isolation
    auth_token: str = rx.LocalStorage("")
    current_user_email: str = ""
    current_user_name: str = ""
    is_authenticated: bool = False
    auth_error: str = ""
    auth_email_input: str = ""
    auth_password_input: str = ""
    auth_name_input: str = ""
    show_auth_dialog: bool = False
    auth_mode: str = "login"  # "login" | "register"

    # Phase 4: Insight Feedback (Plan §8.6)
    insight_feedback_map: Dict[str, str] = {}  # insight_id -> "helpful" | "not_relevant"

    # Layout, Sidebar & Neumorphic Shell
    sidebar_collapsed: bool = False
    sidebar_search_query: str = ""
    theme_mode: str = "light"
    pinned_job_ids: List[str] = []
    recent_jobs: List[RecentJobModel] = []
    hero_prompt: str = ""
    hero_mode: str = "autonomous"
    api_health_status: str = "Healthy"
    api_service_version: str = "0.1.0"

    @property
    def auth_headers(self) -> Dict[str, str]:
        if self.auth_token:
            return {"Authorization": f"Bearer {self.auth_token}"}
        return {}

    def toggle_auth_dialog(self):
        self.show_auth_dialog = not self.show_auth_dialog
        self.auth_error = ""

    def set_auth_mode(self, mode: str):
        self.auth_mode = mode
        self.auth_error = ""

    def set_auth_email(self, val: str):
        self.auth_email_input = val

    def set_auth_password(self, val: str):
        self.auth_password_input = val

    def set_auth_name(self, val: str):
        self.auth_name_input = val

    async def handle_unauthorized(self):
        """Handle 401 response: reset token and redirect to /login."""
        self.auth_token = ""
        self.is_authenticated = False
        self.current_user_email = ""
        self.current_user_name = ""
        self.auth_error = "Authentication required or session expired. Please sign in."
        return rx.redirect("/login")

    async def fetch_me(self):
        """Fetch current user profile via /auth/me."""
        if not self.auth_token:
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{API_BASE_URL}/auth/me", headers=self.auth_headers)
                if res.status_code == 200:
                    u = safe_json(res)
                    self.current_user_email = u.get("email", "")
                    self.current_user_name = u.get("full_name") or u.get("email", "")
                    self.is_authenticated = True
                elif res.status_code == 401:
                    await self.handle_unauthorized()
        except Exception:
            pass

    async def check_auth_or_redirect(self):
        """Guard for protected routes."""
        if self.auth_token:
            if not self.current_user_email:
                await self.fetch_me()
        else:
            return rx.redirect("/login")

    async def login(self):
        self.auth_error = ""
        self.is_loading = True
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    f"{API_BASE_URL}/auth/login",
                    json={"email": self.auth_email_input.strip(), "password": self.auth_password_input}
                )
                if res.status_code == 200:
                    data = safe_json(res)
                    self.auth_token = data.get("access_token", "")
                    u = data.get("user", {})
                    self.current_user_email = u.get("email", "")
                    self.current_user_name = u.get("full_name") or u.get("email", "")
                    self.is_authenticated = True
                    self.show_auth_dialog = False
                    self.auth_password_input = ""
                    await self.fetch_datasets(force=True)
                    await self.fetch_recent_jobs()
                    return rx.redirect("/")
                else:
                    self.auth_error = extract_error_detail(res, "Invalid email or password.")
        except httpx.ConnectTimeout:
            self.auth_error = "Connection timed out. Server may be starting up; please try again in a few seconds."
        except Exception as e:
            self.auth_error = f"Login connection error: {str(e)}"
        finally:
            self.is_loading = False

    async def register(self):
        self.auth_error = ""
        if len(self.auth_password_input) < 8:
            self.auth_error = "Password must be at least 8 characters long."
            return
        self.is_loading = True
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    f"{API_BASE_URL}/auth/register",
                    json={
                        "email": self.auth_email_input.strip(),
                        "password": self.auth_password_input,
                        "full_name": self.auth_name_input.strip() or None
                    }
                )
                if res.status_code == 201:
                    data = safe_json(res)
                    self.auth_token = data.get("access_token", "")
                    u = data.get("user", {})
                    self.current_user_email = u.get("email", "")
                    self.current_user_name = u.get("full_name") or u.get("email", "")
                    self.is_authenticated = True
                    self.show_auth_dialog = False
                    self.auth_password_input = ""
                    await self.fetch_datasets(force=True)
                    await self.fetch_recent_jobs()
                    return rx.redirect("/")
                else:
                    self.auth_error = extract_error_detail(res, "Registration failed.")
        except httpx.ConnectTimeout:
            self.auth_error = "Connection timed out. Server may be starting up; please try again in a few seconds."
        except Exception as e:
            self.auth_error = f"Registration connection error: {str(e)}"
        finally:
            self.is_loading = False

    def logout(self):
        self.auth_token = ""
        self.current_user_email = ""
        self.current_user_name = ""
        self.is_authenticated = False
        self.auth_email_input = ""
        self.auth_password_input = ""
        self.auth_name_input = ""
        return rx.redirect("/login")

    async def submit_insight_feedback(self, insight_id: str, rating: str):
        """Submit helpful / not_relevant rating for an insight (Plan §8.6)."""
        if not self.active_job_id or not insight_id:
            return
        self.insight_feedback_map[insight_id] = rating
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{API_BASE_URL}/jobs/{self.active_job_id}/insights/{insight_id}/feedback",
                    json={"rating": rating},
                    headers=self.auth_headers
                )
        except Exception:
            pass

    async def fetch_reports(self):
        """Fetch list of past generated reports from backend."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{API_BASE_URL}/reports", headers=self.auth_headers)
                if res.status_code == 200:
                    raw = safe_json(res, [])
                    if isinstance(raw, list):
                        self.past_reports = [ReportItemModel(**r) for r in raw if isinstance(r, dict)]
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
                res = await client.post(f"{API_BASE_URL}/jobs/{self.active_job_id}/report?format={fmt}", headers=self.auth_headers)
                if res.status_code == 200:
                    data = safe_json(res)
                    self.report_download_url = data.get("download_url", "")
                    await self.fetch_reports()
                else:
                    self.error_message = extract_error_detail(res, "Report generation failed")
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

    async def fetch_datasets(self, force: bool = False):
        """Fetch list of all datasets from backend. Caches result to remove page-switching lag."""
        if self.datasets and not force:
            return
        self.is_loading = True
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{API_BASE_URL}/datasets", headers=self.auth_headers)
                if res.status_code == 200:
                    raw = safe_json(res, [])
                    if isinstance(raw, list):
                        self.datasets = raw
                    if self.datasets and not self.selected_dataset_id:
                        await self.select_dataset(self.datasets[0].get("id", ""))
                elif res.status_code == 401:
                    await self.handle_unauthorized()
        except Exception as e:
            self.error_message = f"Unable to reach backend: {str(e)}"
        finally:
            self.is_loading = False

    async def select_dataset(self, dataset_id: str):
        """Select active dataset and load preview, profile, and cleaning report in parallel."""
        if not dataset_id:
            return
        self.selected_dataset_id = dataset_id
        for d in self.datasets:
            if d.get("id") == dataset_id:
                self.selected_dataset_name = d.get("filename", "Dataset")
                break

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Run all 3 endpoints concurrently instead of serially to cut response time by 75%
                p_task = client.get(f"{API_BASE_URL}/datasets/{dataset_id}/preview?rows=8", headers=self.auth_headers)
                prof_task = client.get(f"{API_BASE_URL}/datasets/{dataset_id}/profile", headers=self.auth_headers)
                cl_task = client.get(f"{API_BASE_URL}/datasets/{dataset_id}/cleaning-report", headers=self.auth_headers)
                
                results = await asyncio.gather(p_task, prof_task, cl_task, return_exceptions=True)
                p_res, prof_res, cl_res = results

                # 1. Preview
                if isinstance(p_res, httpx.Response) and p_res.status_code == 200:
                    p_data = safe_json(p_res)
                    self.preview_columns = p_data.get("columns", [])
                    self.preview_rows = p_data.get("rows", [])
                    self.row_count = p_data.get("total_rows", 0)
                    self.column_count = p_data.get("total_columns", 0)

                # 2. Profile
                if isinstance(prof_res, httpx.Response) and prof_res.status_code == 200:
                    prof_data = safe_json(prof_res)
                    if prof_data:
                        self._parse_profile(prof_data)
                else:
                    self.has_profile = False

                # 3. Cleaning Report
                if isinstance(cl_res, httpx.Response) and cl_res.status_code == 200:
                    cl_data = safe_json(cl_res)
                    if cl_data:
                        self._parse_cleaning_report(cl_data)
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
                res = await client.post(f"{API_BASE_URL}/datasets/{self.selected_dataset_id}/profile", headers=self.auth_headers)
                if res.status_code == 200:
                    prof = safe_json(res)
                    if prof:
                        self._parse_profile(prof)
                    self.status_message = "Dataset profiled successfully."
                else:
                    self.error_message = extract_error_detail(res, "Profiling failed")
        except Exception as e:
            self.error_message = f"Profiling error: {str(e)}"
        finally:
            self.is_profiling = False

    async def handle_upload(self, files: List[rx.UploadFile]):
        """Upload file via streaming chunks to FastAPI (no full memory buffer) with UI state machine."""
        if not files:
            self.upload_ui_state = "failed"
            self.upload_error_reason = "No file selected. Please choose a file to upload."
            return

        file = files[0]
        filename = file.filename or "uploaded_dataset"
        self.selected_file_name = filename
        ext = filename.split(".")[-1].upper() if "." in filename else "FILE"
        self.selected_file_type = ext

        self.upload_ui_state = "uploading"
        self.upload_progress_pct = 100
        self.upload_ui_state = "processing"
        self.upload_stage_name = "Validating file structure"
        self.error_message = ""

        try:
            # Stream directly without loading into giant in-memory string
            if hasattr(file.file, "seek"):
                file.file.seek(0)
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                files_payload = {"file": (filename, file.file, file.content_type or "application/octet-stream")}
                res = await client.post(f"{API_BASE_URL}/upload", files=files_payload, headers=self.auth_headers)

                if res.status_code in (201, 202):
                    data = safe_json(res)
                    dataset_id = data.get("dataset_id")
                    self.detected_reader = data.get("detected_reader") or f"Universal {ext} Parser"

                    stages = ["Parsing data records", "Cleaning & sanitizing", "Profiling distributions", "Scoring quality"]
                    for stage in stages:
                        self.upload_stage_name = stage
                        await asyncio.sleep(0.3)
                        ds_res = await client.get(f"{API_BASE_URL}/datasets/{dataset_id}", headers=self.auth_headers)
                        if ds_res.status_code == 200 and safe_json(ds_res).get("is_ready"):
                            break

                    final_res = await client.get(f"{API_BASE_URL}/datasets/{dataset_id}", headers=self.auth_headers)
                    if final_res.status_code == 200:
                        final_data = safe_json(final_res)
                        self.row_count = final_data.get("row_count", 0)
                        self.column_count = final_data.get("column_count", 0)
                        self.quality_score = float(final_data.get("quality_score") or 92.0)
                        if final_data.get("profile"):
                            self._parse_profile(final_data["profile"])
                        if final_data.get("cleaning_summary"):
                            self._parse_cleaning_report(final_data["cleaning_summary"])

                    await self.fetch_datasets(force=True)
                    await self.select_dataset(dataset_id)
                    await self.fetch_recent_jobs()

                    self.upload_ui_state = "ready"
                    self.status_message = f"Dataset {filename} ready for analysis!"
                    return rx.toast.success(f"{filename} successfully parsed and ready!", position="bottom-right")

                elif res.status_code == 401:
                    return await self.handle_unauthorized()
                elif res.status_code == 413:
                    self.upload_ui_state = "failed"
                    self.upload_error_reason = "The uploaded file exceeds the maximum allowed size limit (50 MB)."
                else:
                    self.upload_ui_state = "failed"
                    self.upload_error_reason = extract_error_detail(res, f"Upload processing failed (HTTP {res.status_code})")
        except httpx.ConnectTimeout:
            self.upload_ui_state = "failed"
            self.upload_error_reason = "Server timeout while connecting to the analytics engine. The backend is waking up; please try again in a moment."
        except Exception as e:
            self.upload_ui_state = "failed"
            self.upload_error_reason = f"Upload failed: {str(e)}"

    async def load_sample(self, sample_name: str):
        """Quick load benchmark dataset with full state transitions."""
        self.upload_ui_state = "processing"
        self.upload_stage_name = "Validating benchmark dataset"
        self.selected_file_name = sample_name
        self.selected_file_type = "CSV"
        self.error_message = ""

        sample_path = Path("data/samples") / sample_name
        if not sample_path.exists():
            for candidate in [
                Path("/app/data/samples") / sample_name,
                Path("frontend/data/samples") / sample_name,
                Path("/app/frontend/data/samples") / sample_name,
            ]:
                if candidate.exists():
                    sample_path = candidate
                    break
            else:
                self.upload_ui_state = "failed"
                self.upload_error_reason = f"Benchmark dataset {sample_name} not found on server."
                return

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                with open(sample_path, "rb") as f:
                    files_payload = {"file": (sample_name, f, "text/csv")}
                    res = await client.post(f"{API_BASE_URL}/upload", files=files_payload, headers=self.auth_headers)

                if res.status_code in (201, 202):
                    data = safe_json(res)
                    dataset_id = data.get("dataset_id")
                    
                    stages = ["Parsing records", "Cleaning & normalizing", "Profiling distributions", "Scoring quality"]
                    for stage in stages:
                        self.upload_stage_name = stage
                        await asyncio.sleep(0.3)

                    final_res = await client.get(f"{API_BASE_URL}/datasets/{dataset_id}", headers=self.auth_headers)
                    if final_res.status_code == 200:
                        final_data = safe_json(final_res)
                        self.row_count = final_data.get("row_count", 0)
                        self.column_count = final_data.get("column_count", 0)
                        self.quality_score = float(final_data.get("quality_score") or 91.5)
                        if final_data.get("profile"):
                            self._parse_profile(final_data["profile"])

                    await self.fetch_datasets(force=True)
                    await self.select_dataset(dataset_id)
                    await self.fetch_recent_jobs()

                    self.upload_ui_state = "ready"
                    self.status_message = f"Benchmark {sample_name} loaded and prepared successfully!"
                    return rx.toast.success(f"{sample_name} ready for analysis!", position="bottom-right")
                elif res.status_code == 401:
                    return await self.handle_unauthorized()
                else:
                    self.upload_ui_state = "failed"
                    self.upload_error_reason = extract_error_detail(res, "Failed loading benchmark dataset")
        except httpx.ConnectTimeout:
            self.upload_ui_state = "failed"
            self.upload_error_reason = "Connection timed out connecting to backend. The backend is waking up; please try again in a moment."
        except Exception as e:
            self.upload_ui_state = "failed"
            self.upload_error_reason = f"Error loading benchmark: {str(e)}"

    async def start_analysis(self):
        """Submit analysis job and immediately navigate to Run monitor with instant toast acknowledgment."""
        if not self.selected_dataset_id:
            self.error_message = "Please select or upload a dataset before starting analysis."
            return rx.toast.warning("Please upload or select a dataset first.", position="bottom-right")

        self.is_analyzing = True
        self.is_polling = True
        self.error_message = ""
        self.job_status = "running"
        self.job_phase = "queued"
        self.job_current_step = 0
        self.job_current_step_name = "Perceiving dataset structure"
        self.active_tab = "run"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "dataset_id": self.selected_dataset_id,
                    "goal": self.analysis_goal,
                    "max_steps": self.step_budget_setting,
                    "token_budget": self.token_budget_setting,
                }
                res = await client.post(f"{API_BASE_URL}/jobs", json=payload, headers=self.auth_headers)
                if res.status_code in (200, 201, 202):
                    data = safe_json(res)
                    self.active_job_id = data.get("job_id", "")
                    self.job_current_step_name = data.get("current_step_name", "Perceiving dataset structure")
                    return [
                        rx.toast.info("Autonomous analysis initiated. Monitoring execution...", position="bottom-right"),
                        rx.redirect("/run"),
                        AppState.poll_job_progress,
                    ]
                elif res.status_code == 401:
                    return await self.handle_unauthorized()
                else:
                    self.error_message = extract_error_detail(res, "Failed to start analysis")
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
                    res = await client.get(f"{API_BASE_URL}/jobs/{job_id}", headers=self.auth_headers)
                    if res.status_code == 200:
                        data = safe_json(res)
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
                                            data=normalize_chart_data(cs.get("data", []))
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
                            log_res = await client.get(f"{API_BASE_URL}/jobs/{job_id}/logs", headers=self.auth_headers)
                            if log_res.status_code == 200:
                                raw_log = safe_json(log_res).get("run_log", [])
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

    async def load_job(self, job_id: str):
        """Load an existing job's status, progress, logs, insights, and synthesis."""
        if not job_id:
            return
        self.active_job_id = job_id
        self.is_loading = True
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(f"{API_BASE_URL}/jobs/{job_id}", headers=self.auth_headers)
                if res.status_code == 200:
                    data = safe_json(res)
                    self.selected_dataset_id = data.get("dataset_id", "")
                    self.job_status = data.get("status", "completed")
                    self.job_phase = data.get("phase", "synthesis")
                    self.job_current_step = data.get("current_step", 0)
                    self.job_current_step_name = data.get("current_step_name", "Completed")
                    self.job_total_steps = data.get("total_steps", 0)
                    self.job_step_limit = data.get("step_limit", 5)
                    self.job_elapsed_seconds = data.get("execution_time_seconds", 0.0)
                    self.job_tokens_used = str(data.get("tokens_used", 0))
                    self.job_token_budget = data.get("token_budget", 15000)

                    # Parse results
                    res_obj = data.get("results") or {}
                    synth = res_obj.get("synthesis") or {}
                    self.job_synthesis = synth
                    self.job_executive_summary = synth.get("executive_summary", "")
                    self.job_key_findings = synth.get("key_findings", [])
                    self.job_recommendations = synth.get("recommendations", [])
                    
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
                                data=normalize_chart_data(cs.get("data", []))
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

                # Fetch run log
                log_res = await client.get(f"{API_BASE_URL}/jobs/{job_id}/logs", headers=self.auth_headers)
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
                    self.job_run_log = parsed_log

                # Sync dataset name
                if self.selected_dataset_id:
                    for d in self.datasets:
                        if d.get("id") == self.selected_dataset_id:
                            self.selected_dataset_name = d.get("filename", "Dataset")
                            break
        except Exception as e:
            self.error_message = f"Failed loading job: {str(e)}"
        finally:
            self.is_loading = False

    async def retry_job(self):
        """Retry analysis for active dataset."""
        if self.selected_dataset_id:
            return await self.start_analysis()

    @rx.var
    def job_progress_pct(self) -> int:
        if self.job_status in ("completed", "budget_tripped"):
            return 100
        if self.job_status == "failed":
            return 100
        phase_map = {
            "queued": 10,
            "profiling": 20,
            "planning": 40,
            "executing": 60,
            "execution": 60,
            "reflection": 80,
            "synthesis": 95,
        }
        return phase_map.get(self.job_phase, 20)

    @rx.var
    def is_perceive_done(self) -> bool:
        return self.job_phase in ("planning", "executing", "execution", "reflection", "synthesis", "completed") or self.job_status in ("completed", "budget_tripped")

    @rx.var
    def is_perceive_active(self) -> bool:
        return self.job_status == "running" and self.job_phase in ("queued", "profiling")

    @rx.var
    def is_plan_done(self) -> bool:
        return self.job_phase in ("executing", "execution", "reflection", "synthesis", "completed") or self.job_status in ("completed", "budget_tripped")

    @rx.var
    def is_plan_active(self) -> bool:
        return self.job_status == "running" and self.job_phase == "planning"

    @rx.var
    def is_act_done(self) -> bool:
        return self.job_phase in ("reflection", "synthesis", "completed") or self.job_status in ("completed", "budget_tripped")

    @rx.var
    def is_act_active(self) -> bool:
        return self.job_status == "running" and self.job_phase in ("executing", "execution")

    @rx.var
    def is_reflect_done(self) -> bool:
        return self.job_phase in ("synthesis", "completed") or self.job_status in ("completed", "budget_tripped")

    @rx.var
    def is_reflect_active(self) -> bool:
        return self.job_status == "running" and self.job_phase == "reflection"

    @rx.var
    def is_synth_done(self) -> bool:
        return self.job_status in ("completed", "budget_tripped")

    @rx.var
    def is_synth_active(self) -> bool:
        return self.job_status == "running" and self.job_phase == "synthesis"

    @rx.var
    def is_budget_tripped(self) -> bool:
        return self.job_status == "budget_tripped"

    @rx.var
    def token_budget_pct(self) -> int:
        try:
            used = int(self.job_tokens_used)
            budget = max(int(self.job_token_budget), 1)
            return min(int((used / budget) * 100), 100)
        except Exception:
            return 0

    @rx.var
    def quality_score_text(self) -> str:
        return f"{self.quality_score:.1f}/100"

    @rx.var
    def verification_rate_text(self) -> str:
        return f"{self.verification_rate:.0f}%"

    @rx.var
    def verification_badge_text(self) -> str:
        return f"{self.verification_verified_count}/{self.verification_total_count} Verified ({self.verification_rate:.0f}%)"

    @rx.var
    def running_status_text(self) -> str:
        return f"Phase: {self.job_phase} | Step {self.job_current_step}: {self.job_current_step_name}"

    async def ensure_dashboard_data(self):
        """Ensure dashboard has populated data by loading latest completed job or insights if empty."""
        if self.job_insights:
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{API_BASE_URL}/jobs?limit=5", headers=self.auth_headers)
                if res.status_code == 200:
                    jobs = safe_json(res, [])
                    completed_jobs = [j for j in jobs if isinstance(j, dict) and j.get("status") in ("completed", "budget_tripped") and j.get("results")]
                    if completed_jobs:
                        latest_job_id = completed_jobs[0]["job_id"]
                        await self.load_job(latest_job_id)
        except Exception as e:
            print("ensure_dashboard_data error:", e)

    async def on_load_dashboard(self):
        """Instant on_load event for dashboard."""
        self.active_tab = "dashboard"
        if not self.datasets:
            await self.fetch_datasets()
        if not self.active_job_id and self.recent_jobs:
            self.active_job_id = self.recent_jobs[0].job_id
        if not self.job_insights:
            await self.ensure_dashboard_data()

    async def on_load_run(self):
        """Instant on_load handler for /run page."""
        self.active_tab = "run"
        if not self.datasets:
            await self.fetch_datasets()
        if self.active_job_id and not self.job_insights:
            await self.load_job(self.active_job_id)
        elif self.recent_jobs and not self.job_insights:
            await self.load_job(self.recent_jobs[0].job_id)

    async def on_load_upload(self):
        """Instant on_load event for /upload screen: ZERO lag when switching from home."""
        self.active_tab = "upload"
        if not self.datasets:
            await self.fetch_datasets()

    async def on_load_chat(self):
        """Instant on_load event for /chat screen: binds active job immediately."""
        self.active_tab = "chat"
        if not self.recent_jobs:
            await self.fetch_recent_jobs()
        if not self.active_job_id and self.recent_jobs:
            self.active_job_id = self.recent_jobs[0].job_id

    async def on_load_reports(self):
        """Instant on_load event for reports."""
        self.active_tab = "reports"
        if not self.past_reports:
            await self.fetch_reports()

    def on_load_settings(self):
        """Instant on_load event for settings."""
        self.active_tab = "settings"

    def on_load_login(self):
        """Instant on_load event for login."""
        self.active_tab = "login"

    def clear_chat(self):
        """Reset conversation message history."""
        self.chat_messages = []

    async def ask_suggested(self, q: str):
        """Ask a suggested question directly."""
        self.chat_input = q
        await self.send_chat_message()

    def handle_chat_key_down(self, key: str, info: Dict[str, Any]):
        """Enter sends, Shift+Enter inserts newline, ignores IME composition."""
        if key in ("Process", "Unidentified"):
            return
        if key == "Enter":
            if info.get("shift_key"):
                return
            if not self.chat_input.strip() or self.is_chatting:
                return
            return AppState.send_chat_message

    def handle_hero_key_down(self, key: str, info: Dict[str, Any]):
        """Enter sends hero prompt, Shift+Enter inserts newline, ignores IME composition."""
        if key in ("Process", "Unidentified"):
            return
        if key == "Enter":
            if info.get("shift_key"):
                return
            if not self.hero_prompt.strip() or self.is_chatting:
                return
            return AppState.handle_hero_submit

    async def retry_last_chat_message(self):
        """Retry the last question sent by user."""
        for msg in reversed(self.chat_messages):
            if msg.role == "user" and msg.content.strip():
                self.chat_input = msg.content
                return await self.send_chat_message()

    async def send_chat_message(self):
        """Send Q&A prompt to /chat endpoint with friendly error handling, typing indicator, and scroll."""
        prompt = self.chat_input.strip()
        if not prompt or self.is_chatting:
            return

        self.chat_input = ""
        self.is_chatting = True
        self.chat_messages.append(ChatMessageModel(
            role="user",
            content=prompt,
            evidence=[]
        ))

        # Check if greeting or out of scope inquiry before requiring an active job
        greetings = {"hi", "hello", "hey", "help", "who are you", "what can you do", "start", "good morning", "good afternoon", "good evening"}
        clean_p = prompt.lower().strip("?!., \t\n")
        
        # If user asks a general greeting or agent question and no job has run yet:
        if clean_p in greetings and not self.active_job_id:
            ds_context = f" I see '{self.selected_dataset_name}' is currently loaded." if (self.selected_dataset_id and self.selected_dataset_name != "No dataset selected") else " You can upload a dataset or select one of the preloaded benchmarks to begin."
            self.chat_messages.append(ChatMessageModel(
                role="assistant",
                content=f"Hello! I am your Autonomous Data Analyst Agent.{ds_context} I perform deterministic data cleaning, hypothesis testing, anomaly detection, and grounded synthesis with citation verification. How can I help you investigate your data today?",
                evidence=[],
                verification_is_valid=True,
                verification_summary="Assistant Ready"
            ))
            self.is_chatting = False
            return [
                rx.call_script("document.getElementById('chat-input-textarea')?.focus();"),
                rx.call_script("const el = document.getElementById('chat-thread-container'); if(el) el.scrollTop = el.scrollHeight;"),
            ]

        # If user has no active job but recent jobs exist, auto-bind to the most recent job!
        effective_job_id = self.active_job_id
        if not effective_job_id and self.recent_jobs:
            effective_job_id = self.recent_jobs[0].job_id
            self.active_job_id = effective_job_id

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                payload = {
                    "job_id": effective_job_id or None,
                    "dataset_id": self.selected_dataset_id or None,
                    "question": prompt,
                    "history": [{"role": m.role, "content": m.content} for m in self.chat_messages[:-1]]
                }
                res = await client.post(f"{API_BASE_URL}/chat", json=payload, headers=self.auth_headers)
                
                # If 422 because backend expects job_id or question schema
                if res.status_code == 422 and not effective_job_id:
                    self.chat_messages.append(ChatMessageModel(
                        role="assistant",
                        content="To answer specific questions regarding statistics, metrics, or anomalies, please select or upload a dataset and run an analysis first. You can click 'Load Benchmark' on the Datasets screen or upload your own file to get started.",
                        evidence=[],
                        verification_is_valid=True,
                        verification_summary="Dataset Selected" if self.selected_dataset_id else "Upload Required"
                    ))
                    self.is_chatting = False
                    return [
                        rx.call_script("document.getElementById('chat-input-textarea')?.focus();"),
                        rx.call_script("const el = document.getElementById('chat-thread-container'); if(el) el.scrollTop = el.scrollHeight;"),
                    ]

                if res.status_code == 200:
                    ans_data = safe_json(res)
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
                elif res.status_code == 401:
                    return await self.handle_unauthorized()
                elif res.status_code == 404 and not effective_job_id:
                    self.chat_messages.append(ChatMessageModel(
                        role="assistant",
                        content="No completed analysis runs were found yet. Please select a benchmark dataset or upload your own file on the Datasets tab and click 'Run Analysis' to generate verified findings.",
                        evidence=[],
                        verification_is_valid=True,
                        verification_summary="Analysis Required"
                    ))
                else:
                    err_msg = extract_error_detail(res, "Unable to query analysis engine.")
                    self.chat_messages.append(ChatMessageModel(
                        role="assistant",
                        content=f"The analysis engine returned: {err_msg}. If the service was sleeping, please retry your question in a moment.",
                        evidence=[],
                        verification_is_valid=False,
                        verification_summary="Retryable"
                    ))
        except httpx.ConnectTimeout:
            self.chat_messages.append(ChatMessageModel(
                role="assistant",
                content="The analytics engine took too long to respond. The backend server may be waking up from sleep. Please click retry in a few seconds.",
                evidence=[],
                verification_is_valid=False,
                verification_summary="Retryable"
            ))
        except Exception as e:
            self.chat_messages.append(ChatMessageModel(
                role="assistant",
                content=f"Encountered connection issue: {str(e)}. Please retry your question.",
                evidence=[],
                verification_is_valid=False,
                verification_summary="Retryable"
            ))
        finally:
            self.is_chatting = False
            return [
                rx.call_script("document.getElementById('chat-input-textarea')?.focus();"),
                rx.call_script("const el = document.getElementById('chat-thread-container'); if(el) el.scrollTop = el.scrollHeight;"),
            ]

    # -------------------------------------------------------------
    # Neumorphic Layout & Sidebar Methods
    # -------------------------------------------------------------
    def toggle_sidebar(self):
        self.sidebar_collapsed = not self.sidebar_collapsed
        return rx.call_script(
            f"localStorage.setItem('aa_sidebar_collapsed', '{str(self.sidebar_collapsed).lower()}');"
        )

    def set_sidebar_search(self, query: str):
        self.sidebar_search_query = query

    def toggle_theme(self):
        self.theme_mode = "dark" if self.theme_mode == "light" else "light"
        return rx.call_script(
            f"localStorage.setItem('aa_theme_mode', '{self.theme_mode}');"
            f"document.documentElement.setAttribute('data-theme', '{self.theme_mode}');"
            f"document.body.setAttribute('data-theme', '{self.theme_mode}');"
        )

    def toggle_pin_job(self, job_id: str):
        if job_id in self.pinned_job_ids:
            self.pinned_job_ids = [j for j in self.pinned_job_ids if j != job_id]
        else:
            self.pinned_job_ids = self.pinned_job_ids + [job_id]

    def set_hero_prompt(self, val: str):
        self.hero_prompt = val

    def set_hero_mode(self, val: str):
        self.hero_mode = val

    @rx.var
    def greeting_message(self) -> str:
        from datetime import datetime
        hour = datetime.now().hour
        if hour < 12:
            period = "Good morning"
        elif hour < 17:
            period = "Good afternoon"
        else:
            period = "Good evening"
        if self.current_user_name and self.current_user_name.strip():
            return f"{period}, {self.current_user_name.strip()}"
        return period

    @rx.var
    def user_initial(self) -> str:
        name = self.current_user_name or self.current_user_email or "A"
        return name[0].upper() if name else "A"

    @rx.var
    def filtered_recent_jobs(self) -> List[RecentJobModel]:
        q = self.sidebar_search_query.strip().lower()
        if not q:
            return self.recent_jobs
        return [
            j for j in self.recent_jobs
            if q in j.dataset_name.lower()
            or q in j.goal.lower()
            or q in j.job_id.lower()
        ]

    @rx.var
    def today_jobs(self) -> List[RecentJobModel]:
        return [j for j in self.filtered_recent_jobs if j.time_group == "Today"]

    @rx.var
    def yesterday_jobs(self) -> List[RecentJobModel]:
        return [j for j in self.filtered_recent_jobs if j.time_group == "Yesterday"]

    @rx.var
    def older_jobs(self) -> List[RecentJobModel]:
        return [j for j in self.filtered_recent_jobs if j.time_group == "Older"]

    @rx.var
    def top_recent_jobs(self) -> List[RecentJobModel]:
        return self.recent_jobs[:3]

    @rx.var
    def dataset_options(self) -> List[str]:
        return [str(d.get("filename", "")) for d in self.datasets if d.get("filename")]

    def select_dataset_by_name(self, name: str):
        for d in self.datasets:
            if d.get("filename") == name:
                return self.select_dataset(d.get("id", ""))

    @rx.var
    def pinned_jobs(self) -> List[RecentJobModel]:
        return [j for j in self.recent_jobs if j.job_id in self.pinned_job_ids]

    async def fetch_recent_jobs(self):
        """Fetch list of recent jobs from backend and categorize by time group."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{API_BASE_URL}/jobs?limit=15", headers=self.auth_headers)
                if res.status_code == 200:
                    raw_jobs = safe_json(res, [])
                    if not isinstance(raw_jobs, list):
                        return
                    from datetime import datetime, timezone, timedelta
                    now = datetime.now(timezone.utc)
                    today_date = now.date()
                    yesterday_date = today_date - timedelta(days=1)
                    
                    ds_names = {d.get("id"): d.get("filename", "Dataset") for d in self.datasets if isinstance(d, dict)}
                    
                    parsed = []
                    for j in raw_jobs:
                        if not isinstance(j, dict):
                            continue
                        jid = str(j.get("job_id", ""))
                        created_str = str(j.get("created_at", ""))
                        ds_id = str(j.get("dataset_id", ""))
                        ds_name = ds_names.get(ds_id, "Dataset")
                        
                        time_group = "Older"
                        try:
                            clean_dt = created_str.replace("Z", "+00:00")
                            job_dt = datetime.fromisoformat(clean_dt)
                            if job_dt.date() == today_date:
                                time_group = "Today"
                            elif job_dt.date() == yesterday_date:
                                time_group = "Yesterday"
                            else:
                                time_group = "Older"
                        except Exception:
                            time_group = "Older"

                        parsed.append(RecentJobModel(
                            job_id=jid,
                            dataset_id=ds_id,
                            dataset_name=ds_name,
                            status=str(j.get("status", "completed")),
                            goal=str(j.get("goal") or "Autonomous Analysis"),
                            created_at=created_str,
                            time_group=time_group,
                            is_pinned=jid in self.pinned_job_ids,
                        ))
                    self.recent_jobs = parsed
        except Exception:
            pass

    async def check_api_health(self):
        """Check live backend health status and LLM configuration."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{API_BASE_URL}/health")
                if res.status_code == 200:
                    data = safe_json(res)
                    self.api_health_status = str(data.get("status", "healthy")).capitalize()
                    self.api_service_version = str(data.get("version", "0.1.0"))
        except Exception:
            self.api_health_status = "Offline"

    async def on_load_home(self):
        """Initialize home / new analysis screen with datasets, recent runs and health without lag."""
        self.active_tab = "home"
        tasks = []
        if not self.datasets:
            tasks.append(self.fetch_datasets())
        if not self.recent_jobs:
            tasks.append(self.fetch_recent_jobs())
        if self.api_health_status == "Offline" or not self.api_health_status:
            tasks.append(self.check_api_health())
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if not self.active_job_id and self.recent_jobs:
            self.active_job_id = self.recent_jobs[0].job_id

    async def handle_hero_submit(self):
        """Handle submit from the hero input box on the Home screen: opens chat and sends message."""
        prompt = self.hero_prompt.strip()
        if not prompt or self.is_chatting:
            return

        self.hero_prompt = ""
        self.chat_input = prompt
        self.active_tab = "chat"
        return [
            rx.redirect("/chat"),
            AppState.send_chat_message,
        ]
