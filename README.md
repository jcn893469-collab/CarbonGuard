# CarbonGuard

CarbonGuard is a carbon-budget monitoring and recommendation platform for
cloud-computing workloads. It estimates energy and CO2e from caller-provided
inputs, records bounded workload simulations, evaluates application budgets,
and reports stored estimates through a dashboard and CSV export.

## Final status

**Phase 8 — Final integration, deployment configuration, and release
validation.** Phases 1–8 are implemented and validation results are recorded in
[docs/BUILD_PROGRESS.md](docs/BUILD_PROGRESS.md). This project is a local
development/review deliverable, not a production-certified service.

Workload runs are simulated estimates, not measured cloud telemetry. Policy
evaluation is request-driven; `recommend_throttle` is advisory and does not
throttle anything. Policy evaluations are not stored as historical snapshots.
Legacy `CarbonBudget` records are not automatically converted to `BudgetPolicy`.
There is no authentication, authorization, scheduler, cloud-provider
integration, or real enforcement.

## Features

- Register, update, and remove applications where no dependent history exists.
- Register workload configurations and run bounded simulations from the
  dashboard, with persisted history and estimate details.
- Estimate energy and CO2e from explicit average power, duration, and carbon
  intensity inputs.
- Generate and persist bounded simulated workload runs.
- Create, edit, enable/disable, evaluate, and delete one carbon-budget policy
  per application; policy actions remain advisory.
- View all-time recorded estimates, filtered UTC trends, application
  comparisons, workload-level energy/emissions/duration charts, current policy
  evaluations, and formula-neutralized CSV reports.
- Explore responsive energy and emissions trends, application comparisons,
  workload-run scatter plots, run-status summaries, and budget utilization
  visualizations across Overview, Analytics, Workloads, Applications, Budgets,
  and Recommendations.
- Generate explainable, rule-based sustainability recommendations using
  recorded application totals and a clearly labeled 10% scenario estimate.
- Run backend and frontend locally or use the Docker Compose deployment.

The React dashboard supports application and workload registration, workload
simulation and history, policy management, analytics filters, and CSV
download. Analytics reuse Recharts and display stored workload estimates only;
date and application filters are shared with the CSV report. Application
comparison totals respect those filters, while explicitly labeled all-time
metrics remain unfiltered. The workload simulator uses caller-provided
estimates and does not measure cloud infrastructure.

The responsive multi-page interface is available at `/` (Overview),
`/workloads`, `/applications`, `/analytics`, `/policies`, and
`/recommendations`. Application deletion remains blocked when dependent
budgets, policies, workloads, or history exist. Budget-policy thresholds
currently evaluate carbon-emissions budgets; the legacy CarbonBudget API also
stores emissions budgets, not energy limits.

## Architecture and stack

- **Backend:** Python, FastAPI, Uvicorn, Pydantic, SQLAlchemy, Alembic, SQLite.
- **Frontend:** React, React Router, Vite, JavaScript, Tailwind CSS 4, and
  Recharts.
- **Tests:** pytest and FastAPI TestClient, using isolated temporary SQLite
  databases.
- **Deployment:** Docker Compose, a non-root FastAPI container, persistent
  SQLite named volume, and Nginx serving the Vite build and proxying `/api/`.

```text
backend/
  app/                 API routes, schemas, models, database, and services
  migrations/          Alembic migration chain
  tests/               Backend API and behavior tests
  Dockerfile
frontend/
  src/                 React dashboard, policy UI, analytics, and API client
  Dockerfile           Multi-stage Vite build and Nginx runtime
  nginx.conf           Static hosting and same-origin backend proxy
docker-compose.yml     Backend, frontend, health checks, and named data volume
docs/                  API, architecture, setup, progress, and demo guide
```

## Prerequisites

For local development:

- Python 3.10 or newer (validated with Python 3.12).
- Node.js 20.19+ or 22.12+ with npm.

For container deployment, install Docker Desktop (Windows/macOS) or Docker
Engine and the Docker Compose v2 plugin. Docker is not required for local
development.

## Local development setup (Windows PowerShell)

From the project root, use the first terminal for the backend:

```powershell
cd .\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open a second terminal at the project root for the frontend:

```powershell
cd .\frontend
npm ci
npm run dev
```

Open the Vite URL printed in the terminal (normally
`http://127.0.0.1:5173`). The API defaults to `http://127.0.0.1:8000`.

The backend defaults to `backend/data/carbonguard.db`. To set a different
`DATABASE_URL`, copy `backend/.env.example` to `backend/.env` or set the
environment variable in the backend process. To change the frontend API URL,
copy `frontend/.env.example` to `frontend/.env.local`, set
`VITE_API_BASE_URL`, then restart Vite. Vite variables are public client-side
values; never store secrets in them. Optional backend settings and the local
defaults are described in the examples.

Run database migrations from `backend` before starting a fresh local instance.
Never reset or replace an existing database to recover from a migration error.
Inspect its current Alembic revision and preserve its data.

## Docker Compose setup

From the project root, optionally create the local Compose configuration and
start both services:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

The default UI is `http://localhost:8080`; backend health and interactive API
docs are `http://127.0.0.1:8000/api/health` and
`http://127.0.0.1:8000/docs`. The frontend uses a same-origin `/api` proxy, so
it does not depend on container `localhost` or a developer machine URL.
Compose applies migrations before starting Uvicorn and stores SQLite data in
the named `carbonguard-data` volume. `.env` only controls host ports and
explicit CORS origins; it contains no secrets. To stop services without
deleting data, run `docker compose down`. Do not use `docker compose down -v`
unless you intentionally want to remove the persistent database.

See [docs/SETUP.md](docs/SETUP.md) for details and
[docs/DEMO.md](docs/DEMO.md) for the complete sample workflow.

## Tests and build

Backend, from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
```

Frontend, from `frontend`:

```powershell
npm ci
npm run build
```

There is no dedicated frontend unit-test script in `package.json`. The
production build and browser/API smoke checks are the available frontend
validation.

## Main API endpoints

- `GET /`, `GET /api/health`, `GET /api/status`
- `POST /api/applications`, `GET /api/applications`
- `POST /api/estimates`
- `POST /api/applications/{id}/workloads`
- `POST /api/workloads/simulate`, `GET /api/workload-runs`
- `POST /api/budget-policies`, `PATCH`/`DELETE /api/budget-policies/{id}`
- `POST /api/budget-policies/{id}/evaluate`
- `GET /api/analytics/overview`, `GET /api/analytics/trends`
- `GET /api/analytics/export.csv`
- Interactive API reference: `/docs`

For request examples, response shapes, and limits, see
[docs/API.md](docs/API.md).

## Sample demo workflow

1. Start the local backend and frontend, or run Docker Compose.
2. Register an application and create a daily budget policy in the dashboard.
3. Open **Workloads**, register a workload configuration, enter estimate
   inputs, and run a simulation. The result is saved and appears in run
   history.
4. Review the refreshed dashboard analytics and export filtered CSV data.
5. Evaluate the policy to inspect the current status and advisory action.

The estimator uses `energy_kwh = power_w * duration_seconds / 3,600,000` and
`emissions_kg_co2e = energy_kwh * intensity_g_per_kwh / 1,000`. For example,
120 W for 1,800 seconds at 400 g CO2e/kWh is an estimated 0.06 kWh and
0.024 kg CO2e. These values are estimates, not measured telemetry. The full
PowerShell walkthrough is in [docs/DEMO.md](docs/DEMO.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API reference](docs/API.md)
- [Setup and troubleshooting](docs/SETUP.md)
- [End-to-end demo](docs/DEMO.md)
- [Build progress and release checklist](docs/BUILD_PROGRESS.md)
