# Autonomous AI Data Analyst Agent

> **An autonomous, agentic system that ingests raw, messy business data, plans and executes statistical workflows, detects anomalies, generates visualizations, and synthesizes executive-ready business reports without manual step-by-step guidance.**

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
│  Claude API │ Tool Catalogue │ Sandbox │ Memory       │
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

Run the full pytest suite (no tests ignored):
```powershell
.venv\Scripts\python -m pytest
```

Run the Phase 3 End-to-End Pipeline Verification script (runs upload, cleaning, autonomous analysis, insight ranking, chat Q&A, and PDF/Word report exports across all 3 benchmark messy datasets):
```powershell
.venv\Scripts\python scripts/verify_phase3.py
```
Output artifacts are saved to `data/demo_outputs/<dataset_name>/`:
- `insights.json` (ranked insight schemas with impact scores & chart specs)
- `summary.txt` (executive summary & key findings)
- `report.pdf` (ReportLab formatted multi-page PDF report with cover, charts, data quality, & audit trail)
- `report.docx` (python-docx formatted Word report)
- `chart_*.png` (headless Matplotlib Agg rendered visualizations)
- `chat_exchange.json` (conversational Q&A grounded answer, evidence, and citation verification)

---

## 6. Docker Deployment

Launch all services (PostgreSQL + Redis + FastAPI + Reflex):
```bash
docker-compose up --build
```
- Frontend UI: [http://localhost:3000](http://localhost:3000)
- Backend API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
