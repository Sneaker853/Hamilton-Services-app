import React from 'react';
import { FiX } from 'react-icons/fi';
import { useLanguage } from '../components';

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
  const { tt } = useLanguage();
  const score = estimateConfidenceScore(holding);
  const estimatorLabel = formatEstimatorLabel(holding?.return_estimator);
  if (score == null) return <span className="pb-confidence-badge none" title={`${tt('No confidence data')}\n${tt('Estimator')}: ${estimatorLabel}`}>—</span>;
  const pct = Math.round(score * 100);
  let level = 'low';
  if (pct >= 70) level = 'high';
  else if (pct >= 40) level = 'med';
  const confidenceHelp = `${tt('Confidence')}: ${pct}%\n${tt('Estimator')}: ${estimatorLabel}\n${tt("Estimated reliability of this holding's return/risk inputs.")}\n${tt('Higher confidence means stronger model signal and more stable risk profile.')}`;
  return (
    <div className="pb-confidence-cell">
      <span className={`pb-confidence-badge ${level}`} title={confidenceHelp}>
        {pct}%
      </span>
    </div>
  );
};

const HoldingsTable = ({ holdings, onWeightChange, onRemove, onDragStart, onDrop, onDragEnd, onMoveUp, onMoveDown }) => {
  const { tt } = useLanguage();
  return (
  <div className="holdings-table-wrapper">
    <h3 className="pb-sub-title">{tt('Holdings')} ({holdings.length})</h3>
    <div className="holdings-table pb-table-wrap">
      <table>
        <thead>
          <tr>
            <th>{tt('Ticker')}</th>
            <th>{tt('Sector')}</th>
            <th>{tt('Weight (%)')}</th>
            <th>{tt('Confidence')}</th>
            <th>{tt('Value')}</th>
            <th>{tt('Shares')}</th>
            <th className="pb-center-cell">{tt('Reorder')}</th>
            <th className="pb-center-cell">{tt('Action')}</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((holding, idx) => {
            const isTouchDevice = typeof window !== 'undefined' && ('ontouchstart' in window || navigator.maxTouchPoints > 0);
            return (
            <tr
              key={idx}
              draggable={!isTouchDevice}
              aria-label={`${tt('Holding row')} ${holding.ticker}`}
              onDragStart={isTouchDevice ? undefined : () => onDragStart(holding.ticker)}
              onDragOver={isTouchDevice ? undefined : (event) => event.preventDefault()}
              onDrop={isTouchDevice ? undefined : () => onDrop(holding.ticker)}
              onDragEnd={isTouchDevice ? undefined : onDragEnd}
              className="pb-draggable-row"
            >
              <td className="ticker">{holding.ticker}</td>
              <td className="pb-sector-cell">{holding.sector || 'N/A'}</td>
              <td>
              <td className="pb-sector-cell">{holding.sector || tt('N/A')}</td>
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
                    aria-label={`${tt('Move')} ${holding.ticker} ${tt('up')}`}
                    disabled={idx === 0}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    onClick={() => onMoveDown(holding.ticker)}
                    className="pb-reorder-btn"
                    aria-label={`${tt('Move')} ${holding.ticker} ${tt('down')}`}
                    disabled={idx === holdings.length - 1}
                  >
                    ↓
                  </button>
                </div>
              </td>
              <td className="pb-center-cell">
                <button
                  onClick={() => onRemove(holding.ticker)}
                  aria-label={`${tt('Remove')} ${holding.ticker}`}
                  className="pb-remove-btn"
                >
                  <FiX />
                </button>
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  </div>
  );
};

export default HoldingsTable;
