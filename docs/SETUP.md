# Local Setup

## Prerequisites

- Python 3.10 or newer (developed and validated with Python 3.12).
- Node.js 20.19+ or 22.12+ for Vite 6 and Tailwind CSS 4, with npm.
- Windows PowerShell or another terminal.

## Backend

Open a terminal at the project root:

```powershell
cd .\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The default SQLite database is created at `backend/data/carbonguard.db` when
the migration is applied. Configure a different database URL by setting
`DATABASE_URL`, or copy `backend/.env.example` to `backend/.env`. The example
uses a path relative to the backend working directory. Keep local `.env` files
out of source control. Never remove or replace an existing database to address
a migration error; inspect the migration state and data first.

Development CORS defaults to the two local Vite origins. For another frontend
origin, set `CARBONGUARD_CORS_ORIGINS` to a comma-separated list of explicit
HTTP(S) origins (without paths). Set `CARBONGUARD_ENVIRONMENT=production` in
production; the backend then requires explicit CORS origins at startup. Do not
use `*` origins. CORS credentials are disabled. CarbonGuard has no
authentication/authorization layer yet and should not be exposed to untrusted
networks without an external access-control boundary.

The API listens at `http://127.0.0.1:8000`; interactive documentation is at
`http://127.0.0.1:8000/docs`.
`POST /api/estimates` requires average power, duration, and carbon intensity in
each request; no regional intensity is configured or fetched automatically.
The simulator is available at `POST /api/workloads/simulate`. Apply the
additive Alembic migration with `alembic upgrade head` before using it. The
simulator only generates 60 bounded profile samples and does not execute host
workloads. Phase 5 adds budget policy configuration and evaluation under
`/api/budget-policies`; evaluation is based on completed workload-run estimates
and returns recommendations only. No cloud resources or local processes are
throttled or stopped. Phase 6 adds read-only analytics and a CSV report
endpoint. Analytics aggregate stored run estimates; policy snapshots are
computed on request and are not historical evaluation records.

## Frontend

Open a second terminal at the project root:

```powershell
cd .\frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://127.0.0.1:5173`).
The development server uses the default backend URL
`http://127.0.0.1:8000`. To override it, copy `.env.example` to `.env.local`
and set `VITE_API_BASE_URL`; restart Vite after changing environment variables.
Do not put secrets in Vite variables because they are exposed to the browser.

To create the production bundle, run `npm run build` from `frontend`.
Tailwind CSS 4 is integrated through its Vite plugin.
The dashboard's **Budgets & policies** section can register an application
when none exist, create one policy per application, enable/disable policies,
and refresh an evaluation. The API and frontend must use matching CORS/API
origins; the default Vite origin `http://127.0.0.1:5173` is enabled.
The analytics section provides all-time summary cards, UTC emissions trends
for ranges up to 366 days, application comparisons, current policy snapshots,
and CSV downloads. The frontend package does not currently define a standalone
test runner; validate it with the production build and browser workflow.
Dashboard requests have a 15-second timeout, validate analytics response
shapes, and cancel superseded refreshes so older results cannot replace newer
filters.

## Docker Compose deployment

Docker Engine/Desktop and the Docker Compose v2 plugin are required. From the
repository root in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

Open the dashboard at `http://localhost:8080` and the backend API docs at
`http://127.0.0.1:8000/docs`. Backend health is also available at
`http://127.0.0.1:8000/api/health`. Host ports bind to loopback. To change
them, edit the local ignored `.env` file (`CARBONGUARD_FRONTEND_PORT` and
`CARBONGUARD_BACKEND_PORT`); keep
`CARBONGUARD_CORS_ORIGINS` aligned with the frontend browser origin.

Compose runs the backend with `CARBONGUARD_ENVIRONMENT=production`, explicit
CORS origins, and `DATABASE_URL=sqlite:////data/carbonguard.db`. It applies
`alembic upgrade head` before starting Uvicorn, waits for the backend health
check before starting Nginx, and stores SQLite data in the named
`carbonguard-data` volume. Nginx serves the production Vite bundle and proxies
relative `/api/` requests over the Compose network, so no container `localhost`
assumption is used. No external database service is required.

Stop the services without deleting persistent data:

```powershell
docker compose down
```

Do not use `docker compose down -v` unless intentionally deleting the database.
Compose uses the same Alembic migration chain as local development. Existing
local `backend/data/carbonguard.db` is not mounted or copied into the image.
The backend image runs as a non-root user. Neither container includes `.env`
files, the local database, `.venv`, or `node_modules`.

For an API request walkthrough from a clean database, see
[DEMO.md](./DEMO.md). Docker build/runtime validation depends on Docker being
installed; check the Phase 8 release record in [BUILD_PROGRESS.md](./BUILD_PROGRESS.md)
for the actual validation status.

Request bodies are limited to 1 MiB. Estimate inputs are limited to 1,000,000,000
W, 31,536,000 seconds, and 100,000 g CO2e/kWh; simulations retain their
one-day maximum duration. Policy and carbon-budget values have broad finite
upper bounds documented in `API.md`. Collection APIs use pagination with a
maximum page size of 100; CSV export is limited to 10,000 matching runs.

## Tests and common PowerShell notes

Run backend tests from `backend` using the interpreter in `.venv` as shown
above. The frontend build can be checked with `npm run build`.

Alembic commands must also be run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Tests create an isolated SQLite database under pytest's temporary directory;
they do not use or clear the local development database.

- Windows virtual-environment activation may be blocked by execution policy.
  The commands above call `.venv\Scripts\python.exe` directly, avoiding the
  need to activate it.
- Run `cd .\backend` and `cd .\frontend` in their respective terminals; paths
  are relative to the repository root.
- If port 8000 or 5173 is already occupied, stop the other service or update
  the corresponding server command and frontend API URL. Update the backend
  CORS origins only if the frontend's origin changes.
- In the current workspace, port 8000 is occupied by another service. To run
  CarbonGuard without stopping it, start Uvicorn with
  `--port 8001`, then create `frontend/.env.local` containing
  `VITE_API_BASE_URL=http://127.0.0.1:8001` before starting Vite.
- If the dashboard says the API is unavailable, ensure the backend is running
  and `VITE_API_BASE_URL` matches it.
- If Docker commands are not recognized, install or start Docker Desktop (or
  Docker Engine and Compose v2). Local Python/Vite setup does not require Docker.
- If a Compose host port is occupied, choose unused values in the ignored root
  `.env` file. For the local development servers, update the Uvicorn/Vite ports
  and keep the browser API URL and CORS origin consistent.
