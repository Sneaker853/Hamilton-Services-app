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
import { HelpIcon, useLanguage } from '../components';
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

  const currentValue = holdingsValue > 0 ? holdingsValue : investmentAmount;
  const actualGain = currentValue - investmentAmount;
  const actualGainPct = investmentAmount > 0 ? (actualGain / investmentAmount) * 100 : 0;
  const estimatedGain = investmentAmount * (expectedReturnPct / 100);
  const estimatedCurrentValue = investmentAmount + estimatedGain;

  return {
    ...portfolio,
    holdings,
    investmentAmount,
    currentValue,
    actualGain,
    actualGainPct,
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
  const { tt } = useLanguage();
  const [, setStats] = useState(null);
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
    const fallbackCurrentValue = normalizedPortfolios.reduce((sum, portfolio) => sum + portfolio.currentValue, 0);
    const projectedCurrentValue = normalizedPortfolios.reduce((sum, portfolio) => sum + portfolio.estimatedCurrentValue, 0);
    const avgExpectedReturn = activeCount > 0
      ? normalizedPortfolios.reduce((sum, portfolio) => sum + portfolio.expectedReturnPct, 0) / activeCount
      : 0;
    const totalHoldings = normalizedPortfolios.reduce((sum, portfolio) => sum + portfolio.holdings.length, 0);

    return {
      activeCount,
      totalInvested,
      fallbackCurrentValue,
      projectedCurrentValue,
      avgExpectedReturn,
      totalHoldings,
    };
  }, [normalizedPortfolios]);

  const totalCurrentValue = perfData?.current_value ?? portfolioMetrics.fallbackCurrentValue;
  const totalGainLoss = totalCurrentValue - portfolioMetrics.totalInvested;
  const totalGainLossPct = perfData?.portfolio_return_pct
    ?? (portfolioMetrics.totalInvested > 0 ? (totalGainLoss / portfolioMetrics.totalInvested) * 100 : 0);

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
            <p className="dashboard-overline">{tt('Welcome back')}</p>
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
          <p className="dashboard-overline">{tt('Welcome back')}</p>
          <h2 className="dashboard-title">{tt('Portfolio Command Center')}</h2>
        </div>
        <p className="dashboard-updated">{tt('Last updated')}: {new Date().toLocaleString()}</p>
      </div>

      <div className="dashboard-kpis-grid">
        <article className="dashboard-glass dashboard-kpi-card">
          <header>
            <span>{tt('Current Portfolio Value')} <HelpIcon text="The combined market value of all your saved portfolios using the latest available prices. This reflects actual tracked value, not a projection." /></span>
            <FiDollarSign />
          </header>
          <strong>{formatCurrency(totalCurrentValue)}</strong>
          <p>{tt('Invested')}: {formatCurrency(portfolioMetrics.totalInvested)} · {tt('Model Estimate')}: {formatCurrency(portfolioMetrics.projectedCurrentValue)}</p>
        </article>

        <article className="dashboard-glass dashboard-kpi-card">
          <header>
            <span>{tt('Current Gain/Loss')} <HelpIcon text="Your actual gain or loss versus the amount invested, based on the latest tracked portfolio value." /></span>
            {totalGainLoss >= 0 ? <FiTrendingUp /> : <FiTrendingDown />}
          </header>
          <strong className={totalGainLoss >= 0 ? 'positive' : 'negative'}>{formatCurrency(totalGainLoss)}</strong>
          <p>{formatPercent(totalGainLossPct, 1)} vs invested capital</p>
        </article>

        <article className="dashboard-glass dashboard-kpi-card">
          <header>
            <span>{tt('Active Portfolios')} <HelpIcon text="Number of portfolios you've saved. Each portfolio is a collection of stocks, ETFs, or bonds with specific allocations." /></span>
            <FiBriefcase />
          </header>
          <strong>{portfolioMetrics.activeCount}</strong>
          <p>{portfolioMetrics.totalHoldings.toLocaleString()} total holdings</p>
        </article>

        <article className="dashboard-glass dashboard-kpi-card">
          <header>
            <span>{tt('S&P 500 Return')} <HelpIcon text="Return of SPY, a widely used S&P 500 ETF proxy, over the selected period. It gives you a quick benchmark for how the broader U.S. market performed during the same window." /></span>
            <FiBarChart2 />
          </header>
          <strong className={perfData?.sp500_return_pct >= 0 ? 'positive' : 'negative'}>
            {perfData?.sp500_return_pct != null ? formatPercent(perfData.sp500_return_pct, 1) : 'N/A'}
          </strong>
          <p>{tt('SPY over selected period')} · {tt('Portfolio Return')}: {formatPercent(totalGainLossPct, 1)}</p>
        </article>
      </div>

      <section className="dashboard-glass dashboard-performance-card">
        <div className="dashboard-section-head">
          <div>
            <h3>{tt('Performance')}</h3>
            <p>{tt('Combined saved-portfolio value vs SPY over the selected period')}</p>
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
          {perfLoading && <div className="dashboard-chart-loading">{tt('Loading performance data...')}</div>}
          {!perfLoading && trendSeries.length === 0 && (
            <div className="dashboard-chart-empty">
              <p>{tt('No performance data available. Save a portfolio to start tracking.')}</p>
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
                    try {
                      const date = new Date(d + 'T12:00:00');
                      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                    } catch {
                      return d;
                    }
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
              <h3>{tt('Top Holdings')}</h3>
              <p>{tt('Largest allocations across portfolios')}</p>
            </div>
          </div>
          <div className="dashboard-table-wrap">
            <table className="dashboard-table">
              <thead>
                <tr>
                  <th>{tt('Asset')}</th>
                  <th>{tt('Allocation')} <HelpIcon text="The percentage of your total portfolio value that this holding represents." /></th>
                  <th>{tt('Value')}</th>
                  <th>{tt('Exp. Return')} <HelpIcon text="The annualized return expected for this stock based on factor models. Not a guarantee of future performance." /></th>
                </tr>
              </thead>
              <tbody>
                {topHoldings.length === 0 && (
                  <tr>
                    <td colSpan={4} className="dashboard-empty-cell">
                      {tt('No holdings yet.')} <Link to="/portfolio" className="dashboard-inline-link">{tt('Generate a portfolio')}</Link> {tt('to get started.')}
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
              <h3>{tt('Recent Activity')}</h3>
              <p>{tt('Most recently saved portfolios')}</p>
            </div>
          </div>
          <div className="dashboard-activity-list">
            {savedLoading && <p className="dashboard-muted">{tt('Loading activity...')}</p>}
            {!savedLoading && recentPortfolios.length === 0 && (
              <p className="dashboard-muted">{tt('No recent activity.')} <Link to="/portfolio" className="dashboard-inline-link">{tt('Create your first portfolio')}</Link> {tt('to start tracking.')}</p>
            )}
            {!savedLoading && recentPortfolios.map((item) => (
              <button key={item.id} type="button" className="dashboard-activity-item" onClick={() => openInBuilder(item)}>
                <div>
                  <strong>{item.name}</strong>
                  <span>{new Date(item.created_at).toLocaleDateString()}</span>
                </div>
                <div className="dashboard-activity-value">
                  <em>{formatCurrency(item.currentValue)}</em>
                  <small className={item.currentValue >= item.investmentAmount ? 'positive' : 'negative'}>
                    {item.currentValue >= item.investmentAmount ? '+' : ''}{formatPercent(item.actualGainPct, 1)}
                  </small>
                </div>
              </button>
            ))}
          </div>
        </section>
      </div>

      <section className="dashboard-portfolio-cards">
        <div className="dashboard-section-head">
          <div>
            <h3>{tt('Saved Portfolios')}</h3>
            <p>{tt('Quick access to edit and review')}</p>
          </div>
          <Link to="/portfolio-builder" className="dashboard-link-btn">
            {tt('View All')} <FiArrowRight />
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
                      title={tt('Share portfolio')}
                      onClick={(e) => sharePortfolio(e, item.id)}
                    >
                      <FiShare2 size={14} />
                    </button>
                  )}
                </span>
              </header>
              <div>
                <p>{tt('Holdings')}</p>
                <strong>{item.holdings.length}</strong>
              </div>
              <div>
                <p>{tt('Invested')}</p>
                <strong>{formatCurrency(item.investmentAmount)}</strong>
              </div>
              <div>
                <p>{tt('Current Value')}</p>
                <strong className={item.currentValue >= item.investmentAmount ? 'positive' : 'negative'}>
                  {formatCurrency(item.currentValue)}
                </strong>
              </div>
              <div>
                <p>{tt('Expected Return')} <HelpIcon text="Annualized expected return based on factor model analysis. Positive values suggest the portfolio is projected to grow." /></p>
                <strong className={item.expectedReturnPct >= 0 ? 'positive' : 'negative'}>
                  {item.expectedReturnPct >= 0 ? '▲ ' : '▼ '}{formatPercent(item.expectedReturnPct, 1)}
                </strong>
              </div>
            </button>
          ))}
          {recentPortfolios.length === 0 && !savedLoading && (
            <div className="dashboard-glass dashboard-empty-card">
              <p>{tt('No portfolios yet. Build one with optimizer or builder.')}</p>
              <div>
                <Link to="/portfolio" className="dashboard-link-btn">{tt('Use Optimizer')}</Link>
                <Link to="/portfolio-builder" className="dashboard-link-btn alt">{tt('Manual Build')}</Link>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
