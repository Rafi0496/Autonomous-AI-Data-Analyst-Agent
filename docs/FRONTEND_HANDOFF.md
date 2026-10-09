# Frontend Handoff & Backend API Integration Guide

This document is the definitive frontend integration handoff for the **Autonomous AI Data Analyst Agent** backend. It specifies the complete end-to-end user journey, HTTP headers, request/response formats, execution commands for Windows, and operational limitations.

---

## 1. Authentication & Security Specification

- **Base URL**: `http://localhost:8000/api/v1`
- **Authentication Scheme**: HTTP Bearer Token
- **Header Format**:
  ```http
  Authorization: Bearer <JWT_ACCESS_TOKEN>
  ```
- **Tenant Isolation**: All datasets, cleaning summaries, profiling reports, agent jobs, chat history, and exported reports are strictly isolated by `user_id`. Attempting to access another user's resources returns `404 Not Found`.

---

## 2. Standard Error Format

All error responses return a standardized JSON structure:

```json
{
  "detail": "Descriptive error message explaining the failure or constraint violation."
}
```

For HTTP 422 Unprocessable Content (validation failure):
```json
{
  "detail": [
    {
      "loc": ["body", "token_budget"],
      "msg": "Input should be greater than or equal to 1000",
      "type": "greater_than_equal"
    }
  ]
}
```

---

## 3. End-to-End API Flow (With Real Request/Response Payloads)

### Step 1: User Registration & Authentication
#### `POST /api/v1/auth/register`
**Request:**
```http
POST /api/v1/auth/register HTTP/1.1
Content-Type: application/json

{
  "email": "lead.analyst@example.com",
  "password": "SecurePassword2026!",
  "full_name": "Lead Analyst"
}
```
**Response (201 Created):**
```json
{
  "id": "usr_9b1a8d42e6f1",
  "email": "lead.analyst@example.com",
  "full_name": "Lead Analyst",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c3JfOWIxYThkNDJlNmYxIiwiZXhwIjoxNzkxNTU4MDAwfQ.XYZ123...",
  "token_type": "bearer"
}
```

#### `POST /api/v1/auth/login`
**Request:**
```http
POST /api/v1/auth/login HTTP/1.1
Content-Type: application/json

{
  "email": "lead.analyst@example.com",
  "password": "SecurePassword2026!"
}
```
**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c3JfOWIxYThkNDJlNmYxIiwiZXhwIjoxNzkxNTU4MDAwfQ.XYZ123...",
  "token_type": "bearer",
  "user": {
    "id": "usr_9b1a8d42e6f1",
    "email": "lead.analyst@example.com",
    "full_name": "Lead Analyst"
  }
}
```

---

### Step 2: Upload Raw Dataset
#### `POST /api/v1/upload`
**Request:**
```http
POST /api/v1/upload HTTP/1.1
Authorization: Bearer <TOKEN>
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW

------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="file"; filename="retail_sales_messy.csv"
Content-Type: text/csv

<raw CSV bytes>
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```
**Response (201 Created):**
```json
{
  "dataset_id": "ds_89f0a2cb11",
  "filename": "retail_sales_messy.csv",
  "row_count": 120,
  "column_count": 9,
  "file_size_bytes": 10452,
  "columns": [
    "Transaction_ID", "Date", "Customer_ID", "Product",
    "Category", "Region", "Quantity", "Unit_Price", "Payment_Method"
  ]
}
```

---

### Step 3: Clean Dataset (Deterministic Normalization & Sanitization)
#### `POST /api/v1/datasets/{dataset_id}/clean`
**Request:**
```http
POST /api/v1/datasets/ds_89f0a2cb11/clean HTTP/1.1
Authorization: Bearer <TOKEN>
```
**Response (200 OK):**
```json
{
  "dataset_id": "ds_89f0a2cb11",
  "initial_row_count": 120,
  "cleaned_row_count": 98,
  "duplicates_removed": 2,
  "sentinels_detected": [
    {"column": "Quantity", "sentinel_value": 999, "count": 3}
  ],
  "suspected_returns": [
    {"column": "Quantity", "negative_value": -5, "count": 2}
  ],
  "imputed_columns": {
    "Payment_Method": {"missing_count": 20, "strategy": "mode", "fill_value": "Credit Card"}
  },
  "is_sampled": false,
  "sampling_rate": 1.0,
  "sampling_disclosure": null
}
```

---

### Step 4: Profile Dataset (Statistical Baseline & Data Quality)
#### `POST /api/v1/datasets/{dataset_id}/profile` (or `GET /api/v1/datasets/{dataset_id}/profile`)
**Request:**
```http
POST /api/v1/datasets/ds_89f0a2cb11/profile HTTP/1.1
Authorization: Bearer <TOKEN>
```
**Response (200 OK):**
```json
{
  "dataset_id": "ds_89f0a2cb11",
  "quality_score": 78.5,
  "row_count": 98,
  "column_count": 9,
  "columns": {
    "Quantity": {
      "inferred_type": "numeric",
      "missing_count": 0,
      "unique_count": 12,
      "mean": 3.82,
      "std": 2.14,
      "min": 1.0,
      "max": 10.0
    },
    "Payment_Method": {
      "inferred_type": "categorical",
      "missing_count": 0,
      "unique_count": 3,
      "top_categories": {"Credit Card": 48, "PayPal": 32, "Cash": 18}
    }
  },
  "quality_summary": {
    "missing_cells_percent": 0.0,
    "quality_tier": "B"
  }
}
```

---

### Step 5: Launch Autonomous Analysis Job
#### `POST /api/v1/jobs`
**Request:**
```http
POST /api/v1/jobs HTTP/1.1
Authorization: Bearer <TOKEN>
Content-Type: application/json

{
  "dataset_id": "ds_89f0a2cb11",
  "goal": "Identify key revenue drivers, regional variations, and anomalies in sales data.",
  "max_steps": 4,
  "token_budget": 15000
}
```
**Response (202 Accepted):**
```json
{
  "job_id": "job_e71b30fa12",
  "dataset_id": "ds_89f0a2cb11",
  "status": "pending",
  "message": "Analysis job queued successfully."
}
```

---

### Step 6: Poll Job Status Fields
#### `GET /api/v1/jobs/{job_id}`
Frontend polls this endpoint at 1-second intervals until `status` enters a terminal state: `"completed"`, `"budget_tripped"`, or `"failed"`.

**Response (200 OK - Processing):**
```json
{
  "job_id": "job_e71b30fa12",
  "status": "processing",
  "phase": "executing",
  "current_step": 2,
  "current_step_name": "Running segment comparison on Region vs Unit_Price",
  "total_steps": 4,
  "progress_percent": 50,
  "tokens_used": 4210,
  "budget_tripped": false,
  "error": null
}
```

**Response (200 OK - Completed):**
```json
{
  "job_id": "job_e71b30fa12",
  "status": "completed",
  "phase": "synthesis",
  "current_step": 4,
  "current_step_name": "Synthesis and citation verification complete",
  "total_steps": 4,
  "progress_percent": 100,
  "tokens_used": 8450,
  "budget_tripped": false,
  "error": null
}
```

---

### Step 7: Retrieve Ranked Insights & Execution Logs
#### `GET /api/v1/jobs/{job_id}/insights`
**Request:**
```http
GET /api/v1/jobs/job_e71b30fa12/insights HTTP/1.1
Authorization: Bearer <TOKEN>
```
**Response (200 OK):**
```json
{
  "job_id": "job_e71b30fa12",
  "insights": [
    {
      "id": "ins_c81f01",
      "type": "segment_difference",
      "title": "East Region Unit Price Outperforms West Region",
      "description": "Mean unit price in East is 142.50 compared to 98.20 in West (difference of 44.30, p=0.0042).",
      "confidence": "high",
      "p_value": 0.0042,
      "effect_size": 0.78,
      "caveats": ["Sample evaluated on observed records (n=98)."],
      "citations": [
        {"metric_key": "East_mean", "value": 142.50, "source": "segment_compare"}
      ]
    }
  ]
}
```

#### `GET /api/v1/jobs/{job_id}/logs`
**Response (200 OK):**
```json
{
  "job_id": "job_e71b30fa12",
  "run_log": [
    {
      "round": 1,
      "step": 1,
      "tool": "segment_compare",
      "tool_args": {"segment_column": "Region", "metric_column": "Unit_Price"},
      "status": "success",
      "duration_ms": 34.2
    }
  ]
}
```

---

### Step 8: Human-in-the-Loop Feedback (Plan §8.6)
#### `POST /api/v1/jobs/{job_id}/insights/{insight_id}/feedback`
Allows analysts to rate findings as "helpful" or "not_relevant" with optional commentary.

**Request:**
```http
POST /api/v1/jobs/job_e71b30fa12/insights/ins_c81f01/feedback HTTP/1.1
Authorization: Bearer <TOKEN>
Content-Type: application/json

{
  "rating": "helpful",
  "comment": "Confirmed by regional operations team. Will factor into Q4 supply plan."
}
```
**Response (201 Created):**
```json
{
  "insight_id": "ins_c81f01",
  "rating": "helpful",
  "comment": "Confirmed by regional operations team. Will factor into Q4 supply plan.",
  "recorded_at": "2026-10-09T08:45:00Z"
}
```

---

### Step 9: Conversational Follow-Up Q&A (Chat)
#### `POST /api/v1/chat`
Answers questions grounded strictly in computed facts. Suppresses nonexistent columns/entities without hallucinating formulas.

**Request:**
```http
POST /api/v1/chat HTTP/1.1
Authorization: Bearer <TOKEN>
Content-Type: application/json

{
  "job_id": "job_e71b30fa12",
  "dataset_id": "ds_89f0a2cb11",
  "question": "What is the share of Credit Card payments among non-missing payment method rows?"
}
```
**Response (200 OK):**
```json
{
  "answer": "Based on data_observed (n=1): Credit Card share was 0.49.",
  "status": "success",
  "provider": "gemini",
  "model": "gemini-3.1-flash-lite",
  "fallback_to_heuristic": false,
  "tool_called": "query_sql",
  "verification": {
    "is_valid": true,
    "total_claims_checked": 1,
    "verified_claims_count": 1,
    "unverified_claims": []
  }
}
```

---

### Step 10: Generate and Download Business Reports
#### `POST /api/v1/jobs/{job_id}/report?format=pdf`
**Request:**
```http
POST /api/v1/jobs/job_e71b30fa12/report?format=pdf HTTP/1.1
Authorization: Bearer <TOKEN>
```
**Response (200 OK):**
```json
{
  "report_id": "rep_94a7e2b10",
  "job_id": "job_e71b30fa12",
  "format": "pdf",
  "filename": "retail_sales_messy_report.pdf",
  "download_url": "/api/v1/reports/rep_94a7e2b10/download"
}
```

#### `GET /api/v1/reports/{report_id}/download`
**Request:**
```http
GET /api/v1/reports/rep_94a7e2b10/download HTTP/1.1
Authorization: Bearer <TOKEN>
```
**Response (200 OK):**
Binary file stream (`Content-Type: application/pdf`, `Content-Disposition: attachment; filename="retail_sales_messy_report.pdf"`).

---

## 4. Environment Variables Reference

Create a `.env` file in the repository root (do **not** commit it):

```env
# Core API Settings
PROJECT_NAME="Autonomous AI Data Analyst Agent"
API_V1_STR="/api/v1"
SECRET_KEY="replace-with-a-random-32-byte-hex-string"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ALLOW_ANONYMOUS=False

# Database & Celery Broker
DATABASE_URL="sqlite:///./data/app.db"
REDIS_URL="redis://localhost:6379/0"
CELERY_TASK_ALWAYS_EAGER=True

# LLM Providers & Keys
LLM_PROVIDER="gemini"
GEMINI_API_KEY="your-gemini-api-key"
ANTHROPIC_API_KEY=""

# Guardrails & Budgets
MAX_ROW_COUNT_LIMIT=100000
SAMPLE_THRESHOLD_ROWS=25000
SAMPLE_TARGET_ROWS=10000
DEFAULT_TOKEN_BUDGET=15000
DEFAULT_MAX_STEPS=5
```

---

## 5. Startup Commands for Windows

Open separate PowerShell terminals within the repository root:

### Terminal 1: Backend API (FastAPI)
```powershell
# Activate virtual environment
& 'C:\Users\Shaik Rafi\.venvs\autonomous-ai-data-analyst\Scripts\Activate.ps1'

# Run FastAPI with live reload
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be accessible at: `http://localhost:8000/docs`

### Terminal 2: Celery Worker (Optional for local development)
If running asynchronous workers instead of `CELERY_TASK_ALWAYS_EAGER=True`:
```powershell
& 'C:\Users\Shaik Rafi\.venvs\autonomous-ai-data-analyst\Scripts\Activate.ps1'
celery -A backend.app.core.celery_app worker --loglevel=info --pool=solo
```
*(Note: `--pool=solo` is mandatory on Windows for Celery).*

### Terminal 3: Reflex Frontend
```powershell
& 'C:\Users\Shaik Rafi\.venvs\autonomous-ai-data-analyst\Scripts\Activate.ps1'
cd frontend
reflex run
```
Reflex UI will be accessible at: `http://localhost:3000`

---

## 6. Known Limitations & Operational Boundaries

1. **Large Scale Sampling Policy**:
   - Datasets up to 25,000 rows are analyzed in full.
   - Datasets exceeding 25,000 rows (up to 100,000 rows) are deterministically sampled down to 10,000 rows (seed=42) during cleaning. All narratives, insights, chat answers, and PDF reports explicitly disclose the sample basis and original row count.
2. **Missing Entity & Column Safeguards**:
   - The chat system strictly forbids generating SQL or hallucinating surrogate formulas for entities not present in the dataset (e.g. asking for "customer lifetime value" on a marketing campaign without customer retention history returns an explicit refusal listing available columns).
3. **Data Quality Suppression**:
   - Statistical correlations and trends are suppressed when the exclusion/missingness rate exceeds 50% (`exclusion_rate > 0.5`). The chat and reports explicitly report what was evaluated and why it was suppressed.
4. **Token Budget Enforcement**:
   - Both reactive tracking and proactive estimation (`est_plan_tokens = 1200`, `est_synth_tokens = 1800`) are enforced. If a run projects exceeding the budget, the orchestrator trips the budget and switches to deterministic heuristic synthesis to guarantee safe termination without unbudgeted API billing.
