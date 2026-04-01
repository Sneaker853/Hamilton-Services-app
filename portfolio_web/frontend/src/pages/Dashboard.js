import React, { useEffect, useMemo, useState, useCallback } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import {
  ResponsiveContainer,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  LineChart,
  Line,
  ReferenceLine,
} from 'recharts';
import {
  FiArrowRight,
  FiBarChart2,
  FiBriefcase,
  FiDollarSign,
  FiShare2,
  FiTrendingDown,
  FiTrendingUp,
} from 'react-icons/fi';
import { HelpIcon } from '../components';
import './Dashboard.css';

const PERIOD_MONTHS = [
  { key: '1M', months: 1 },
  { key: '3M', months: 3 },
  { key: '6M', months: 6 },
  { key: '1Y', months: 12 },
];

const asNumber = (value, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const formatCurrency = (value) => {
  const amount = asNumber(value, 0);
  return amount.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  });
};

const formatPercent = (value, digits = 2) => {
  const amount = asNumber(value, 0);
  const sign = amount > 0 ? '+' : '';
  return `${sign}${amount.toFixed(digits)}%`;
};

const normalizeSavedPortfolio = (portfolio) => {
  const holdings = Array.isArray(portfolio?.data?.holdings) ? portfolio.data.holdings : [];
  const holdingsValue = holdings.reduce((sum, holding) => sum + asNumber(holding?.value), 0);
  const investmentAmount = asNumber(portfolio?.data?.investment_amount, holdingsValue);

  let expectedReturnPct = 0;
  if (holdings.length > 0) {
    const totalHoldingValue = holdings.reduce((sum, holding) => {
      const value = asNumber(holding?.value);
      if (value > 0) return sum + value;
      return sum + (investmentAmount * asNumber(holding?.weight)) / 100;
    }, 0);

    if (totalHoldingValue > 0) {
      const weightedReturn = holdings.reduce((sum, holding) => {
        const holdingValue = asNumber(holding?.value) > 0
          ? asNumber(holding?.value)
          : (investmentAmount * asNumber(holding?.weight)) / 100;
        return sum + holdingValue * asNumber(holding?.expected_return);
      }, 0);
      expectedReturnPct = weightedReturn / totalHoldingValue;
    }
  }

  const estimatedGain = investmentAmount * (expectedReturnPct / 100);
  const estimatedCurrentValue = investmentAmount + estimatedGain;

  return {
    ...portfolio,
    holdings,
    investmentAmount,
    expectedReturnPct,
    estimatedGain,
    estimatedCurrentValue,
  };
};

const aggregateTopHoldings = (portfolios, totalInvested) => {
  const map = new Map();

  portfolios.forEach((portfolio) => {
    portfolio.holdings.forEach((holding) => {
      const ticker = String(holding?.ticker || '').trim();
      if (!ticker) return;

      const value = asNumber(holding?.value) > 0
        ? asNumber(holding?.value)
        : (portfolio.investmentAmount * asNumber(holding?.weight)) / 100;
      const expectedReturnPct = asNumber(holding?.expected_return);

      const existing = map.get(ticker) || {
        ticker,
        name: holding?.name || ticker,
        value: 0,
        weightedExpectedReturn: 0,
      };

      existing.value += value;
      existing.weightedExpectedReturn += value * expectedReturnPct;
      map.set(ticker, existing);
    });
  });

  return Array.from(map.values())
    .map((item) => ({
      ...item,
      allocationPct: totalInvested > 0 ? (item.value / totalInvested) * 100 : 0,
      expectedReturnPct: item.value > 0 ? item.weightedExpectedReturn / item.value : 0,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);
};

const Dashboard = ({ apiBase }) => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [savedPortfolios, setSavedPortfolios] = useState([]);
  const [savedLoading, setSavedLoading] = useState(false);
  const [period, setPeriod] = useState('6M');
  const [perfData, setPerfData] = useState(null);
  const [perfLoading, setPerfLoading] = useState(false);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await axios.get(`${apiBase}/stocks/summary`);
        setStats(response.data);
      } catch (error) {
        console.error('Error fetching stats:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, [apiBase]);

  useEffect(() => {
    const fetchSaved = async () => {
      const authUser = localStorage.getItem('authUser');
      if (!authUser) return;

      setSavedLoading(true);
      try {
        const response = await axios.get(`${apiBase}/portfolios`, { withCredentials: true });
        setSavedPortfolios(response.data?.portfolios || []);
      } catch (error) {
        console.error('Error fetching saved portfolios:', error);
      } finally {
        setSavedLoading(false);
      }
    };

    fetchSaved();
  }, [apiBase]);

  const fetchPerformance = useCallback(async (months) => {
    const authUser = localStorage.getItem('authUser');
    if (!authUser) return;
    setPerfLoading(true);
    try {
      const res = await axios.get(`${apiBase}/dashboard-performance`, {
        params: { months },
        withCredentials: true,
      });
      setPerfData(res.data);
    } catch (err) {
      console.error('Error fetching dashboard performance:', err);
      setPerfData(null);
    } finally {
      setPerfLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    const pm = PERIOD_MONTHS.find((p) => p.key === period);
    fetchPerformance(pm ? pm.months : 6);
  }, [period, fetchPerformance]);

  const normalizedPortfolios = useMemo(
    () => savedPortfolios.map(normalizeSavedPortfolio),
    [savedPortfolios]
  );

  const portfolioMetrics = useMemo(() => {
    const activeCount = normalizedPortfolios.length;
    const totalInvested = normalizedPortfolios.reduce((sum, portfolio) => sum + portfolio.investmentAmount, 0);
    const totalCurrentValue = normalizedPortfolios.reduce((sum, portfolio) => sum + portfolio.estimatedCurrentValue, 0);
    const totalGainLoss = totalCurrentValue - totalInvested;
    const totalGainLossPct = totalInvested > 0 ? (totalGainLoss / totalInvested) * 100 : 0;
    const avgExpectedReturn = activeCount > 0
      ? normalizedPortfolios.reduce((sum, portfolio) => sum + portfolio.expectedReturnPct, 0) / activeCount
      : 0;
    const totalHoldings = normalizedPortfolios.reduce((sum, portfolio) => sum + portfolio.holdings.length, 0);

    return {
      activeCount,
      totalInvested,
      totalCurrentValue,
      totalGainLoss,
      totalGainLossPct,
      avgExpectedReturn,
      totalHoldings,
    };
  }, [normalizedPortfolios]);

  const trendSeries = perfData?.series || [];

  const topHoldings = useMemo(
    () => aggregateTopHoldings(normalizedPortfolios, portfolioMetrics.totalInvested),
    [normalizedPortfolios, portfolioMetrics.totalInvested]
  );

  const recentPortfolios = useMemo(
    () => [...normalizedPortfolios]
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      .slice(0, 6),
    [normalizedPortfolios]
  );

  const openInBuilder = (portfolio) => {
    localStorage.setItem('builderDraftPortfolio', JSON.stringify({
      name: portfolio.name,
      investment_amount: portfolio.data?.investment_amount,
      holdings: portfolio.data?.holdings || [],
    }));
    window.location.href = '/portfolio-builder';
  };

  const sharePortfolio = async (e, portfolioId) => {
    e.stopPropagation();
    try {
      const csrfToken = document.cookie.split('; ').find(c => c.startsWith('csrf_token='))?.split('=')[1];
      const response = await axios.post(
        `${apiBase}/portfolios/${portfolioId}/share`,
        {},
        { withCredentials: true, headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {} }
      );
      const token = response.data?.share_token;
      if (token) {
        const shareUrl = `${window.location.origin}/shared/${token}`;
        await navigator.clipboard.writeText(shareUrl);
        alert('Share link copied to clipboard!');
      }
    } catch (err) {
      console.error('Error sharing portfolio:', err);
      alert('Could not create share link. Please try again.');
    }
  };

  if (loading) {
    return (
      <div className="dashboard-root">
        <div className="dashboard-header">
          <div>
            <p className="dashboard-overline">Welcome back</p>
            <h2 className="dashboard-title">Investor</h2>
          </div>
        </div>
        <div className="dashboard-kpis-grid">
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="dashboard-glass dashboard-kpi-card skeleton" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-root">
      <div className="dashboard-header">
        <div>
          <p className="dashboard-overline">Welcome back</p>
          <h2 className="dashboard-title">Portfolio Command Center</h2>
        </div>
        <p className="dashboard-updated">Last updated: {new Date().toLocaleString()}</p>
      </div>

      <div className="dashboard-kpis-grid">
        <article className="dashboard-glass dashboard-kpi-card">
          <header>
            <span>Total Portfolio Value <HelpIcon text="The estimated current value of all your saved portfolios combined, based on original investment plus expected gains." /></span>
            <FiDollarSign />
          </header>
          <strong>{formatCurrency(portfolioMetrics.totalCurrentValue)}</strong>
          <p>{formatPercent(portfolioMetrics.totalGainLossPct)} expected annual</p>
        </article>

        <article className="dashboard-glass dashboard-kpi-card">
          <header>
            <span>Expected Gain/Loss <HelpIcon text="Projected annual profit or loss across all your portfolios, based on the Fama-French 5-factor model's expected returns." /></span>
            {portfolioMetrics.totalGainLoss >= 0 ? <FiTrendingUp /> : <FiTrendingDown />}
          </header>
          <strong>{formatCurrency(portfolioMetrics.totalGainLoss)}</strong>
          <p>{formatPercent(portfolioMetrics.avgExpectedReturn)} annual return</p>
        </article>

        <article className="dashboard-glass dashboard-kpi-card">
          <header>
            <span>Active Portfolios <HelpIcon text="Number of portfolios you've saved. Each portfolio is a collection of stocks, ETFs, or bonds with specific allocations." /></span>
            <FiBriefcase />
          </header>
          <strong>{portfolioMetrics.activeCount}</strong>
          <p>{portfolioMetrics.totalHoldings.toLocaleString()} total holdings</p>
        </article>

        <article className="dashboard-glass dashboard-kpi-card">
          <header>
            <span>vs S&P 500 <HelpIcon text="How your portfolios' expected return compares to the S&P 500's historical average of ~9% annually. Positive means outperforming the market benchmark." /></span>
            <FiBarChart2 />
          </header>
          <strong>{formatPercent(portfolioMetrics.avgExpectedReturn - 9, 1)}</strong>
          <p>Market P/E {stats?.statistics?.avg_pe?.toFixed(1) || 'N/A'}</p>
        </article>
      </div>

      <section className="dashboard-glass dashboard-performance-card">
        <div className="dashboard-section-head">
          <div>
            <h3>Performance</h3>
            <p>Combined portfolio value vs S&P 500 (SPY)</p>
          </div>
          <div className="dashboard-period-controls">
            {PERIOD_MONTHS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={period === item.key ? 'active' : ''}
                onClick={() => setPeriod(item.key)}
              >
                {item.key}
              </button>
            ))}
          </div>
        </div>

        <div className="dashboard-chart-wrap">
          {perfLoading && <div className="dashboard-chart-loading">Loading performance data...</div>}
          {!perfLoading && trendSeries.length === 0 && (
            <div className="dashboard-chart-empty">
              <p>No performance data available. Save a portfolio to start tracking.</p>
            </div>
          )}
          {!perfLoading && trendSeries.length > 0 && (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendSeries} margin={{ top: 8, right: 12, left: 10, bottom: 0 }}>
                <CartesianGrid stroke="rgba(100, 116, 139, 0.15)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(d) => {
                    if (!d) return '';
                    const parts = d.split('-');
                    return parts.length >= 2 ? `${parts[1]}/${parts[2] || ''}` : d;
                  }}
                  interval="preserveStartEnd"
                  minTickGap={40}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => {
                    if (v >= 1000000) return `$${(v / 1000000).toFixed(1)}M`;
                    if (v >= 1000) return `$${(v / 1000).toFixed(0)}k`;
                    return `$${v}`;
                  }}
                  domain={['auto', 'auto']}
                  width={65}
                />
                {perfData?.total_invested > 0 && (
                  <ReferenceLine
                    y={perfData.total_invested}
                    stroke="rgba(148,163,184,0.4)"
                    strokeDasharray="4 4"
                    label={{ value: 'Invested', fill: '#64748b', fontSize: 10, position: 'insideTopRight' }}
                  />
                )}
                <Tooltip
                  contentStyle={{
                    background: 'rgba(13, 19, 33, 0.95)',
                    border: '1px solid rgba(100, 116, 139, 0.25)',
                    borderRadius: 10,
                    color: '#e2e8f0',
                  }}
                  formatter={(value, name) => [formatCurrency(value), name === 'portfolio' ? 'Your Portfolios' : 'S&P 500']}
                  labelFormatter={(d) => d}
                />
                <Line type="monotone" dataKey="portfolio" name="portfolio" stroke="#22d3ee" strokeWidth={2.5} dot={false} />
                <Line type="monotone" dataKey="sp500" name="sp500" stroke="#64748b" strokeWidth={1.8} dot={false} strokeDasharray="5 3" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
        {perfData && !perfLoading && trendSeries.length > 0 && (
          <div className="dashboard-perf-summary">
            <span className={perfData.portfolio_return_pct >= 0 ? 'positive' : 'negative'}>
              Portfolio: {formatPercent(perfData.portfolio_return_pct)}
            </span>
            <span className={perfData.sp500_return_pct >= 0 ? 'positive' : 'negative'}>
              S&P 500: {formatPercent(perfData.sp500_return_pct)}
            </span>
            <span className={(perfData.portfolio_return_pct - perfData.sp500_return_pct) >= 0 ? 'positive' : 'negative'}>
              Alpha: {formatPercent(perfData.portfolio_return_pct - perfData.sp500_return_pct)}
            </span>
          </div>
        )}
      </section>

      <div className="dashboard-two-col">
        <section className="dashboard-glass">
          <div className="dashboard-section-head">
            <div>
              <h3>Top Holdings</h3>
              <p>Largest allocations across portfolios</p>
            </div>
          </div>
          <div className="dashboard-table-wrap">
            <table className="dashboard-table">
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Allocation <HelpIcon text="The percentage of your total portfolio value that this holding represents." /></th>
                  <th>Value</th>
                  <th>Exp. Return <HelpIcon text="The annualized return expected for this stock based on factor models. Not a guarantee of future performance." /></th>
                </tr>
              </thead>
              <tbody>
                {topHoldings.length === 0 && (
                  <tr>
                    <td colSpan={4} className="dashboard-empty-cell">
                      No holdings yet. <Link to="/portfolio" className="dashboard-inline-link">Generate a portfolio</Link> to get started.
                    </td>
                  </tr>
                )}
                {topHoldings.map((holding) => (
                  <tr key={holding.ticker}>
                    <td>{holding.ticker}</td>
                    <td>{holding.allocationPct.toFixed(1)}%</td>
                    <td>{formatCurrency(holding.value)}</td>
                    <td className={holding.expectedReturnPct >= 0 ? 'positive' : 'negative'}>
                      {holding.expectedReturnPct >= 0 ? '▲ ' : '▼ '}{formatPercent(holding.expectedReturnPct, 1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="dashboard-glass">
          <div className="dashboard-section-head">
            <div>
              <h3>Recent Activity</h3>
              <p>Most recently saved portfolios</p>
            </div>
          </div>
          <div className="dashboard-activity-list">
            {savedLoading && <p className="dashboard-muted">Loading activity…</p>}
            {!savedLoading && recentPortfolios.length === 0 && (
              <p className="dashboard-muted">No recent activity. <Link to="/portfolio" className="dashboard-inline-link">Create your first portfolio</Link> to start tracking.</p>
            )}
            {!savedLoading && recentPortfolios.map((item) => (
              <button key={item.id} type="button" className="dashboard-activity-item" onClick={() => openInBuilder(item)}>
                <div>
                  <strong>{item.name}</strong>
                  <span>{new Date(item.created_at).toLocaleDateString()}</span>
                </div>
                <em>{formatCurrency(item.investmentAmount)}</em>
              </button>
            ))}
          </div>
        </section>
      </div>

      <section className="dashboard-portfolio-cards">
        <div className="dashboard-section-head">
          <div>
            <h3>Saved Portfolios</h3>
            <p>Quick access to edit and review</p>
          </div>
          <Link to="/portfolio-builder" className="dashboard-link-btn">
            View All <FiArrowRight />
          </Link>
        </div>
        <div className="dashboard-cards-grid">
          {recentPortfolios.slice(0, 6).map((item) => (
            <button
              key={item.id}
              className="dashboard-glass dashboard-portfolio-card"
              type="button"
              onClick={() => openInBuilder(item)}
            >
              <header>
                <strong>{item.name}</strong>
                <span className="dashboard-card-header-actions">
                  <span>{item.source || 'manual'}</span>
                  {localStorage.getItem('authUser') && (
                    <button
                      type="button"
                      className="dashboard-share-btn"
                      title="Share portfolio"
                      onClick={(e) => sharePortfolio(e, item.id)}
                    >
                      <FiShare2 size={14} />
                    </button>
                  )}
                </span>
              </header>
              <div>
                <p>Holdings</p>
                <strong>{item.holdings.length}</strong>
              </div>
              <div>
                <p>Investment</p>
                <strong>{formatCurrency(item.investmentAmount)}</strong>
              </div>
              <div>
                <p>Expected Return <HelpIcon text="Annualized expected return based on factor model analysis. Positive values suggest the portfolio is projected to grow." /></p>
                <strong className={item.expectedReturnPct >= 0 ? 'positive' : 'negative'}>
                  {item.expectedReturnPct >= 0 ? '▲ ' : '▼ '}{formatPercent(item.expectedReturnPct, 1)}
                </strong>
              </div>
            </button>
          ))}
          {recentPortfolios.length === 0 && !savedLoading && (
            <div className="dashboard-glass dashboard-empty-card">
              <p>No portfolios yet. Build one with optimizer or builder.</p>
              <div>
                <Link to="/portfolio" className="dashboard-link-btn">Use Optimizer</Link>
                <Link to="/portfolio-builder" className="dashboard-link-btn alt">Manual Build</Link>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
