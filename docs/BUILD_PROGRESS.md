# Build Progress

## Project

- **Name:** CarbonGuard
- **Objective:** Monitor carbon budgets and evaluate cloud-computing workload
  emissions.
- **Current phase:** Phase 8 — Final integration, deployment readiness, and release validation

## Implemented phases

- **Phase 1 — Foundation:** FastAPI, React/Vite, health/status endpoints, CORS,
  and explicit unavailable metric placeholders.
- **Phase 2 — Persistence and application management:** SQLAlchemy models,
  SQLite configuration, Alembic, application/budget/workload APIs, monitoring
  records, policy-event records, and experiment records.
- **Phase 3 — Energy and emissions estimator:** `POST /api/estimates` uses
  caller-provided average power, duration, and carbon intensity. Estimates
  are transparent, stateless, and identified as estimates.
- **Phase 4 — Workload simulator:** bounded 60-sample profiles, persisted run
  history, and APIs for simulation and run retrieval. No host workload runs.
- **Phase 5 — Carbon-budget policy evaluation:** persistent per-application
  policy configuration, recorded-run aggregation, status and advisory action
  evaluation, and a dashboard interface. No real enforcement is performed.

## Phase 6 — Analytics, historical trends, and reporting

### Features implemented

- Read-only analytics are calculated from completed `workload_runs` and their
  recorded Phase 3 energy/emissions estimates. No estimates are regenerated.
- Overview totals include registered applications, enabled policies, all-time
  completed workload-run count, all-time estimated kWh and kg CO2e, current
  policy status counts, and recommended interventions. Run totals are
  explicitly all-time; policy statuses are current evaluations.
- Application comparisons include all-time completed run count, energy,
  emissions, and an enabled policy evaluation. Applications without runs
  return zero totals; applications without enabled policies have no status.
- Historical trends support daily, weekly, and monthly UTC buckets over a
  validated range of up to 366 days. Query semantics are `[start, end)`;
  weekly buckets start Monday 00:00 UTC. Empty periods are explicitly
  zero-filled with `is_empty: true`. Emissions and energy are separate fields;
  the frontend plots estimated emissions only with labeled units.
- Policy statuses in overview/application/policy endpoints are evaluated on
  request using the existing Phase 5 evaluator. No historical policy
  snapshots are stored or inferred; comparisons distinguish all-time run
  totals from current-period budget utilization.
- Application-specific analytics combines application data, all-time totals,
  a selected-range trend, and its enabled policy's current evaluation.
- CSV export includes a metadata row and completed run rows with UTC report
  range, estimate classification, application/run IDs and name, completion
  time, estimated energy/emissions, source, estimation method, and current
  policy ID/period/budget/status/action when available. Current policy values
  are labeled with the snapshot timestamp. CSV quoting is provided by
  Python's `csv` writer. Exports are limited to 10,000 runs and can be scoped
  to one application.
- The dashboard adds summary cards, date/interval/application selectors,
  Recharts emissions trend, application comparison and detail focus, current
  policy status, manual refresh, CSV download, and loading/empty/error
  feedback.

### Phase 6 endpoints

- `GET /api/analytics/overview`
- `GET /api/analytics/trends?start=...&end=...&interval=daily&application_id=...`
- `GET /api/analytics/applications?skip=0&limit=100`
- `GET /api/analytics/policies`
- `GET /api/analytics/applications/{application_id}?start=...&end=...&interval=daily`
- `GET /api/analytics/export.csv?start=...&end=...&application_id=...`

No database migration was needed; analytics derive from the Phase 2, 4, and 5
tables.

### Files created for Phase 6

- `backend/app/api/analytics.py`
- `backend/app/schemas/analytics.py`
- `backend/app/services/analytics.py`
- `backend/tests/test_analytics.py`
- `frontend/src/components/AnalyticsDashboard.jsx`

### Files modified for Phase 6

- `backend/app/main.py`, `backend/app/api/routes.py`
- `backend/tests/test_health.py`
- `frontend/src/pages/Dashboard.jsx`
- `frontend/src/services/api.js`
- `frontend/src/index.css`
- `docs/API.md`, `docs/ARCHITECTURE.md`, `docs/SETUP.md`,
  `docs/BUILD_PROGRESS.md`, `README.md`

### Phase 6 validation

- Backend: `python -m pytest -v` from `backend` — **98 passed**, with one
  upstream Starlette/httpx `TestClient` deprecation warning.
- Frontend: `npm run build` from `frontend` — passed. Vite produced separate
  application (about 238 KB) and charts (about 377 KB) chunks without the
  earlier oversized-chunk warning.
- Migration check: `alembic current` reported `c9f21e6a7b34 (head)` and
  `alembic check` reported no new upgrade operations. Phase 6 adds no migration.
- Live API smoke test: `/`, `/api/health`, `/api/status`, and `/docs` returned
  HTTP 200. The analytics overview, weekly trends, application detail, and
  application-filtered CSV export were also verified. CORS allowed
  `http://127.0.0.1:5173`.
- Browser smoke test used an isolated SQLite database. The dashboard created an
  application and daily policy, then displayed a simulated 120 W, 1,800-second
  workload at 400 g CO2e/kWh as 0.06 kWh and 0.024 kg CO2e. Refresh showed one
  run, 100% budget utilization, `critical` policy status, and
  `recommend_throttle`. The CSV API returned the corresponding run and current
  policy snapshot; the dashboard displayed its export success message. The
  browser automation did not independently observe a download event.
- The isolated validation database was temporary and removed after testing.
- Known validation issue: the backend suite emits the upstream
  Starlette/httpx `TestClient` deprecation warning; all tests pass. No other
  unresolved Phase 6 validation failures remain.

## Phase 5 policy behavior

- Added one `BudgetPolicy` per application, enforced by a unique database
  index. Existing Phase 2 `CarbonBudget` records and APIs remain separate and
  unchanged.
- Policies configure a positive finite kg CO2e budget; daily, weekly, or
  monthly period; warning and critical thresholds; enabled state; and one of
  `monitor`, `warn`, or `recommend_throttle`.
- Defaults: warning threshold 80%, critical threshold 95%, enabled, and action
  `warn`. Warning must be positive and below critical. Critical thresholds
  above 100% are allowed.
- Evaluations sum recorded emissions from completed runs, using
  `completed_at`, with UTC half-open period intervals `[start, end)`. Daily
  periods follow UTC days, weeks start Monday 00:00 UTC, and months follow
  UTC calendar boundaries. Each request uses one UTC reference time.
- Values are rounded to 12 decimal places for consumption/remaining and 6 for
  utilization. Comparisons use unrounded decimal values.
- `exceeded` (>100% consumed) takes precedence over critical, including when
  the critical threshold is configured above 100%; otherwise critical,
  warning, then within-budget thresholds apply. Exactly 100% is not exceeded.
- Actions are recommendations only. `monitor` never recommends intervention;
  `warn` recommends a warning at warning status or higher; `recommend_throttle`
  recommends a warning at warning status and throttling at critical/exceeded.
- No evaluation event history, scheduler, cloud integration, throttling,
  process termination, or blocking is implemented.

## Files created for Phase 5

- `backend/app/api/policies.py`
- `backend/app/schemas/policies.py`
- `backend/app/services/policies.py`
- `backend/migrations/versions/c9f21e6a7b34_add_budget_policies.py`
- `backend/tests/test_policies.py`
- `frontend/src/components/BudgetPolicies.jsx`

## Files modified for Phase 5

- `backend/app/models/entities.py`
- `backend/app/models/__init__.py`
- `backend/app/services/database.py`
- `backend/app/main.py`
- `backend/app/api/routes.py`
- `backend/app/api/applications.py`
- `backend/tests/test_health.py`
- `frontend/src/services/api.js`
- `frontend/src/pages/Dashboard.jsx`
- `frontend/src/components/MetricCard.jsx`
- `frontend/src/index.css`
- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `docs/SETUP.md`
- `docs/BUILD_PROGRESS.md`
- `README.md`

## API endpoints

- `POST /api/budget-policies` — create one policy for an application.
- `GET /api/budget-policies` — list policies, optionally filtered by
  `application_id`.
- `GET /api/budget-policies/{policy_id}` — retrieve a policy.
- `PATCH /api/budget-policies/{policy_id}` — update configuration or enabled
  state.
- `POST /api/budget-policies/{policy_id}/evaluate` — evaluate a policy,
  including a disabled policy (recommendation remains monitor-only).
- `POST /api/budget-policies/evaluate` — evaluate all enabled policies using
  one request reference time.
- `GET /api/applications/{application_id}/budget-status` — current status for
  an enabled policy; returns 404 if none is enabled.

Evaluation responses include UTC period boundaries, budget, consumed and
remaining kg CO2e, utilization, status, contributing run IDs and stored
emissions, the configured/recommended actions, and explicit
`recommendation_only` enforcement semantics.

## Migration and validation

- New additive migration: `c9f21e6a7b34`, parent
  `a3616f13edf7`. It creates only `budget_policies`, its constraints, and
  indexes. Earlier migrations and tables were not edited or dropped.
- The migration was applied first to a separate SQLite validation database,
  where `alembic check` reported no new operations. The temporary database was
  removed after checking.
- The development database was at Phase 4 head before migration and contained
  zero applications, budgets, workloads, or workload runs. After applying the
  migration, `alembic current` reports `c9f21e6a7b34 (head)`, `alembic check`
  reports no new upgrade operations, and the existing row counts remain zero.
- Full backend suite: **88 passed, 1 upstream Starlette/httpx TestClient
  deprecation warning**.
- Frontend production bundle: `npm run build` completed successfully.
- Live HTTP smoke checks used a separate temporary database. Root, health,
  status, docs, application registration, policy create/read/filter/update,
  simulation, individual/all/current-status evaluation, and disabled-policy
  behavior returned expected results. A 120 W, 1,800-second run at
  400 g CO2e/kWh recorded 0.024 kg CO2e; against a 0.024 kg daily budget the
  evaluator reported 100% utilization, `critical`, and
  `recommend_throttle`.
- Browser verification on the configured Vite origin `127.0.0.1:5173`
  confirmed API connectivity, policy enable/disable, displayed status and
  contributing run, and the recommendation-only label. A first check on
  port 5174 was blocked because that origin is intentionally not in the
  configured CORS allowlist; the configured 5173 origin passed.
- Smoke-test servers were stopped and the temporary HTTP database was removed.
  No smoke-test records were written to the development database.

## Known limitations

- Evaluation is request-driven; there is no background scheduler or event
  history.
- Phase 4 runs use simulated profiles and estimated emissions, not measured
  cloud telemetry. Policy recommendations do not affect workload execution.
- Phase 2 `CarbonBudget` records coexist with the one-per-application Phase 5
  `BudgetPolicy`; they are not automatically converted.
- The upstream Starlette/httpx TestClient deprecation warning remains.

## Phase 7 — Security, performance, and reliability hardening

### Features implemented

- The security review identified spreadsheet formula injection through exported
  application names. CSV exports now neutralize names beginning with formula
  characters without changing stored values.
- CORS origins are configurable. Development defaults to the two local Vite
  origins; production requires explicit origins, rejects wildcard/path origins,
  and does not enable credentials.
- Added common security response headers, `no-store` for API responses, and a
  1 MiB request-body limit.
- Tightened request schemas with finite-number and domain bounds, rejection of
  unknown fields, bounded database IDs, and server-controlled record fields.
  Validation error responses omit submitted values and internal validation
  context.
- Added bounded pagination to policy reads and evaluation endpoints, plus
  clearer frontend API errors, request timeouts, response-shape checks, and
  cancellation of superseded dashboard requests.
- Added composite indexes for workload-run status/completion-time analytics
  and application/status/completion-time analytics. Query-plan checks confirm
  SQLite uses these indexes for the corresponding time-filtered queries.
- Policy evaluations requested together now load recorded runs once per batch
  of at most 100 policies rather than issuing a separate run query for each
  policy. Evaluation thresholds, UTC periods, contribution ordering, and
  recommendation semantics are unchanged.

New input limits: estimates accept power up to 1,000,000,000 W, duration up to
31,536,000 seconds, and carbon intensity up to 100,000 g CO2e/kWh; simulation
duration remains limited to 86,400 seconds. Budgets are limited to 1e12 kg
CO2e, policy thresholds to 1,000,000%, and integer database IDs to positive
signed 32-bit values. These limits are enforced by request validation.

### Files created for Phase 7

- `backend/app/core/config.py`
- `backend/app/core/middleware.py`
- `backend/app/schemas/limits.py`
- `backend/app/api/parameters.py`
- `backend/migrations/versions/d47e1b9c2a63_add_workload_run_analytics_indexes.py`

### Files modified for Phase 7

- Backend API/configuration: `backend/app/main.py`,
  `backend/app/api/routes.py`, `backend/app/api/analytics.py`,
  `backend/app/api/policies.py`, `backend/app/api/applications.py`,
  `backend/app/api/records.py`, `backend/app/api/simulation.py`
- Backend models/schemas/services: `backend/app/models/entities.py`,
  `backend/app/schemas/estimates.py`, `backend/app/schemas/simulation.py`,
  `backend/app/schemas/applications.py`, `backend/app/schemas/policies.py`,
  `backend/app/schemas/records.py`, `backend/app/services/analytics.py`,
  `backend/app/services/policies.py`
- Backend tests/configuration: `backend/tests/test_health.py`,
  `backend/tests/test_analytics.py`, `backend/tests/test_estimates_api.py`,
  `backend/tests/test_estimation.py`, `backend/tests/test_simulation.py`,
  `backend/tests/test_policies.py`, `backend/tests/test_applications_api.py`,
  `backend/.env.example`
- Frontend: `frontend/src/services/api.js`,
  `frontend/src/components/AnalyticsDashboard.jsx`
- Documentation: `docs/API.md`, `docs/SETUP.md`, `docs/ARCHITECTURE.md`,
  `docs/BUILD_PROGRESS.md`, `README.md`

### Phase 7 validation

- Backend: `.\.venv\Scripts\python.exe -m pytest -v` from `backend` —
  **121 passed**, with one upstream Starlette/httpx `TestClient` deprecation
  warning. This includes the query-count regression test for batched policy
  evaluation.
- Focused analytics and policy tests after the batching change —
  **47 passed**, with the same deprecation warning.
- Frontend: `npm run build` from `frontend` — passed. Vite produced the
  application and charts production bundles.
- Dependency checks: `npm audit` reported **0 vulnerabilities**;
  `pip check` reported no broken requirements. `pip-audit` is not installed,
  so a Python package vulnerability scan was not performed.
- Migration: `alembic current` reports `d47e1b9c2a63 (head)` and
  `alembic check` reports no new upgrade operations.
- Database: SQLite `PRAGMA integrity_check` returned `ok`. The additive
  migration was also tested on an isolated temporary database and applied to
  the existing development database without changing existing row counts.
- Analytics query-plan checks showed SQLite using the new composite indexes
  instead of scanning all workload runs for the covered time-filtered query
  shapes.
- No Phase 7 live-server or browser smoke test was performed.

## Phase 8 — Final integration, deployment readiness, and release validation

### Completed work

- Audited the Phase 1–7 implementation, including API contracts, persistence,
  migrations, simulation, policy evaluation, analytics, CSV export, frontend
  API handling, and documentation. No Phase 7 prerequisite gap was found.
- Finalized the existing two-service deployment: a non-root FastAPI image with
  startup migrations and health check, and a multi-stage Vite/Nginx image with
  same-origin `/api/` proxying. Compose uses a persistent named SQLite volume,
  health-ordered startup, loopback host bindings, configurable host ports and
  explicit production CORS origins.
- Confirmed safe environment examples and ignored local `.env`, database,
  virtual-environment, cache, and generated build artifacts. Nested
  `backend/.env.example` and `frontend/.env.example` files are explicitly
  unignored so setup templates remain shareable.
- Updated the release documentation in `README.md`, `docs/SETUP.md`,
  `docs/API.md`, `docs/ARCHITECTURE.md`, and `docs/DEMO.md`.

### Phase 8 validation

- Backend test command (using the available bundled Python with the existing
  project site-packages and a workspace-local pytest temp directory):
  `C:\Users\opguy\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest -v --basetemp=C:\Users\opguy\Desktop\CarbonGuard\backend\.pytest-phase8` —
  **121 passed, 2 warnings**. Warnings were the upstream Starlette/httpx
  `TestClient` deprecation and a sandbox cache-write warning; no test failures.
- Frontend command: `npm.cmd run build` from `frontend` — passed. Vite
  transformed 622 modules and produced the application and charts bundles.
- Migration commands on the existing database: `alembic current` reported
  `d47e1b9c2a63 (head)` and `alembic check` reported no new operations.
- Migration lifecycle on a separate temporary SQLite database: `alembic
  upgrade head` applied all four revisions successfully, reached
  `d47e1b9c2a63`, and `alembic check` reported no new operations. The temporary
  database was removed afterward.
- Live API smoke test used a separate temporary database and port. Root,
  health, status, application registration, policy creation, stateless estimate,
  simulated workload, stored run retrieval, policy evaluation, analytics
  overview/trend filtering, CSV export, and invalid application handling all
  returned expected results. The sample produced `0.06` kWh, `0.024` kg CO2e,
  `critical`, 100% utilization, and `recommend_throttle`. CSV contents included
  the recorded run. The temporary database was removed afterward.
- Browser smoke test used a temporary Vite server and the isolated API. The
  dashboard visibly showed API connected, one recorded run, 0.06 kWh, 0.024 kg
  CO2e, the critical current policy, 100% utilization, and the recommendation-only
  notice. The test tab and servers were closed afterward.
- Docker build/runtime validation: **blocked** because Docker CLI/Desktop is
  not installed in the validation environment. Compose and Dockerfiles were
  statically inspected; no live container claim is made.
- Frontend unit-test command: **not available**; `package.json` defines no test
  script. Production build and browser smoke testing were used instead.
- Python dependency audit: `pip-audit` is not installed. Existing recorded
  Phase 7 `npm audit` and `pip check` results remain documented; no new audit
  was claimed in Phase 8.

### Release-readiness checklist

- [x] Functional integration workflow verified through API and browser.
- [x] Backend suite passes: 121/121.
- [x] Frontend production build passes.
- [x] Migration chain has one head and clean `alembic check`.
- [x] Fresh temporary database initializes and passes SQLite migration lifecycle.
- [x] Configuration examples, secret exclusion, and persistent SQLite path reviewed.
- [x] README, setup, API, architecture, demo, and progress documentation complete.
- [x] Simulation, estimated telemetry, recommendation-only actions, request-driven
  policy evaluation, non-historical policy status, legacy budgets, and missing
  authentication/cloud integration limitations are explicitly documented.
- [ ] Docker build/runtime validation — blocked by unavailable Docker CLI.
- [ ] Python vulnerability audit — not verified because `pip-audit` is unavailable.

### Security and reliability limitations

- The application still has no authentication/authorization or distributed
  rate limiter. Deploy only behind appropriate access controls.
- No restrictive Content Security Policy was added because it can interfere
  with the interactive API documentation.
- The upstream Starlette/httpx `TestClient` deprecation warning remains.
- Authentication/authorization, distributed rate limiting, restrictive CSP,
  deployment monitoring, scheduler-driven evaluation, cloud-provider telemetry,
  and real workload enforcement remain outside the implemented scope.

## Post-release completion update — 2026-10-29

The initial repository audit found that the Phase 8 notes above described
release validation, but the live dashboard still disabled Workloads and
documented simulation as API-only. The baseline frontend production build
passed. The backend test suite could not be run with the system Python because
its SQLAlchemy dependency was absent; the project virtual environment was
available and used for the follow-up validation below.

### Completed in this update

- Added a Workloads dashboard section and working sidebar navigation.
- Connected the interface to application/workload registration, bounded
  simulation, persisted run history, estimate results, and explicit UTC
  timestamps through the centralized API client.
- Added client-side native input constraints for backend-supported ranges,
  prevented repeated submission while a simulation is running, presented API
  errors and empty/loading states, and refreshed analytics after successful
  runs.
- Added policy editing and confirmed deletion in the dashboard, plus a
  backward-compatible `DELETE /api/budget-policies/{policy_id}` API operation.
  Deleting a policy leaves the application and its run history untouched.
- Updated README, API, and demo documentation to match the actual dashboard.

### Files modified in this update

- `backend/app/api/policies.py`
- `backend/tests/test_policies.py`
- `frontend/src/services/api.js`
- `frontend/src/pages/Dashboard.jsx`
- `frontend/src/components/Workloads.jsx`
- `frontend/src/components/BudgetPolicies.jsx`
- `frontend/src/index.css`
- `README.md`
- `docs/API.md`
- `docs/DEMO.md`
- `docs/BUILD_PROGRESS.md`

### Follow-up validation

- Backend: `.\.venv\Scripts\python.exe -m pytest -q` from `backend` —
  **122 passed, 1 upstream Starlette/httpx deprecation warning**. The new
  policy-deletion regression test verifies workload and application records
  remain available.
- Frontend: `npm run build` from `frontend` — passed; Vite transformed 623
  modules and generated the production application and charts bundles.
- No migration was needed. No existing database or record was modified by the
  implementation.
- No frontend test script or browser-test framework is configured. Docker
  validation remains unavailable as recorded in Phase 8.

### Remaining limitations

Workload outputs remain simulated estimates, not measured provider telemetry;
policy evaluations are on demand and are not historical snapshots; advisory
actions do not enforce workload changes. Authentication, cloud-provider
integration, and scheduler-driven evaluation remain outside the existing
project scope.

## Multi-page project completion update — 2026-10-29

### Implemented

- Replaced the long single-page interface with React Router routes for
  Overview, Workloads, Applications, Analytics & Reports, Budgets & Policies,
  and Sustainability Recommendations. The sidebar, connectivity status,
  breadcrumb, footer, and responsive CarbonGuard theme persist across pages.
- Added an Overview page with stored all-time KPI cards, a recent UTC emissions
  trend, and actual application comparisons.
- Added an Applications page supporting validated registration, editing,
  status changes, deletion where the backend permits, selected-application run
  history, and true all-time application totals from the analytics API.
- Added a standalone Analytics & Reports route retaining existing date,
  application, aggregation, and CSV-export behavior.
- Added rule-based recommendations ranked from actual all-time application
  estimates. The illustrative 10% per-comparable-run savings scenario is
  explicitly labeled as projected, not measured or realized.
- Added saved-run configuration reload and rerun controls in Workloads.
- Added the React Router runtime dependency. No backend models or migrations
  were needed.

### Files created and modified for this update

- Created `frontend/src/pages/OverviewPage.jsx`,
  `frontend/src/pages/WorkloadsPage.jsx`,
  `frontend/src/pages/ApplicationsPage.jsx`,
  `frontend/src/pages/AnalyticsPage.jsx`,
  `frontend/src/pages/PoliciesPage.jsx`, and
  `frontend/src/pages/RecommendationsPage.jsx`.
- Updated `frontend/src/App.jsx`, `frontend/src/pages/Dashboard.jsx`,
  `frontend/src/components/AnalyticsDashboard.jsx`,
  `frontend/src/components/Workloads.jsx`,
  `frontend/src/services/api.js`, `frontend/src/index.css`,
  `frontend/package.json`, and `frontend/package-lock.json`.
- Updated `README.md`, `docs/ARCHITECTURE.md`, and
  `docs/BUILD_PROGRESS.md`.

### Remaining feature limitations

- Existing policy schemas and evaluator support emissions budgets only; no
  energy-budget evaluator exists. UI/API descriptions do not claim energy
  policies.
- Applications with workload records cannot be deleted because the backend
  intentionally preserves dependent history.
- Recommendation savings are a transparent scenario assumption, not measured
  performance data. Simulations remain caller-input estimates, not provider
  telemetry.

### Validation status

- Backend: `.\.venv\Scripts\python.exe -m pytest -q` from `backend` —
  **122 passed**, with one upstream Starlette/httpx deprecation warning.
- Frontend: `npm run build` from `frontend` — **passed** with 640 modules
  transformed and separate application/charts bundles.
- Migration verification: `alembic current` reported
  `d47e1b9c2a63 (head)` and `alembic check` found no new operations.
- Browser smoke workflow on an isolated SQLite database: application create,
  update, and safe deletion of a record-free application succeeded; workload
  registration, simulation, and saved-configuration rerun produced two
  persisted 0.06 kWh / 0.024 kg CO2e runs; Analytics showed 2 runs, 0.12 kWh,
  and 0.048 kg CO2e; the daily policy evaluated to `exceeded` from the two
  persisted runs; recommendations used the same application totals and
  disclosed the 10% scenario assumption.
- CSV: the dashboard reported successful CSV creation/download. The browser
  harness did not expose a download event, so the file event itself was not
  independently asserted in this pass; the backend CSV endpoint and response
  checks remain covered by the existing analytics tests.
- No migration or writes to the existing development database were made during
  browser validation. The isolated test database and servers were removed.
- Docker and frontend unit-test validation remain unavailable: Docker is not
  installed in the environment, and the frontend has no unit-test script.
