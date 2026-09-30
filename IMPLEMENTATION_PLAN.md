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
│  Provider-Agnostic LLM Layer (Claude / Gemini)        │
│  Tool Catalogue │ Sandbox │ Memory                    │
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
- [x] Tool catalogue as typed Python functions (`run_correlation()`, `detect_outliers()`, `segment_compare()`, `trend_analysis()`, `query_sql()`) — *Verified: Standalone typed services returning structured data; 17 unit tests passing across all 3 benchmark messy datasets.*
- [x] Claude API integration with function calling — *Verified: Prototype script `scripts/prototype_tool_call.py` validates Anthropic API schema, tool selection, argument extraction, and execution.*
- [x] Plan-Act-Reflect orchestration loop — *Verified: `PlanActReflectOrchestrator` implements autonomous planning from data profile, real step execution, iterative reflection, and `write_summary()` synthesis.*
- [x] Sandbox execution environment — start with restricted-subprocess; **verify with an adversarial test** (agent-generated code that tries file/network access) — *Verified: Closed-catalogue architecture + DuckDB in-memory isolation rejecting SQL writes (`DROP`, `INSERT`, `UPDATE`), semicolon injection, and path traversals (`/etc/passwd`, `C:\`, network URLs).*
- [x] Step/token budget guardrails — **verify with a test that deliberately trips the budget** — *Verified: Automated tests `test_step_budget_tripping_graceful_partial_fallback` and `test_token_budget_tripping_graceful_partial_fallback` assert graceful loop termination and partial-result synthesis.*
- [x] Run log / explainability layer (per-step trace, visible not just internal) — *Verified: Step-by-step trace capturing step number, timestamp, tool name, duration in ms, status, arguments, and rationale; exposed via `/api/v1/jobs/{job_id}/logs`.*
- [x] Celery task wiring: each analysis job runs async, status streamed to Reflex state via polling or WebSocket push — *Verified: Celery worker task `run_analysis_task` + fallback background task execution with live step progress updates via `/api/v1/jobs/{job_id}`.*
- [x] Integration test: full agent loop run unattended, end-to-end, on a real messy dataset — manually verify every claim traces to a computed result — *Verified: `test_full_agent_loop_unattended` and `scripts/verify_phase2.py` run unattended on messy retail data; `citation_checker.py` confirms 100.0% of numeric claims trace to computed tool results.*
- [x] Provider-agnostic LLM layer (`llm_client.py`) — *Verified: `LLMClient` interface with `ClaudeClient`, `GeminiClient`, and `HeuristicClient` implementations. Provider selected via `LLM_PROVIDER` env var. Tool catalogue converted per-provider in one place (`get_tools_for_claude()`, `get_tools_for_gemini()`). Marked live tests with `@pytest.mark.live`.*
- [x] Real token accounting from provider usage metadata — *Verified: Removed hardcoded `+= 350` per step. Token counts sourced from `response.usage` (Claude) and `response.usage_metadata` (Gemini). Marked "unknown" when unavailable (heuristic mode).*
- [x] Data cleaning casing & domain validity rules — *Verified: Frequency-based canonical casing preserves Title Case over lowercase and short acronyms (Engineering, HR, Marketing, Sales, Accessories, Electronics, LinkedIn, Google Ads). Domain validity sanitizes negative business metrics and invalid ages (<0, >100) before imputation.*
- [x] Sentinel detection & data-quality findings surfacing — *Verified: Sentinels (e.g. Quantity=999) detected and converted to NaN prior to imputation. Data quality findings (sentinels, invalid values, imputation rates) surfaced to LLM synthesis and citation fact pool.*
- [x] Statistical rigor & Z-score restoration — *Verified: Z-score threshold restored to standard 3.0. Imputation companion mask tracked on disk; statistical tools exclude imputed rows reporting n_used and unflattened segment medians.*
- [x] Model name logged in run_log — *Verified: Each run log entry records `planner` field with the LLM provider name (e.g., "llm:gemini", "llm:claude", "heuristic") and latency in ms.*

### Phase 3 — Insight, Visualization & Reporting (Weeks 9–12)
- [x] Chart generation tool (`generate_chart()`) & declarative `chart_spec` → Bar, line, box, histogram, scatter, heatmap with headless PNG rendering (`backend/app/services/chart_render.py`) and Reflex `rx.recharts` visualization — *Verified: Multi-type chart specs and headless Agg rendering.*
- [x] Dashboard page: ranked insight cards + embedded charts + narrative per finding — *Verified: Pure-Python Reflex dashboard (`pages/dashboard.py`) with confidence badges, caveats, exclusion rates, recharts components, data quality panel, and explainability run-log.*
- [x] Conversational Q&A chat page, re-invoking tools only when new computation is needed — *Verified: `POST /chat` and Reflex chat page (`pages/chat.py`) with 3-tool budget, prompt guardrails, in-memory history, starter questions, and citation verification.*
- [x] Report export: **both PDF and Word** (PRD FR-17 requires both, not just PDF) — *Verified: ReportLab PDF and python-docx export (`report_pdf.py`, `report_docx.py`) with 5 sections: Cover, Executive Summary, Top Insights with charts, Data Quality audit, and Methodology trail.*
- [x] Insight ranking/significance scoring — *Verified: Deterministic impact scoring (0..1), confidence classification (high/medium/low), deduplication, and max 8 cap in `backend/app/services/insights.py`.*
- [x] Visible token/cost tracker on the dashboard (Plan §8.5 — user-facing, not just an internal budget) — *Verified: Step progress, token usage, latency metrics, and budget limits on dashboard and settings pages.*
- [x] Multi-dataset autonomous end-to-end verification (`scripts/verify_phase3.py`) — *Verified: Full flow across retail, HR, and marketing messy datasets producing demo artifacts.*

### Phase 3 Hardening — Architecture & Plan-Act-Reflect Mechanics
1. **Batched Tool Calls per Plan:**
   - The initial planning phase (`llm_client.plan()`) receives the dataset profile, cleaning summary, and analytical goal.
   - It outputs a batched plan of tool calls with typed arguments and model-generated rationales.
   - These tool calls are placed in a FIFO execution queue (`pending_plan`).
2. **Sequential Act Phase:**
   - The orchestrator dequeues and executes each tool call sequentially.
   - Each step measures raw execution duration using `time.perf_counter()` with millisecond precision (`duration_ms`).
   - Planning latency (`llm_latency_ms`) is attributed to the initial step of the batch.
3. **Dynamic Reflection & Bounded Follow-ups:**
   - When the `pending_plan` queue becomes empty, and if the current step count is below `max_steps`, reflection is triggered (`llm_client.reflect()`).
   - The model observes execution history and tool findings, generating:
     a. A synthesis observation (`reflection`), stored in `run_log` on the step entry.
     b. Bounded follow-up tool calls (if necessary), appended to `pending_plan`.
   - Reflection latency (`reflection_latency_ms`) is tracked with millisecond precision.
4. **Max Rounds & Guardrails:**
   - Maximum execution rounds are strictly bounded by `max_steps` (default 5 or 6).
   - Additional guardrails include total runtime timeout (default 120s) and token budget limits (e.g. 15,000 tokens).
5. **Deterministic Insight Ranking & Suppression:**
   - Impact score formula: `raw_score * confidence_factor` (`{"high": 1.0, "medium": 0.75, "low": 0.5}`).
   - Analytical suppression: if `n_used < 20` or `exclusion_rate > 0.5`, analytical finding is suppressed and converted to a data quality caveat (`"insufficient data for <analysis>"`).
   - Zero outliers are folded into methodology with `impact_score <= 0.10`.
   - Trend analysis enforces OLS linear regression: if $p \ge 0.05$, titled `"No significant trend in X"`, with effect size equal to standardized slope and $n_{periods}$ reported separately.
   - Partitioning: Output splits into top 6 analytical insights and max 4 data quality insights.
6. **Bound Citation Checking & Verification:**
   - Synthesis returns structured claims: `{text, source_id, metric_key, value, unit}`.
   - Numeric values are validated against specific source metrics with 2% rounding tolerance and metric key consistency.
   - Pre-strip verification threshold $\ge 95\%$ enforced; single regeneration on failure; offending unverified sentences stripped cleanly.

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
