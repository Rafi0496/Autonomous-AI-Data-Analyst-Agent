# Autonomous AI Data Analyst Agent — Implementation Plan (Reflex Edition)

## Architecture Overview

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

> **Verification Rule:** Items must be checked off **only once actually verified**, not just scaffolded.

---

## Build Order & Progress Tracker

### Phase 1 — Foundations & Data Pipeline (Weeks 1–4)
- [x] Project structure scaffold (`backend/`, `frontend/` as a Reflex app, `shared/`) — *Verified: Clean directory layout, package initialization, and module imports.*
- [x] Backend: FastAPI skeleton with routes — *Verified: `/api/v1/health`, `/upload`, `/datasets` endpoints running with CORS & DB lifespan.*
- [x] Database models (SQLAlchemy + PostgreSQL) — *Verified: `Dataset` and `User` models with JSON profile persistence and table lifecycle.*
- [x] File upload endpoint (CSV/XLSX/JSON) + validation, clear errors on malformed input — *Verified: Chunked streaming upload, extension & size validation, 400/422 errors on empty/malformed files.*
- [x] Data cleaning pipeline (`clean_data()`) — *Verified: Deduplication, currency/date coercion, and auto-imputation validated on real messy datasets.*
- [x] Data profiling pipeline (`profile_dataset()`) — *Verified: Inferred types, statistical metrics (mean, std, IQR outliers), quality score, and warnings.*
- [x] Reflex app scaffold: `rx.App`, page routing (`/upload`, `/dashboard`, `/chat`, `/reports`, `/settings`) — *Verified: Route registration and app initialization checked via automated test.*
- [x] Upload page (`rx.upload` component) wired to backend — *Verified: Drag-and-drop file ingestion, quick-load benchmark triggers, and action buttons.*
- [x] Data profile results view, driven by `rx.State` — *Verified: Reactive state management, KPI stat cards, quality alerts, and column profile table.*
- [x] Docker Compose setup (Postgres + Redis + FastAPI + Reflex) — *Verified: `docker-compose.yml`, `backend/Dockerfile`, and `frontend/Dockerfile` configured.*
- [x] Unit tests for cleaning/profiling run against 3 real messy datasets (retail, HR, marketing — see Plan §8.1) — *Verified: 15/15 tests passing in pytest and end-to-end validation script.*

### Phase 2 — Autonomous Agent Core (Weeks 5–8)
- [ ] Tool catalogue as typed Python functions (`run_correlation()`, `detect_outliers()`, `segment_compare()`, `trend_analysis()`, `query_sql()`)
- [ ] Claude API integration with function calling
- [ ] Plan-Act-Reflect orchestration loop
- [ ] Sandbox execution environment — start with restricted-subprocess; **verify with an adversarial test** (agent-generated code that tries file/network access)
- [ ] Step/token budget guardrails — **verify with a test that deliberately trips the budget**
- [ ] Run log / explainability layer (per-step trace, visible not just internal)
- [ ] Celery task wiring: each analysis job runs async, status streamed to Reflex state via polling or WebSocket push
- [ ] Integration test: full agent loop run unattended, end-to-end, on a real messy dataset — manually verify every claim traces to a computed result

### Phase 3 — Insight, Visualization & Reporting (Weeks 9–12)
- [ ] Chart generation tool (`generate_chart()`) → Plotly figures via `rx.plotly`
- [ ] Dashboard page: ranked insight cards + embedded charts + narrative per finding
- [ ] Conversational Q&A chat page, re-invoking tools only when new computation is needed
- [ ] Report export: **both PDF and Word** (PRD FR-17 requires both, not just PDF)
- [ ] Insight ranking/significance scoring
- [ ] Visible token/cost tracker on the dashboard (Plan §8.5 — user-facing, not just an internal budget)
- [ ] Usability test with 3–5 outside users on real datasets; log friction points against the 3-click first-insight goal

### Phase 4 — Real-World Readiness (Weeks 13–16)
- [ ] JWT authentication wired between Reflex sessions and FastAPI
- [ ] Multi-user data isolation
- [ ] Scheduled/recurring analysis (Celery beat)
- [ ] Feedback loop: mark an insight "helpful" / "not relevant" (Plan §8.6)
- [ ] Scale handling: max file size/row count + sampling strategy for large files (Plan §8.7)
- [ ] Full test pass: Pytest (backend/tools/agent), Reflex component tests, integration tests
- [ ] CI/CD (GitHub Actions) running the full suite on every push
- [ ] Docker deployment to target VM / Render / Railway
- [ ] README + architecture docs updated to reflect Reflex (not React)
- [ ] Rehearsed live demo script using at least 2 real messy datasets
