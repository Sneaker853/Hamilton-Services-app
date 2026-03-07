import React from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ScatterChart,
  Scatter,
  Cell,
  ZAxis,
  Legend
} from 'recharts';

const EmptyChart = ({ title, message }) => (
  <div style={{
    height: '100%',
    minHeight: '240px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    color: '#94a3b8',
    fontSize: '13px'
  }}>
    <div style={{ fontWeight: '700', color: '#cbd5e1' }}>{title}</div>
    <div>{message}</div>
  </div>
);

const formatNumber = (value) => {
  if (typeof value !== 'number') return value;
  return Number.isFinite(value) ? value.toFixed(2) : 'N/A';
};

export const PerformanceLineChart = ({ data, historicalData, height = 260 }) => {
  const hasProjected = data && data.length > 0;
  const hasHistorical = historicalData && historicalData.length > 0;

  if (!hasProjected && !hasHistorical) {
    return <EmptyChart title="Performance" message="No performance history yet" />;
  }

  // When both series exist, merge them on a shared timeline
  // Historical uses actual dates; projected uses M1..M12 relative labels
  // We'll render them in separate charts stacked, or as dual‐line if both are present

  const tooltipStyle = {
    background: 'rgba(10, 14, 26, 0.96)',
    border: '1px solid rgba(90, 110, 150, 0.35)',
    borderRadius: '10px',
    color: '#f8fafc'
  };

  if (hasHistorical && hasProjected) {
    // Merge: historical comes first, then projected continues from last historical value
    const lastHistorical = historicalData[historicalData.length - 1];

    // Build merged data array — historical points get "historical" key, projected get "projected"
    const merged = [];
    historicalData.forEach((pt) => {
      merged.push({ date: pt.date, historical: pt.value });
    });

    // Scale projected so M1 starts at last historical value
    const projectedStart = data[0]?.value || lastHistorical.value;
    const scaleFactor = projectedStart > 0 ? lastHistorical.value / projectedStart : 1;

    // Add bridge point so the projected line connects to the historical endpoint
    merged.push({
      date: lastHistorical.date,
      historical: lastHistorical.value,
      projected: lastHistorical.value,
    });

    data.forEach((pt) => {
      merged.push({ date: pt.date, projected: Math.round(pt.value * scaleFactor * 100) / 100 });
    });

    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={merged} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="rgba(255, 255, 255, 0.08)" strokeDasharray="3 3" />
          <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
          <YAxis stroke="#94a3b8" fontSize={11} />
          <Tooltip contentStyle={tooltipStyle} formatter={(value) => formatNumber(value)} />
          <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
          <Line
            type="monotone"
            dataKey="historical"
            name="Historical"
            stroke="#22d3ee"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="projected"
            name="Projected"
            stroke="#a78bfa"
            strokeWidth={2}
            strokeDasharray="6 3"
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  // Historical only
  if (hasHistorical) {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={historicalData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="rgba(255, 255, 255, 0.08)" strokeDasharray="3 3" />
          <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
          <YAxis stroke="#94a3b8" fontSize={11} />
          <Tooltip contentStyle={tooltipStyle} formatter={(value) => formatNumber(value)} />
          <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
          <Line
            type="monotone"
            dataKey="value"
            name="Historical"
            stroke="#22d3ee"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  // Projected only (fallback — no historical data available)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="rgba(255, 255, 255, 0.08)" strokeDasharray="3 3" />
        <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
        <YAxis stroke="#94a3b8" fontSize={11} />
        <Tooltip contentStyle={tooltipStyle} formatter={(value) => formatNumber(value)} />
        <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
        <Line
          type="monotone"
          dataKey="value"
          name="Projected"
          stroke="#a78bfa"
          strokeWidth={2}
          strokeDasharray="6 3"
          dot={false}
          activeDot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

// Cubic spline interpolation for the frontier bullet shape.
// Uses 'return' as the independent variable (monotonically increasing)
// and 'risk' as the dependent variable (forms the hyperbola).
const interpolateFrontier = (points, resolution = 120) => {
  if (points.length < 2) return points;
  if (points.length === 2) {
    const result = [];
    for (let i = 0; i <= resolution; i++) {
      const t = i / resolution;
      result.push({
        risk: points[0].risk + t * (points[1].risk - points[0].risk),
        return: points[0].return + t * (points[1].return - points[0].return),
      });
    }
    return result;
  }

  // Independent variable: return (monotonically increasing after sort)
  // Dependent variable: risk (forms the U/bullet shape)
  const xs = points.map(p => p.return);
  const ys = points.map(p => p.risk);
  const n = xs.length;

  // Natural cubic spline (no monotonicity constraint — risk is NOT monotone)
  // Build tridiagonal system for spline coefficients
  const h = [];
  for (let i = 0; i < n - 1; i++) {
    h.push(xs[i + 1] - xs[i] || 1e-10);
  }

  // Solve for second derivatives (moments) using tridiagonal system
  const alpha = new Array(n).fill(0);
  for (let i = 1; i < n - 1; i++) {
    alpha[i] = (3 / h[i]) * (ys[i + 1] - ys[i]) - (3 / h[i - 1]) * (ys[i] - ys[i - 1]);
  }

  const l = new Array(n).fill(1);
  const mu = new Array(n).fill(0);
  const z = new Array(n).fill(0);

  for (let i = 1; i < n - 1; i++) {
    l[i] = 2 * (xs[i + 1] - xs[i - 1]) - h[i - 1] * mu[i - 1];
    mu[i] = h[i] / l[i];
    z[i] = (alpha[i] - h[i - 1] * z[i - 1]) / l[i];
  }

  const c = new Array(n).fill(0);
  const b = new Array(n - 1).fill(0);
  const d = new Array(n - 1).fill(0);

  for (let j = n - 2; j >= 0; j--) {
    c[j] = z[j] - mu[j] * c[j + 1];
    b[j] = (ys[j + 1] - ys[j]) / h[j] - h[j] * (c[j + 1] + 2 * c[j]) / 3;
    d[j] = (c[j + 1] - c[j]) / (3 * h[j]);
  }

  // Interpolate
  const result = [];
  const xMin = xs[0];
  const xMax = xs[n - 1];
  for (let i = 0; i <= resolution; i++) {
    const x = xMin + (i / resolution) * (xMax - xMin);
    // Find the segment
    let seg = 0;
    for (let j = 0; j < n - 1; j++) {
      if (x >= xs[j]) seg = j;
    }
    const dx = x - xs[seg];
    const y = ys[seg] + b[seg] * dx + c[seg] * dx * dx + d[seg] * dx * dx * dx;
    result.push({ risk: Number(Math.max(y, 0).toFixed(2)), return: Number(x.toFixed(2)) });
  }
  return result;
};

export const EfficientFrontierChart = ({ data, height = 260 }) => {
  if (!data || data.length === 0) {
    return <EmptyChart title="Efficient Frontier" message="Add more holdings to generate a frontier" />;
  }

  // Sort by return (low → high) so the hyperbola traces correctly:
  // bottom-right → min-variance vertex (leftmost) → top-right
  const sorted = [...data].sort((a, b) => a.return - b.return);
  // Generate smooth curve through the frontier points
  const smoothCurve = interpolateFrontier(sorted, 80);

  const CustomFrontierTooltip = ({ active, payload }) => {
    if (!active || !payload || payload.length === 0) return null;
    const point = payload[0]?.payload;
    if (!point) return null;
    return (
      <div style={{
        background: 'rgba(10, 14, 26, 0.96)',
        border: '1px solid rgba(90, 110, 150, 0.35)',
        borderRadius: '10px',
        padding: '8px 12px',
        color: '#f8fafc',
        fontSize: 13,
      }}>
        <div style={{ color: '#22d3ee', fontWeight: 600, marginBottom: 4 }}>
          Risk: {formatNumber(point.risk)}%
        </div>
        <div>Return: {formatNumber(point.return)}%</div>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={smoothCurve} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
        <CartesianGrid stroke="rgba(255, 255, 255, 0.08)" strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey="risk"
          name="Risk (%)"
          stroke="#94a3b8"
          fontSize={11}
          tickFormatter={(v) => `${formatNumber(v)}%`}
          domain={['dataMin - 1', 'dataMax + 1']}
          label={{ value: 'Risk (%)', position: 'insideBottom', offset: -5, fill: '#94a3b8', fontSize: 12, fontWeight: 600 }}
        />
        <YAxis
          type="number"
          dataKey="return"
          name="Return (%)"
          stroke="#94a3b8"
          fontSize={11}
          tickFormatter={(v) => `${formatNumber(v)}%`}
          domain={['dataMin - 1', 'dataMax + 2']}
          label={{ value: 'Return (%)', angle: -90, position: 'insideLeft', offset: 10, fill: '#94a3b8', fontSize: 12, fontWeight: 600 }}
        />
        <Tooltip content={<CustomFrontierTooltip />} cursor={{ strokeDasharray: '3 3', stroke: 'rgba(148, 163, 184, 0.3)' }} />
        <Line
          type="monotone"
          dataKey="return"
          stroke="#22d3ee"
          strokeWidth={2}
          dot={false}
          activeDot={false}
          isAnimationActive={false}
        />
        <Scatter
          data={sorted}
          dataKey="return"
          fill="#22d3ee"
          tooltipType="none"
        >
          {sorted.map((entry, index) => (
            <Cell key={`cell-${index}`} fill="#22d3ee" r={5} />
          ))}
        </Scatter>
      </ComposedChart>
    </ResponsiveContainer>
  );
};

export const RiskReturnScatter = ({ data, height = 260 }) => {
  if (!data || data.length === 0) {
    return <EmptyChart title="Risk vs Return" message="No holdings to plot" />;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="rgba(255, 255, 255, 0.08)" strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey="risk"
          name="Risk (%)"
          stroke="#94a3b8"
          fontSize={11}
          tickFormatter={(value) => `${formatNumber(value)}%`}
          domain={['dataMin - 1', 'dataMax + 1']}
        />
        <YAxis
          type="number"
          dataKey="return"
          name="Return (%)"
          stroke="#94a3b8"
          fontSize={11}
          tickFormatter={(value) => `${formatNumber(value)}%`}
          domain={['dataMin - 1', 'dataMax + 1']}
        />
        <ZAxis dataKey="weight" range={[60, 220]} />
        <Tooltip
          cursor={{ strokeDasharray: '3 3' }}
          contentStyle={{
            background: 'rgba(10, 14, 26, 0.96)',
            border: '1px solid rgba(90, 110, 150, 0.35)',
            borderRadius: '10px',
            color: '#f8fafc'
          }}
          labelStyle={{ color: '#f8fafc', fontWeight: 600 }}
          itemStyle={{ color: '#cbd5e1' }}
          labelFormatter={(_, payload) => payload?.[0]?.payload?.name || 'Asset'}
          formatter={(value, name) => {
            if (!Number.isFinite(Number(value))) return [value, name];
            if (name === 'weight') return [`${formatNumber(value)}%`, 'Weight'];
            return [`${formatNumber(value)}%`, name];
          }}
        />
        <Scatter data={data} fill="#22d3ee" />
      </ScatterChart>
    </ResponsiveContainer>
  );
};

const getHeatColor = (value) => {
  if (typeof value !== 'number') return 'rgba(255, 255, 255, 0.06)';
  const clamped = Math.max(-1, Math.min(1, value));
  const intensity = Math.abs(clamped);
  const base = clamped >= 0 ? [0, 217, 255] : [255, 107, 107];
  return `rgba(${base[0]}, ${base[1]}, ${base[2]}, ${0.15 + intensity * 0.55})`;
};

export const CorrelationHeatmap = ({ matrix, labels }) => {
  if (!matrix || matrix.length === 0 || !labels || labels.length === 0) {
    return <EmptyChart title="Correlation Heatmap" message="No correlation data available" />;
  }

  return (
    <div style={{ overflow: 'auto', maxHeight: '460px', width: '100%', paddingBottom: '4px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: `120px repeat(${labels.length}, 40px)`, gap: '6px', width: 'max-content', minWidth: '100%' }}>
        <div />
        {labels.map((label) => (
          <div key={`col-${label}`} style={{ fontSize: '11px', color: '#94a3b8', textAlign: 'center' }}>
            {label}
          </div>
        ))}
        {matrix.map((row, rowIdx) => (
          <React.Fragment key={`row-${rowIdx}`}>
            <div style={{ fontSize: '11px', color: '#94a3b8', padding: '6px 0' }}>
              {labels[rowIdx]}
            </div>
            {row.map((value, colIdx) => (
              <div
                key={`cell-${rowIdx}-${colIdx}`}
                style={{
                  background: getHeatColor(value),
                  borderRadius: '6px',
                  height: '34px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '11px',
                  color: '#f8fafc'
                }}
              >
                {formatNumber(value)}
              </div>
            ))}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};
