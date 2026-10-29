import { useEffect, useState } from "react";
import {
  ChartPanel,
  DurationEnergyScatter,
  GroupedEnergyEmissions,
  TrendLine,
} from "./AnalyticsCharts.jsx";
import {
  createWorkload,
  listApplications,
  listApplicationWorkloads,
  listWorkloadRuns,
  simulateWorkload,
} from "../services/api.js";

const initialRunForm = {
  duration_seconds: "1800",
  average_power_w: "120",
  carbon_intensity_g_per_kwh: "400",
  cpu_utilization_percent: "",
  seed: "",
};

function formatNumber(value, maximumFractionDigits = 6) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(value);
}

function formatUtcDateTime(value) {
  return `${new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value))} UTC`;
}

function Alert({ error, notice }) {
  return (
    <>
      {error && <div className="policy-alert policy-alert--error" role="alert">{error}</div>}
      {notice && <div className="policy-alert policy-alert--success" role="status">{notice}</div>}
    </>
  );
}

export default function Workloads({
  onRunCompleted,
  refreshKey: applicationRefreshKey,
}) {
  const [applications, setApplications] = useState([]);
  const [applicationId, setApplicationId] = useState("");
  const [workloads, setWorkloads] = useState([]);
  const [runs, setRuns] = useState([]);
  const [workloadName, setWorkloadName] = useState("");
  const [workloadType, setWorkloadType] = useState("cpu-bound");
  const [selectedWorkloadId, setSelectedWorkloadId] = useState("");
  const [form, setForm] = useState(initialRunForm);
  const [loading, setLoading] = useState(true);
  const [savingWorkload, setSavingWorkload] = useState(false);
  const [running, setRunning] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [latestRun, setLatestRun] = useState(null);
  const completedRuns = runs.filter((run) => run.status === "completed");
  const recentRunSeries = completedRuns
    .slice(0, 12)
    .reverse()
    .map((run, index) => ({
      ...run,
      chart_label: `${index + 1} · ${run.name}`,
    }));
  const profileTotals = new Map();
  for (const run of completedRuns) {
    const profile = profileTotals.get(run.workload_type) || {
      label: run.workload_type,
      count: 0,
      energy: 0,
      emissions: 0,
    };
    profile.count += 1;
    profile.energy += run.energy_kwh;
    profile.emissions += run.emissions_kg_co2e;
    profileTotals.set(run.workload_type, profile);
  }
  const profileComparison = [...profileTotals.values()]
    .filter((profile) => profile.count > 0)
    .map((profile) => ({
      label: profile.label,
      energy: profile.energy / profile.count,
      emissions: profile.emissions / profile.count,
    }));

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    async function loadApplications() {
      setLoading(true);
      setError("");
      try {
        const data = await listApplications({ signal: controller.signal });
        if (active) {
          setApplications(data);
          setApplicationId((current) =>
            data.some((application) => String(application.id) === current)
              ? current
              : data.length
                ? String(data[0].id)
                : "",
          );
        }
      } catch (loadError) {
        if (active && loadError.name !== "AbortError") setError(loadError.message);
      } finally {
        if (active) setLoading(false);
      }
    }

    loadApplications();
    return () => {
      active = false;
      controller.abort();
    };
  }, [applicationRefreshKey]);

  useEffect(() => {
    if (!applicationId) {
      setWorkloads([]);
      setRuns([]);
      setSelectedWorkloadId("");
      return undefined;
    }

    const controller = new AbortController();
    let active = true;

    async function loadApplicationData() {
      setLoading(true);
      setError("");
      try {
        const [workloadData, runData] = await Promise.all([
          listApplicationWorkloads(applicationId, { signal: controller.signal }),
          listWorkloadRuns(applicationId, { signal: controller.signal }),
        ]);
        if (active) {
          setWorkloads(workloadData);
          setRuns(runData);
          setSelectedWorkloadId((current) =>
            workloadData.some((workload) => String(workload.id) === current)
              ? current
              : workloadData.length
                ? String(workloadData[0].id)
                : "",
          );
        }
      } catch (loadError) {
        if (active && loadError.name !== "AbortError") setError(loadError.message);
      } finally {
        if (active) setLoading(false);
      }
    }

    loadApplicationData();
    return () => {
      active = false;
      controller.abort();
    };
  }, [applicationId, refreshKey]);

  async function handleRegisterWorkload(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!applicationId) {
      setError("Register an application before configuring a workload.");
      return;
    }
    setSavingWorkload(true);
    try {
      const created = await createWorkload(applicationId, {
        name: workloadName.trim(),
        workload_type: workloadType,
        status: "registered",
      });
      setWorkloads((current) => [...current, created]);
      setSelectedWorkloadId(String(created.id));
      setWorkloadName("");
      setNotice("Workload configuration registered.");
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSavingWorkload(false);
    }
  }

  async function handleRun(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    const workload = workloads.find(
      (item) => String(item.id) === selectedWorkloadId,
    );
    if (!workload) {
      setError("Select a registered workload before starting a simulation.");
      return;
    }

    setRunning(true);
    try {
      const result = await simulateWorkload({
        application_id: Number(applicationId),
        name: workload.name,
        workload_type: workload.workload_type,
        duration_seconds: Number(form.duration_seconds),
        average_power_w: Number(form.average_power_w),
        carbon_intensity_g_per_kwh: Number(form.carbon_intensity_g_per_kwh),
        cpu_utilization_percent:
          form.cpu_utilization_percent === ""
            ? null
            : Number(form.cpu_utilization_percent),
        seed: form.seed === "" ? null : Number(form.seed),
      });
      setLatestRun(result);
      setRuns((current) => [result, ...current.filter((run) => run.run_id !== result.run_id)].slice(0, 100));
      setNotice("Simulation completed and its estimated result was saved.");
      onRunCompleted?.();
    } catch (runError) {
      setError(runError.message);
    } finally {
      setRunning(false);
    }
  }

  function loadRunConfiguration(run) {
    const savedWorkload = workloads.find(
      (workload) => workload.id === run.workload_id,
    );
    if (!savedWorkload) {
      setError("The saved workload definition is not available for this application.");
      return;
    }
    setSelectedWorkloadId(String(savedWorkload.id));
    setForm({
      duration_seconds: String(run.parameters.duration_seconds),
      average_power_w: String(run.parameters.average_power_w),
      carbon_intensity_g_per_kwh: String(run.parameters.carbon_intensity_g_per_kwh),
      cpu_utilization_percent:
        run.parameters.cpu_utilization_percent === null
          ? ""
          : String(run.parameters.cpu_utilization_percent),
      seed: run.parameters.seed === null ? "" : String(run.parameters.seed),
    });
    setError("");
    setNotice(`Loaded saved configuration from ${run.name}. Review it, then start a new run.`);
    document.getElementById("workload-simulator")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  return (
    <section className="workloads-section" id="workloads" aria-labelledby="workloads-title">
      <div className="section-heading">
        <div>
          <h2 id="workloads-title">Workloads</h2>
          <p>Configure and run bounded workload-profile simulations. Results are estimates, not cloud telemetry.</p>
        </div>
        <span className="period-label">SIMULATED · ESTIMATED</span>
      </div>

      <Alert error={error} notice={notice} />

      {loading && applications.length === 0 ? (
        <div className="workload-panel workload-loading" role="status">Loading applications…</div>
      ) : applications.length === 0 ? (
        <div className="workload-panel workload-empty">
          <strong>No applications are registered yet.</strong>
          <span>Register an application in Budgets &amp; policies before configuring a workload.</span>
          <a className="button button--secondary" href="#policies">Go to applications</a>
        </div>
      ) : (
        <>
          <div className="workload-toolbar">
            <label className="field">
              Application
              <select
                value={applicationId}
                disabled={running}
                onChange={(event) => {
                  setApplicationId(event.target.value);
                  setLatestRun(null);
                  setNotice("");
                }}
              >
                {applications.map((application) => (
                  <option key={application.id} value={application.id}>{application.name}</option>
                ))}
              </select>
            </label>
            <button
              className="button button--secondary"
              type="button"
              onClick={() => setRefreshKey((current) => current + 1)}
              disabled={loading || running}
            >
              {loading ? "Refreshing…" : "Refresh workloads"}
            </button>
          </div>

          <div className="workload-layout">
            <article className="workload-panel" id="workload-simulator">
              <div className="policy-panel__heading">
                <div>
                  <h3>Configure workload</h3>
                  <p>Register a supported workload profile for the selected application.</p>
                </div>
              </div>
              <form className="policy-form" onSubmit={handleRegisterWorkload}>
                <label className="field">
                  Workload name
                  <input
                    value={workloadName}
                    onChange={(event) => setWorkloadName(event.target.value)}
                    minLength={1}
                    maxLength={120}
                    required
                  />
                </label>
                <label className="field">
                  Workload profile
                  <select value={workloadType} onChange={(event) => setWorkloadType(event.target.value)}>
                    <option value="cpu-bound">CPU-bound</option>
                    <option value="memory-bound">Memory-bound</option>
                    <option value="mixed">Mixed</option>
                  </select>
                </label>
                <button className="button button--secondary" disabled={savingWorkload}>
                  {savingWorkload ? "Registering…" : "Register workload"}
                </button>
              </form>
              <p className="workload-note">Registration saves a workload definition; it does not start a run.</p>
            </article>

            <article className="workload-panel">
              <div className="policy-panel__heading">
                <div>
                  <h3>Run simulation</h3>
                  <p>Enter explicit estimate inputs; the simulator does not execute host or cloud workloads.</p>
                </div>
              </div>
              {workloads.length === 0 ? (
                <div className="policy-empty-inline">Register a workload configuration to enable simulation.</div>
              ) : (
                <form className="policy-form" onSubmit={handleRun}>
                  <label className="field">
                    Registered workload
                    <select
                      value={selectedWorkloadId}
                      disabled={running}
                      onChange={(event) => setSelectedWorkloadId(event.target.value)}
                    >
                      {workloads.map((workload) => (
                        <option key={workload.id} value={workload.id}>
                          {workload.name} · {workload.workload_type}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="workload-form-grid">
                    <label className="field">
                      Duration (seconds)
                      <input
                        type="number"
                        min="0.000001"
                        max="86400"
                        step="any"
                        value={form.duration_seconds}
                        onChange={(event) => setForm({ ...form, duration_seconds: event.target.value })}
                        required
                      />
                    </label>
                    <label className="field">
                      Average power (W)
                      <input
                        type="number"
                        min="0"
                        max="1000000000"
                        step="any"
                        value={form.average_power_w}
                        onChange={(event) => setForm({ ...form, average_power_w: event.target.value })}
                        required
                      />
                    </label>
                    <label className="field">
                      Carbon intensity (g CO₂e/kWh)
                      <input
                        type="number"
                        min="0"
                        max="100000"
                        step="any"
                        value={form.carbon_intensity_g_per_kwh}
                        onChange={(event) => setForm({ ...form, carbon_intensity_g_per_kwh: event.target.value })}
                        required
                      />
                    </label>
                    <label className="field">
                      CPU utilization (%), optional
                      <input
                        type="number"
                        min="0"
                        max="100"
                        step="any"
                        value={form.cpu_utilization_percent}
                        onChange={(event) => setForm({ ...form, cpu_utilization_percent: event.target.value })}
                      />
                    </label>
                    <label className="field">
                      Random seed, optional
                      <input
                        type="number"
                        min="0"
                        max="4294967295"
                        step="1"
                        value={form.seed}
                        onChange={(event) => setForm({ ...form, seed: event.target.value })}
                      />
                    </label>
                  </div>
                  <button className="button button--primary" disabled={running}>
                    {running ? "Simulation running…" : "Run workload simulation"}
                  </button>
                </form>
              )}
            </article>
          </div>

          {latestRun && (
            <article className="workload-result" aria-live="polite">
              <div className="section-heading section-heading--compact">
                <div>
                  <h3>Latest simulation result</h3>
                  <p>{latestRun.name} · {formatUtcDateTime(latestRun.completed_at)}</p>
                </div>
                <span className="status-badge">{latestRun.status}</span>
              </div>
              <div className="workload-result__metrics">
                <div><span>Estimated energy</span><strong>{formatNumber(latestRun.energy_kwh)} kWh</strong></div>
                <div><span>Estimated emissions</span><strong>{formatNumber(latestRun.emissions_kg_co2e)} kg CO₂e</strong></div>
                <div><span>Runtime</span><strong>{formatNumber(latestRun.duration_seconds, 2)} seconds</strong></div>
                <div><span>Average power</span><strong>{formatNumber(latestRun.average_power_w, 2)} W</strong></div>
              </div>
              <details className="workload-details">
                <summary>Configuration and profile details</summary>
                <dl>
                  <dt>Application ID</dt><dd>{latestRun.application_id}</dd>
                  <dt>Workload type</dt><dd>{latestRun.workload_type}</dd>
                  <dt>Carbon intensity</dt><dd>{formatNumber(latestRun.carbon_intensity_g_per_kwh, 2)} g CO₂e/kWh</dd>
                  <dt>Method</dt><dd>{latestRun.estimation_method} · {latestRun.estimation_source}</dd>
                  <dt>Profile samples</dt><dd>{latestRun.profile.sample_count}</dd>
                  <dt>Parameters</dt><dd><code>{JSON.stringify(latestRun.parameters)}</code></dd>
                </dl>
              </details>
            </article>
          )}

          <section className="workload-analytics" aria-labelledby="workload-analytics-title">
            <div className="section-heading">
              <div>
                <h2 id="workload-analytics-title">Recent run analytics</h2>
                <p>Recent recorded completed runs for the selected application. Values are estimates.</p>
              </div>
              <span className="period-label">LATEST {Math.min(completedRuns.length, 100)} RUNS</span>
            </div>
            <div className="analytics-chart-grid">
              <ChartPanel
                title="Energy across recent runs"
                subtitle="Estimated energy · kWh"
                data={recentRunSeries}
                emptyMessage="No completed runs are available to chart for this application."
              >
                <TrendLine
                  data={recentRunSeries}
                  dataKey="energy_kwh"
                  name="Estimated energy"
                  unit="kWh"
                  xKey="chart_label"
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.name || ""}
                />
              </ChartPanel>
              <ChartPanel
                title="Emissions across recent runs"
                subtitle="Estimated emissions · kg CO₂e"
                data={recentRunSeries}
                emptyMessage="No completed runs are available to chart for this application."
              >
                <TrendLine
                  data={recentRunSeries}
                  dataKey="emissions_kg_co2e"
                  name="Estimated emissions"
                  unit="kg CO₂e"
                  color="#6e9a50"
                  xKey="chart_label"
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.name || ""}
                />
              </ChartPanel>
              <ChartPanel
                title="Energy vs workload duration"
                subtitle="Each point is a completed recent run"
                data={completedRuns}
                emptyMessage="No completed runs are available to chart for this application."
              >
                <DurationEnergyScatter data={completedRuns.slice(0, 100)} />
              </ChartPanel>
              <ChartPanel
                title="Workload profile comparison"
                subtitle="Average recorded values per completed run · separate unit axes"
                data={profileComparison.length > 1 ? profileComparison : []}
                emptyMessage="Run at least two recorded workload profile types to compare their averages."
              >
                <GroupedEnergyEmissions
                  data={profileComparison}
                  labelKey="label"
                />
              </ChartPanel>
            </div>
          </section>

          <div className="workload-history">
            <div className="section-heading section-heading--compact">
              <div>
                <h3>Recent workload runs</h3>
                <p>Persisted simulated estimates for the selected application (up to 100).</p>
              </div>
            </div>
            {loading ? (
              <div className="workload-empty" role="status">Loading workload history…</div>
            ) : runs.length === 0 ? (
              <div className="workload-empty">No runs yet. Configure a workload and run a simulation to create the first estimate.</div>
            ) : (
              <div className="analytics-table-wrap">
                <table className="analytics-table workload-table">
                  <thead>
                    <tr>
                      <th scope="col">Workload</th>
                      <th scope="col">Completed (UTC)</th>
                      <th scope="col">Status</th>
                      <th scope="col">Energy (kWh)</th>
                      <th scope="col">Emissions (kg CO₂e)</th>
                      <th scope="col">Runtime (s)</th>
                      <th scope="col">Configuration</th>
                      <th scope="col">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr key={run.run_id}>
                        <th scope="row">{run.name}<small>{run.workload_type} · {run.estimation_source}</small></th>
                        <td>{formatUtcDateTime(run.completed_at)}</td>
                        <td><span className={`status-badge ${run.status === "failed" ? "status-badge--exceeded" : ""}`}>{run.status}</span></td>
                        <td>{formatNumber(run.energy_kwh)}</td>
                        <td>{formatNumber(run.emissions_kg_co2e)}</td>
                        <td>{formatNumber(run.duration_seconds, 2)}</td>
                        <td>
                          <details className="workload-run-details">
                            <summary>View details</summary>
                            <dl>
                              <dt>Average power</dt>
                              <dd>{formatNumber(run.average_power_w, 2)} W</dd>
                              <dt>Carbon intensity</dt>
                              <dd>{formatNumber(run.carbon_intensity_g_per_kwh, 2)} g CO₂e/kWh</dd>
                              <dt>CPU utilization</dt>
                              <dd>
                                {run.parameters.cpu_utilization_percent === null
                                  ? "Not provided"
                                  : `${formatNumber(run.parameters.cpu_utilization_percent, 2)}%`}
                              </dd>
                              <dt>Profile samples</dt>
                              <dd>{run.profile.sample_count}</dd>
                              <dt>Estimation method</dt>
                              <dd>{run.estimation_method}</dd>
                            </dl>
                          </details>
                        </td>
                        <td>
                          <button
                            className="button button--secondary"
                            type="button"
                            onClick={() => loadRunConfiguration(run)}
                            disabled={running}
                          >
                            Rerun
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
