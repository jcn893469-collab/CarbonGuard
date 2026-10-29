import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
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
  EnergyEmissionsScatter,
  RunStatusDonut,
  TrendLine,
} from "../components/AnalyticsCharts.jsx";
import {
  getAnalyticsOverview,
  getAnalyticsTrend,
  getAnalyticsWorkloads,
} from "../services/api.js";

function getRange() {
  const end = new Date();
  end.setUTCHours(0, 0, 0, 0);
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - 13);
  const nextDay = new Date(end);
  nextDay.setUTCDate(nextDay.getUTCDate() + 1);
  return { start: start.toISOString(), end: nextDay.toISOString() };
}

function number(value, digits = 3) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

function SummaryCard({ label, value, unit, hint }) {
  return (
    <article className="metric-card analytics-metric">
      <div className="metric-card__topline">
        <span className="metric-card__eyebrow">{label}</span>
        <span className="metric-card__icon" aria-hidden="true">↗</span>
      </div>
      <p className="analytics-metric__value">{value === null ? "—" : number(value)} <small>{unit}</small></p>
      <p className="metric-card__description">{hint}</p>
    </article>
  );
}

export default function OverviewPage() {
  const { refreshKey } = useOutletContext();
  const [data, setData] = useState(null);
  const [trend, setTrend] = useState(null);
  const [workloadAnalytics, setWorkloadAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const range = useMemo(getRange, []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError("");

    Promise.all([
      getAnalyticsOverview({ signal: controller.signal }),
      getAnalyticsTrend({ ...range, interval: "daily", signal: controller.signal }),
      getAnalyticsWorkloads({ ...range, signal: controller.signal }),
    ])
      .then(([overview, dailyTrend, workloadData]) => {
        if (active) {
          setData(overview);
          setTrend(dailyTrend);
          setWorkloadAnalytics(workloadData);
        }
      })
      .catch((loadError) => {
        if (active && loadError.name !== "AbortError") setError(loadError.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [range, refreshKey]);

  const topApplications = [...(data?.applications || [])]
    .sort((left, right) =>
      right.estimated_emissions_kg_co2e_all_time -
      left.estimated_emissions_kg_co2e_all_time)
    .slice(0, 5);
  const recentTrend = trend?.buckets || [];
  const completedRuns = (workloadAnalytics?.runs || []).filter(
    (run) => run.status === "completed",
  );
  const rankedEmissions = [...(data?.applications || [])]
    .filter((application) => application.completed_workload_run_count > 0)
    .sort((left, right) =>
      right.estimated_emissions_kg_co2e_all_time -
      left.estimated_emissions_kg_co2e_all_time);

  return (
    <>
      <section className="welcome">
        <div>
          <div className="section-kicker"><span /> CARBON INTELLIGENCE</div>
          <h1>Make every workload count.</h1>
          <p>
            Understand persisted workload estimates, compare application
            footprints, and find practical opportunities to use less energy.
          </p>
          <div className="overview-actions">
            <Link className="button button--primary" to="/workloads">Run a simulation</Link>
            <Link className="button button--secondary" to="/applications">Manage applications</Link>
          </div>
        </div>
        <div className="welcome__orbit" aria-hidden="true">
          <span className="orbit orbit--outer" />
          <span className="orbit orbit--inner" />
          <span className="orbit__core">C</span>
          <span className="orbit__leaf">✳</span>
        </div>
      </section>

      <section className="overview-section" aria-labelledby="overview-metrics-title">
        <div className="section-heading">
          <div>
            <h2 id="overview-metrics-title">Workspace snapshot</h2>
            <p>All-time totals from persisted completed workload simulations.</p>
          </div>
          <span className="period-label">ESTIMATED · ALL TIME</span>
        </div>
        {error && <div className="policy-alert policy-alert--error" role="alert">{error}</div>}
        {loading && !data ? (
          <div className="analytics-loading" role="status">Loading recorded workspace metrics…</div>
        ) : data ? (
          <>
            <div className="metric-grid overview-metrics">
              <SummaryCard label="ESTIMATED EMISSIONS" value={data.all_time_estimated_emissions_kg_co2e} unit="kg CO₂e" hint="Completed workload runs" />
              <SummaryCard label="ESTIMATED ENERGY" value={data.all_time_estimated_energy_kwh} unit="kWh" hint="Completed workload runs" />
              <SummaryCard label="COMPLETED RUNS" value={data.all_time_completed_workload_run_count} unit="runs" hint="All recorded time" />
              <SummaryCard label="APPLICATIONS" value={data.registered_application_count} unit="registered" hint={`${data.enabled_policy_count} enabled policies`} />
            </div>
            <div className="overview-grid">
              <article className="preview-card analytics-card">
                <div className="section-heading section-heading--compact">
                  <div>
                    <h3>Recent emissions trend</h3>
                    <p>Daily estimated kg CO₂e · last 14 UTC days</p>
                  </div>
                  <span className="period-label">ESTIMATED</span>
                </div>
                {trend?.buckets.some((bucket) => !bucket.is_empty) ? (
                  <div className="analytics-chart">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={trend.buckets} margin={{ top: 12, right: 12, bottom: 4, left: 0 }}>
                        <CartesianGrid stroke="#edf1ed" strokeDasharray="3 3" vertical={false} />
                        <XAxis
                          dataKey="period_start"
                          tickFormatter={(value) => new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", timeZone: "UTC" }).format(new Date(value))}
                          tick={{ fill: "#849188", fontSize: 9 }}
                          axisLine={false}
                          tickLine={false}
                          minTickGap={20}
                        />
                        <YAxis tick={{ fill: "#849188", fontSize: 9 }} axisLine={false} tickLine={false} width={54} />
                        <Tooltip
                          labelFormatter={(value) => new Date(value).toLocaleDateString()}
                          formatter={(value) => [`${number(Number(value))} kg CO₂e`, "Estimated emissions"]}
                        />
                        <Line dataKey="estimated_emissions_kg_co2e" stroke="#39845b" strokeWidth={2} dot={false} isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="analytics-empty">
                    <strong>No completed estimates in the recent period.</strong>
                    <Link to="/workloads">Run a workload simulation to begin.</Link>
                  </div>
                )}
              </article>
              <article className="preview-card analytics-card">
                <div className="section-heading section-heading--compact">
                  <div>
                    <h3>Highest-emission applications</h3>
                    <p>Ranked by all-time recorded estimates</p>
                  </div>
                </div>
                {topApplications.length ? (
                  <div className="overview-app-list">
                    {topApplications.map((application) => (
                      <div className="overview-app-row" key={application.application_id}>
                        <span>{application.application_name}</span>
                        <strong>{number(application.estimated_emissions_kg_co2e_all_time)} kg CO₂e</strong>
                      </div>
                    ))}
                    <Link className="application-history-link" to="/analytics">View analytics and reports</Link>
                  </div>
                ) : (
                  <div className="analytics-empty analytics-empty--compact">
                    <strong>No applications to compare.</strong>
                    <Link to="/applications">Register an application to get started.</Link>
                  </div>
                )}
              </article>
            </div>
            <div className="analytics-chart-grid overview-chart-grid" aria-label="Overview analytics charts">
              <ChartPanel
                title="Energy consumption trend"
                subtitle="Daily estimated energy · last 14 UTC days · kWh"
                data={recentTrend.filter((bucket) => !bucket.is_empty)}
                emptyMessage="No completed-run energy estimates in the recent 14-day period."
              >
                <TrendLine data={recentTrend.map((bucket) => ({
                  ...bucket,
                  label: new Intl.DateTimeFormat(undefined, {
                    month: "short", day: "numeric", timeZone: "UTC",
                  }).format(new Date(bucket.period_start)),
                }))} dataKey="estimated_energy_kwh" name="Estimated energy" unit="kWh" />
              </ChartPanel>
              <ChartPanel
                title="Application emissions comparison"
                subtitle="All-time completed-run totals · kg CO₂e"
                data={rankedEmissions}
                emptyMessage="No completed-run emissions recorded for any application."
              >
                <ComparisonBar
                  data={rankedEmissions.slice(0, 8).reverse()}
                  dataKey="estimated_emissions_kg_co2e_all_time"
                  labelKey="application_name"
                  name="Emissions"
                  unit="kg CO₂e"
                />
              </ChartPanel>
              <ChartPanel
                title="Energy vs emissions"
                subtitle="Recent completed workload runs"
                data={completedRuns}
                emptyMessage="No completed workload runs are available in this period."
              >
                <EnergyEmissionsScatter data={completedRuns} />
              </ChartPanel>
              <ChartPanel
                title="Workload run status"
                subtitle="Recorded run counts · last 14 UTC days"
                data={Object.entries(workloadAnalytics?.status_counts || {}).filter(([, count]) => count > 0)}
                emptyMessage="No workload runs were recorded in the recent 14-day period."
              >
                <RunStatusDonut counts={workloadAnalytics?.status_counts} />
              </ChartPanel>
            </div>
          </>
        ) : null}
      </section>
    </>
  );
}
