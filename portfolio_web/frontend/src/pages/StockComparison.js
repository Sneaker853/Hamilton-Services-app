import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { FiX, FiSearch, FiTrendingUp, FiTrendingDown } from 'react-icons/fi';
import { HelpIcon, useLanguage } from '../components';
import { downloadCsv } from '../utils/exportCsv';
import './StockComparison.css';

const asNumber = (value, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const normalizePercentLike = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.abs(numeric) <= 1.5 ? numeric * 100 : numeric;
};

const formatPct = (value, digits = 2) => {
  const num = asNumber(value);
  const sign = num > 0 ? '+' : '';
  return `${sign}${num.toFixed(digits)}%`;
};

const formatCurrency = (value) =>
  asNumber(value).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });

const formatPercentMetric = (value, digits = 2) => {
  const normalized = normalizePercentLike(value);
  if (normalized == null) return '—';
  return formatPct(normalized, digits);
};

const formatLargeNumber = (value) => {
  const num = asNumber(value);
  if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (num >= 1e6) return `$${(num / 1e6).toFixed(1)}M`;
  return formatCurrency(num);
};

const buildMetricRows = (tt) => [
  { key: 'name', label: tt('Company'), format: (v) => v || '—' },
  { key: 'exchange', label: tt('Exchange'), format: (v) => v || '—' },
  { key: 'sector', label: tt('Sector'), format: (v) => v || '—' },
  { key: 'current_price', label: tt('Price'), format: formatCurrency },
  { key: 'market_cap', label: tt('Market Cap'), format: formatLargeNumber, help: tt('Total market capitalization (share price × shares outstanding).') },
  { key: 'pe_ratio', label: tt('P/E Ratio'), format: (v) => asNumber(v) ? asNumber(v).toFixed(2) : '—', help: tt('Price-to-earnings ratio. Lower may indicate better value.') },
  { key: 'roe', label: tt('ROE'), format: (v) => formatPercentMetric(v), help: tt('Return on equity — measures profitability relative to shareholder equity.') },
  { key: 'beta', label: tt('Beta'), format: (v) => asNumber(v) ? asNumber(v).toFixed(2) : '—', help: tt('Market sensitivity. β > 1 = more volatile than market.') },
  { key: 'dividend_yield', label: tt('Dividend Yield'), format: (v) => formatPercentMetric(v), help: tt('Annual dividend as a percentage of share price.') },
  { key: 'expected_return', label: tt('Expected Return'), format: (v) => formatPercentMetric(v, 1), help: tt('Annualized expected return from the FF5 factor model.') },
  { key: 'volatility', label: tt('Volatility'), format: (v) => formatPercentMetric(v, 1), help: tt('Annualized standard deviation of returns.') },
];

const StockComparison = ({ apiBase }) => {
  const { tt } = useLanguage();
  const metricRows = buildMetricRows(tt);
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [selectedStocks, setSelectedStocks] = useState([]);
  const [stockData, setStockData] = useState({});
  const [searching, setSearching] = useState(false);

  const searchStocks = useCallback(async (q) => {
    if (!q || q.length < 1) {
      setSuggestions([]);
      return;
    }
    setSearching(true);
    try {
      const res = await axios.get(`${apiBase}/stocks/search`, { params: { q, limit: 8 } });
      setSuggestions(res.data?.results || []);
    } catch {
      setSuggestions([]);
    } finally {
      setSearching(false);
    }
  }, [apiBase]);

  useEffect(() => {
    const timeout = setTimeout(() => searchStocks(query), 300);
    return () => clearTimeout(timeout);
  }, [query, searchStocks]);

  const addStock = async (ticker) => {
    if (selectedStocks.includes(ticker) || selectedStocks.length >= 6) return;
    setSelectedStocks((prev) => [...prev, ticker]);
    setQuery('');
    setSuggestions([]);

    if (!stockData[ticker]) {
      try {
        const res = await axios.get(`${apiBase}/stocks/${encodeURIComponent(ticker)}`);
        if (res.data) {
          setStockData((prev) => ({ ...prev, [ticker]: res.data }));
        }
      } catch {
        // Data unavailable for this ticker
      }
    }
  };

  const removeStock = (ticker) => {
    setSelectedStocks((prev) => prev.filter((t) => t !== ticker));
  };

  const comparedStocks = selectedStocks
    .map((t) => stockData[t])
    .filter(Boolean);

  const bestForMetric = (key, higherIsBetter = true) => {
    if (comparedStocks.length < 2) return -1;
    let bestIdx = 0;
    comparedStocks.forEach((s, i) => {
      const current = asNumber(s[key]);
      const best = asNumber(comparedStocks[bestIdx][key]);
      if (current === 0 && best !== 0) return;
      if (higherIsBetter ? current > best : current < best) bestIdx = i;
    });
    return bestIdx;
  };

  const handleExport = () => {
    if (comparedStocks.length === 0) return;
    const headers = ['Metric', ...comparedStocks.map((s) => s.ticker)];
    const rows = metricRows.map((row) => [
      row.label,
      ...comparedStocks.map((s) => String(row.format(s[row.key]))),
    ]);
    downloadCsv('stock_comparison', headers, rows);
  };

  return (
    <div className="page-container stock-comparison-root">
      <div className="page-header">
        <h1>{tt('Stock Comparison')}</h1>
        <p className="page-subtitle">
          {tt('Compare fundamentals and metrics for up to 6 stocks side-by-side')}
        </p>
      </div>

      {/* Search input */}
      <div className="stock-comparison-search">
        <div className="stock-search-input-wrap">
          <FiSearch className="stock-search-icon" />
          <input
            type="text"
            className="stock-search-input"
            placeholder={tt('Search by ticker or company name...')}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            maxLength={50}
          />
          {searching && <span className="stock-search-spinner" />}
        </div>
        {suggestions.length > 0 && (
          <ul className="stock-search-suggestions">
            {suggestions.map((s) => (
              <li key={s.ticker}>
                <button type="button" onClick={() => addStock(s.ticker)}>
                  <strong>{s.ticker}</strong>
                  <span>{s.name}</span>
                  <small>{s.exchange} · {s.sector}</small>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Selected chips */}
      {selectedStocks.length > 0 && (
        <div className="stock-comparison-chips">
          {selectedStocks.map((t) => (
            <span key={t} className="stock-chip">
              {t}
              <button type="button" onClick={() => removeStock(t)} aria-label={`Remove ${t}`}>
                <FiX size={14} />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Comparison table */}
      {comparedStocks.length >= 2 && (
        <>
          <div className="comparison-actions">
            <button className="comparison-export-btn" onClick={handleExport}>
              {tt('Export Comparison CSV')}
            </button>
          </div>
          <div className="comparison-table-wrap">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th className="comparison-label-col">{tt('Metric')}</th>
                  {comparedStocks.map((s, i) => (
                    <th key={i}>
                      <div className="comparison-col-head">
                        <strong>{s.ticker}</strong>
                        <small>{s.name}</small>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {metricRows.map((row) => {
                  const bestIdx =
                    row.key === 'pe_ratio' ? bestForMetric(row.key, false)
                    : ['expected_return', 'roe', 'dividend_yield', 'market_cap'].includes(row.key)
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
                      {comparedStocks.map((s, i) => (
                        <td key={i} className={i === bestIdx ? 'comparison-best' : ''}>
                          {row.format(s[row.key])}
                        </td>
                      ))}
                    </tr>
                  );
                })}
                {/* Price trend indicator */}
                <tr>
                  <td className="comparison-label-col">{tt('Trend (beta)')}</td>
                  {comparedStocks.map((s, i) => {
                    const beta = asNumber(s.beta);
                    return (
                      <td key={i}>
                        {beta >= 1 ? (
                          <span className="trend-up"><FiTrendingUp /> {tt('Aggressive')}</span>
                        ) : beta > 0 ? (
                          <span className="trend-down"><FiTrendingDown /> {tt('Defensive')}</span>
                        ) : (
                          <span>—</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}

      {selectedStocks.length === 1 && comparedStocks.length <= 1 && (
        <p className="comparison-hint">
          {comparedStocks.length === 0
            ? tt('Loading stock data...')
            : tt('Add at least one more stock to compare.')}
        </p>
      )}

      {selectedStocks.length === 0 && (
        <p className="comparison-hint">{tt('Search and select stocks above to begin comparing.')}</p>
      )}
    </div>
  );
};

export default StockComparison;
