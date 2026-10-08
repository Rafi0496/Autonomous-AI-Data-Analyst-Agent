# Backend API Contract & Specification

This document is the definitive API contract for frontend integration with the Autonomous AI Data Analyst Agent backend.

## 1. Authentication & Security

- **Base URL**: `/api/v1`
- **Authentication Scheme**: HTTP Bearer Token (`Authorization: Bearer <JWT_TOKEN>`)
- **Token Acquisition**: Via `POST /api/v1/auth/login` or `POST /api/v1/auth/register`
- **Multi-Tenant Isolation**: Enforced across all endpoints. Users can only inspect, run jobs on, chat with, and download reports for their own datasets and jobs.
- **Anonymous Access**: Disabled by default (`ALLOW_ANONYMOUS=false`). Requests without a valid Bearer token return `401 Unauthorized`.

## 2. Standard Error Response Schema

All error responses (4xx and 5xx) strictly adhere to the uniform JSON error schema:

```json
{
  "error": "HTTP_404_NOT_FOUND",
  "message": "Dataset 'ds-12345' not found.",
  "details": "Dataset 'ds-12345' not found.",
  "request_id": "c1f7a02c-5678-4321-9876-0123456789ab"
}
```

| Error Code | Status | Meaning |
|---|:---:|---|
| `HTTP_400_BAD_REQUEST` | 400 | Malformed parameters, password < 8 chars, or unsupported file format |
| `HTTP_401_UNAUTHORIZED` | 401 | Missing, expired, or invalid authentication credentials |
| `HTTP_403_FORBIDDEN` | 403 | Attempting to access another user's dataset, job, schedule, or report |
| `HTTP_404_NOT_FOUND` | 404 | Target resource does not exist |
| `HTTP_413_REQUEST_ENTITY_TOO_LARGE` | 413 | Uploaded file exceeds 50 MB |
| `HTTP_422_UNPROCESSABLE_ENTITY` | 422 | Pydantic request body schema validation failed |
| `HTTP_429_TOO_MANY_REQUESTS` | 429 | Rate limit exceeded (e.g. >10 rapid login attempts) |
| `HTTP_500_INTERNAL_SERVER_ERROR` | 500 | Unhandled server exception with redacted internal details |

## 3. Job Lifecycle Fields & State Machine

When monitoring analysis execution via `GET /api/v1/jobs/{job_id}`, the response provides complete explainability fields:

| Field | Type | Description | Values / Examples |
|---|---|---|---|
| `status` | `string` | High-level status | `running`, `completed`, `failed` |
| `phase` | `string` | Execution phase | `queued`, `planning`, `execution`, `reflection`, `synthesis` |
| `current_step` | `integer` | 0-indexed step count | `0, 1, 2, ...` |
| `current_step_name`| `string` | Human-readable current action | `planning_initial_strategy`, `running_sql_profiling`, `synthesizing_report` |
| `total_steps` | `integer` | Cumulative steps completed | `3` |
| `step_limit` | `integer` | Configured step budget | `5` (default) |
| `tokens_used` | `integer` | Cumulative LLM tokens consumed | `12450` |
| `token_budget` | `integer` | Configured token limit | `15000` (default) |
| `execution_time_seconds`| `float` | Elapsed execution time | `14.28` |
| `results` | `object` | Final analysis payload (when completed/failed) | Detailed insights, charts, and summary |
| `verification`| `object` | Citation and verification metrics | `claim_count`, `verified_count`, `number_verification_rate`, `claim_presence_rate` |

## 4. Insights Payload Specification

The `results` payload contains partitioned insight categories:

1. **Analytical Insights (`analytical_insights`)**: Statistically validated domain findings (correlations, segments, regressions).
2. **Data Quality Insights (`data_quality_insights`)**: Data hygiene findings (raw score vs cleaned score, imputation shares, sentinel rates, missing values).
3. **Suppressed Insights (`suppressed_insights`)**: Findings evaluated by statistical guardrails but pruned due to small sample size ($n < 20$) or high exclusion ($> 50\%$).

```json
{
  "analytical_insights": [
    {
      "id": "insight_salary_dept",
      "type": "segment_difference",
      "finding": "Engineering annual salaries average $95,000 compared to Sales at $55,000 (p < 0.001).",
      "basis": "data_clean",
      "sample_size": 250,
      "confidence_interval": [
        91200.0,
        98800.0
      ]
    }
  ],
  "data_quality_insights": [
    {
      "id": "insight_dq_raw",
      "type": "data_quality",
      "quality_score": 46.0,
      "raw_quality_score": 46.0,
      "post_cleaning_completeness": 92.5,
      "cleaned_quality_score": 92.5,
      "imputation_policy": "Identifiers and segments left missing; numeric mask preserved."
    }
  ],
  "suppressed_insights": [
    {
      "id": "suppressed_1",
      "type": "outlier_rate",
      "reason": "Suppressed due to small sample size: n_used=12 < 20."
    }
  ]
}
```

## 5. Chat & Report Workflows

### Interactive Chat Query (`POST /api/v1/chat`)
- **Request Payload**:
```json
{
  "job_id": "018f67ab-1234-7890-abcd-ef0123456789",
  "question": "What is the average salary by department among observed records?",
  "history": []
}
```
- **Response Payload**:
```json
{
  "answer": "Based on observed records (data_observed, n=248), Engineering averages $94,820, Marketing averages $72,400, and Sales averages $56,100.",
  "evidence": [
    {
      "table": "data_observed",
      "columns": [
        "department",
        "salary"
      ],
      "row_count": 248
    }
  ],
  "verification": {
    "verified": true,
    "claim_count": 3,
    "verified_count": 3,
    "pre_strip_rate": 100.0,
    "post_strip_rate": 100.0
  }
}
```

### Report Generation & Download Flow
1. **Generate**: `POST /api/v1/jobs/{job_id}/report?format=pdf` (or `docx`)
   - Response: `{"report_id": "98a1b2c3", "download_url": "/api/v1/reports/98a1b2c3/download"}`
2. **Download**: `GET /api/v1/reports/{report_id}/download`
   - Returns streaming `application/pdf` or `application/vnd.openxmlformats-officedocument.wordprocessingml.document`.

## 6. Complete API Route Directory

| HTTP Method | Endpoint Path | Auth Required | Description |
|---|---|:---:|---|
| `GET` | `/` | No (Public) | Root |
| `POST` | `/api/v1/auth/login` | No (Public) | Login |
| `GET` | `/api/v1/auth/me` | Yes (Bearer Token) | Get Me |
| `POST` | `/api/v1/auth/register` | No (Public) | Register |
| `POST` | `/api/v1/chat` | Yes (Bearer Token) | Handle Chat Query |
| `POST` | `/api/v1/chat/` | Yes (Bearer Token) | Handle Chat Query |
| `GET` | `/api/v1/datasets` | Yes (Bearer Token) | List Datasets |
| `GET` | `/api/v1/datasets/{dataset_id}` | Yes (Bearer Token) | Get Dataset |
| `POST` | `/api/v1/datasets/{dataset_id}/clean` | Yes (Bearer Token) | Clean Dataset Endpoint |
| `GET` | `/api/v1/datasets/{dataset_id}/cleaning-report` | Yes (Bearer Token) | Get Dataset Cleaning Report Endpoint |
| `GET` | `/api/v1/datasets/{dataset_id}/preview` | Yes (Bearer Token) | Get Dataset Preview |
| `GET` | `/api/v1/datasets/{dataset_id}/profile` | Yes (Bearer Token) | Get Dataset Profile |
| `POST` | `/api/v1/datasets/{dataset_id}/profile` | Yes (Bearer Token) | Profile Dataset Endpoint |
| `GET` | `/api/v1/health` | No (Public) | Health Check |
| `GET` | `/api/v1/jobs` | Yes (Bearer Token) | List Analysis Jobs |
| `POST` | `/api/v1/jobs` | Yes (Bearer Token) | Submit Analysis Job |
| `GET` | `/api/v1/jobs/{job_id}` | Yes (Bearer Token) | Get Job Status |
| `GET` | `/api/v1/jobs/{job_id}/insights` | Yes (Bearer Token) | Get Job Insights |
| `GET` | `/api/v1/jobs/{job_id}/insights/{insight_id}/feedback` | Yes (Bearer Token) | Get Insight Feedback |
| `POST` | `/api/v1/jobs/{job_id}/insights/{insight_id}/feedback` | Yes (Bearer Token) | Submit Insight Feedback |
| `GET` | `/api/v1/jobs/{job_id}/logs` | Yes (Bearer Token) | Get Job Run Log |
| `POST` | `/api/v1/jobs/{job_id}/report` | Yes (Bearer Token) | Create Job Report |
| `GET` | `/api/v1/reports` | Yes (Bearer Token) | List Reports |
| `GET` | `/api/v1/reports/` | Yes (Bearer Token) | List Reports |
| `GET` | `/api/v1/reports/{report_id}/download` | Yes (Bearer Token) | Download Report |
| `GET` | `/api/v1/schedules` | Yes (Bearer Token) | List Schedules |
| `POST` | `/api/v1/schedules` | Yes (Bearer Token) | Create Schedule |
| `DELETE` | `/api/v1/schedules/{schedule_id}` | Yes (Bearer Token) | Delete Schedule |
| `POST` | `/api/v1/schedules/{schedule_id}/trigger` | Yes (Bearer Token) | Trigger Schedule |
| `POST` | `/api/v1/upload` | Yes (Bearer Token) | Upload Dataset File |
| `GET` | `/health` | No (Public) | Health Check |

---
*Auto-generated from live FastAPI OpenAPI contract.*
