import React from 'react';
import { FiX } from 'react-icons/fi';

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const normalizeConfidenceScore = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  const normalized = numeric > 1 ? numeric / 100 : numeric;
  return clamp(normalized, 0, 1);
};

const normalizePercentLike = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.abs(numeric) <= 1.5 ? numeric * 100 : numeric;
};

const estimateConfidenceScore = (holding) => {
  const directScore = normalizeConfidenceScore(holding?.confidence_score ?? holding?.confidence);
  if (directScore !== null) return directScore;

  const expectedReturnPct = normalizePercentLike(holding?.expected_return);
  const volatilityPct = normalizePercentLike(holding?.volatility);
  const beta = Number(holding?.beta);
  const residualPct = normalizePercentLike(holding?.residual_std);

  const components = [];

  if (expectedReturnPct !== null) {
    components.push(clamp((expectedReturnPct + 5) / 25, 0, 1));
  }
  if (volatilityPct !== null && volatilityPct > 0) {
    components.push(clamp((45 - volatilityPct) / 35, 0, 1));
  }
  if (Number.isFinite(beta)) {
    components.push(clamp(1 - Math.abs(beta - 1) / 1.5, 0, 1));
  }
  if (residualPct !== null) {
    components.push(clamp(1 - residualPct / 40, 0, 1));
  }

  if (!components.length) return null;
  return components.reduce((sum, value) => sum + value, 0) / components.length;
};

/* Confidence badge: maps score (0–1) to color + label */
const formatEstimatorLabel = (estimator) => {
  const raw = String(estimator || '').trim();
  if (!raw) return 'Heuristic';
  return raw
    .replace(/_/g, ' ')
    .split(' ')
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(' ');
};

const ConfidenceBadge = ({ holding }) => {
  const score = estimateConfidenceScore(holding);
  const estimatorLabel = formatEstimatorLabel(holding?.return_estimator);
  if (score == null) return <span className="pb-confidence-badge none" title={`No confidence data\nEstimator: ${estimatorLabel}`}>—</span>;
  const pct = Math.round(score * 100);
  let level = 'low';
  if (pct >= 70) level = 'high';
  else if (pct >= 40) level = 'med';
  const confidenceHelp = `Confidence: ${pct}%\nEstimator: ${estimatorLabel}\nEstimated reliability of this holding's return/risk inputs.\nHigher confidence means stronger model signal and more stable risk profile.`;
  return (
    <div className="pb-confidence-cell">
      <span className={`pb-confidence-badge ${level}`} title={confidenceHelp}>
        {pct}%
      </span>
    </div>
  );
};

const HoldingsTable = ({ holdings, onWeightChange, onRemove, onDragStart, onDrop, onDragEnd, onMoveUp, onMoveDown }) => (
  <div className="holdings-table-wrapper">
    <h3 className="pb-sub-title">Holdings ({holdings.length})</h3>
    <div className="holdings-table pb-table-wrap">
      <table>
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Sector</th>
            <th>Weight (%)</th>
            <th>Confidence</th>
            <th>Value</th>
            <th>Shares</th>
            <th className="pb-center-cell">Reorder</th>
            <th className="pb-center-cell">Action</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((holding, idx) => (
            <tr
              key={idx}
              draggable
              aria-label={`Holding row ${holding.ticker}`}
              onDragStart={() => onDragStart(holding.ticker)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => onDrop(holding.ticker)}
              onDragEnd={onDragEnd}
              className="pb-draggable-row"
            >
              <td className="ticker">{holding.ticker}</td>
              <td className="pb-sector-cell">{holding.sector || 'N/A'}</td>
              <td>
                <input
                  type="number"
                  value={holding.weight}
                  onChange={(e) => onWeightChange(holding.ticker, e.target.value)}
                  min="0"
                  max="100"
                  step="0.1"
                  className="pb-weight-input"
                />
              </td>
              <td><ConfidenceBadge holding={holding} /></td>
              <td>${holding.value?.toLocaleString(undefined, { maximumFractionDigits: 0 }) || '0'}</td>
              <td>{holding.shares?.toFixed(2) || '0'}</td>
              <td className="pb-center-cell">
                <div className="pb-row-reorder-actions">
                  <button
                    type="button"
                    onClick={() => onMoveUp(holding.ticker)}
                    className="pb-reorder-btn"
                    aria-label={`Move ${holding.ticker} up`}
                    disabled={idx === 0}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    onClick={() => onMoveDown(holding.ticker)}
                    className="pb-reorder-btn"
                    aria-label={`Move ${holding.ticker} down`}
                    disabled={idx === holdings.length - 1}
                  >
                    ↓
                  </button>
                </div>
              </td>
              <td className="pb-center-cell">
                <button
                  onClick={() => onRemove(holding.ticker)}
                  aria-label={`Remove ${holding.ticker}`}
                  className="pb-remove-btn"
                >
                  <FiX />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

export default HoldingsTable;
