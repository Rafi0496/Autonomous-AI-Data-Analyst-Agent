# PROJECT PLAN & IMPLEMENTATION GUIDE
## Autonomous AI Data Analyst Agent

Technology stack, system architecture, and a four-phase build plan — from first data pipeline to a deployed, demo-ready product.

- **Document Type:** Project Plan & Implementation Guide
- **Companion Document:** Product Requirements Document (PRD), v1.0
- **Project:** Autonomous AI Data Analyst Agent • Batch No. 03
- **Department:** Computer Science & Engineering (AI & ML)
- **Academic Year / Sem:** Year IV • Semester I • Section B
- **Team:** D. Bala Varshith • R. Nikitha Varma • S. K. Rafi
- **Suggested Duration:** 16 weeks, 4 phases of 4 weeks each (adjust to your academic calendar)

**How to use this document:** Section 1 recaps the product goal. Section 2 defines the complete technology stack. Section 3 explains the system architecture and the agent's reasoning loop. Sections 4–7 give a week-by-week plan for each of the four build phases with concrete tasks and deliverables. Section 8 lists the specific features that make the project feel like a genuine real-world product rather than a classroom demo. Sections 9–12 cover team roles, testing, risk, and the final submission checklist.

---

## 1. Project Recap

The Autonomous AI Data Analyst Agent is a system that takes a raw, possibly messy dataset and autonomously cleans it, explores it, chooses appropriate analysis methods, generates visualizations, and writes a plain-language report — the way a human data analyst would, but without a human directing each step. It targets startups, SMBs, managers, students, researchers, and analysts who need fast, reliable insight without heavy technical effort or the cost of a dedicated analytics team.

The defining difference from a BI tool or AutoML platform is autonomy: the system plans its own investigation rather than executing a fixed pipeline the user configured in advance.

---

## 2. Technology Stack

The stack is chosen to be learnable within an academic timeline while still reflecting how this class of product is built in industry. Substitutions are noted where a lighter-weight option is reasonable for a student project.

### 2.1 Frontend

| Layer | Technology | Purpose |
|---|---|---|
| Framework | Reflex (Python) | Pure-Python framework that compiles to a real React app; single-page app for upload, dashboard, chat, and reports. |
| Styling | Tailwind CSS (via Reflex) | Fast, consistent, professional UI without heavy custom CSS or a separate JS toolchain. |
| Charts | Plotly (via Reflex's `rx.plotly` component) | Renders the agent's generated visualizations interactively. |
| State/data fetching | Reflex State (`rx.State`) | Handles async calls to the backend and job status polling natively in Python. |
| Realtime updates | Reflex's built-in WebSocket state sync | Streams the agent's live progress ("cleaning data…", "running correlation analysis…") to the UI. |

### 2.2 Backend & API

| Layer | Technology | Purpose |
|---|---|---|
| API framework | Python + FastAPI | REST endpoints plus WebSocket support; async-friendly for long-running agent jobs. |
| Task queue | Celery + Redis (or FastAPI BackgroundTasks for a lighter setup) | Runs analysis jobs asynchronously so uploads don't block the API. |
| Auth | JWT-based auth (FastAPI-Users or custom) | Per-user accounts and data isolation. |
| Validation | Pydantic | Type-safe request/response schemas. |

### 2.3 Agent & AI Layer

| Layer | Technology | Purpose |
|---|---|---|
| LLM reasoning | **Provider-agnostic LLM layer** (`llm_client.py`): Anthropic Claude API + Google Gemini API (via `google-genai` SDK). Selectable at runtime via `LLM_PROVIDER=claude\|gemini\|heuristic`. | Drives planning, tool selection, reflection, and plain-language synthesis. Real token accounting from provider usage metadata. Heuristic mode available for offline/test runs. Development running on Gemini free tier. |
| Agent orchestration | Custom Plan-Act-Reflect loop (`orchestrator.py`) | Structures the multi-step agent loop, tool routing, and memory. |
| Tool layer | Custom Python "tools" wrapping pandas / statsmodels / scikit-learn | The concrete actions the agent can call: `run_correlation()`, `detect_outliers()`, `segment_compare()`, `trend_analysis()`, `query_sql()`, etc. |
| Sandboxed execution | Closed-catalogue architecture + DuckDB in-memory isolation | Executes analysis within a strictly bounded tool catalogue, without file-system or network access. |

### 2.4 Data Processing & Storage

| Layer | Technology | Purpose |
|---|---|---|
| Data manipulation | pandas, NumPy | Cleaning, transformation, aggregation. |
| Statistics / ML | scikit-learn, statsmodels, SciPy | Correlation, regression, clustering, anomaly/outlier detection, time-series checks. |
| Ad-hoc querying | DuckDB (in-process SQL over uploaded files) | Lets the agent run SQL directly over uploaded CSV/Parquet without a separate DB load step. |
| Application database | PostgreSQL | Users, accounts, dataset metadata, saved reports, schedule configs. |
| File storage | Local disk (dev) / S3-compatible object storage (prod) | Uploaded datasets and generated report files. |
| Caching / queue broker | Redis | Celery broker and short-lived result caching. |

### 2.5 Reporting, DevOps & Testing

| Layer | Technology | Purpose |
|---|---|---|
| Report generation | ReportLab / WeasyPrint (PDF), python-docx (Word) | Produces the exportable business report. |
| Containerization | Docker + docker-compose | Consistent local dev and deployment across the team. |
| CI/CD | GitHub Actions | Automated tests and build checks on every push. |
| Deployment target | Render / Railway / a single cloud VM (AWS EC2 / GCP) | Low-cost hosting sufficient for an academic demo. |
| Testing | Pytest (backend), Jest + React Testing Library (frontend) | Unit and integration tests for pipeline, agent tools, and UI. |
| Monitoring (lightweight) | Structured logging + a simple token/cost tracker | Observability into agent behavior and API spend. |

---

## 3. System Architecture

### 3.1 End-to-end flow

- **Upload / Connect** — user uploads a file or connects a database; the file is stored and registered in Postgres.
- **Profile** — a deterministic (non-LLM) profiling step computes column types, null rates, cardinality, and basic distributions. This gives the agent a factual starting picture, cheaply.
- **Plan** — the LLM agent receives the data profile (and the user's stated goal, if any) and produces a short ordered plan of analysis steps, each mapped to a specific tool.
- **Act** — the orchestrator executes each planned step as a real tool call (pandas/statsmodels/SQL) inside the sandbox and returns structured results (numbers, tables, chart specs) — never free-form text at this stage.
- **Reflect** — after each step, the agent checks whether the result changes the plan (e.g., an unexpected spike worth investigating). It may insert new steps, within a fixed step/token budget.
- **Synthesize** — once the plan completes (or the budget is reached), the LLM converts the structured results into a plain-language narrative, strictly citing the computed values rather than inventing new ones.
- **Deliver** — results render as an interactive dashboard in the UI and can be exported as a PDF/Word report; the user can now ask natural-language follow-up questions against the same context.

### 3.2 Why a profiling step happens before the LLM plans anything

Sending raw data straight to an LLM is slow, expensive, and unreliable for numeric precision. Instead, deterministic Python code computes the factual profile first (row/column counts, types, missingness, summary statistics); the LLM only ever reasons over this structured summary, and every later analysis step is itself a real computation, not a language-model guess. This is what keeps the system's insights grounded and directly satisfies FR-08–FR-13 and the explainability requirement in the PRD.

### 3.3 Tool catalogue (the agent's available actions)

| Tool | What it does |
|---|---|
| `clean_data()` | Handles missing values, type coercion, duplicate rows, per-column strategy. |
| `profile_dataset()` | Computes shape, types, nulls, cardinality, summary statistics. |
| `run_correlation()` | Computes pairwise correlation across numeric columns; flags strong relationships. |
| `detect_outliers()` | Statistical outlier detection (IQR / z-score / isolation forest). |
| `segment_compare()` | Groups data by a categorical column and compares a metric across segments. |
| `trend_analysis()` | Time-series decomposition / rolling trend detection for date-indexed data. |
| `generate_chart()` | Produces the appropriate chart spec (bar, line, scatter, heatmap) for a given result. |
| `query_sql()` | Runs an agent-composed SQL query over the dataset via DuckDB for ad-hoc questions. |
| `write_summary()` | Synthesizes structured results into a plain-language explanation (final step only). |

### 3.4 Guardrails

- Hard cap on plan steps and total tokens per analysis session (bounds cost and prevents infinite loops).
- Every numeric claim in the final report must trace back to a specific tool result (checked programmatically before rendering).
- Sandboxed execution: no network access, no arbitrary file-system writes, resource/time limits per tool call.
- Timeout with graceful partial-result fallback rather than a hard failure.

---

## 4. Phase Overview

| Phase | Weeks | Theme | Exit Criteria |
|---|---|---|---|
| Phase 1 | 1–4 | Foundations & Data Pipeline | Upload, clean, and profile a real dataset end-to-end through a working UI. |
| Phase 2 | 5–8 | Autonomous Agent Core | Agent plans and executes a multi-step analysis via real tool calls, unattended. |
| Phase 3 | 9–12 | Insight, Visualization & Reporting | Full dashboard, conversational Q&A, and an exportable business report. |
| Phase 4 | 13–16 | Real-World Readiness & Deployment | Authenticated, tested, deployed system with scheduling and a rehearsed live demo. |

Each phase below lists objectives, week-by-week tasks, primary tech touched, and concrete deliverables. Adjust week numbers to fit your institution's academic calendar — the sequence and dependencies matter more than the exact dates.

---

## PHASE 1 — Foundations & Data Pipeline (Weeks 1–4)

**Objective:** Establish the project skeleton and prove the non-agentic half of the system: a user can upload real data, see it cleaned and profiled, and view a basic UI shell.

| Week | Focus | Tasks |
|---|---|---|
| 1 | Setup | Initialize Git repo, project structure, Docker Compose (Postgres + Redis + API + frontend skeleton). Agree on coding standards and branch strategy. |
| 1–2 | Ingestion | Build file upload endpoint (CSV/XLSX/JSON); validate structure; store file and metadata in Postgres. Add a SQL-database connector for a stretch goal. |
| 2–3 | Cleaning pipeline | Implement `clean_data()`: missing-value handling, type inference/coercion, duplicate detection, outlier flagging — as a standalone, testable Python module. |
| 3 | Profiling | Implement `profile_dataset()`: shape, types, null rates, cardinality, summary statistics; render as a data-quality summary. |
| 4 | UI shell | Build the Reflex upload page + a static "data profile" results view. Wire it to the backend via REST. |
| 4 | Testing & review | Unit tests for cleaning/profiling on at least 3 real-world messy datasets (see Section 8.1). Fix edge cases found. |

**Deliverables**
- Working upload → clean → profile pipeline, callable via API and visible in a basic UI.
- Test suite covering missing values, mixed types, duplicates, and outliers on real sample datasets.
- Dockerized local dev environment the whole team can run identically.
- Short internal design note on the database schema (users, datasets, dataset_versions).

---

## PHASE 2 — Autonomous Agent Core (Weeks 5–8)

**Objective:** Build the part that makes this project genuinely "agentic" rather than a scripted pipeline — an LLM-driven planner that chooses and executes analysis steps on its own.

| Week | Focus | Tasks |
|---|---|---|
| 5 | Research spike | Evaluate agent-orchestration approaches (LangGraph vs. a custom Plan-Act-Reflect loop). Prototype a single tool call through the LLM's function-calling API. |
| 5–6 | Tool layer | Implement the tool catalogue as callable, typed Python functions: `run_correlation()`, `detect_outliers()`, `segment_compare()`, `trend_analysis()`, `query_sql()`. |
| 6 | Sandbox | Set up a restricted execution environment for any agent-generated code (resource limits, no network/file access outside the session dataset). |
| 6–7 | Planner | Prompt-engineer the planning step: given a data profile (+ optional user goal), the LLM returns an ordered list of tool calls with justification. |
| 7 | Executor & reflect loop | Build the orchestrator that executes the plan step by step, feeds results back to the LLM, and allows bounded re-planning (Reflect step). |
| 8 | Guardrails | Add step/token budgets, timeouts, graceful partial-result handling, and a run log capturing every step taken (for explainability). |
| 8 | Integration test | Run the full agent loop unattended on a real dataset end-to-end and manually verify every claim traces to a real computed result. |

**Deliverables**
- A working agent loop: profile → plan → execute tool calls → reflect → stop, with no manual step-by-step prompting.
- A documented tool catalogue other teammates (and later, the reporting layer) can call.
- A visible run log per analysis session, listing each step the agent took and why.
- Enforced step/token budget with logged token/cost usage per session.

**Phase 2 As-Built Verification Status (Completed & Fully Verified):**
- [x] Tool Catalogue: `run_correlation()`, `detect_outliers()`, `segment_compare()`, `trend_analysis()`, `generate_chart()`, `query_sql()`, `write_summary()` returning typed structured data.
- [x] Single tool-call Claude/Gemini API prototype tested via `scripts/prototype_tool_call.py` and dedicated live test suite (`backend/tests/test_live_claude_api.py`, marked with `@pytest.mark.live`).
- [x] Plan-Act-Reflect Orchestrator (`backend/app/agent/orchestrator.py`) with reflection-driven follow-ups and per-step latency and real token tracking.
- [x] Closed-catalogue & DuckDB in-memory isolation guardrails against SQL writes & filesystem traversals verified with adversarial tests.
- [x] Step/token budget guardrail tripping verified with automated tests tripping budgets and asserting graceful partial fallbacks.
- [x] Ordered explainability run log stored in `AnalysisJob` model and exposed via `/api/v1/jobs/{job_id}/logs`.
- [x] Data Cleaning & Integrity: Frequency-based canonical casing (preserving Title Case over lowercase, e.g., Engineering, HR, Marketing, Sales, Accessories, Electronics, LinkedIn, Google Ads), domain validity rules (sanitizing negative metrics and invalid ages [0, 100]), and extreme sentinel detection (e.g. Quantity=999).
- [x] Statistical Rigor: Restored standard Z-score threshold to 3.0; tracked boolean companion imputation masks on disk; statistical tools exclude imputed rows reporting n_used and clean denominators.
- [x] Full agent loop unattended integration test verified on messy retail data with programmatic citation verification (`citation_checker.py`, 100.0% verification rate). Data quality findings (sentinels, invalid values, imputation rates) surfaced to executive synthesis and fact pool.

---

## PHASE 3 — Insight, Visualization & Reporting (Weeks 9–12)

**Objective:** Turn raw agent output into something a non-technical user finds genuinely useful: an interactive dashboard, a conversational interface, and a shareable report.

| Week | Focus | Tasks |
|---|---|---|
| 9 | Chart generation | Implement `generate_chart()`: map each result type to an appropriate chart spec (trend→line, relationship→scatter, correlation→heatmap, comparison→bar). |
| 9–10 | Dashboard UI | Build the results dashboard in React: ranked insight cards, embedded charts (Plotly/Recharts), and the agent's plain-language narrative per finding. |
| 10 | Conversational Q&A | Add a chat interface that answers natural-language follow-ups using existing context, re-invoking tools (incl. `query_sql()`) only when a new computation is required. |
| 11 | Report export | Implement PDF/Word export (ReportLab/WeasyPrint or python-docx): executive summary, key findings, charts, methodology appendix. |
| 11–12 | Insight ranking | Add relevance/significance scoring so the most important findings surface first rather than a flat list. |
| 12 | Usability pass | Run the flow past 3–5 outside users (classmates/faculty) on real datasets; fix friction points in under 3-click first-insight goal. |

**Deliverables (Phase 3 Completed & Verified)**
- Interactive Reflex dashboard showing ranked insights, charts (`rx.recharts`), confidence badges, data quality stats, and explainability run-log.
- Working conversational follow-up Q&A grounded in the analyzed dataset (`POST /chat`) with strict guardrails and citation verification.
- One-click PDF (ReportLab) and Word (python-docx) report export with 5 comprehensive analytical sections and embedded chart PNGs.
- End-to-end verification script (`scripts/verify_phase3.py`) validating the entire pipeline across 3 benchmark messy datasets.

---

## PHASE 4 — Real-World Readiness & Deployment (Weeks 13–16)

**Objective:** Take the working prototype and make it feel like a real, trustworthy product — secure, tested, deployed, and rehearsed for demonstration.

| Week | Focus | Tasks |
|---|---|---|
| 13 | Auth & multi-user | Add JWT-based accounts, per-user dataset isolation, and a saved-reports/history view. |
| 13–14 | Automation | Implement scheduled/recurring analysis (e.g., weekly refresh) with a notification on completion (email or in-app). |
| 14 | Resilience | Handle large/edge-case files gracefully (sampling strategy for big datasets, clear errors for malformed input, timeout fallbacks). |
| 14–15 | Testing | Full test pass: unit tests (Pytest), integration tests for the agent loop, frontend tests (Jest), and manual testing on messy real-world datasets. |
| 15 | Deployment | Containerize and deploy to a cloud VM / Render / Railway; set up GitHub Actions CI to run tests on every push. |
| 15–16 | Documentation & demo prep | Write setup/README docs, finalize architecture diagrams, prepare a 2–3 business-scenario live demo script, rehearse the presentation. |
| 16 | Final polish | UI cleanup, performance pass, fix outstanding bugs, freeze scope for submission. |

**Deliverables**
- Deployed, publicly reachable instance of the system.
- Authenticated multi-user support with data isolation.
- Passing CI test suite (unit + integration).
- Final documentation set: README, architecture diagram, and this plan updated with "as-built" notes.
- Rehearsed live demo using at least two different real-world-style datasets.

---

## 8. Making It Feel Like a Real-World Product

These are the specific, concrete additions that separate a classroom prototype from something that reads as a genuine product solving a genuine problem. Treat this as a checklist to weave into the phases above, not a separate phase.

### 8.1 Use real, messy demo datasets
- Pick 3–4 realistic business scenarios for demos: retail/e-commerce sales, HR attrition, marketing campaign performance, and a financial/operations dataset.
- Deliberately include messiness in at least one demo dataset — missing values, inconsistent date formats, duplicate rows — so the cleaning pipeline has something real to prove itself against.
- Public sources such as Kaggle or UCI Machine Learning Repository work well; keep each dataset's license/attribution noted in your documentation.

### 8.2 Explainability, not a black box
- Always show the agent's run log ("what it did and why") alongside the final narrative, not just the conclusion.
- Every chart and statistic in the report should be clickable/traceable back to the step that produced it.
- Avoid presenting any number the agent did not actually compute — this is both a trust feature and a direct requirement from the PRD.

### 8.3 Proactive, not just reactive
- Scheduled/recurring analysis (e.g., "check this data source every Monday") with a notification when something changes.
- Automatic anomaly/alert flagging — the agent should point out something noteworthy even if the user didn't ask a specific question.

### 8.4 Business-friendly output
- Reports should lead with an executive summary in plain language, not raw statistical output.
- Support export formats a business user actually shares: PDF and Word, not just an in-app view.

### 8.5 Trust, security & cost-awareness
- Per-user authentication and strict data isolation between accounts.
- A visible token/cost tracker per analysis run — shows engineering maturity and answers "what does this cost to run?" in a demo or viva.
- Sandboxed code execution so a malicious or malformed dataset cannot compromise the host system.

### 8.6 Feedback loop
- Let users mark an insight as "helpful" / "not relevant"; log this even if you don't have time to build a full learning loop from it — it demonstrates awareness of human-in-the-loop design.

### 8.7 Handle scale sensibly
- Define and enforce a maximum file size / row count for V1, with a clear message when exceeded.
- For larger files, use a sampling strategy for exploratory steps rather than failing outright.

---

## 9. Suggested Team Role Division

A starting split across the three team members, based on natural module boundaries. Adjust to match individual strengths — the important thing is that each phase has a clear owner per module so work can proceed in parallel.

| Member | Primary Ownership | Key Modules |
|---|---|---|
| D. Bala Varshith | Backend & Agent Engine | FastAPI backend, agent orchestration loop, LLM tool-calling integration, sandboxed execution. |
| R. Nikitha Varma | Data Pipeline & Analysis | Cleaning/profiling pipeline, statistical/ML tool implementations, anomaly detection, SQL/DuckDB layer. |
| S. K. Rafi | Frontend, Reporting & DevOps | Reflex (Python) dashboard, chat UI, chart rendering, PDF/Word report generation, Docker/CI/CD, deployment. |

All three members should collaborate closely on Phase 2 (the agent core), since it is the project's central technical contribution and the strongest source of viva/evaluation questions.

---

## 10. Testing & Evaluation Plan

| Level | What's tested | How |
|---|---|---|
| Unit | Cleaning functions, individual tools (correlation, outliers, etc.) | Pytest, with known-answer fixtures on synthetic data. |
| Integration | Full agent loop on a real dataset end-to-end | Automated run comparing output structure against expected schema; manual review of narrative accuracy. |
| Usability | First-insight time, click count, clarity of report | Structured sessions with 3–5 outside users on real datasets, per PRD success metrics. |
| Regression | No breakage across releases | GitHub Actions CI running the full suite on every push. |
| Security | Data isolation, sandbox escape attempts | Manual review + basic negative testing (e.g., attempt file-system access from a tool call). |

---

## 11. Technical Risk Management

Complements the product-level risks in the PRD with implementation-specific risks.

| Risk | Mitigation |
|---|---|
| Team unfamiliar with agent-orchestration frameworks. | Timeboxed research spike in Phase 2, Week 5, before committing to a framework. |
| LLM API costs exceed budget during development. | Use a small/cheap model for iteration, reserve the full model for demo runs; enforce token budgets from day one. |
| Sandbox implementation is more complex than expected. | Start with a simple restricted-subprocess approach in Phase 2; only move to Docker-in-Docker if time allows. |
| Scope creep across four phases. | Treat Section 5 (In Scope) of the PRD as a hard boundary; log "nice-to-have" ideas separately for a post-submission backlog. |
| Integration slippage between frontend and backend teams. | Agree on API contracts (OpenAPI schema) at the end of Phase 1, before parallel work begins in Phase 2–3. |

---

## 12. Final Submission Checklist

- [ ] Deployed, working demo instance (URL) with at least two demo datasets pre-loaded.
- [ ] Complete source code in a Git repository with a clear README (setup, run, architecture).
- [ ] This Project Plan and the companion PRD, updated with any "as-built" changes.
- [ ] Project report / dissertation chapter documenting the system for academic submission.
- [ ] Presentation slides covering problem, architecture, live demo, and results/metrics.
- [ ] Test suite and a short results summary (coverage, key metrics from Section 10).
- [ ] Rehearsed live demo script covering at least one messy real-world dataset end-to-end.

---

*End of Project Plan. Refer to the companion PRD for detailed functional and non-functional requirements, user stories, and success metrics.*
