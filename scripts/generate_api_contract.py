"""Generate docs/openapi.json and comprehensive frontend docs/API.md."""
import json
from pathlib import Path
from backend.app.main import app

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
OPENAPI_PATH = DOCS_DIR / "openapi.json"
API_MD_PATH = DOCS_DIR / "API.md"

def generate_openapi_json() -> dict:
    """Extract and save live OpenAPI JSON schema."""
    schema = app.openapi()
    with open(OPENAPI_PATH, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, sort_keys=True)
    print(f"Generated {OPENAPI_PATH}")
    return schema

def generate_api_markdown(schema: dict) -> None:
    """Generate comprehensive documentation for frontend developers."""
    lines = []
    lines.append("# Backend API Contract & Specification\n")
    lines.append("This document is the definitive API contract for frontend integration with the Autonomous AI Data Analyst Agent backend.\n")
    
    # 1. Base URL & Authentication
    lines.append("## 1. Authentication & Security\n")
    lines.append("- **Base URL**: `/api/v1`")
    lines.append("- **Authentication Scheme**: HTTP Bearer Token (`Authorization: Bearer <JWT_TOKEN>`)")
    lines.append("- **Token Acquisition**: Via `POST /api/v1/auth/login` or `POST /api/v1/auth/register`")
    lines.append("- **Multi-Tenant Isolation**: Enforced across all endpoints. Users can only inspect, run jobs on, chat with, and download reports for their own datasets and jobs.")
    lines.append("- **Anonymous Access**: Disabled by default (`ALLOW_ANONYMOUS=false`). Requests without a valid Bearer token return `401 Unauthorized`.\n")

    # 2. Consistent Error Response Schema
    lines.append("## 2. Standard Error Response Schema\n")
    lines.append("All error responses (4xx and 5xx) strictly adhere to the uniform JSON error schema:\n")
    lines.append("```json")
    lines.append(json.dumps({
        "error": "HTTP_404_NOT_FOUND",
        "message": "Dataset 'ds-12345' not found.",
        "details": "Dataset 'ds-12345' not found.",
        "request_id": "c1f7a02c-5678-4321-9876-0123456789ab"
    }, indent=2))
    lines.append("```\n")
    lines.append("| Error Code | Status | Meaning |")
    lines.append("|---|:---:|---|")
    lines.append("| `HTTP_400_BAD_REQUEST` | 400 | Malformed parameters, password < 8 chars, or unsupported file format |")
    lines.append("| `HTTP_401_UNAUTHORIZED` | 401 | Missing, expired, or invalid authentication credentials |")
    lines.append("| `HTTP_403_FORBIDDEN` | 403 | Attempting to access another user's dataset, job, schedule, or report |")
    lines.append("| `HTTP_404_NOT_FOUND` | 404 | Target resource does not exist |")
    lines.append("| `HTTP_413_REQUEST_ENTITY_TOO_LARGE` | 413 | Uploaded file exceeds 50 MB |")
    lines.append("| `HTTP_422_UNPROCESSABLE_ENTITY` | 422 | Pydantic request body schema validation failed |")
    lines.append("| `HTTP_429_TOO_MANY_REQUESTS` | 429 | Rate limit exceeded (e.g. >10 rapid login attempts) |")
    lines.append("| `HTTP_500_INTERNAL_SERVER_ERROR` | 500 | Unhandled server exception with redacted internal details |\n")

    # 3. Job Lifecycle Fields
    lines.append("## 3. Job Lifecycle Fields & State Machine\n")
    lines.append("When monitoring analysis execution via `GET /api/v1/jobs/{job_id}`, the response provides complete explainability fields:\n")
    lines.append("| Field | Type | Description | Values / Examples |")
    lines.append("|---|---|---|---|")
    lines.append("| `status` | `string` | High-level status | `running`, `completed`, `failed` |")
    lines.append("| `phase` | `string` | Execution phase | `queued`, `planning`, `execution`, `reflection`, `synthesis` |")
    lines.append("| `current_step` | `integer` | 0-indexed step count | `0, 1, 2, ...` |")
    lines.append("| `current_step_name`| `string` | Human-readable current action | `planning_initial_strategy`, `running_sql_profiling`, `synthesizing_report` |")
    lines.append("| `total_steps` | `integer` | Cumulative steps completed | `3` |")
    lines.append("| `step_limit` | `integer` | Configured step budget | `5` (default) |")
    lines.append("| `tokens_used` | `integer` | Cumulative LLM tokens consumed | `12450` |")
    lines.append("| `token_budget` | `integer` | Configured token limit | `15000` (default) |")
    lines.append("| `execution_time_seconds`| `float` | Elapsed execution time | `14.28` |")
    lines.append("| `results` | `object` | Final analysis payload (when completed/failed) | Detailed insights, charts, and summary |")
    lines.append("| `verification`| `object` | Citation and verification metrics | `claim_count`, `verified_count`, `number_verification_rate`, `claim_presence_rate` |\n")

    # 4. Insights Payload Specification
    lines.append("## 4. Insights Payload Specification\n")
    lines.append("The `results` payload contains partitioned insight categories:\n")
    lines.append("1. **Analytical Insights (`analytical_insights`)**: Statistically validated domain findings (correlations, segments, regressions).")
    lines.append("2. **Data Quality Insights (`data_quality_insights`)**: Data hygiene findings (raw score vs cleaned score, imputation shares, sentinel rates, missing values).")
    lines.append("3. **Suppressed Insights (`suppressed_insights`)**: Findings evaluated by statistical guardrails but pruned due to small sample size ($n < 20$) or high exclusion ($> 50\%$).\n")
    lines.append("```json")
    lines.append(json.dumps({
        "analytical_insights": [
            {
                "id": "insight_salary_dept",
                "type": "segment_difference",
                "finding": "Engineering annual salaries average $95,000 compared to Sales at $55,000 (p < 0.001).",
                "basis": "data_clean",
                "sample_size": 250,
                "confidence_interval": [91200.0, 98800.0]
            }
        ],
        "data_quality_insights": [
            {
                "id": "insight_dq_raw",
                "type": "data_quality",
                "raw_quality_score": 46.0,
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
    }, indent=2))
    lines.append("```\n")

    # 5. Interactive Chat & Report Flows
    lines.append("## 5. Chat & Report Workflows\n")
    lines.append("### Interactive Chat Query (`POST /api/v1/chat`)")
    lines.append("- **Request Payload**:")
    lines.append("```json")
    lines.append(json.dumps({
        "job_id": "018f67ab-1234-7890-abcd-ef0123456789",
        "question": "What is the average salary by department among observed records?",
        "history": []
    }, indent=2))
    lines.append("```")
    lines.append("- **Response Payload**:")
    lines.append("```json")
    lines.append(json.dumps({
        "answer": "Based on observed records (data_observed, n=248), Engineering averages $94,820, Marketing averages $72,400, and Sales averages $56,100.",
        "evidence": [
            {
                "table": "data_observed",
                "columns": ["department", "salary"],
                "row_count": 248
            }
        ],
        "verification": {
            "verified": True,
            "claim_count": 3,
            "verified_count": 3,
            "pre_strip_rate": 100.0,
            "post_strip_rate": 100.0
        }
    }, indent=2))
    lines.append("```\n")

    lines.append("### Report Generation & Download Flow")
    lines.append("1. **Generate**: `POST /api/v1/jobs/{job_id}/report?format=pdf` (or `docx`)")
    lines.append("   - Response: `{\"report_id\": \"98a1b2c3\", \"download_url\": \"/api/v1/reports/98a1b2c3/download\"}`")
    lines.append("2. **Download**: `GET /api/v1/reports/{report_id}/download`")
    lines.append("   - Returns streaming `application/pdf` or `application/vnd.openxmlformats-officedocument.wordprocessingml.document`.\n")

    # 6. Complete Endpoint Directory
    lines.append("## 6. Complete API Route Directory\n")
    lines.append("| HTTP Method | Endpoint Path | Auth Required | Description |")
    lines.append("|---|---|:---:|---|")
    
    paths_dict = schema.get("paths", {})
    for path, methods in sorted(paths_dict.items()):
        for method, op in sorted(methods.items()):
            if method.lower() in ("head", "options"):
                continue
            summary = op.get("summary") or op.get("description") or "API endpoint"
            summary_clean = summary.split("\n")[0].replace("|", "\\|")
            
            # Auth check
            is_public = path in ("/health", "/", "/api/v1/health") or "auth" in path or "upload" in path and False
            if "/auth/register" in path or "/auth/login" in path or path in ("/health", "/", "/api/v1/health"):
                auth_req = "No (Public)"
            else:
                auth_req = "Yes (Bearer Token)"
            
            lines.append(f"| `{method.upper()}` | `{path}` | {auth_req} | {summary_clean} |")

    lines.append("\n---\n*Auto-generated from live FastAPI OpenAPI contract.*\n")

    with open(API_MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Generated {API_MD_PATH}")

if __name__ == "__main__":
    schema = generate_openapi_json()
    generate_api_markdown(schema)
