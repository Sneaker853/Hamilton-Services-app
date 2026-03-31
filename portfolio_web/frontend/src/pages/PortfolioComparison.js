import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { FiCheck } from 'react-icons/fi';
import { HelpIcon } from '../components';
import { downloadCsv } from '../utils/exportCsv';
import './PortfolioComparison.css';

const asNumber = (value, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const formatPct = (value, digits = 2) => {
  const num = asNumber(value);
  const sign = num > 0 ? '+' : '';
  return `${sign}${num.toFixed(digits)}%`;
};

const formatCurrency = (value) =>
  asNumber(value).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

const extractMetrics = (portfolio) => {
  const data = portfolio?.data || {};
  const summary = data.summary || {};
  const metrics = data.metrics || {};
  const holdings = Array.isArray(data.holdings) ? data.holdings : [];
  const investment = asNumber(data.investment_amount, 0);

  const expectedReturn = asNumber(summary.expected_return ?? metrics.expected_return);
  const volatility = asNumber(summary.volatility ?? metrics.volatility);
  const sharpe = asNumber(metrics.sharpe_ratio ?? summary.sharpe_ratio);

  // Sectors
  const sectorMap = {};
  holdings.forEach((h) => {
    const sector = h.sector || 'Unknown';
    sectorMap[sector] = (sectorMap[sector] || 0) + asNumber(h.weight);
  });
  const topSectors = Object.entries(sectorMap)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  // Top holdings
  const topHoldings = [...holdings]
    .sort((a, b) => asNumber(b.weight) - asNumber(a.weight))
    .slice(0, 5);

  return {
    name: portfolio.name || 'Unnamed',
    source: portfolio.source || 'manual',
    createdAt: portfolio.created_at,
    holdingsCount: holdings.length,
    investment,
    expectedReturn: Math.abs(expectedReturn) > 1.5 ? expectedReturn : expectedReturn * 100,
    volatility: Math.abs(volatility) > 1.5 ? volatility : volatility * 100,
    sharpe,
    topSectors,
    topHoldings,
  };
};

const METRIC_ROWS = [
  { key: 'holdingsCount', label: 'Holdings', format: (v) => v },
  { key: 'investment', label: 'Investment', format: formatCurrency },
  { key: 'expectedReturn', label: 'Expected Return', format: (v) => formatPct(v), help: 'Annualized expected return from the FF5 factor model.' },
  { key: 'volatility', label: 'Volatility', format: (v) => formatPct(v, 1), help: 'Annualized standard deviation of portfolio returns.' },
  { key: 'sharpe', label: 'Sharpe Ratio', format: (v) => v.toFixed(2), help: 'Risk-adjusted return: (Return − Rf) ÷ Volatility.' },
  { key: 'source', label: 'Source', format: (v) => v },
];

const PortfolioComparison = ({ apiBase }) => {
  const [portfolios, setPortfolios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState([]);

  useEffect(() => {
    const fetchPortfolios = async () => {
      const authUser = localStorage.getItem('authUser');
      if (!authUser) {
        setLoading(false);
        return;
      }
      try {
        const response = await axios.get(`${apiBase}/portfolios`, { withCredentials: true });
        setPortfolios(response.data?.portfolios || []);
      } catch (err) {
        console.error('Error fetching portfolios:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchPortfolios();
  }, [apiBase]);

  const toggleSelect = (id) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  };

  const comparedPortfolios = useMemo(
    () => portfolios.filter((p) => selected.includes(p.id)).map(extractMetrics),
    [portfolios, selected]
  );

  const handleExportComparison = () => {
    if (comparedPortfolios.length === 0) return;
    const headers = ['Metric', ...comparedPortfolios.map((p) => p.name)];
    const rows = METRIC_ROWS.map((row) => [
      row.label,
      ...comparedPortfolios.map((p) => String(row.format(p[row.key]))),
    ]);
    downloadCsv('portfolio_comparison', headers, rows);
  };

  const bestForMetric = (key, higherIsBetter = true) => {
    if (comparedPortfolios.length < 2) return -1;
    let bestIdx = 0;
    comparedPortfolios.forEach((p, i) => {
      const current = asNumber(p[key]);
      const best = asNumber(comparedPortfolios[bestIdx][key]);
      if (higherIsBetter ? current > best : current < best) bestIdx = i;
    });
    return bestIdx;
  };

  if (loading) {
    return (
      <div className="page-container comparison-root">
        <div className="page-header">
          <h1>Portfolio Comparison</h1>
          <p className="page-subtitle">Loading portfolios…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container comparison-root">
      <div className="page-header">
        <h1>Portfolio Comparison</h1>
        <p className="page-subtitle">
          Select 2 or more saved portfolios to compare side-by-side
        </p>
      </div>

      {/* Portfolio selector */}
      <div className="comparison-selector">
        {portfolios.length === 0 && (
          <p className="comparison-empty">No saved portfolios. Create and save a portfolio first.</p>
        )}
        {portfolios.map((p) => {
          const isSelected = selected.includes(p.id);
          return (
            <button
              key={p.id}
              type="button"
              className={`comparison-chip ${isSelected ? 'active' : ''}`}
              onClick={() => toggleSelect(p.id)}
            >
              {isSelected ? <FiCheck size={14} /> : null}
              {p.name || 'Unnamed'}
            </button>
          );
        })}
      </div>

      {/* Comparison table */}
      {comparedPortfolios.length >= 2 && (
        <>
          <div className="comparison-actions">
            <button className="comparison-export-btn" onClick={handleExportComparison}>
              Export Comparison CSV
            </button>
          </div>
          <div className="comparison-table-wrap">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th className="comparison-label-col">Metric</th>
                  {comparedPortfolios.map((p, i) => (
                    <th key={i}>
                      <div className="comparison-col-head">
                        <strong>{p.name}</strong>
                        <small>{p.source}</small>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {METRIC_ROWS.map((row) => {
                  const bestIdx = ['expectedReturn', 'sharpe'].includes(row.key)
                    ? bestForMetric(row.key, true)
                    : row.key === 'volatility'
                    ? bestForMetric(row.key, false)
                    : -1;
                  return (
                    <tr key={row.key}>
                      <td className="comparison-label-col">
                        {row.label}
                        {row.help && <> <HelpIcon text={row.help} /></>}
                      </td>
                      {comparedPortfolios.map((p, i) => (
                        <td key={i} className={i === bestIdx ? 'comparison-best' : ''}>
                          {row.format(p[row.key])}
                        </td>
                      ))}
                    </tr>
                  );
                })}
                {/* Top sectors */}
                <tr>
                  <td className="comparison-label-col">Top Sectors</td>
                  {comparedPortfolios.map((p, i) => (
                    <td key={i}>
                      {p.topSectors.map(([name, weight]) => (
                        <div key={name} className="comparison-sector-row">
                          <span>{name}</span>
                          <span>{weight.toFixed(1)}%</span>
                        </div>
                      ))}
                    </td>
                  ))}
                </tr>
                {/* Top holdings */}
                <tr>
                  <td className="comparison-label-col">Top Holdings</td>
                  {comparedPortfolios.map((p, i) => (
                    <td key={i}>
                      {p.topHoldings.map((h) => (
                        <div key={h.ticker} className="comparison-sector-row">
                          <span>{h.ticker}</span>
                          <span>{asNumber(h.weight).toFixed(1)}%</span>
                        </div>
                      ))}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}

      {selected.length === 1 && (
        <p className="comparison-hint">Select at least one more portfolio to compare.</p>
      )}
    </div>
  );
};

export default PortfolioComparison;
