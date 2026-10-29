import { useEffect, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import ConnectionStatus from "../components/ConnectionStatus.jsx";

const navigation = [
  { to: "/", label: "Overview", icon: "▦", end: true },
  { to: "/workloads", label: "Workloads", icon: "◷" },
  { to: "/applications", label: "Applications", icon: "▤" },
  { to: "/analytics", label: "Analytics & reports", icon: "↗" },
  { to: "/policies", label: "Budgets & policies", icon: "◎" },
  { to: "/recommendations", label: "Recommendations", icon: "✳" },
];

const routeTitles = {
  "/": "Overview",
  "/workloads": "Workloads",
  "/applications": "Applications",
  "/analytics": "Analytics & reports",
  "/policies": "Budgets & policies",
  "/recommendations": "Sustainability recommendations",
};

export default function Dashboard({ health }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const location = useLocation();
  const title = routeTitles[location.pathname] || "Overview";
  const outletContext = useMemo(
    () => ({
      refreshKey,
      refreshData: () => setRefreshKey((current) => current + 1),
    }),
    [refreshKey],
  );

  useEffect(() => {
    document.title = `${title} | CarbonGuard`;
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [title]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" to="/" aria-label="CarbonGuard home">
          <span className="brand__mark" aria-hidden="true">
            C
          </span>
          <span>
            <strong>CarbonGuard</strong>
            <small>Cloud sustainability</small>
          </span>
        </Link>

        <div className="sidebar__section-label">WORKSPACE</div>
        <nav className="sidebar__nav" aria-label="Main navigation">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              className={({ isActive }) => `nav-item${isActive ? " nav-item--active" : ""}`}
              to={item.to}
              end={item.end}
            >
              <span aria-hidden="true">{item.icon}</span> {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__footer">
          <div className="phase-tag"><span /> CARBON INTELLIGENCE</div>
          <p>Review recorded estimates and explainable sustainability opportunities.</p>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> {title}</div>
          <ConnectionStatus status={health.status} />
        </header>

        <div className="dashboard-content">
          <Outlet context={outletContext} />

          <footer className="page-footer">
            <span>CarbonGuard <span className="footer-dot">·</span> Cloud sustainability</span>
            <span>
              {health.status === "connected"
                ? `${health.details.application} v${health.details.version}`
                : "No carbon data is being collected"}
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
