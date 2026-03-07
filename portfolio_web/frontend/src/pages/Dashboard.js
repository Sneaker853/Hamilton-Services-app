import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import {
  ResponsiveContainer,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  AreaChart,
  Area,
  Line,
} from 'recharts';
import {
  FiArrowRight,
  FiBarChart2,
  FiBriefcase,
  FiDollarSign,
  FiTrendingDown,
  FiTrendingUp,
} from 'react-icons/fi';
import './Dashboard.css';

const PERIODS = [
  { key: '1M', points: 8, benchmarkReturn: 0.012 },
  { key: '3M', points: 10, benchmarkReturn: 0.03 },
  { key: '6M', points: 12, benchmarkReturn: 0.05 },
  { key: '1Y', points: 12, benchmarkReturn: 0.09 },
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

const buildTrendSeries = (periodKey, totalInvested, totalCurrentValue) => {
  const period = PERIODS.find((item) => item.key === periodKey) || PERIODS[1];
  const labels = Array.from({ length: period.points }, (_, index) => `${index + 1}`);
  const start = totalInvested > 0 ? totalInvested : Math.max(totalCurrentValue, 1);
  const end = totalCurrentValue > 0 ? totalCurrentValue : start;
  const benchmarkEnd = start * (1 + period.benchmarkReturn);

  return labels.map((label, index) => {
    const progress = period.points === 1 ? 1 : index / (period.points - 1);
    const smooth = progress + Math.sin(progress * Math.PI) * 0.04;
    const portfolioValue = start + (end - start) * smooth;
    const benchmarkValue = start + (benchmarkEnd - start) * progress;

    return {
      label,
      portfolio: Math.round(portfolioValue),
      benchmark: Math.round(benchmarkValue),
    };
  });
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

  const trendSeries = useMemo(
    () => buildTrendSeries(period, portfolioMetrics.totalInvested, portfolioMetrics.totalCurrentValue),
    [period, portfolioMetrics.totalInvested, portfolioMetrics.totalCurrentValue]
  );

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
            <span>Total Portfolio Value</span>
            <FiDollarSign />
          </header>
          <strong>{formatCurrency(portfolioMetrics.totalCurrentValue)}</strong>
          <p>{formatPercent(portfolioMetrics.totalGainLossPct)} expected annual</p>
        </article>

        <article className="dashboard-glass dashboard-kpi-card">
          <header>
            <span>Expected Gain/Loss</span>
            {portfolioMetrics.totalGainLoss >= 0 ? <FiTrendingUp /> : <FiTrendingDown />}
          </header>
          <strong>{formatCurrency(portfolioMetrics.totalGainLoss)}</strong>
          <p>{formatPercent(portfolioMetrics.avgExpectedReturn)} annual return</p>
        </article>

        <article className="dashboard-glass dashboard-kpi-card">
          <header>
            <span>Active Portfolios</span>
            <FiBriefcase />
          </header>
          <strong>{portfolioMetrics.activeCount}</strong>
          <p>{portfolioMetrics.totalHoldings.toLocaleString()} total holdings</p>
        </article>

        <article className="dashboard-glass dashboard-kpi-card">
          <header>
            <span>vs S&P 500</span>
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
            <p>Portfolio vs S&P 500 benchmark</p>
          </div>
          <div className="dashboard-period-controls">
            {PERIODS.map((item) => (
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
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trendSeries} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="portfolioGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(100, 116, 139, 0.2)" strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <YAxis
                tick={{ fontSize: 11, fill: '#64748b' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(value) => `$${Math.round(value / 1000)}k`}
              />
              <Tooltip
                contentStyle={{
                  background: 'rgba(13, 19, 33, 0.95)',
                  border: '1px solid rgba(100, 116, 139, 0.25)',
                  borderRadius: 10,
                  color: '#e2e8f0',
                }}
                formatter={(value) => formatCurrency(value)}
              />
              <Area
                type="monotone"
                dataKey="portfolio"
                stroke="#22d3ee"
                strokeWidth={2}
                fill="url(#portfolioGrad)"
                dot={false}
              />
              <Line type="monotone" dataKey="benchmark" stroke="#64748b" strokeWidth={1.6} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
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
                  <th>Allocation</th>
                  <th>Value</th>
                  <th>Exp. Return</th>
                </tr>
              </thead>
              <tbody>
                {topHoldings.length === 0 && (
                  <tr>
                    <td colSpan={4} className="dashboard-empty-cell">No holdings yet.</td>
                  </tr>
                )}
                {topHoldings.map((holding) => (
                  <tr key={holding.ticker}>
                    <td>{holding.ticker}</td>
                    <td>{holding.allocationPct.toFixed(1)}%</td>
                    <td>{formatCurrency(holding.value)}</td>
                    <td className={holding.expectedReturnPct >= 0 ? 'positive' : 'negative'}>
                      {formatPercent(holding.expectedReturnPct, 1)}
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
              <p className="dashboard-muted">No recent activity. Start by creating a portfolio.</p>
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
                <span>{item.source || 'manual'}</span>
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
                <p>Expected Return</p>
                <strong className={item.expectedReturnPct >= 0 ? 'positive' : 'negative'}>
                  {formatPercent(item.expectedReturnPct, 1)}
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
