import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AnalyticsPage from "./pages/AnalyticsPage.jsx";
import ApplicationsPage from "./pages/ApplicationsPage.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import OverviewPage from "./pages/OverviewPage.jsx";
import PoliciesPage from "./pages/PoliciesPage.jsx";
import RecommendationsPage from "./pages/RecommendationsPage.jsx";
import WorkloadsPage from "./pages/WorkloadsPage.jsx";
import { useApiHealth } from "./hooks/useApiHealth.js";

export default function App() {
  const health = useApiHealth();
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Dashboard health={health} />}>
          <Route index element={<OverviewPage />} />
          <Route path="workloads" element={<WorkloadsPage />} />
          <Route path="applications" element={<ApplicationsPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="policies" element={<PoliciesPage />} />
          <Route path="recommendations" element={<RecommendationsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
