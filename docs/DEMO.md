# CarbonGuard end-to-end demo

This walkthrough demonstrates application registration, policy configuration,
an explicit energy/emissions estimate, a recorded workload simulation, policy
evaluation, analytics, and CSV export. Run it against a development server
using a disposable or isolated SQLite database. It creates persistent
application/run records; do not run it against production data.

The dashboard can register applications and workload configurations, run
simulations, review run history, and configure/refresh policies. `POST
/api/estimates` remains available for a stateless estimate; `POST
/api/workloads/simulate` stores its estimate on the run record.

## 1. Start the application

Follow [SETUP.md](./SETUP.md) for local or Compose startup. For local
development, confirm:

- Frontend: `http://127.0.0.1:5173`
- Backend health: `http://127.0.0.1:8000/api/health`
- API docs: `http://127.0.0.1:8000/docs`

## 2. Register an application and policy in the dashboard

Open the frontend, use **Register application**, and create a daily policy.
For the sample below, configure a budget of `0.024` kg CO2e, warning threshold
`80%`, critical threshold `95%`, and action `recommend_throttle`. If a policy
already exists for the application, use it only if its settings fit this
scenario; the API enforces one policy per application.

## 3. Estimate and record a simulated workload

In PowerShell, set the API base URL and create a stateless estimate:

```powershell
$api = "http://127.0.0.1:8000"
Invoke-RestMethod -Method Post -Uri "$api/api/estimates" `
  -ContentType "application/json" `
  -Body '{"average_power_w":120,"duration_seconds":1800,"carbon_intensity_g_per_kwh":400}'
```

Expected stateless estimate: `0.06` kWh and `0.024` kg CO2e. This request
does not store anything. In the dashboard, open **Workloads**, select the
application, register `phase8-demo-workload` as `cpu-bound`, enter the same
power, duration, and carbon-intensity values, and run it. The dashboard
displays and retains the simulated result in run history.

Alternatively, create the simulated run directly through the API. Copy the
application ID from the dashboard (or list applications with
`GET /api/applications`):

```powershell
$applicationId = 1 # Replace with the ID created in the dashboard.
$policy = (Invoke-RestMethod -Uri "$api/api/budget-policies?application_id=$applicationId" |
  Select-Object -First 1)
if (-not $policy) {
  throw "Create a budget policy for this application before continuing."
}
$run = Invoke-RestMethod -Method Post -Uri "$api/api/workloads/simulate" `
  -ContentType "application/json" `
  -Body (@{
    application_id = $applicationId
    name = "phase8-demo-workload"
    workload_type = "cpu-bound"
    duration_seconds = 1800
    average_power_w = 120
    carbon_intensity_g_per_kwh = 400
    cpu_utilization_percent = 75
    seed = 42
  } | ConvertTo-Json)

$run | Select-Object run_id, application_id, energy_kwh, emissions_kg_co2e, source, estimation_source
```

Expected result: `201 Created`, approximately `0.06` kWh and `0.024` kg CO2e,
`source: simulated`, and `estimation_source: estimated`. The simulator creates
60 descriptive profile samples; it does not execute code or measure a host.

## 4. Retrieve the run and evaluate the policy

```powershell
Invoke-RestMethod -Uri "$api/api/workload-runs/$($run.run_id)"
Invoke-RestMethod -Method Post `
  -Uri "$api/api/budget-policies/$($policy.id)/evaluate"
```

Use the policy ID returned by the policy list above. With the sample
0.024 kg CO2e run and a 0.024 kg daily budget, expected evaluation fields are:
`consumed_kg_co2e: 0.024`, `remaining_kg_co2e: 0`, `utilization_percent: 100`,
`status: critical`, and `recommended_action: recommend_throttle`. Equality at
100% is critical at the 95% threshold, not exceeded. This action is only a
recommendation: CarbonGuard does not throttle the workload. Period evaluation
uses UTC and the current period; it is not a historical snapshot.

## 5. Refresh analytics and export a report

In the dashboard select a date range containing the run, choose a trend
interval, and refresh analytics. The application totals use completed stored
run estimates; current policy evaluations are calculated on request. Use
**Export CSV** to download a report. The same APIs can be called directly:

```powershell
Invoke-RestMethod -Uri "$api/api/analytics/overview"
$start = [DateTime]::UtcNow.Date.ToString("o")
$end = [DateTime]::UtcNow.Date.AddDays(1).ToString("o")
$query = "start=$([Uri]::EscapeDataString($start))&end=$([Uri]::EscapeDataString($end))&interval=daily&application_id=$applicationId"
Invoke-WebRequest -Uri "$api/api/analytics/trends?$query"
Invoke-WebRequest -Uri "$api/api/analytics/export.csv?start=$([Uri]::EscapeDataString($start))&end=$([Uri]::EscapeDataString($end))&application_id=$applicationId" `
  -OutFile ".\carbonguard-demo.csv"
```

The CSV contains report metadata and matching completed runs. Current policy
fields are explicitly snapshots at export time; historical policy evaluations
are not persisted. Application names beginning with spreadsheet-formula
characters are neutralized in exported values only.
