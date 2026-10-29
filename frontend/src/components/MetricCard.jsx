export default function MetricCard({
  eyebrow,
  title,
  description,
  value = "Not available yet",
}) {
  return (
    <article className="metric-card">
      <div className="metric-card__topline">
        <span className="metric-card__eyebrow">{eyebrow}</span>
        <span className="metric-card__icon" aria-hidden="true">
          ↗
        </span>
      </div>
      <h3>{title}</h3>
      <p className="metric-card__value">{value}</p>
      <p className="metric-card__description">{description}</p>
    </article>
  );
}
