import { useOutletContext } from "react-router-dom";
import AnalyticsDashboard from "../components/AnalyticsDashboard.jsx";

export default function AnalyticsPage() {
  const { refreshKey } = useOutletContext();
  return (
    <div className="page-section">
      <div className="page-intro">
        <span className="section-kicker"><span /> MEASURED FROM STORED ESTIMATES</span>
        <h1>Analytics &amp; reports</h1>
        <p>Filter historical estimates by UTC date, aggregation interval, and application.</p>
      </div>
      <AnalyticsDashboard refreshKey={refreshKey} />
    </div>
  );
}
