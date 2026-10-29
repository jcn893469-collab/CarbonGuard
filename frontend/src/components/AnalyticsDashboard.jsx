import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ChartPanel,
  ComparisonBar,
  DurationEnergyScatter,
  EnergyEmissionsScatter,
  GroupedEnergyEmissions,
  RunStatusDonut,
  ShareDonut,
  TrendLine,
} from "./AnalyticsCharts.jsx";
import {
  apiBaseUrl,
  downloadAnalyticsReport,
  getAnalyticsOverview,
  getAnalyticsTrend,
  getAnalyticsWorkloads,
} from "../services/api.js";

function utcDate(value) {
  return value.toISOString().slice(0, 10);
}

function getInitialRange(days = 30) {
  const today = new Date();
  const end = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()));
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - days + 1);
  return { start: utcDate(start), end: utcDate(end) };
}

function toQueryRange(startDate, inclusiveEndDate) {
  const start = new Date(`${startDate}T00:00:00.000Z`);
  const end = new Date(`${inclusiveEndDate}T00:00:00.000Z`);
  end.setUTCDate(end.getUTCDate() + 1);
  return { start: start.toISOString(), end: end.toISOString() };
}

function formatNumber(value, digits = 3) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

function formatDate(value, interval) {
  const date = new Date(value);
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    ...(interval === "monthly" ? { year: "numeric" } : {}),
    timeZone: "UTC",
  }).format(date);
}

function formatUtcDateTime(value) {
  return `${new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value))} UTC`;
}

function policyLabel(evaluation) {
  return evaluation ? evaluation.status.replaceAll("_", " ") : "No enabled policy";
}

function Metric({ label, value, unit, window }) {
  return (
    <article className="metric-card analytics-metric">
      <div className="metric-card__topline">
        <span className="metric-card__eyebrow">{label}</span>
        <span className="metric-card__icon" aria-hidden="true">↗</span>
      </div>
      <p className="analytics-metric__value">
        {value === null ? "—" : formatNumber(value)} <small>{unit}</small>
      </p>
      <p className="metric-card__description">{window}</p>
    </article>
  );
}

export default function AnalyticsDashboard({ refreshKey, onOverview }) {
  const [range, setRange] = useState(() => getInitialRange());
  const [interval, setInterval] = useState("daily");
  const [applicationFilter, setApplicationFilter] = useState("");
  const [overview, setOverview] = useState(null);
  const [trend, setTrend] = useState(null);
  const [workloadAnalytics, setWorkloadAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [manualRefreshKey, setManualRefreshKey] = useState(0);

  const queryRange = useMemo(
    () => toQueryRange(range.start, range.end),
    [range.start, range.end],
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    async function loadAnalytics() {
      setLoading(true);
      setError("");
      try {
        const [summary, historicalTrend, workloadData] = await Promise.all([
          getAnalyticsOverview({ signal: controller.signal }),
          getAnalyticsTrend({
            ...queryRange,
            interval,
            applicationId: applicationFilter,
            signal: controller.signal,
          }),
          getAnalyticsWorkloads({
            ...queryRange,
            applicationId: applicationFilter,
            signal: controller.signal,
          }),
        ]);
        if (active) {
          setOverview(summary);
          onOverview?.(summary);
          setTrend(historicalTrend);
          setWorkloadAnalytics(workloadData);
        }
      } catch (loadError) {
        if (active && loadError.name !== "AbortError") {
          setError(loadError.message);
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    loadAnalytics();
    return () => {
      active = false;
      controller.abort();
    };
  }, [
    queryRange.start,
    queryRange.end,
    interval,
    applicationFilter,
    refreshKey,
    manualRefreshKey,
    onOverview,
  ]);

  const applications = overview?.applications || [];
  const selectedApplication =
    applications.find((item) => String(item.application_id) === applicationFilter) ||
    null;
  const policyCounts = overview?.policy_status_counts;
  const chartData = (trend?.buckets || []).map((bucket) => ({
    ...bucket,
    label: formatDate(bucket.period_start, trend.interval),
  }));
  const appChartData = workloadAnalytics?.applications || [];
  const energyAppChartData = [...appChartData]
    .sort((left, right) => left.estimated_energy_kwh - right.estimated_energy_kwh);
  const completedRuns = (workloadAnalytics?.runs || []).filter(
    (run) => run.status === "completed",
  );
  const runChartData = [...completedRuns]
    .sort((left, right) => right.emissions_kg_co2e - left.emissions_kg_co2e)
    .slice(0, 10)
    .sort((left, right) => left.emissions_kg_co2e - right.emissions_kg_co2e)
    .map((run) => ({
      ...run,
      chart_name: `${run.name} · ${new Date(run.completed_at).toLocaleDateString()}`,
    }));
  const orderedApplications = [...applications].sort(
    (left, right) =>
      right.estimated_emissions_kg_co2e_all_time -
      left.estimated_emissions_kg_co2e_all_time,
  );

  function handleDateChange(field, value) {
    setRange((current) => ({ ...current, [field]: value }));
    setFeedback("");
  }

  async function handleExport() {
    setExporting(true);
    setError("");
    setFeedback("");
    try {
      const { blob, filename } = await downloadAnalyticsReport({
        ...queryRange,
        applicationId: applicationFilter,
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setFeedback("CSV report downloaded. Policy fields are current snapshots, not historical evaluations.");
    } catch (exportError) {
      setError(exportError.message);
    } finally {
      setExporting(false);
    }
  }

  function renderPolicyStatus(evaluation) {
    return (
      <span className={`status-badge ${evaluation ? `status-badge--${evaluation.status}` : "status-badge--empty"}`}>
        {policyLabel(evaluation)}
      </span>
    );
  }

  return (
    <section className="analytics-section" aria-labelledby="analytics-title">
      <div className="section-heading analytics-section__heading">
        <div>
          <h2 id="analytics-title">Carbon analytics</h2>
          <p>Recorded workload estimates and on-request policy evaluations.</p>
        </div>
        <div className="analytics-actions">
          <button
            type="button"
            className="button button--secondary"
            onClick={() => setManualRefreshKey((current) => current + 1)}
            disabled={loading}
          >
            {loading ? "Refreshing…" : "Refresh analytics"}
          </button>
          <button
            type="button"
            className="button button--primary"
            onClick={handleExport}
            disabled={exporting || loading}
          >
            {exporting ? "Preparing…" : "Export CSV"}
          </button>
        </div>
      </div>

      {error && <div className="policy-alert policy-alert--error" role="alert">{error}</div>}
      {feedback && <div className="policy-alert policy-alert--success" role="status">{feedback}</div>}

      <div className="analytics-toolbar">
        <label className="analytics-control">
          Start date (UTC)
          <input
            type="date"
            value={range.start}
            max={range.end}
            onChange={(event) => handleDateChange("start", event.target.value)}
          />
        </label>
        <label className="analytics-control">
          End date (UTC, inclusive)
          <input
            type="date"
            value={range.end}
            min={range.start}
            onChange={(event) => handleDateChange("end", event.target.value)}
          />
        </label>
        <label className="analytics-control">
          Aggregation
          <select value={interval} onChange={(event) => setInterval(event.target.value)}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </label>
        <label className="analytics-control analytics-control--application">
          Application trend
          <select
            value={applicationFilter}
            onChange={(event) => setApplicationFilter(event.target.value)}
          >
            <option value="">All applications</option>
            {applications.map((application) => (
              <option key={application.application_id} value={application.application_id}>
                {application.application_name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading && !overview ? (
        <div className="analytics-loading" role="status">Loading carbon analytics…</div>
      ) : (
        <>
          {overview && (
            <>
              <div className="metric-grid analytics-metrics">
                <Metric
                  label="ESTIMATED EMISSIONS"
                  value={overview.all_time_estimated_emissions_kg_co2e}
                  unit="kg CO₂e"
                  window="All recorded time · completed runs"
                />
                <Metric
                  label="ESTIMATED ENERGY"
                  value={overview.all_time_estimated_energy_kwh}
                  unit="kWh"
                  window="All recorded time · completed runs"
                />
                <Metric
                  label="WORKLOAD RUNS"
                  value={overview.all_time_completed_workload_run_count}
                  unit="runs"
                  window="All recorded time · completed runs"
                />
                <Metric
                  label="APPLICATIONS"
                  value={overview.registered_application_count}
                  unit="registered"
                  window={`${overview.enabled_policy_count} enabled policies`}
                />
              </div>

              <div className="policy-count-strip" aria-label="Current policy status counts">
                <span>Current policy status · evaluated {formatUtcDateTime(overview.evaluated_at)}</span>
                <strong className="policy-count policy-count--within">Within budget {policyCounts.within_budget}</strong>
                <strong className="policy-count policy-count--warning">Warnings {policyCounts.warning}</strong>
                <strong className="policy-count policy-count--critical">Critical {policyCounts.critical}</strong>
                <strong className="policy-count policy-count--exceeded">Exceeded {policyCounts.exceeded}</strong>
                <strong className="policy-count">Recommended interventions {overview.recommended_intervention_count}</strong>
              </div>
            </>
          )}

          <div className="analytics-grid">
            <article className="preview-card analytics-card">
              <div className="section-heading section-heading--compact">
                <div>
                  <h3>Estimated emissions trend</h3>
                  <p>
                    kg CO₂e per {interval === "daily" ? "day" : interval === "weekly" ? "week" : "month"} ·
                    {" "}{applicationFilter ? "selected application" : "all applications"} ·
                    {" "}UTC
                  </p>
                </div>
                <span className="period-label">ESTIMATED</span>
              </div>
              {error && !trend ? (
                <div className="analytics-empty">Trend data could not be loaded.</div>
              ) : chartData.some((bucket) => !bucket.is_empty) ? (
                <div className="analytics-chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 14, right: 12, bottom: 4, left: 0 }}>
                      <CartesianGrid stroke="#edf1ed" strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="label" tick={{ fill: "#849188", fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={20} />
                      <YAxis
                        tick={{ fill: "#849188", fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        width={58}
                        label={{
                          value: "kg CO₂e",
                          angle: -90,
                          position: "insideLeft",
                          style: { fill: "#849188", fontSize: 9 },
                        }}
                      />
                      <Tooltip
                        formatter={(value) => [`${formatNumber(Number(value))} kg CO₂e`, "Estimated emissions"]}
                        labelFormatter={(_, payload) =>
                          payload?.[0]?.payload
                            ? `${payload[0].payload.period_start} – ${payload[0].payload.period_end}`
                            : ""
                        }
                      />
                      <Line
                        type="monotone"
                        dataKey="estimated_emissions_kg_co2e"
                        name="Estimated emissions"
                        stroke="#39845b"
                        strokeWidth={2}
                        dot={{ r: 3, fill: "#39845b" }}
                        activeDot={{ r: 5 }}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="analytics-empty">
                  <strong>No completed run estimates in this range.</strong>
                  <span>Register an application, create a policy, and simulate a workload to populate this trend.</span>
                </div>
              )}
            </article>

            <article className="preview-card analytics-card analytics-policy-card">
              <div className="section-heading section-heading--compact">
                <div>
                  <h3>Current budget policies</h3>
                  <p>On-request evaluation · not historical snapshots</p>
                </div>
              </div>
              {overview?.policy_evaluations.length ? (
                <ul className="analytics-policy-list">
                  {overview.policy_evaluations.map((evaluation) => {
                    const application = applications.find(
                      (item) => item.application_id === evaluation.application_id,
                    );
                    return (
                      <li key={evaluation.policy_id}>
                        <div className="analytics-policy-list__heading">
                          <strong>{application?.application_name || `Application ${evaluation.application_id}`}</strong>
                          {renderPolicyStatus(evaluation)}
                        </div>
                        <span>
                          {formatNumber(evaluation.consumed_kg_co2e)} / {formatNumber(evaluation.budget_kg_co2e)} kg CO₂e · {formatNumber(evaluation.utilization_percent, 2)}%
                        </span>
                        <span className="analytics-policy-list__action">
                          Recommended: {evaluation.recommended_action.replaceAll("_", " ")}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <div className="analytics-empty analytics-empty--compact">
                  No enabled budget policies. Create one in Budgets &amp; policies to see current status.
                </div>
              )}
            </article>
          </div>

          <div className="analytics-chart-grid" aria-label="Filtered analytics charts">
            <ChartPanel
              title="Energy consumption trend"
              subtitle={`Estimated kWh per ${interval === "daily" ? "day" : interval === "weekly" ? "week" : "month"} · UTC`}
              data={chartData.filter((bucket) => !bucket.is_empty)}
              emptyMessage="No completed-run energy estimates in the selected range."
            >
              <TrendLine data={chartData} dataKey="estimated_energy_kwh" name="Estimated energy" unit="kWh" />
            </ChartPanel>
            <ChartPanel
              title="Energy by application"
              subtitle="Filtered completed-run totals · kWh"
              data={energyAppChartData.filter((item) => item.estimated_energy_kwh > 0)}
              emptyMessage="No completed-run energy totals for the selected filters."
            >
              <ComparisonBar data={energyAppChartData} dataKey="estimated_energy_kwh" labelKey="application_name" name="Energy" unit="kWh" />
            </ChartPanel>
            <ChartPanel
              title="Emissions distribution"
              subtitle="Contribution to filtered total · kg CO₂e"
              data={appChartData.filter((item) => item.estimated_emissions_kg_co2e > 0)}
              emptyMessage="Recorded emissions total is zero for the selected filters."
            >
              <ShareDonut
                data={appChartData.filter((item) => item.estimated_emissions_kg_co2e > 0)}
                dataKey="estimated_emissions_kg_co2e"
                labelKey="application_name"
                unit="kg CO₂e"
              />
            </ChartPanel>
            <ChartPanel
              title="Workload energy vs duration"
              subtitle="Each point is a completed recorded run"
              data={completedRuns}
              emptyMessage="No completed workload runs in the selected range."
            >
              <DurationEnergyScatter data={completedRuns} />
            </ChartPanel>
            <ChartPanel
              title="Emissions per workload run"
              subtitle="Highest-emission completed runs in this range · kg CO₂e"
              data={runChartData}
              emptyMessage="No completed workload runs in the selected range."
            >
              <ComparisonBar data={runChartData} dataKey="emissions_kg_co2e" labelKey="chart_name" name="Emissions" unit="kg CO₂e" highlightHighValue />
            </ChartPanel>
            <ChartPanel
              title="Application energy and emissions"
              subtitle="Separate axes: kWh (left) and kg CO₂e (right)"
              data={appChartData.filter((item) => item.completed_workload_run_count > 0)}
              emptyMessage="No completed-run totals for the selected filters."
            >
              <GroupedEnergyEmissions data={[...appChartData].sort((a, b) =>
                a.estimated_emissions_kg_co2e - b.estimated_emissions_kg_co2e).map((item) => ({
                application_name: item.application_name,
                energy: item.estimated_energy_kwh,
                emissions: item.estimated_emissions_kg_co2e,
              }))} />
            </ChartPanel>
            <ChartPanel
              title="Energy vs emissions"
              subtitle="Each point is a completed recorded run"
              data={completedRuns}
              emptyMessage="No completed runs to compare for the selected filters."
            >
              <EnergyEmissionsScatter data={completedRuns} />
            </ChartPanel>
            <ChartPanel
              title="Workload run status"
              subtitle="Recorded run counts in the selected range"
              data={Object.entries(workloadAnalytics?.status_counts || {}).filter(([, count]) => count > 0)}
              emptyMessage="No workload runs were recorded in the selected range."
            >
              <RunStatusDonut counts={workloadAnalytics?.status_counts} />
            </ChartPanel>
          </div>

          {selectedApplication && (
            <article className="preview-card application-focus">
              <div className="section-heading section-heading--compact">
                <div>
                  <h3>{selectedApplication.application_name}</h3>
                  <p>All-time run totals · trend above is filtered to the selected date range</p>
                </div>
                {renderPolicyStatus(selectedApplication.enabled_policy_evaluation)}
              </div>
              <div className="application-focus__metrics">
                <span>{formatNumber(selectedApplication.completed_workload_run_count, 0)} completed runs</span>
                <span>{formatNumber(selectedApplication.estimated_energy_kwh_all_time)} kWh estimated energy</span>
                <span>{formatNumber(selectedApplication.estimated_emissions_kg_co2e_all_time)} kg CO₂e estimated emissions</span>
                <span>
                  {selectedApplication.application_status}
                  {selectedApplication.owner ? ` · owner ${selectedApplication.owner}` : ""}
                </span>
                {selectedApplication.enabled_policy_evaluation && (
                  <span>Recommended: {selectedApplication.enabled_policy_evaluation.recommended_action.replaceAll("_", " ")}</span>
                )}
                <a
                  className="application-history-link"
                  href={`${apiBaseUrl}/api/applications/${selectedApplication.application_id}/workload-runs`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open recorded workload-run history
                </a>
              </div>
            </article>
          )}

          <article className="preview-card analytics-card application-comparison">
            <div className="section-heading section-heading--compact">
              <div>
                <h3>Application comparison</h3>
                <p>All-time totals · sorted by estimated emissions, not adjusted for workload differences</p>
              </div>
            </div>
            {orderedApplications.length ? (
              <div className="analytics-table-wrap">
                <table className="analytics-table">
                  <thead>
                    <tr>
                      <th scope="col">Application</th>
                      <th scope="col">Completed runs</th>
                      <th scope="col">Energy (kWh)</th>
                      <th scope="col">Emissions (kg CO₂e)</th>
                      <th scope="col">Current policy</th>
                      <th scope="col">Utilization</th>
                      <th scope="col">Recommendation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orderedApplications.map((application) => {
                      const evaluation = application.enabled_policy_evaluation;
                      return (
                        <tr key={application.application_id}>
                          <th scope="row">
                            <button
                              type="button"
                              className="application-select"
                              onClick={() => setApplicationFilter(String(application.application_id))}
                            >
                              {application.application_name}
                            </button>
                          </th>
                          <td>{formatNumber(application.completed_workload_run_count, 0)}</td>
                          <td>{formatNumber(application.estimated_energy_kwh_all_time)}</td>
                          <td>{formatNumber(application.estimated_emissions_kg_co2e_all_time)}</td>
                          <td>{renderPolicyStatus(evaluation)}</td>
                          <td>{evaluation ? `${formatNumber(evaluation.utilization_percent, 2)}% of ${formatNumber(evaluation.budget_kg_co2e)} kg` : "—"}</td>
                          <td>{evaluation ? evaluation.recommended_action.replaceAll("_", " ") : "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="analytics-empty analytics-empty--compact">
                No applications yet. Register an application, create a budget policy, and run a simulation to populate analytics.
              </div>
            )}
          </article>
        </>
      )}
    </section>
  );
}
