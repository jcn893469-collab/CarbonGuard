import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import {
  ChartPanel,
  ComparisonBar,
  TrendLine,
} from "../components/AnalyticsCharts.jsx";
import {
  createApplicationRecord,
  deleteApplication,
  getApplicationAnalyticsDetail,
  getAnalyticsOverview,
  listApplications,
  listWorkloadRuns,
  updateApplication,
} from "../services/api.js";

const emptyForm = { name: "", description: "", owner: "", status: "active" };

function formatNumber(value) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 6 }).format(value);
}

function formatUtc(value) {
  return `${new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value))} UTC`;
}

export default function ApplicationsPage() {
  const { refreshData } = useOutletContext();
  const [applications, setApplications] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [runs, setRuns] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [overview, setOverview] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [runsLoading, setRunsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selectedApplication = useMemo(
    () => applications.find((application) => String(application.id) === selectedId) || null,
    [applications, selectedId],
  );
  async function loadApplications() {
    setLoading(true);
    setError("");
    try {
      const data = await listApplications();
      setApplications(data);
      setSelectedId((current) =>
        data.some((application) => String(application.id) === current)
          ? current
          : data.length
            ? String(data[0].id)
            : "",
      );
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadApplications();
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setRuns([]);
      setAnalytics(null);
      return undefined;
    }
    const controller = new AbortController();
    let active = true;
    setAnalytics(null);
    setRuns([]);
    setRunsLoading(true);
    Promise.all([
      listWorkloadRuns(selectedId, { signal: controller.signal }),
      getApplicationAnalyticsDetail(selectedId, { signal: controller.signal }),
      getAnalyticsOverview({ signal: controller.signal }),
    ])
      .then(([runData, analyticsData, overviewData]) => {
        if (active) {
          setRuns(runData);
          setAnalytics(analyticsData);
          setOverview(overviewData);
        }
      })
      .catch((loadError) => {
        if (active && loadError.name !== "AbortError") setError(loadError.message);
      })
      .finally(() => {
        if (active) setRunsLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [selectedId]);

  const applicationTrend = (analytics?.trend?.buckets || []).map((bucket) => ({
    ...bucket,
    chart_label: new Intl.DateTimeFormat(undefined, {
      month: "short", day: "numeric", timeZone: "UTC",
    }).format(new Date(bucket.period_start)),
  }));
  const recentCompletedRuns = runs
    .filter((run) => run.status === "completed")
    .slice(0, 10)
    .map((run) => ({
      ...run,
      chart_label: `${run.name} · ${new Date(run.completed_at).toLocaleDateString()}`,
    }));
  const applicationComparisons = (overview?.applications || [])
    .filter((application) => application.completed_workload_run_count > 0)
    .sort((left, right) =>
      right.estimated_emissions_kg_co2e_all_time -
      left.estimated_emissions_kg_co2e_all_time);

  function startEditing(application) {
    setEditingId(application.id);
    setForm({
      name: application.name,
      description: application.description || "",
      owner: application.owner || "",
      status: application.status,
    });
    setError("");
    setNotice("");
  }

  function cancelEditing() {
    setEditingId(null);
    setForm(emptyForm);
    setError("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    const payload = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      owner: form.owner.trim() || null,
      status: form.status,
    };
    try {
      const saved = editingId
        ? await updateApplication(editingId, payload)
        : await createApplicationRecord(payload);
      setApplications((current) =>
        editingId
          ? current.map((application) => application.id === saved.id ? saved : application)
          : [...current, saved],
      );
      setSelectedId(String(saved.id));
      setNotice(editingId ? "Application updated." : "Application registered.");
      setEditingId(null);
      setForm(emptyForm);
      refreshData();
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(application) {
    if (!window.confirm(`Delete application "${application.name}"? Applications with budgets, policies, workloads, or history cannot be deleted.`)) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await deleteApplication(application.id);
      setApplications((current) => current.filter((item) => item.id !== application.id));
      if (String(application.id) === selectedId) {
        setSelectedId("");
        setRuns([]);
        setAnalytics(null);
      }
      if (editingId === application.id) cancelEditing();
      setNotice("Application deleted.");
      refreshData();
    } catch (deleteError) {
      setError(deleteError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-section">
      <div className="page-intro">
        <span className="section-kicker"><span /> APPLICATION REGISTRY</span>
        <h1>Applications</h1>
        <p>Register service owners, update application details, and review their persisted workload estimates.</p>
      </div>

      {error && <div className="policy-alert policy-alert--error" role="alert">{error}</div>}
      {notice && <div className="policy-alert policy-alert--success" role="status">{notice}</div>}

      <div className="application-page-layout">
        <article className="workload-panel">
          <div className="policy-panel__heading">
            <div>
              <h3>{editingId ? "Edit application" : "Register application"}</h3>
              <p>Names are unique. Deletion is restricted when records depend on the application.</p>
            </div>
          </div>
          <form className="policy-form" onSubmit={handleSubmit}>
            <label className="field">
              Application name
              <input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                minLength={1}
                maxLength={120}
                required
              />
            </label>
            <label className="field">
              Owner
              <input
                value={form.owner}
                onChange={(event) => setForm({ ...form, owner: event.target.value })}
                maxLength={120}
                placeholder="Team or service owner"
              />
            </label>
            <label className="field">
              Description
              <textarea
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
                maxLength={2000}
                rows={3}
                placeholder="What does this application do?"
              />
            </label>
            <label className="field">
              Status
              <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </label>
            <div className="policy-management-actions">
              <button className="button button--primary" disabled={saving}>
                {saving ? "Saving…" : editingId ? "Save changes" : "Register application"}
              </button>
              {editingId && (
                <button className="button button--secondary" type="button" onClick={cancelEditing} disabled={saving}>
                  Cancel
                </button>
              )}
            </div>
          </form>
        </article>

        <article className="workload-panel">
          <div className="section-heading section-heading--compact">
            <div>
              <h3>Registered applications</h3>
              <p>Choose an application to inspect its latest stored runs.</p>
            </div>
            <button type="button" className="button button--secondary" onClick={loadApplications} disabled={loading}>
              {loading ? "Refreshing…" : "Refresh"}
            </button>
          </div>
          {loading && applications.length === 0 ? (
            <div className="workload-empty" role="status">Loading applications…</div>
          ) : applications.length === 0 ? (
            <div className="workload-empty">No applications registered. Add the first application using the form.</div>
          ) : (
            <div className="application-list">
              {applications.map((application) => (
                <div
                  className={`application-list-item${application.id === selectedApplication?.id ? " application-list-item--selected" : ""}`}
                  key={application.id}
                >
                  <button
                    className="application-list-item__select"
                    type="button"
                    onClick={() => setSelectedId(String(application.id))}
                  >
                    <strong>{application.name}</strong>
                    <span>{application.owner || "No owner"} · {application.status}</span>
                  </button>
                  <div className="policy-management-actions">
                    <button className="button button--secondary" type="button" onClick={() => startEditing(application)}>Edit</button>
                    <button className="button button--danger" type="button" onClick={() => handleDelete(application)} disabled={saving}>Delete</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </article>
      </div>

      {selectedApplication && (
        <section className="application-runs" aria-labelledby="application-runs-title">
          <div className="section-heading">
            <div>
              <h2 id="application-runs-title">{selectedApplication.name} · workload history</h2>
              <p>{selectedApplication.description || "No application description provided."}</p>
            </div>
            <span className={`status-badge ${selectedApplication.status === "inactive" ? "status-badge--warning" : ""}`}>
              {selectedApplication.status}
            </span>
          </div>
          <div className="metric-grid application-run-metrics">
            <article className="metric-card"><span className="metric-card__eyebrow">COMPLETED RUNS · ALL TIME</span><p className="analytics-metric__value">{runsLoading ? "…" : analytics?.totals.completed_workload_run_count ?? "—"}</p></article>
            <article className="metric-card"><span className="metric-card__eyebrow">ESTIMATED ENERGY · ALL TIME</span><p className="analytics-metric__value">{runsLoading ? "…" : analytics ? `${formatNumber(analytics.totals.estimated_energy_kwh)} kWh` : "—"}</p></article>
            <article className="metric-card"><span className="metric-card__eyebrow">ESTIMATED EMISSIONS · ALL TIME</span><p className="analytics-metric__value">{runsLoading ? "…" : analytics ? `${formatNumber(analytics.totals.estimated_emissions_kg_co2e)} kg CO₂e` : "—"}</p></article>
          </div>
          <div className="analytics-chart-grid">
            <ChartPanel
              title="Energy over time"
              subtitle="Daily recorded completed-run estimates · last 30 UTC days · kWh"
              data={applicationTrend.filter((bucket) => !bucket.is_empty)}
              emptyMessage="No completed-run energy estimates in the recent 30-day period."
            >
              <TrendLine
                data={applicationTrend}
                dataKey="estimated_energy_kwh"
                name="Estimated energy"
                unit="kWh"
                xKey="chart_label"
              />
            </ChartPanel>
            <ChartPanel
              title="Emissions over time"
              subtitle="Daily recorded completed-run estimates · last 30 UTC days · kg CO₂e"
              data={applicationTrend.filter((bucket) => !bucket.is_empty)}
              emptyMessage="No completed-run emissions in the recent 30-day period."
            >
              <TrendLine
                data={applicationTrend}
                dataKey="estimated_emissions_kg_co2e"
                name="Estimated emissions"
                unit="kg CO₂e"
                color="#6e9a50"
                xKey="chart_label"
              />
            </ChartPanel>
            <ChartPanel
              title="Recent workload comparison"
              subtitle="Completed runs for the selected application · kg CO₂e"
              data={recentCompletedRuns}
              emptyMessage="No completed workload runs to compare."
            >
              <ComparisonBar
                data={recentCompletedRuns}
                dataKey="emissions_kg_co2e"
                labelKey="chart_label"
                name="Emissions"
                unit="kg CO₂e"
              />
            </ChartPanel>
            <ChartPanel
              title="Application emissions context"
              subtitle="All-time completed-run totals · kg CO₂e"
              data={applicationComparisons}
              emptyMessage="No completed application data is available for comparison."
            >
              <ComparisonBar
                data={[...applicationComparisons].reverse()}
                dataKey="estimated_emissions_kg_co2e_all_time"
                labelKey="application_name"
                name="All-time emissions"
                unit="kg CO₂e"
              />
            </ChartPanel>
          </div>
          {runsLoading ? (
            <div className="workload-empty" role="status">Loading application workload history…</div>
          ) : runs.length ? (
            <>
            <p className="application-history-note">Showing the latest {runs.length} runs. Summary metrics above include all recorded completed runs.</p>
            <div className="analytics-table-wrap">
              <table className="analytics-table workload-table">
                <thead><tr><th scope="col">Workload</th><th scope="col">Completed (UTC)</th><th scope="col">Status</th><th scope="col">Energy (kWh)</th><th scope="col">Emissions (kg CO₂e)</th></tr></thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.run_id}>
                      <th scope="row">{run.name}<small>{run.workload_type} · {run.estimation_source}</small></th>
                      <td>{formatUtc(run.completed_at)}</td>
                      <td>{run.status}</td>
                      <td>{formatNumber(run.energy_kwh)}</td>
                      <td>{formatNumber(run.emissions_kg_co2e)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            </>
          ) : (
            <div className="workload-empty">No workload runs for this application yet.</div>
          )}
        </section>
      )}
    </div>
  );
}
