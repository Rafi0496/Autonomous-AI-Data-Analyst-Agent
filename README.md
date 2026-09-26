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

2. **Create virtual environment and install dependencies:**
   ```bash
   uv venv --python 3.11
   .venv\Scripts\activate
   uv pip install -r requirements.txt
   ```

3. **Generate benchmark sample datasets:**
   ```bash
   python data/generate_samples.py
   ```

4. **Run backend API:**
   ```bash
   uvicorn backend.app.main:app --reload --port 8000
   ```
   Interactive API docs are available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

5. **Run Reflex Frontend:**
   ```bash
   cd frontend
   reflex run
   ```
   The UI will open at [http://localhost:3000](http://localhost:3000).

---

## 5. Automated Verification & Testing

Run the full pytest suite (15 unit and integration tests):
```bash
pytest -v
```

Run the live Phase 1 verification script:
```bash
python scripts/verify_phase1.py
```

---

## 6. Docker Deployment

Launch all services (PostgreSQL + Redis + FastAPI + Reflex):
```bash
docker-compose up --build
```
- Frontend UI: [http://localhost:3000](http://localhost:3000)
- Backend API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
