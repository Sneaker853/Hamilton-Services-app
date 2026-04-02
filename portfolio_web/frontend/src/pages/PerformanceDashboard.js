import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { FiTrendingUp, FiChevronDown } from 'react-icons/fi';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, ReferenceLine, CartesianGrid } from 'recharts';
import { useLanguage } from '../components';
import './PerformanceDashboard.css';

export default function PerformanceDashboard({ apiBase }) {
  const { tt } = useLanguage();
  const [portfolios, setPortfolios] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [perfData, setPerfData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [perfLoading, setPerfLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchPortfolios = useCallback(async () => {
    try {
      const res = await axios.get(`${apiBase}/portfolios`);
      const list = res.data.portfolios || [];
      setPortfolios(list);
      if (list.length > 0 && !selectedId) setSelectedId(list[0].id);
    } catch (err) {
      if (err.response?.status === 401) setError('Please log in to view performance.');
      else setError('Failed to load portfolios.');
    } finally {
      setLoading(false);
    }
  }, [apiBase, selectedId]);

  useEffect(() => { fetchPortfolios(); }, [fetchPortfolios]);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    const fetchPerf = async () => {
      setPerfLoading(true);
      try {
        const res = await axios.get(`${apiBase}/portfolio-performance/${selectedId}`);
        if (!cancelled) setPerfData(res.data);
      } catch {
        if (!cancelled) setPerfData(null);
      } finally {
        if (!cancelled) setPerfLoading(false);
      }
    };
    fetchPerf();
    return () => { cancelled = true; };
  }, [apiBase, selectedId]);

  const fmt = (v) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

  // Compute Y-axis domain that zooms into the actual data range
  const yDomain = useMemo(() => {
    if (!perfData?.series?.length) return [0, 100];
    let min = Infinity, max = -Infinity;
    for (const pt of perfData.series) {
      const a = pt.actual ?? Infinity;
      const p = pt.projected ?? Infinity;
      if (a < min) min = a;
      if (p < min) min = p;
      if (a > max) max = a;
      if (p > max) max = p;
    }
    // Also include the investment amount in the range
    const inv = perfData.investment_amount || 0;
    if (inv < min) min = inv;
    if (inv > max) max = inv;
    const padding = Math.max((max - min) * 0.15, max * 0.01);
    return [Math.floor(min - padding), Math.ceil(max + padding)];
  }, [perfData]);

  // Smart Y-axis tick formatter based on range
  const formatYAxis = useCallback((v) => {
    const range = yDomain[1] - yDomain[0];
    if (range < 2000) return `$${Number(v).toLocaleString()}`;
    if (range < 20000) return `$${(v / 1000).toFixed(1)}k`;
    return `$${(v / 1000).toFixed(0)}k`;
  }, [yDomain]);

  // Gain/loss since inception
  const gainLoss = perfData ? perfData.current_actual_value - perfData.investment_amount : 0;

  if (loading) return <div className="perf-page"><div className="perf-loading">{tt('Loading portfolios...')}</div></div>;
  if (error) return <div className="perf-page"><div className="perf-error">{error}</div></div>;
  if (portfolios.length === 0) return (
    <div className="perf-page">
      <div className="perf-empty"> 
        <FiTrendingUp size={48} />
        <p>{tt('No saved portfolios yet.')}</p>
        <p>{tt('Save a portfolio from the Optimizer or Builder to track its performance.')}</p>
      </div>
    </div>
  );

  return (
    <div className="perf-page">
      <div className="perf-header">
        <h2><FiTrendingUp /> {tt('Performance Dashboard')}</h2>
        <div className="perf-selector">
          <FiChevronDown className="perf-selector-icon" />
          <select value={selectedId || ''} onChange={e => setSelectedId(parseInt(e.target.value))}>
            {portfolios.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      </div>

      {perfLoading && <div className="perf-loading">{tt('Loading performance data...')}</div>}

      {perfData && !perfLoading && (
        <>
          <div className="perf-stats">
            <div className="perf-stat-card">
              <div className="perf-stat-label">{tt('Invested')}</div>
              <div className="perf-stat-value">{fmt(perfData.investment_amount)}</div>
            </div>
            <div className={`perf-stat-card ${perfData.total_return_pct >= 0 ? 'positive' : 'negative'}`}> 
              <div className="perf-stat-label">{tt('Current Value')}</div>
              <div className="perf-stat-value">{fmt(perfData.current_actual_value)}</div>
              <div className={`perf-stat-delta ${gainLoss >= 0 ? 'up' : 'down'}`}>
                {gainLoss >= 0 ? '+' : ''}{fmt(gainLoss)}
              </div>
            </div>
            <div className={`perf-stat-card ${perfData.total_return_pct >= 0 ? 'positive' : 'negative'}`}>
              <div className="perf-stat-label">{tt('Actual Return')}</div>
              <div className="perf-stat-value">{perfData.total_return_pct >= 0 ? '+' : ''}{perfData.total_return_pct.toFixed(2)}%</div>
            </div>
            <div className="perf-stat-card"> 
              <div className="perf-stat-label">{tt('Model Estimate')}</div>
              <div className="perf-stat-value">{perfData.projected_return_pct >= 0 ? '+' : ''}{perfData.projected_return_pct.toFixed(2)}%</div>
              <div className="perf-stat-note">{tt('FF5 projection')}</div>
            </div>
            <div className={`perf-stat-card ${perfData.alpha_pct >= 0 ? 'positive' : 'negative'}`}>
              <div className="perf-stat-label">{tt('Alpha')}</div>
              <div className="perf-stat-value">{perfData.alpha_pct >= 0 ? '+' : ''}{perfData.alpha_pct.toFixed(2)}%</div>
            </div>
          </div>

          <div className="perf-chart-card">
            <h3>{tt('Actual vs Model Projection')}</h3>
            <p className="perf-chart-sub">{perfData.days_tracked} {tt('days tracked since')} {perfData.created_date}</p>
            <p className="perf-chart-note">
              {tt('The dashed line shows the theoretical growth path based on expected returns from the factor model, not a guarantee.')} 
              {tt("The solid line shows your portfolio's real market performance.")}
            </p>
            <ResponsiveContainer width="100%" height={380}>
              <LineChart data={perfData.series} margin={{ top: 10, right: 20, left: 15, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,0.15)" />
                <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={40} tickFormatter={d => { try { return new Date(d + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); } catch { return d; } }} />
                <YAxis
                  domain={yDomain}
                  tick={{ fill: '#888', fontSize: 11 }}
                  tickFormatter={formatYAxis}
                  width={70}
                />
                <ReferenceLine
                  y={perfData.investment_amount}
                  stroke="rgba(148,163,184,0.5)"
                  strokeDasharray="4 4"
                  label={{ value: tt('Invested'), fill: '#64748b', fontSize: 10, position: 'insideTopRight' }}
                />
                <Tooltip
                  contentStyle={{ background: '#1e2330', border: '1px solid #333', borderRadius: 8 }}
                  labelStyle={{ color: '#b0bec5' }}
                  formatter={(v, name) => [fmt(v), name]}
                />
                <Legend />
                <Line type="monotone" dataKey="actual" name={tt('Actual')} stroke="#00bcd4" strokeWidth={2.5} dot={false} />
                <Line type="monotone" dataKey="projected" name={tt('Model Estimate')} stroke="#ff9800" strokeWidth={1.5} strokeDasharray="6 3" dot={false} opacity={0.7} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
