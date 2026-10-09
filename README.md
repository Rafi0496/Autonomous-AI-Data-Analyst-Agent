# Autonomous AI Data Analyst Agent

![CI](https://github.com/Rafi0496/Autonomous-AI-Data-Analyst-Agent/actions/workflows/ci.yml/badge.svg?branch=master)

An LLM-driven agent that turns raw, messy tabular data into verified insights.
It cleans the data, plans and runs statistical analyses in a sandboxed tool
catalogue, reflects on the results, and explains its findings in plain language.
Every numeric claim in the summary is bound to a computed result and checked
before it is shown.

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────┐
│              Reflex Frontend (Pure Python)            │
│  Upload │ Dashboard │ Chat │ Reports │ Settings       │
├─────────────────────────────────────────────────────┤
│      Reflex's native WebSocket state sync + REST      │
├─────────────────────────────────────────────────────┤
│               FastAPI Backend (Python)                │
│  Auth │ Upload │ Analysis Jobs │ Chat │ Reports       │
├─────────────────────────────────────────────────────┤
│              Celery + Redis (async job queue)         │
├─────────────────────────────────────────────────────┤
│              Agent Engine (Plan-Act-Reflect)          │
│  Configurable LLM (Gemini evaluated default, Claude supported) │ Tool Catalogue │ Sandbox │ Memory  │
├─────────────────────────────────────────────────────┤
│              Data Layer                               │
│  PostgreSQL │ Redis │ DuckDB │ File Storage           │
└─────────────────────────────────────────────────────┘
```

---

## 2. Technology Stack

- **Frontend**: [Reflex](https://reflex.dev) (Pure Python UI framework with built-in WebSocket state sync and Tailwind styling)
- **Backend API**: FastAPI, Pydantic v2, Uvicorn
- **Data Layer**: SQLAlchemy 2.0, PostgreSQL (production) / SQLite fallback (local dev)
- **Data Engineering & Stats**: pandas, NumPy, openpyxl, DuckDB, SciPy, scikit-learn, statsmodels
- **Visualizations**: Plotly (`rx.plotly` in Reflex)
- **Reporting**: ReportLab / WeasyPrint (PDF) & `python-docx` (Word)
- **Testing**: Pytest, TestClient, Pytest-Asyncio
- **Orchestration / Containers**: Docker & Docker Compose

---

## 3. Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   ├── health.py
│   │   │       │   ├── upload.py
│   │   │       │   └── datasets.py
│   │   │       └── api.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── database.py
│   │   ├── models/
│   │   │   ├── dataset.py
│   │   │   └── user.py
│   │   ├── services/
│   │   │   ├── cleaning.py      # clean_data() standalone pipeline
│   │   │   ├── profiling.py     # profile_dataset() standalone pipeline
│   │   │   └── storage.py       # chunked streaming, file validation
│   │   └── main.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_cleaning.py
│   │   ├── test_profiling.py
│   │   ├── test_upload_api.py
│   │   ├── test_reflex_integration.py
│   │   └── test_datasets/       # retail, HR, marketing messy datasets
│   └── Dockerfile
├── frontend/                    # Reflex application
│   ├── rxconfig.py
│   ├── frontend/
│   │   ├── components/
│   │   │   ├── layout.py        # Dark-mode sidebar & header
│   │   │   └── stats_card.py    # Metric stat cards
│   │   ├── pages/
│   │   │   ├── upload.py        # rx.upload + benchmark loaders + profile view
│   │   │   ├── dashboard.py     # Executive analytics dashboard
│   │   │   ├── chat.py          # Conversational Q&A chat
│   │   │   ├── reports.py       # PDF & Word export center
│   │   │   └── settings.py      # Token budgets & LLM keys
│   │   ├── state.py             # Global AppState (reactive)
│   │   └── frontend.py          # App initialization & route registry
│   └── Dockerfile
├── shared/
│   ├── constants.py
│   └── schemas/
│       ├── dataset.py
│       └── profile.py
├── data/
│   ├── samples/                 # Retail, HR, Marketing benchmark CSVs
│   ├── uploads/
│   └── processed/
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── IMPLEMENTATION_PLAN.md       # Build order & verification tracker
├── PROJECT_PLAN.md              # 16-Week Project Plan & Architecture Guide
└── scripts/
    └── verify_phase1.py         # End-to-end Phase 1 validation script
```

---

## 4. Getting Started

### Prerequisites
- Python 3.11+
- Git
- `uv` (recommended) or standard `pip`
- Node.js 18+ (for Reflex web compiler)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd "Autonomous AI Data Analyst Agent"
   ```

2. **Set up virtual environment (Windows):**
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Create a `.env` file in the project root:
   ```env
   LLM_PROVIDER=gemini       # Options: gemini, claude, or heuristic (offline mode)
   GEMINI_API_KEY=your_key_here
   # ANTHROPIC_API_KEY=your_key_here
   ```

4. **Run Backend API (Windows):**
   ```powershell
   .venv\Scripts\uvicorn backend.app.main:app --reload --port 8000
   ```
   Interactive API documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

5. **Run Celery Worker (Windows - Optional for async job queues):**
   ```powershell
   .venv\Scripts\celery -A backend.app.core.celery_app worker --loglevel=info -P solo
   ```
   *Note: If Celery or Redis is not running, the backend automatically executes analysis jobs via FastAPI BackgroundTasks.*

6. **Run Reflex Frontend (Windows):**
   ```powershell
   cd frontend
   ..\.venv\Scripts\reflex run
   ```
   The interactive UI will be available at [http://localhost:3000](http://localhost:3000).

---

## 5. Automated Verification & Testing

Run the full pytest suite (offline + live):
```powershell
.venv\Scripts\python -m pytest -m "not live"
```

Run Phase 4 Live Demo Walkthrough (Retail & HR scenarios end-to-end with Auth, Cleaning, Plan-Act-Reflect, Insights, Feedback, Q&A, and PDF/Word exports):
```powershell
.venv\Scripts\python scripts/demo_scenario_walkthrough.py
```

Run the Phase 3 End-to-End Pipeline Verification script:
```powershell
.venv\Scripts\python scripts/verify_phase3.py
```

---

## 6. Phase 4 Enterprise Features

- **JWT Authentication & Multi-User Isolation**: User registration, login, and token issuance (`POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`). Strict data isolation between tenant accounts for uploaded datasets, generated reports, and analysis jobs.
- **Scheduled & Recurring Analysis**: Automation via Celery beat and REST endpoints (`POST /api/v1/schedules`, `GET /api/v1/schedules`, `POST /api/v1/schedules/{id}/trigger`) allowing scheduled weekly or daily dataset monitoring.
- **Human-in-the-Loop Feedback (Plan §8.6)**: Interactive feedback loop enabling analysts to mark insights as "Helpful" or "Not Relevant" with comments (`POST /api/v1/jobs/{job_id}/insights/{insight_id}/feedback`).
- **Scale Handling & Sampling Strategy (Plan §8.7)**: Configurable scale limits (`MAX_ROW_COUNT_LIMIT = 100,000`, `SAMPLE_THRESHOLD_ROWS = 25,000`). Large datasets are automatically sampled for fast exploratory analysis with population metrics preserved in data quality reporting.

---

## 7. Docker Deployment

Launch all services (PostgreSQL + Redis + FastAPI + Reflex):
```bash
docker-compose up --build
```
- Frontend UI: [http://localhost:3000](http://localhost:3000)
- Backend API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 8. Reproduce the Evaluation

To reproduce the full benchmark evaluation, metrics, and visual figures:

```bash
# 1. Generate synthetic benchmark datasets (10 planted + 10 null seeds, ~2,000 rows each)
python evaluation/generate.py --planted-seeds 10 --null-seeds 10 --rows 2000

# 2. Run benchmark evaluation across systems (A: heuristic, B: gemini live, C: citation ablation, D: claude)
python evaluation/run.py --systems A,B,C,D

# 3. Run scale benchmark (1k, 10k, 25k, 100k rows)
python evaluation/scale_test.py --sizes 1000,10000,25000,100000

# 4. Generate evaluation report and charts
python evaluation/report.py
```

Results, audit tables, and publication-ready charts will be generated in:
- Markdown report: `docs/EVAL_RESULTS.md`
- Visual figures: `docs/figures/recall_by_system.png`, `docs/figures/false_positives_by_system.png`, `docs/figures/runtime_vs_rows.png`
- Blind manual review sample: `docs/eval_manual_review.csv`
*(Note: Live LLM runs are excluded from CI to prevent API token consumption; offline unit tests run automatically in CI).*

