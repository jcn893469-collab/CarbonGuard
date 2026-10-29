# CarbonGuard API

Local base URL: `http://127.0.0.1:8000`

## `GET /`

Basic project status response.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
```

```json
{
  "message": "CarbonGuard API is running.",
  "status": "service_ready"
}
```

## `GET /api/health`

Confirms the API process responds and identifies the application version.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

```json
{
  "status": "healthy",
  "application": "CarbonGuard API",
  "version": "0.1.0"
}
```

The frontend uses this endpoint to display backend connectivity. It does not
report carbon measurements or the availability of future services.

## `GET /api/status`

Reports the current implementation phase.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/status
```

```json
{
  "project": "CarbonGuard",
  "phase": "Phase 8",
  "status": "release_validation_complete",
  "next_phase": "none"
}
```

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.
In the Compose deployment, the backend docs are available through the mapped
backend port at `http://127.0.0.1:8000/docs`.

## API protections and configuration

The API limits request bodies to 1 MiB and applies `X-Content-Type-Options`,
`Referrer-Policy`, and `X-Frame-Options` response headers. API responses,
including CSV reports, use `Cache-Control: no-store`. A restrictive Content
Security Policy is not set on the API because the interactive OpenAPI page uses
inline resources.

CORS is restricted to the local Vite origins by default in development. Set
`CARBONGUARD_CORS_ORIGINS` to a comma-separated list of explicit HTTP(S)
origins for other environments. `CARBONGUARD_ENVIRONMENT=production` requires
that setting at startup; wildcard origins and origins containing paths are
rejected. Credentialed CORS is disabled. CarbonGuard does not currently
implement authentication or authorization; configure access controls at a
trusted network boundary before exposing it to untrusted users.

All JSON request bodies are limited to 1 MiB. Create/update schemas reject
unknown fields rather than silently ignoring attempted internal-field writes.
Pagination is bounded to 100 rows per request. Estimates accept power up to
1,000,000,000 W, duration up to 31,536,000 seconds, and carbon intensity up to
100,000 g CO2e/kWh. Simulation duration remains capped at 86,400 seconds.
Carbon-budget values are capped at 1,000,000,000,000 kg CO2e, and budget-policy
thresholds are capped at 1,000,000 percent; critical thresholds above 100%
remain supported. These broad bounds protect numeric calculations and are not
recommended operational settings. Integer database IDs are limited to the
positive signed 32-bit range. Imported experiment-result JSON rejects
non-finite floating-point values.

## Application management

Collection endpoints accept `skip` (default `0`) and `limit` (default `50`,
maximum `100`) where listed.

| Method and path | Purpose |
|---|---|
| `POST /api/applications` | Create an application (`201`) |
| `GET /api/applications` | List applications |
| `GET /api/applications/{application_id}` | Retrieve an application |
| `PUT /api/applications/{application_id}` | Replace application fields |
| `DELETE /api/applications/{application_id}` | Delete only if it has no dependent records (`204`, otherwise `409`) |
| `POST /api/applications/{application_id}/budgets` | Create a carbon budget (`201`) |
| `GET /api/applications/{application_id}/budgets` | List budgets |
| `GET /api/budgets/{budget_id}` | Retrieve a budget |
| `PUT /api/budgets/{budget_id}` | Replace budget fields |
| `DELETE /api/budgets/{budget_id}` | Delete a budget (`204`) |
| `POST /api/applications/{application_id}/workloads` | Register a workload (`201`) |
| `GET /api/applications/{application_id}/workloads` | List workloads |
| `GET /api/workloads/{workload_id}` | Retrieve a workload |
| `GET /api/applications/{application_id}/monitoring-records` | List submitted records |
| `POST /api/applications/{application_id}/monitoring-records` | Store a submitted record (`201`) |
| `GET /api/monitoring-records/{record_id}` | Retrieve a submitted record |
| `GET /api/applications/{application_id}/policy-events` | List stored policy events |
| `GET /api/policy-events/{event_id}` | Retrieve a stored policy event |
| `GET /api/experiments` | List stored experiment results |
| `POST /api/experiments` | Store a manual/imported result (`201`) |
| `GET /api/experiments/{experiment_id}` | Retrieve a stored result |
| `POST /api/budget-policies` | Create one budget policy for an application (`201`) |
| `GET /api/budget-policies?skip=0&limit=50` | List a bounded page of policies; optionally filter by `application_id` |
| `GET /api/budget-policies/{policy_id}` | Retrieve a policy |
| `PATCH /api/budget-policies/{policy_id}` | Update policy settings, including `enabled` |
| `DELETE /api/budget-policies/{policy_id}` | Delete a policy (`204`) without deleting application or workload history |
| `POST /api/budget-policies/{policy_id}/evaluate` | Evaluate one policy, including a disabled policy |
| `POST /api/budget-policies/evaluate?skip=0&limit=50` | Evaluate a bounded page of enabled policies |
| `GET /api/applications/{application_id}/budget-status` | Get the current enabled-policy evaluation |

Example application and budget requests:

```powershell
$application = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/applications `
  -ContentType 'application/json' `
  -Body '{"name":"checkout","owner":"platform","description":"Checkout service"}'

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/applications/$($application.id)/budgets" `
  -ContentType 'application/json' `
  -Body '{"budget_kg_co2e":25.0,"warning_threshold_percent":80,"period":"monthly"}'
```

The create response contains the application ID, fields, and UTC timestamps.
Application names are case-insensitively unique. An application with any
dependent budget or historical record cannot be deleted; the API returns
`409 Conflict`. Missing resources return `404`; invalid request fields return
`422`.

Monitoring records are stored exactly as submitted after validation. They do
not trigger energy/emissions calculations. Workload definitions can be
registered independently; the workload simulator below runs the bounded
profile simulation and persists an estimated result. The Phase 2 policy-event
endpoints are audit-record APIs; policy evaluations are returned by the Phase
5 budget-policy endpoints below.
Experiment records accept `manual` or `imported` methods only; no experiments
are run.

Example monitoring record request:

```json
{
  "energy_kwh": 1.5,
  "emissions_kg_co2e": 0.7,
  "source_type": "measured"
}
```

## Migrations

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Phase 7 adds revision `d47e1b9c2a63` on top of
`c9f21e6a7b34`. It adds only two workload-run indexes and does not rewrite or
delete existing records.

For future model changes, generate and review a migration, then apply it:

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe change"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## Automated tests

From `backend` with the project's environment installed:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests exercise health and CRUD APIs via FastAPI `TestClient` against an isolated
temporary SQLite database.

## `POST /api/estimates`

Calculate estimated energy and emissions from caller-supplied average power,
duration, and carbon intensity. No carbon intensity is fetched or inferred.
This endpoint does not store the estimate or modify a workload.

Request:

```json
{
  "average_power_w": 120,
  "duration_seconds": 1800,
  "carbon_intensity_g_per_kwh": 400
}
```

Example PowerShell:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/estimates `
  -ContentType 'application/json' `
  -Body '{"average_power_w":120,"duration_seconds":1800,"carbon_intensity_g_per_kwh":400}'
```

Response (values from the implemented calculation):

```json
{
  "energy_kwh": 0.06,
  "emissions_kg_co2e": 0.024,
  "average_power_w": 120.0,
  "duration_seconds": 1800.0,
  "carbon_intensity_g_per_kwh": 400.0,
  "estimation_method": "power_duration",
  "source": "estimated",
  "assumptions": [
    "Average power is supplied by the caller and treated as constant for the duration.",
    "Carbon intensity is supplied explicitly by the caller; it is not fetched or verified against a regional grid.",
    "The output is an estimate, not measured telemetry."
  ],
  "units": {
    "average_power_w": "W",
    "duration_seconds": "s",
    "carbon_intensity_g_per_kwh": "g CO2e/kWh",
    "energy_kwh": "kWh",
    "emissions_kg_co2e": "kg CO2e"
  }
}
```

The transparent model uses:

```text
energy_kwh = average_power_w * duration_seconds / 3,600,000
emissions_kg_co2e = energy_kwh * carbon_intensity_g_per_kwh / 1000
```

Power and duration are treated as constant/representative inputs for the whole
interval. Carbon intensity must be supplied for each request, is nonnegative
and expressed in `g CO2e/kWh`; there is no default, external lookup, or claim
that it represents a particular electricity grid. Finite values are required;
duration must be positive, while zero power and zero intensity are allowed.
Power is limited to 1,000,000,000 W, duration to 31,536,000 seconds (365
days), and carbon intensity to 100,000 g CO2e/kWh. Simulation duration retains
its stricter existing one-day limit. These limits reject extreme numeric
inputs before calculation; supported limits are returned by validation errors.
Intermediate calculations are not rounded; returned results are rounded to 12
decimal places. Invalid values return `422`.

This route accepts power rather than deriving it from CPU utilization. It
therefore avoids treating utilization alone as a physical power measurement.

## Workload simulation

`POST /api/workloads/simulate` accepts an existing `application_id`, workload
`name`, `workload_type` (`cpu-bound`, `memory-bound`, or `mixed`), simulated
duration, average power, carbon intensity, optional descriptive CPU
utilization, and optional nonnegative 32-bit seed. Duration must be positive
and no more than 86,400 seconds. Power and carbon intensity must be finite,
nonnegative, and within the documented estimate limits. CPU
utilization does not derive or change power.

Each simulation generates 60 relative power samples, in-memory only; it never
executes workload code or waits for the simulated duration. Workload-type
variation factors are sampled uniformly and normalized around the provided
average-power input:

- `cpu-bound`: factors in `[0.65, 1.35]`
- `memory-bound`: factors in `[0.9, 1.1]`
- `mixed`: factors in `[0.5, 1.5]`

If a seed is supplied, the same type and seed produce the same relative
profile. Without a seed, the profile is not reproducible. Run IDs and
timestamps are not reproducible. Energy and emissions are calculated by the
existing `POST /api/estimates` service using the provided mean power and
duration, so a constant 120 W for 1,800 seconds at 400 g CO2e/kWh gives 0.06
kWh and 0.024 kg CO2e. The returned profile describes variability; it does
not alter the supplied average-power estimate.

The existing registered workload definition is reused when the same
application and name are supplied with the same type. A name/type conflict
returns `409`. Simulation parameters and output are persisted in the new
`workload_runs` table; no earlier application, budget, or workload records are
deleted.

Example request:

```json
{
  "application_id": 1,
  "name": "demo-cpu-workload",
  "workload_type": "cpu-bound",
  "duration_seconds": 1800,
  "average_power_w": 120,
  "carbon_intensity_g_per_kwh": 400,
  "cpu_utilization_percent": 75,
  "seed": 42
}
```

`POST /api/workloads/simulate` returns `201` and a unique `run_id`, associated
application/workload IDs, the request parameters, a reproducible profile,
simulation start/completion timestamps, energy/emissions, estimation method,
`source: "simulated"` and `estimation_source: "estimated"`.

Run history:

- `GET /api/workload-runs?skip=0&limit=50` — list recent runs.
- `GET /api/workload-runs/{run_id}` — retrieve a run and its result (`404` if
  absent).
- `GET /api/applications/{application_id}/workload-runs?skip=0&limit=50` —
  list runs for an application (`404` if the application does not exist).

Collection limits are 1–100. Application deletion remains restricted when
workload definitions or runs exist. Simulation results are estimates, not
measured infrastructure telemetry; real policy enforcement and real workload
execution are not implemented.

## Carbon-budget policies

`POST /api/budget-policies` creates one policy per application. A second policy
for the same application returns `409`; legacy Phase 2 `CarbonBudget` records
remain separate and unchanged. `application_id` must reference a registered
application and fit the positive signed 32-bit ID range. Budget values must be
positive and finite, up to 1,000,000,000,000 kg CO2e. Periods are `daily`,
`weekly`, or `monthly`; actions are `monitor`, `warn`, or
`recommend_throttle`. Defaults are an 80% warning threshold, a 95% critical
threshold, enabled, and `warn`. Thresholds must be positive, at most
1,000,000%, and warning must be lower than critical. Critical thresholds above
100% are allowed. The dashboard supports editing and deleting a policy; its
delete action asks for confirmation and preserves application and run history.
The API returns `204` for successful deletion and `404` for an unknown policy.

Example:

```powershell
$policy = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/budget-policies `
  -ContentType 'application/json' `
  -Body '{"application_id":1,"budget_kg_co2e":1.0,"period":"monthly","warning_threshold_percent":80,"critical_threshold_percent":95,"action":"recommend_throttle"}'

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/budget-policies/$($policy.id)/evaluate"
```

Example evaluation response (one stored 0.024 kg CO2e run against a
0.024 kg daily budget):

```json
{
  "policy_id": 1,
  "application_id": 1,
  "enabled": true,
  "period": "daily",
  "period_start": "2026-10-20T00:00:00Z",
  "period_end": "2026-10-21T00:00:00Z",
  "time_basis": "UTC",
  "run_timestamp_field": "completed_at",
  "budget_kg_co2e": 0.024,
  "consumed_kg_co2e": 0.024,
  "remaining_kg_co2e": 0.0,
  "utilization_percent": 100.0,
  "status": "critical",
  "contributing_run_count": 1,
  "contributing_runs": [
    {
      "run_id": "d5080e6b-8055-4a7e-982d-ae3de07940c7",
      "completed_at": "2026-10-20T03:58:12.942803Z",
      "emissions_kg_co2e": 0.024,
      "source": "simulated",
      "estimation_method": "power_duration"
    }
  ],
  "configured_action": "recommend_throttle",
  "recommended_action": "recommend_throttle",
  "enforcement_mode": "recommendation_only",
  "consumption_source": "recorded_workload_run_estimates"
}
```

Evaluation uses only recorded completed `workload_runs`, their stored
`emissions_kg_co2e`, and `completed_at`. It does not recalculate estimates.
All period boundaries are UTC calendar periods represented as half-open
intervals `[period_start, period_end)`: daily periods are UTC days, weekly
periods start Monday at 00:00 UTC, and monthly periods run from the first day
of a UTC month to the first day of the next month. A single UTC reference time
is used for each evaluation request. Returned consumption and remaining budget
are rounded to 12 decimal places; utilization is rounded to 6 decimal places.

Status precedence is: consumption above 100% of the budget is `exceeded`
first, even when the configured critical threshold exceeds 100%; otherwise a
value at or above critical is `critical`, a value at or above warning is
`warning`, and lower consumption is `within_budget`. Exactly 100% is not
`exceeded`.

Actions are recommendations only: `monitor` never recommends intervention;
`warn` recommends a warning at warning status or higher; and
`recommend_throttle` reports a warning at warning status and recommends
throttling at critical or exceeded status. No workload is actually throttled,
paused, cancelled, or blocked. Evaluation responses identify
`enforcement_mode: "recommendation_only"`, include the UTC boundaries, policy
status, budget/consumption/utilization, and the IDs and stored emissions of
contributing runs. Applications with no completed runs report zero
consumption and utilization. Disabled policies are omitted from evaluate-all
and the application current-status endpoint, but can be evaluated directly.
An application without an enabled policy has no current budget status and
returns `404`.

## Analytics and reporting

Energy/emissions aggregates use completed `workload_runs` only. The workload
analytics endpoint also exposes failed runs for status counts and run-level
inspection. Values are already-recorded Phase 3 estimates and are not
recalculated. All-time totals are explicitly labeled `all_recorded_time`;
current policy status is evaluated at request time and is not stored as
historical policy history.

| Method and path | Purpose |
|---|---|
| `GET /api/analytics/overview` | All-time totals, current enabled-policy evaluations, and all registered applications' comparison metrics |
| `GET /api/analytics/trends` | Estimated energy/emissions buckets within a bounded UTC range |
| `GET /api/analytics/workloads` | Date/application-filtered run details, status counts, and completed-run application totals |
| `GET /api/analytics/applications?skip=0&limit=100` | Paginated all-time per-application metrics and current enabled-policy evaluations |
| `GET /api/analytics/policies?skip=0&limit=100` | Paginated current-on-request evaluations for enabled policies and configuration for disabled policies |
| `GET /api/analytics/applications/{application_id}` | Application details, all-time totals, selected-range trend, and enabled-policy evaluation |
| `GET /api/analytics/export.csv` | CSV report for a required UTC time range, optionally scoped to one application |

The overview `run_metrics_window` is `all_recorded_time`; `policy_status_window`
is `current_policy_periods`. Overview `policy_evaluations` contain one current
evaluation per enabled policy, and the per-application comparison entries
reuse those evaluations from the same request. In the separate comparison
endpoint evaluations are also computed on request. Disabled policies are
shown without an evaluation. This API does not imply continuous monitoring.

Trend query parameters:

- `start` and `end`: timezone-aware ISO 8601 timestamps. Both must be present
  together or both omitted. When omitted, the default is the preceding 30 days
  ending at the current UTC time.
- The requested range is half-open `[start, end)` and may not exceed 366 days.
- `interval`: `daily`, `weekly`, or `monthly` (default `daily`). Buckets are
  aligned to UTC calendar boundaries; weekly buckets begin Monday 00:00 UTC.
- `application_id`: optional positive registered application ID.

Empty trend buckets are included with zero totals, run count `0`, and
`is_empty: true`, so charts can distinguish explicit empty periods from
missing measurements. For example:

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:8000/api/analytics/trends?start=2026-10-01T00%3A00%3A00Z&end=2026-10-08T00%3A00%3A00Z&interval=daily"
```

Each bucket contains `period_start`, `period_end`, `estimated_energy_kwh`,
`estimated_emissions_kg_co2e`, `completed_workload_run_count`, and `is_empty`.
The trend data source is `recorded_completed_workload_runs`. No policy
utilization is plotted as historical data because the application does not
persist historical policy evaluations. The dashboard presents current policy
evaluations in a separate panel.

Workload analytics use the same optional timezone-aware `start`/`end` and
`application_id` filters and half-open UTC boundary semantics. Results include
all run statuses for status counts and run-level inspection, while per-
application energy and emissions totals include completed runs only. The
endpoint returns at most 5,000 runs; larger ranges return HTTP 422 and should
be narrowed. This endpoint supports filtered application comparisons, workload
scatter plots, and status charts without relying on the workload-history
endpoint's 100-record page limit.

CSV export:

```powershell
Invoke-WebRequest `
  "http://127.0.0.1:8000/api/analytics/export.csv?start=2026-10-01T00%3A00%3A00Z&end=2026-10-08T00%3A00%3A00Z&application_id=1" `
  -OutFile .\carbonguard-report.csv
```

The CSV contains a `report_metadata` row followed by `workload_run` rows.
Columns include the report start/end and estimate classification, the
policy-snapshot timestamp, application ID/name, run ID/completion time,
estimated kWh and kg CO2e, source and estimation method, and the current
policy ID/period/budget/status/recommended action when an enabled policy is
available. CSV values are escaped by the standard CSV writer. Application
names beginning with `=`, `+`, `-`, or `@` after leading whitespace/control
characters are prefixed with an apostrophe in the export so spreadsheet
software treats them as text; stored application names are not modified.
Application filters are applied in the query; export is limited to 10,000
matching runs and responses are marked `Cache-Control: no-store`.
The policy fields are a snapshot at report generation time, not historical
status. A metadata-only report is returned if no matching completed runs
exist. No configuration or secret data is exported.
