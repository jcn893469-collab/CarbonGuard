import { useOutletContext } from "react-router-dom";
import Workloads from "../components/Workloads.jsx";

export default function WorkloadsPage() {
  const { refreshKey, refreshData } = useOutletContext();
  return (
    <div className="page-section">
      <div className="page-intro">
        <span className="section-kicker"><span /> SIMULATION WORKSPACE</span>
        <h1>Workloads</h1>
        <p>Configure, simulate, and inspect persisted workload estimates.</p>
      </div>
      <Workloads refreshKey={refreshKey} onRunCompleted={refreshData} />
    </div>
  );
}
