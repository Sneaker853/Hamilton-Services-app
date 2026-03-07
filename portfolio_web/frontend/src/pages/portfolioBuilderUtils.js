/**
 * Shared utility functions and constants used by PortfolioBuilder sub-components.
 * Extracted from PortfolioBuilder.js for maintainability.
 */

export const COLORS = ['#22d3ee', '#818cf8', '#f472b6', '#34d399', '#fb923c', '#a78bfa', '#38bdf8', '#fbbf24', '#f87171', '#4ade80'];

export const pieLegendStyle = {
  fontSize: '11px',
  color: '#94a3b8',
  paddingTop: '8px',
  lineHeight: '20px',
};

export const renderPieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
  if (percent < 0.05) return null;
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  return (
    <text x={x} y={y} fill="#fff" textAnchor="middle" dominantBaseline="central"
      fontSize={11} fontWeight={600}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

export const renderPieTooltip = ({ active, payload }) => {
  if (!active || !payload || !payload.length) return null;
  const item = payload[0];
  const percent = typeof item.percent === 'number' ? (item.percent * 100).toFixed(1) : null;
  const value = Number(item.value);
  const color = item.color || item.payload?.fill || '#22d3ee';
  return (
    <div className="pb-tooltip-card">
      <div className="pb-tooltip-row">
        <span className="pb-tooltip-dot" style={{ background: color }} />
        <span className="pb-tooltip-name">{item.name}</span>
      </div>
      <div className="pb-tooltip-value">
        {percent !== null
          ? `${percent}%`
          : (Number.isFinite(value) ? `${value.toFixed(1)}%` : `${item.value}`)}
      </div>
    </div>
  );
};

export const toFiniteNumber = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

export const normalizePercentValue = (value) => {
  const numeric = toFiniteNumber(value);
  if (numeric === null) return null;
  return Math.abs(numeric) <= 1.5 ? numeric * 100 : numeric;
};

export const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

export const getHoldingExpectedReturnPct = (holding) => {
  const fromModel = normalizePercentValue(holding.expected_return);
  if (fromModel !== null) {
    return clamp(fromModel, -40, 80);
  }
  const pe = toFiniteNumber(holding.pe_ratio);
  if (pe && pe > 0) {
    return clamp(100 / pe, -20, 30);
  }
  console.warn(`[DEPRECATED] Using hardcoded 8% return fallback for ${holding.ticker || 'unknown'}`);
  return 8;
};

export const getHoldingVolatilityPct = (holding) => {
  const fromModel = normalizePercentValue(holding.volatility);
  if (fromModel !== null && fromModel > 0) {
    return clamp(fromModel, 2, 120);
  }
  const beta = toFiniteNumber(holding.beta);
  if (beta !== null) {
    return clamp(Math.abs(beta) * 18, 6, 70);
  }
  console.warn(`[DEPRECATED] Using hardcoded 20% volatility fallback for ${holding.ticker || 'unknown'}`);
  return 20;
};

export const estimatePairCorrelation = (left, right) => {
  if (left.ticker === right.ticker) return 1;
  const leftSector = left.sector || 'Unknown';
  const rightSector = right.sector || 'Unknown';
  const leftClass = (left.asset_class || 'stock').toLowerCase();
  const rightClass = (right.asset_class || 'stock').toLowerCase();
  if (leftClass === rightClass && leftSector === rightSector) return 0.72;
  if (leftClass === rightClass) return 0.45;
  if ((leftClass === 'bond' && rightClass !== 'bond') || (rightClass === 'bond' && leftClass !== 'bond')) return 0.2;
  const betaLeft = toFiniteNumber(left.beta) ?? 1;
  const betaRight = toFiniteNumber(right.beta) ?? 1;
  const betaDistance = Math.abs(betaLeft - betaRight);
  return clamp(0.5 - betaDistance * 0.2, -0.15, 0.65);
};

export const buildCorrelationMatrix = (portfolioHoldings) => {
  if (!portfolioHoldings.length) return [];
  return portfolioHoldings.map((rowHolding) => (
    portfolioHoldings.map((colHolding) => Number(estimatePairCorrelation(rowHolding, colHolding).toFixed(2)))
  ));
};

export const buildHoldingsSignature = (holdings) => {
  if (!Array.isArray(holdings) || holdings.length === 0) return '';
  return holdings
    .filter((holding) => !!holding?.ticker)
    .map((holding) => {
      const weight = Number(holding.weight);
      const normalizedWeight = Number.isFinite(weight) ? weight : 0;
      return `${holding.ticker}:${normalizedWeight.toFixed(4)}`;
    })
    .sort()
    .join('|');
};

export const formatPct = (v, decimals = 2) => {
  if (v == null || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(decimals)}%`;
};

export const formatNum = (v, decimals = 4) => {
  if (v == null || !Number.isFinite(v)) return '—';
  return v.toFixed(decimals);
};

export const ANALYTICS_TABS = [
  { key: 'benchmark', label: 'Benchmark', icon: 'FiTrendingUp' },
  { key: 'backtest', label: 'Backtest', icon: 'FiBarChart2' },
  { key: 'stress', label: 'Stress Test', icon: 'FiAlertTriangle' },
  { key: 'riskDecomp', label: 'Risk Decomp', icon: 'FiTarget' },
  { key: 'drift', label: 'Drift', icon: 'FiRefreshCw' },
];
