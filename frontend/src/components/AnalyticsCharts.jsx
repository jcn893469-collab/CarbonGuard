import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = ["#39845b", "#75a85e", "#d0a244", "#cb7058", "#6688a0", "#9273a8"];
const AXIS_STYLE = { fill: "#849188", fontSize: 10 };
const GRID_COLOR = "#edf1ed";

export function formatChartNumber(value, digits = 3) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(Number(value) || 0);
}

export function ChartPanel({ title, subtitle, data, emptyMessage, children, className = "" }) {
  return (
    <article className={`preview-card analytics-card analytics-chart-panel ${className}`}>
      <div className="section-heading section-heading--compact">
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </div>
      {data?.length ? (
        <div className="analytics-chart">{children}</div>
      ) : (
        <div className="analytics-empty analytics-empty--compact" role="status">
          {emptyMessage || "No recorded data is available for this chart."}
        </div>
      )}
    </article>
  );
}

export function TrendLine({ data, dataKey, name, unit, color = COLORS[0], xKey = "label", labelFormatter }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 12, right: 12, bottom: 4, left: 0 }}>
        <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={xKey} tick={AXIS_STYLE} axisLine={false} tickLine={false} minTickGap={20} />
        <YAxis
          tick={AXIS_STYLE}
          axisLine={false}
          tickLine={false}
          width={58}
          label={{ value: unit, angle: -90, position: "insideLeft", fill: "#849188", fontSize: 9 }}
        />
        <Tooltip
          labelFormatter={labelFormatter}
          formatter={(value) => [`${formatChartNumber(value)} ${unit}`, name]}
        />
        <Line type="monotone" dataKey={dataKey} name={name} stroke={color} strokeWidth={2}
          dot={{ r: 3, fill: color }} activeDot={{ r: 5 }} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function ComparisonBar({
  data,
  dataKey,
  labelKey,
  name,
  unit,
  color = COLORS[0],
  height,
  highlightHighValue = false,
}) {
  const maximum = Math.max(0, ...data.map((item) => Number(item[dataKey]) || 0));
  return (
    <ResponsiveContainer width="100%" height={height || "100%"}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 22, bottom: 8, left: 8 }}>
        <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" horizontal={false} />
        <XAxis
          type="number"
          tick={AXIS_STYLE}
          axisLine={false}
          tickLine={false}
          label={{ value: unit, position: "insideBottom", offset: -3, fill: "#849188", fontSize: 9 }}
        />
        <YAxis type="category" dataKey={labelKey} width={115} tick={AXIS_STYLE} axisLine={false} tickLine={false} />
        <Tooltip formatter={(value) => [`${formatChartNumber(value)} ${unit}`, name]} />
        <Bar dataKey={dataKey} name={name} fill={color} radius={[0, 4, 4, 0]} isAnimationActive={false}>
          {data.map((item, index) => (
            <Cell
              key={item[labelKey] || index}
              fill={highlightHighValue && maximum > 0 && Number(item[dataKey]) >= maximum * 0.8
                ? "#cb7058"
                : color}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ShareDonut({ data, dataKey, labelKey, unit, colors = COLORS }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={data} dataKey={dataKey} nameKey={labelKey} innerRadius="52%" outerRadius="78%"
          paddingAngle={2} isAnimationActive={false}>
          {data.map((item, index) => <Cell key={item[labelKey] || index} fill={colors[index % colors.length]} />)}
        </Pie>
        <Tooltip formatter={(value, name) => [`${formatChartNumber(value)} ${unit}`, name]} />
        <Legend verticalAlign="bottom" height={32} wrapperStyle={{ fontSize: 10, color: "#64756a" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function RunStatusDonut({ counts, colors = ["#39845b", "#cb7058", "#8c9990"] }) {
  const data = Object.entries(counts || {})
    .filter(([, value]) => value > 0)
    .map(([name, value]) => ({ name: name.replaceAll("_", " "), value }));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius="52%" outerRadius="78%"
          paddingAngle={2} isAnimationActive={false}>
          {data.map((item, index) => <Cell key={item.name} fill={colors[index % colors.length]} />)}
        </Pie>
        <Tooltip formatter={(value, name) => [formatChartNumber(value, 0), name]} />
        <Legend verticalAlign="bottom" height={32} wrapperStyle={{ fontSize: 10, color: "#64756a" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function EnergyEmissionsScatter({ data, xKey = "energy_kwh", yKey = "emissions_kg_co2e" }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ScatterChart margin={{ top: 12, right: 20, bottom: 10, left: 4 }}>
        <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey={xKey}
          name="Energy"
          unit=" kWh"
          tick={AXIS_STYLE}
          axisLine={false}
          label={{ value: "Energy (kWh)", position: "insideBottom", offset: -5, fill: "#849188", fontSize: 9 }}
        />
        <YAxis
          type="number"
          dataKey={yKey}
          name="Emissions"
          unit=" kg CO₂e"
          tick={AXIS_STYLE}
          axisLine={false}
          label={{ value: "Emissions (kg CO₂e)", angle: -90, position: "insideLeft", fill: "#849188", fontSize: 9 }}
        />
        <Tooltip cursor={{ strokeDasharray: "3 3" }} content={({ active, payload }) => {
          if (!active || !payload?.length) return null;
          const item = payload[0].payload;
          return (
            <div className="chart-tooltip">
              <strong>{item.name || "Recorded workload"}</strong>
              <span>{formatChartNumber(item[xKey])} kWh</span>
              <span>{formatChartNumber(item[yKey])} kg CO₂e</span>
              {item.completed_at && <span>{new Date(item.completed_at).toLocaleString()}</span>}
            </div>
          );
        }} />
        <Scatter data={data} fill={COLORS[0]} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

export function DurationEnergyScatter({ data }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ScatterChart margin={{ top: 12, right: 20, bottom: 10, left: 4 }}>
        <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey="duration_seconds"
          name="Duration"
          unit=" sec"
          tick={AXIS_STYLE}
          axisLine={false}
          label={{ value: "Duration (seconds)", position: "insideBottom", offset: -5, fill: "#849188", fontSize: 9 }}
        />
        <YAxis
          type="number"
          dataKey="energy_kwh"
          name="Energy"
          unit=" kWh"
          tick={AXIS_STYLE}
          axisLine={false}
          label={{ value: "Energy (kWh)", angle: -90, position: "insideLeft", fill: "#849188", fontSize: 9 }}
        />
        <Tooltip cursor={{ strokeDasharray: "3 3" }} content={({ active, payload }) => {
          if (!active || !payload?.length) return null;
          const item = payload[0].payload;
          return (
            <div className="chart-tooltip">
              <strong>{item.name}</strong>
              <span>{formatChartNumber(item.duration_seconds, 2)} seconds</span>
              <span>{formatChartNumber(item.energy_kwh)} kWh</span>
              {item.completed_at && <span>{new Date(item.completed_at).toLocaleString()}</span>}
            </div>
          );
        }} />
        <Scatter data={data} fill={COLORS[1]} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

export function BudgetComparison({ actual, budget, warning, critical }) {
  const data = [
    { name: "Recorded emissions", value: actual },
    { name: "Configured budget", value: budget },
  ];
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 12, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="name" tick={AXIS_STYLE} axisLine={false} tickLine={false} />
        <YAxis tick={AXIS_STYLE} axisLine={false} tickLine={false}
          label={{ value: "kg CO₂e", angle: -90, position: "insideLeft", fill: "#849188", fontSize: 9 }} />
        <Tooltip formatter={(value) => [`${formatChartNumber(value)} kg CO₂e`, "Emissions"]} />
        <ReferenceLine y={budget * warning / 100} stroke="#d0a244" strokeDasharray="4 4"
          label={{ value: "Warning", position: "insideTopRight", fill: "#966d20", fontSize: 9 }} />
        <ReferenceLine y={budget * critical / 100} stroke="#cb7058" strokeDasharray="4 4"
          label={{ value: "Critical", position: "insideTopRight", fill: "#a64f43", fontSize: 9 }} />
        <Bar dataKey="value" name="Emissions / budget" radius={[4, 4, 0, 0]} isAnimationActive={false}>
          <Cell fill={actual >= budget * critical / 100 ? "#cb7058" : actual >= budget * warning / 100 ? "#d0a244" : COLORS[0]} />
          <Cell fill="#a8b8aa" />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function GroupedEnergyEmissions({ data, labelKey = "application_name" }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data} margin={{ top: 12, right: 14, bottom: 4, left: 4 }}>
        <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={labelKey} tick={AXIS_STYLE} axisLine={false} tickLine={false} />
        <YAxis yAxisId="energy" tick={AXIS_STYLE} axisLine={false}
          label={{ value: "Energy (kWh)", angle: -90, position: "insideLeft", fill: "#849188", fontSize: 9 }} />
        <YAxis yAxisId="emissions" orientation="right" tick={AXIS_STYLE} axisLine={false}
          label={{ value: "Emissions (kg CO₂e)", angle: 90, position: "insideRight", fill: "#849188", fontSize: 9 }} />
        <Tooltip formatter={(value, name) => [
          `${formatChartNumber(value)} ${name === "Energy" ? "kWh" : "kg CO₂e"}`, name,
        ]} />
        <Legend wrapperStyle={{ fontSize: 10, color: "#64756a" }} />
        <Bar yAxisId="energy" dataKey="energy" name="Energy" fill={COLORS[0]} radius={[3, 3, 0, 0]} />
        <Bar yAxisId="emissions" dataKey="emissions" name="Emissions" fill={COLORS[2]} radius={[3, 3, 0, 0]} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function ProjectedEmissionsChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 22, bottom: 8, left: 8 }}>
        <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tick={AXIS_STYLE} axisLine={false}
          label={{ value: "kg CO₂e", position: "insideBottom", offset: -3, fill: "#849188", fontSize: 9 }} />
        <YAxis type="category" dataKey="name" width={115} tick={AXIS_STYLE} axisLine={false} />
        <Tooltip formatter={(value, name) => [`${formatChartNumber(value)} kg CO₂e`, name]} />
        <Legend wrapperStyle={{ fontSize: 10, color: "#64756a" }} />
        <Bar dataKey="recorded" name="Average recorded run" fill={COLORS[0]} radius={[0, 4, 4, 0]} />
        <Bar dataKey="projected" name="10% reduction estimate" fill={COLORS[2]} radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
