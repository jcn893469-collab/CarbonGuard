import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import BudgetPolicies from "../components/BudgetPolicies.jsx";
import { getAnalyticsOverview } from "../services/api.js";

export default function PoliciesPage() {
  const { refreshKey, refreshData } = useOutletContext();
  const [evaluations, setEvaluations] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    getAnalyticsOverview({ signal: controller.signal })
      .then((overview) => {
        if (active) {
          setEvaluations(overview.policy_evaluations);
          setError("");
        }
      })
      .catch((loadError) => {
        if (active && loadError.name !== "AbortError") setError(loadError.message);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [refreshKey]);

  return (
    <div className="page-section">
      <div className="page-intro">
        <span className="section-kicker"><span /> POLICY ENGINE · RECOMMENDATION ONLY</span>
        <h1>Budgets &amp; policies</h1>
        <p>Manage application emission budgets and evaluate them against persisted completed runs.</p>
      </div>
      {error && <div className="policy-alert policy-alert--error" role="alert">{error}</div>}
      <BudgetPolicies evaluations={evaluations} onPolicyChange={refreshData} />
    </div>
  );
}
