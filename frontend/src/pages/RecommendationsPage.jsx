import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ChartPanel,
  ComparisonBar,
  ProjectedEmissionsChart,
} from "../components/AnalyticsCharts.jsx";
import { getAnalyticsOverview } from "../services/api.js";

function formatNumber(value) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(value);
}

export default function RecommendationsPage() {
  const { refreshKey } = useOutletContext();
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError("");
    getAnalyticsOverview({ signal: controller.signal })
      .then((overview) => {
        if (active) setApplications(overview.applications);
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
  }, [refreshKey, retryKey]);

  const rankedApplications = useMemo(
    () => applications
      .filter((application) => application.completed_workload_run_count > 0)
      .sort((left, right) =>
        right.estimated_emissions_kg_co2e_all_time -
        left.estimated_emissions_kg_co2e_all_time),
    [applications],
  );

  return (
    <div className="page-section">
      <div className="page-intro">
        <span className="section-kicker"><span /> EXPLAINABLE · DATA-DRIVEN</span>
        <h1>Sustainability recommendations</h1>
        <p>Prioritize opportunities using persisted application totals from completed simulated runs.</p>
      </div>
      {error && <div className="policy-alert policy-alert--error" role="alert">{error}</div>}
      {loading && !applications.length ? (
        <div className="analytics-loading" role="status">Loading application and workload data…</div>
      ) : error ? (
        <div className="workload-empty recommendation-empty">
          <strong>Recommendations could not be calculated.</strong>
          <span>Fix the API error above and refresh this page to load persisted application data.</span>
          <button className="button button--secondary" type="button" onClick={() => setRetryKey((current) => current + 1)}>Retry</button>
        </div>
      ) : rankedApplications.length ? (
        <>
          <div className="recommendation-disclaimer">
            <strong>Projected savings are scenario estimates, not measured outcomes.</strong>
            <span>Each scenario uses an illustrative 10% reduction applied to the application's average recorded completed-run emissions. Validate changes with new runs before drawing conclusions.</span>
          </div>
          <div className="recommendation-grid">
            <article className="preview-card analytics-card">
              <div className="section-heading section-heading--compact">
                <div>
                  <h3>Recorded emissions by application</h3>
                  <p>All-time completed-run estimates · kg CO₂e</p>
                </div>
                <span className="period-label">ACTUAL STORED ESTIMATES</span>
              </div>
              <div className="analytics-chart recommendation-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rankedApplications.slice(0, 8)} layout="vertical" margin={{ top: 8, right: 18, bottom: 8, left: 12 }}>
                    <CartesianGrid stroke="#edf1ed" strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" tick={{ fill: "#849188", fontSize: 9 }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="application_name" width={115} tick={{ fill: "#64756a", fontSize: 9 }} axisLine={false} tickLine={false} />
                    <Tooltip formatter={(value) => [`${formatNumber(Number(value))} kg CO₂e`, "Recorded estimates"]} />
                    <Bar dataKey="estimated_emissions_kg_co2e_all_time" fill="#39845b" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </article>
            <article className="preview-card analytics-card recommendation-method">
              <h3>How suggestions are generated</h3>
              <ol>
                <li>Use the backend's all-time totals from persisted completed workload runs.</li>
                <li>Rank applications by estimated emissions; prioritize the highest recorded contributors first.</li>
                <li>Calculate the scenario savings as 10% of the application's average recorded completed-run emissions.</li>
              </ol>
              <Link className="application-history-link" to="/analytics">Review date-filtered analytics and export</Link>
            </article>
          </div>
          <div className="analytics-chart-grid recommendation-analytics-grid">
            <ChartPanel
              title="Recorded energy by application"
              subtitle="All-time completed-run totals · kWh"
              data={rankedApplications.filter((application) => application.estimated_energy_kwh_all_time > 0)}
              emptyMessage="No completed-run energy totals are available."
            >
              <ComparisonBar
                data={[...rankedApplications].reverse()}
                dataKey="estimated_energy_kwh_all_time"
                labelKey="application_name"
                name="Recorded energy"
                unit="kWh"
              />
            </ChartPanel>
            <ChartPanel
              title="Recorded vs hypothetical emissions"
              subtitle="Per comparable run · kg CO₂e · projected values are estimates, not measured outcomes"
              data={rankedApplications}
              emptyMessage="No completed runs are available for this scenario."
            >
              <ProjectedEmissionsChart data={rankedApplications.map((application) => {
                const averageRun = application.estimated_emissions_kg_co2e_all_time /
                  application.completed_workload_run_count;
                return {
                  name: application.application_name,
                  recorded: averageRun,
                  projected: averageRun * 0.9,
                };
              })} />
            </ChartPanel>
          </div>
          <div className="recommendation-cards">
            {rankedApplications.map((application, index) => {
              const averageRunEmissions =
                application.estimated_emissions_kg_co2e_all_time /
                application.completed_workload_run_count;
              const projectedSavings = averageRunEmissions * 0.1;
              return (
                <article className="recommendation-card" key={application.application_id}>
                  <div className="recommendation-card__rank">{String(index + 1).padStart(2, "0")}</div>
                  <div className="recommendation-card__content">
                    <span className="section-kicker"><span /> PRIORITY {index === 0 ? "1" : "FOLLOW-UP"}</span>
                    <h2>{index === 0 ? "Review the highest-emission application" : "Review workload efficiency"}</h2>
                    <p>
                      <strong>{application.application_name}</strong> has {formatNumber(application.estimated_emissions_kg_co2e_all_time)} kg CO₂e across {application.completed_workload_run_count} completed runs. Review its workload settings and compare new runs after any change.
                    </p>
                    <div className="recommendation-card__metrics">
                      <span>Recorded energy <strong>{formatNumber(application.estimated_energy_kwh_all_time)} kWh</strong></span>
                      <span>Average recorded run <strong>{formatNumber(averageRunEmissions)} kg CO₂e</strong></span>
                      <span>10% scenario <strong>{formatNumber(projectedSavings)} kg CO₂e per comparable run</strong></span>
                    </div>
                  </div>
                  <span className="status-badge status-badge--warning">Projected, not realized</span>
                </article>
              );
            })}
          </div>
        </>
      ) : (
        <div className="workload-empty recommendation-empty">
          <strong>No persisted completed workload data is available yet.</strong>
          <span>Run a simulation before CarbonGuard generates recommendations. The system does not invent savings or use sample metrics.</span>
          <Link className="button button--primary" to="/workloads">Configure a workload</Link>
        </div>
      )}
    </div>
  );
}
