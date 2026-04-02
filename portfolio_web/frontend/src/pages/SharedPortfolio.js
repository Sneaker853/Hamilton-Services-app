import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { FiExternalLink } from 'react-icons/fi';
import { HelpIcon } from '../components';
import { useLanguage } from '../components';
import './SharedPortfolio.css';

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

const SharedPortfolio = ({ apiBase }) => {
  const { tt } = useLanguage();
  const { shareToken } = useParams();
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchShared = async () => {
      try {
        const response = await axios.get(`${apiBase}/shared/${shareToken}`);
        setPortfolio(response.data);
      } catch (err) {
        setError(err.response?.data?.detail || tt('Portfolio not found or link has expired.'));
      } finally {
        setLoading(false);
      }
    };
    fetchShared();
  }, [apiBase, shareToken]);

  if (loading) {
    return (
      <div className="page-container shared-portfolio-root">
        <div className="page-header">
          <h1>Shared Portfolio</h1>
          <p className="page-subtitle">{tt('Loading...')}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container shared-portfolio-root">
        <div className="page-header">
          <h1>{tt('Shared Portfolio')}</h1>
          <p className="page-subtitle shared-error">{error}</p>
        </div>
      </div>
    );
  }

  const data = portfolio?.data || {};
  const holdings = Array.isArray(data.holdings) ? data.holdings : [];
  const summary = data.summary || {};
  const metrics = data.metrics || {};
  const investment = asNumber(data.investment_amount, 0);
  const expectedReturn = asNumber(summary.expected_return ?? metrics.expected_return);
  const volatility = asNumber(summary.volatility ?? metrics.volatility);
  const sharpe = asNumber(metrics.sharpe_ratio ?? summary.sharpe_ratio);

  return (
    <div className="page-container shared-portfolio-root">
      <div className="page-header">
        <h1>{portfolio.name}</h1>
        <p className="page-subtitle">
          Shared by {portfolio.shared_by} · {portfolio.source} ·{' '}
          {new Date(portfolio.created_at).toLocaleDateString()}
        </p>
      </div>

      <div className="shared-badge">
        <FiExternalLink /> {tt('Read-only shared view')}
      </div>

      {/* Summary metrics */}
      <div className="shared-metrics-grid">
        <div className="shared-metric-card">
          <span className="shared-metric-label">{tt('Investment')}</span>
          <span className="shared-metric-value">{formatCurrency(investment)}</span>
        </div>
        <div className="shared-metric-card">
          <span className="shared-metric-label">
            Expected Return <HelpIcon text="Annualized expected return from the FF5 model." />
          </span>
          <span className="shared-metric-value">{formatPct(Math.abs(expectedReturn) > 1.5 ? expectedReturn : expectedReturn * 100)}</span>
        </div>
        <div className="shared-metric-card">
          <span className="shared-metric-label">
            Volatility <HelpIcon text="Annualized standard deviation of returns." />
          </span>
          <span className="shared-metric-value">{formatPct(Math.abs(volatility) > 1.5 ? volatility : volatility * 100, 1)}</span>
        </div>
        <div className="shared-metric-card">
          <span className="shared-metric-label">
            Sharpe <HelpIcon text="Risk-adjusted return: (Return − Rf) ÷ Volatility." />
          </span>
          <span className="shared-metric-value">{sharpe.toFixed(2)}</span>
        </div>
      </div>

      {/* Holdings table */}
      {holdings.length > 0 && (
        <div className="shared-holdings-wrap">
          <h3>Holdings ({holdings.length})</h3>
          <table className="shared-holdings-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Name</th>
                <th>Weight</th>
                <th>Sector</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {holdings
                .sort((a, b) => asNumber(b.weight) - asNumber(a.weight))
                .map((h) => (
                  <tr key={h.ticker}>
                    <td><strong>{h.ticker}</strong></td>
                    <td>{h.name || '—'}</td>
                    <td>{asNumber(h.weight).toFixed(2)}%</td>
                    <td>{h.sector || '—'}</td>
                    <td>{formatCurrency(asNumber(h.amount))}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default SharedPortfolio;
