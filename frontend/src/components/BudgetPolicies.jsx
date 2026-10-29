import { useEffect, useMemo, useState } from "react";
import {
  BudgetComparison,
  ChartPanel,
  RunStatusDonut,
} from "./AnalyticsCharts.jsx";
import {
  createApplication,
  createBudgetPolicy,
  deleteBudgetPolicy,
  evaluateBudgetPolicy,
  listApplications,
  listBudgetPolicies,
  updateBudgetPolicy,
} from "../services/api.js";

const initialForm = {
  budget_kg_co2e: "10",
  period: "monthly",
  warning_threshold_percent: "80",
  critical_threshold_percent: "95",
  action: "warn",
};

function formatNumber(value, maximumFractionDigits = 6) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(value);
}

function statusLabel(status) {
  return status.replaceAll("_", " ");
}

function formatUtcDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

export default function BudgetPolicies({ evaluations, onPolicyChange }) {
  const [applications, setApplications] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [selectedApplicationId, setSelectedApplicationId] = useState("");
  const [evaluation, setEvaluation] = useState(null);
  const [form, setForm] = useState(initialForm);
  const [newApplicationName, setNewApplicationName] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selectedPolicy = useMemo(
    () =>
      policies.find(
        (policy) => String(policy.application_id) === selectedApplicationId,
      ) || null,
    [policies, selectedApplicationId],
  );
  const evaluatedStatusCounts = Object.fromEntries(
    ["within_budget", "warning", "critical", "exceeded"].map((status) => [
      status,
      (evaluations || []).filter((item) => item.status === status).length,
    ]),
  );

  async function loadData() {
    setLoading(true);
    setError("");
    try {
      const [applicationData, policyData] = await Promise.all([
        listApplications(),
        listBudgetPolicies(),
      ]);
      setApplications(applicationData);
      setPolicies(policyData);
      setSelectedApplicationId((current) => {
        if (applicationData.some((application) => String(application.id) === current)) {
          return current;
        }
        return applicationData.length ? String(applicationData[0].id) : "";
      });
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    const currentEvaluation = selectedPolicy?.enabled
      ? evaluations.find((item) => item.policy_id === selectedPolicy.id) || null
      : null;
    setEvaluation(currentEvaluation);
  }, [selectedPolicy?.id, selectedPolicy?.enabled, evaluations]);

  async function handleCreateApplication(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const created = await createApplication(newApplicationName.trim());
      setApplications((current) => [...current, created]);
      setSelectedApplicationId(String(created.id));
      setNewApplicationName("");
      setNotice("Application registered.");
      onPolicyChange?.();
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleCreatePolicy(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    const warning = Number(form.warning_threshold_percent);
    const critical = Number(form.critical_threshold_percent);
    if (!selectedApplicationId) {
      setError("Select a registered application first.");
      return;
    }
    if (!(Number(form.budget_kg_co2e) > 0)) {
      setError("Budget must be greater than zero.");
      return;
    }
    if (!(warning > 0) || !(critical > warning)) {
      setError("Thresholds must be positive, and critical must exceed warning.");
      return;
    }

    setSaving(true);
    try {
      await createBudgetPolicy({
        application_id: Number(selectedApplicationId),
        budget_kg_co2e: Number(form.budget_kg_co2e),
        period: form.period,
        warning_threshold_percent: warning,
        critical_threshold_percent: critical,
        action: form.action,
        enabled: true,
      });
      setNotice("Budget policy created.");
      await loadData();
      onPolicyChange?.();
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleEvaluate() {
    if (!selectedPolicy) return;
    setEvaluating(true);
    setError("");
    try {
      const result = await evaluateBudgetPolicy(selectedPolicy.id);
      setEvaluation(result);
      setNotice("Budget status refreshed from recorded workload runs.");
      onPolicyChange?.();
    } catch (evaluateError) {
      setError(evaluateError.message);
    } finally {
      setEvaluating(false);
    }
  }

  async function handleTogglePolicy() {
    if (!selectedPolicy) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await updateBudgetPolicy(selectedPolicy.id, {
        enabled: !selectedPolicy.enabled,
      });
      setNotice(`Policy ${selectedPolicy.enabled ? "disabled" : "enabled"}.`);
      await loadData();
      onPolicyChange?.();
    } catch (updateError) {
      setError(updateError.message);
    } finally {
      setSaving(false);
    }
  }

  function startEditingPolicy() {
    if (!selectedPolicy) return;
    setForm({
      budget_kg_co2e: String(selectedPolicy.budget_kg_co2e),
      period: selectedPolicy.period,
      warning_threshold_percent: String(selectedPolicy.warning_threshold_percent),
      critical_threshold_percent: String(selectedPolicy.critical_threshold_percent),
      action: selectedPolicy.action,
    });
    setEditingPolicy(true);
    setError("");
    setNotice("");
  }

  async function handleUpdatePolicy(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    const warning = Number(form.warning_threshold_percent);
    const critical = Number(form.critical_threshold_percent);
    if (!(Number(form.budget_kg_co2e) > 0)) {
      setError("Budget must be greater than zero.");
      return;
    }
    if (!(warning > 0) || !(critical > warning)) {
      setError("Thresholds must be positive, and critical must exceed warning.");
      return;
    }

    setSaving(true);
    try {
      await updateBudgetPolicy(selectedPolicy.id, {
        budget_kg_co2e: Number(form.budget_kg_co2e),
        period: form.period,
        warning_threshold_percent: warning,
        critical_threshold_percent: critical,
        action: form.action,
      });
      setEditingPolicy(false);
      setNotice("Budget policy updated.");
      await loadData();
      onPolicyChange?.();
    } catch (updateError) {
      setError(updateError.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeletePolicy() {
    if (!selectedPolicy) return;
    const confirmed = window.confirm(
      `Delete the budget policy for ${selectedApplication?.name || "this application"}? This will not delete workload history.`,
    );
    if (!confirmed) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await deleteBudgetPolicy(selectedPolicy.id);
      setEditingPolicy(false);
      setNotice("Budget policy deleted. Workload history was preserved.");
      await loadData();
      onPolicyChange?.();
    } catch (deleteError) {
      setError(deleteError.message);
    } finally {
      setSaving(false);
    }
  }

  const selectedApplication = applications.find(
    (application) => String(application.id) === selectedApplicationId,
  );

  return (
    <section className="policy-section" id="policies" aria-labelledby="policy-title">
      <div className="section-heading">
        <div>
          <h2 id="policy-title">Budgets &amp; policies</h2>
          <p>
            Evaluate recorded run estimates against an application budget.
            Actions are recommendations only.
          </p>
        </div>
        <span className="period-label">POLICY ENGINE · SIMULATED</span>
      </div>

      {error && <div className="policy-alert policy-alert--error" role="alert">{error}</div>}
      {notice && <div className="policy-alert policy-alert--success" role="status">{notice}</div>}
      {loading ? (
        <div className="policy-panel policy-loading" role="status">Loading applications and policies…</div>
      ) : applications.length === 0 ? (
        <div className="policy-panel policy-empty">
          <div>
            <strong>Register an application to get started</strong>
            <p>Policies are attached to registered applications.</p>
          </div>
          <form className="application-form" onSubmit={handleCreateApplication}>
            <label>
              Application name
              <input
                value={newApplicationName}
                onChange={(event) => setNewApplicationName(event.target.value)}
                maxLength={120}
                required
              />
            </label>
            <button className="button button--primary" disabled={saving}>
              {saving ? "Registering…" : "Register application"}
            </button>
          </form>
        </div>
      ) : (
        <div className="policy-layout">
          <article className="policy-panel">
            <div className="policy-panel__heading">
              <div>
                <h3>Application budget</h3>
                <p>Select an application to manage its policy.</p>
              </div>
              {selectedPolicy && (
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={handleTogglePolicy}
                  disabled={saving}
                >
                  {selectedPolicy.enabled ? "Disable policy" : "Enable policy"}
                </button>
              )}
            </div>

            <label className="field">
              Application
              <select
                value={selectedApplicationId}
                onChange={(event) => {
                  setSelectedApplicationId(event.target.value);
                  setEditingPolicy(false);
                  setError("");
                  setNotice("");
                }}
              >
                {applications.map((application) => (
                  <option key={application.id} value={application.id}>
                    {application.name}
                  </option>
                ))}
              </select>
            </label>

            {selectedPolicy ? (
              <div className="policy-summary">
                <div className="policy-summary__row">
                  <span>Budget</span>
                  <strong>{formatNumber(selectedPolicy.budget_kg_co2e)} kg CO₂e / {selectedPolicy.period}</strong>
                </div>
                <div className="policy-summary__row">
                  <span>Warning / critical</span>
                  <strong>{formatNumber(selectedPolicy.warning_threshold_percent)}% / {formatNumber(selectedPolicy.critical_threshold_percent)}%</strong>
                </div>
                <div className="policy-summary__row">
                  <span>Configured action</span>
                  <strong>{selectedPolicy.action.replaceAll("_", " ")}</strong>
                </div>
                {!selectedPolicy.enabled && (
                  <p className="policy-disabled-note">This policy is disabled and excluded from evaluate-all.</p>
                )}
                <div className="policy-management-actions">
                  <button
                    type="button"
                    className="button button--secondary"
                    onClick={startEditingPolicy}
                    disabled={saving}
                  >
                    Edit settings
                  </button>
                  <button
                    type="button"
                    className="button button--danger"
                    onClick={handleDeletePolicy}
                    disabled={saving}
                  >
                    Delete policy
                  </button>
                </div>
                <button
                  type="button"
                  className="button button--secondary button--full"
                  onClick={handleEvaluate}
                  disabled={evaluating}
                >
                  {evaluating ? "Evaluating…" : "Refresh budget status"}
                </button>
                {editingPolicy && (
                  <form className="policy-form policy-edit-form" onSubmit={handleUpdatePolicy}>
                    <label className="field">
                      Carbon budget (kg CO₂e)
                      <input
                        type="number"
                        min="0.000001"
                        step="any"
                        value={form.budget_kg_co2e}
                        onChange={(event) => setForm({ ...form, budget_kg_co2e: event.target.value })}
                        required
                      />
                    </label>
                    <label className="field">
                      Budget period
                      <select value={form.period} onChange={(event) => setForm({ ...form, period: event.target.value })}>
                        <option value="daily">Daily (UTC day)</option>
                        <option value="weekly">Weekly (Monday–Sunday, UTC)</option>
                        <option value="monthly">Monthly (UTC calendar month)</option>
                      </select>
                    </label>
                    <div className="policy-form__row">
                      <label className="field">
                        Warning threshold (%)
                        <input
                          type="number"
                          min="0.01"
                          step="any"
                          value={form.warning_threshold_percent}
                          onChange={(event) => setForm({ ...form, warning_threshold_percent: event.target.value })}
                          required
                        />
                      </label>
                      <label className="field">
                        Critical threshold (%)
                        <input
                          type="number"
                          min="0.01"
                          step="any"
                          value={form.critical_threshold_percent}
                          onChange={(event) => setForm({ ...form, critical_threshold_percent: event.target.value })}
                          required
                        />
                      </label>
                    </div>
                    <label className="field">
                      Recommended policy action
                      <select value={form.action} onChange={(event) => setForm({ ...form, action: event.target.value })}>
                        <option value="monitor">Monitor only</option>
                        <option value="warn">Warn at threshold</option>
                        <option value="recommend_throttle">Recommend throttle at critical</option>
                      </select>
                    </label>
                    <div className="policy-management-actions">
                      <button className="button button--primary" disabled={saving}>
                        {saving ? "Saving…" : "Save policy"}
                      </button>
                      <button
                        className="button button--secondary"
                        type="button"
                        onClick={() => setEditingPolicy(false)}
                        disabled={saving}
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}
              </div>
            ) : (
              <>
                <div className="policy-empty-inline">
                  No policy is configured for {selectedApplication?.name || "this application"}.
                </div>
                <form className="policy-form" onSubmit={handleCreatePolicy}>
                  <label className="field">
                    Carbon budget (kg CO₂e)
                    <input
                      type="number"
                      min="0.000001"
                      step="any"
                      value={form.budget_kg_co2e}
                      onChange={(event) => setForm({ ...form, budget_kg_co2e: event.target.value })}
                      required
                    />
                  </label>
                  <label className="field">
                    Budget period
                    <select
                      value={form.period}
                      onChange={(event) => setForm({ ...form, period: event.target.value })}
                    >
                      <option value="daily">Daily (UTC day)</option>
                      <option value="weekly">Weekly (Monday–Sunday, UTC)</option>
                      <option value="monthly">Monthly (UTC calendar month)</option>
                    </select>
                  </label>
                  <div className="policy-form__row">
                    <label className="field">
                      Warning threshold (%)
                      <input
                        type="number"
                        min="0.01"
                        step="any"
                        value={form.warning_threshold_percent}
                        onChange={(event) => setForm({ ...form, warning_threshold_percent: event.target.value })}
                        required
                      />
                    </label>
                    <label className="field">
                      Critical threshold (%)
                      <input
                        type="number"
                        min="0.01"
                        step="any"
                        value={form.critical_threshold_percent}
                        onChange={(event) => setForm({ ...form, critical_threshold_percent: event.target.value })}
                        required
                      />
                    </label>
                  </div>
                  <label className="field">
                    Recommended policy action
                    <select
                      value={form.action}
                      onChange={(event) => setForm({ ...form, action: event.target.value })}
                    >
                      <option value="monitor">Monitor only</option>
                      <option value="warn">Warn at threshold</option>
                      <option value="recommend_throttle">Recommend throttle at critical</option>
                    </select>
                  </label>
                  <button className="button button--primary" disabled={saving}>
                    {saving ? "Saving…" : "Create policy"}
                  </button>
                </form>
              </>
            )}
          </article>

          <article className="policy-panel policy-status-panel" aria-live="polite">
            <div className="policy-panel__heading">
              <div>
                <h3>Current period status</h3>
                <p>Consumption is summed from recorded completed workload runs.</p>
              </div>
              {evaluation && (
                <span className={`status-badge status-badge--${evaluation.status}`}>
                  {statusLabel(evaluation.status)}
                </span>
              )}
            </div>
            {!selectedPolicy ? (
              <div className="policy-status-empty">Create a policy to see its budget status.</div>
            ) : !selectedPolicy.enabled ? (
              <div className="policy-status-empty">This policy is disabled. Enable it or manually evaluate it.</div>
            ) : evaluation ? (
              <>
                <div className="budget-stats">
                  <div><span>Consumed</span><strong>{formatNumber(evaluation.consumed_kg_co2e)} <small>kg CO₂e</small></strong></div>
                  <div><span>Remaining</span><strong>{formatNumber(evaluation.remaining_kg_co2e)} <small>kg CO₂e</small></strong></div>
                  <div><span>Utilization</span><strong>{formatNumber(evaluation.utilization_percent, 2)}<small>%</small></strong></div>
                </div>
                <div
                  className="budget-progress"
                  role="progressbar"
                  aria-label="Budget utilization"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.min(100, Math.max(0, evaluation.utilization_percent))}
                  aria-valuetext={`${formatNumber(evaluation.utilization_percent, 2)} percent of budget used`}
                >
                  <span
                    className={`budget-progress__fill budget-progress__fill--${evaluation.status}`}
                    style={{ width: `${Math.min(100, Math.max(0, evaluation.utilization_percent))}%` }}
                  />
                  <span className="budget-progress__marker budget-progress__marker--warning"
                    style={{ left: `${Math.min(100, selectedPolicy.warning_threshold_percent)}%` }}
                    aria-hidden="true" />
                  <span className="budget-progress__marker budget-progress__marker--critical"
                    style={{ left: `${Math.min(100, selectedPolicy.critical_threshold_percent)}%` }}
                    aria-hidden="true" />
                </div>
                <p className="budget-threshold-labels">
                  Warning {formatNumber(selectedPolicy.warning_threshold_percent, 1)}% ·
                  {" "}Critical {formatNumber(selectedPolicy.critical_threshold_percent, 1)}%
                </p>
                <div className="period-details">
                  Period: {formatUtcDate(evaluation.period_start)} – {formatUtcDate(evaluation.period_end)} (UTC)
                </div>
                <div className="recommendation">
                  <span>Recommended action</span>
                  <strong>{evaluation.recommended_action.replaceAll("_", " ")}</strong>
                  <small>Recommendation only — no workload is throttled or stopped.</small>
                </div>
                <div className="contribution-heading">
                  <strong>Contributing workload runs</strong>
                  <span>{evaluation.contributing_run_count} recorded</span>
                </div>
                {evaluation.contributing_runs.length ? (
                  <ul className="contribution-list">
                    {evaluation.contributing_runs.map((run) => (
                      <li key={run.run_id}>
                        <span title={run.run_id}>{run.run_id.slice(0, 8)}…</span>
                        <span>{formatNumber(run.emissions_kg_co2e)} kg CO₂e · {run.source} estimate</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="no-contributions">No completed workload runs in this UTC period.</p>
                )}
              </>
            ) : (
              <div className="policy-status-empty">Evaluating current period…</div>
            )}
          </article>
        </div>
      )}
      {!loading && applications.length > 0 && (
        <div className="analytics-chart-grid policy-analytics-grid">
          <ChartPanel
            title="Actual emissions vs budget"
            subtitle={evaluation ? `${selectedApplication?.name || "Selected application"} · current ${evaluation.period} UTC period · kg CO₂e` : "Current recorded policy period"}
            data={evaluation && evaluation.budget_kg_co2e > 0 ? [evaluation] : []}
            emptyMessage={!selectedPolicy
              ? "No budget policy is configured for the selected application."
              : !selectedPolicy.enabled
                ? "This policy is disabled; evaluate it manually to view current recorded emissions."
                : "No current policy evaluation is available yet."}
          >
            <BudgetComparison
              actual={evaluation.consumed_kg_co2e}
              budget={evaluation.budget_kg_co2e}
              warning={selectedPolicy.warning_threshold_percent}
              critical={selectedPolicy.critical_threshold_percent}
            />
          </ChartPanel>
          <ChartPanel
            title="Policy evaluation statuses"
            subtitle="Latest on-request evaluations across enabled policies"
            data={Object.entries(evaluatedStatusCounts).filter(([, count]) => count > 0)}
            emptyMessage="No policy evaluations have been recorded for enabled policies."
          >
            <RunStatusDonut
              counts={evaluatedStatusCounts}
              colors={["#39845b", "#d0a244", "#cb8d50", "#cb7058"]}
            />
          </ChartPanel>
        </div>
      )}
    </section>
  );
}
