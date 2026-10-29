const labels = {
  checking: "Checking API",
  connected: "API connected",
  unavailable: "API unavailable",
};

export default function ConnectionStatus({ status }) {
  return (
    <div className={`connection-status connection-status--${status}`} role="status">
      <span className="connection-status__dot" aria-hidden="true" />
      <span>{labels[status]}</span>
    </div>
  );
}
