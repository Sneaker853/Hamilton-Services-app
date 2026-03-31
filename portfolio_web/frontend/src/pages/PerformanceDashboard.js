import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { FiTrendingUp, FiChevronDown } from 'react-icons/fi';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import './PerformanceDashboard.css';

export default function PerformanceDashboard({ apiBase }) {
  const [portfolios, setPortfolios] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [perfData, setPerfData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [perfLoading, setPerfLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchPortfolios = useCallback(async () => {
    try {
      const res = await axios.get(`${apiBase}/api/portfolios`);
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
        const res = await axios.get(`${apiBase}/api/portfolio-performance/${selectedId}`);
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

  if (loading) return <div className="perf-page"><div className="perf-loading">Loading portfolios...</div></div>;
  if (error) return <div className="perf-page"><div className="perf-error">{error}</div></div>;
  if (portfolios.length === 0) return (
    <div className="perf-page">
      <div className="perf-empty">
        <FiTrendingUp size={48} />
        <p>No saved portfolios yet.</p>
        <p>Save a portfolio from the Optimizer or Builder to track its performance.</p>
      </div>
    </div>
  );

  const fmt = (v) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

  return (
    <div className="perf-page">
      <div className="perf-header">
        <h2><FiTrendingUp /> Performance Dashboard</h2>
        <div className="perf-selector">
          <FiChevronDown className="perf-selector-icon" />
          <select value={selectedId || ''} onChange={e => setSelectedId(parseInt(e.target.value))}>
            {portfolios.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      </div>

      {perfLoading && <div className="perf-loading">Loading performance data...</div>}

      {perfData && !perfLoading && (
        <>
          <div className="perf-stats">
            <div className="perf-stat-card">
              <div className="perf-stat-label">Invested</div>
              <div className="perf-stat-value">{fmt(perfData.investment_amount)}</div>
            </div>
            <div className="perf-stat-card">
              <div className="perf-stat-label">Current Value</div>
              <div className="perf-stat-value">{fmt(perfData.current_actual_value)}</div>
            </div>
            <div className={`perf-stat-card ${perfData.total_return_pct >= 0 ? 'positive' : 'negative'}`}>
              <div className="perf-stat-label">Actual Return</div>
              <div className="perf-stat-value">{perfData.total_return_pct >= 0 ? '+' : ''}{perfData.total_return_pct.toFixed(2)}%</div>
            </div>
            <div className="perf-stat-card">
              <div className="perf-stat-label">Projected Return</div>
              <div className="perf-stat-value">{perfData.projected_return_pct >= 0 ? '+' : ''}{perfData.projected_return_pct.toFixed(2)}%</div>
            </div>
            <div className={`perf-stat-card ${perfData.alpha_pct >= 0 ? 'positive' : 'negative'}`}>
              <div className="perf-stat-label">Alpha</div>
              <div className="perf-stat-value">{perfData.alpha_pct >= 0 ? '+' : ''}{perfData.alpha_pct.toFixed(2)}%</div>
            </div>
          </div>

          <div className="perf-chart-card">
            <h3>Actual vs Projected Value</h3>
            <p className="perf-chart-sub">{perfData.days_tracked} days tracked since {perfData.created_date}</p>
            <ResponsiveContainer width="100%" height={350}>
              <AreaChart data={perfData.series} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradActual" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00bcd4" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#00bcd4" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradProjected" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ff9800" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#ff9800" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fill: '#888', fontSize: 11 }} tickFormatter={d => d.slice(5)} />
                <YAxis tick={{ fill: '#888', fontSize: 11 }} tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ background: '#1e2330', border: '1px solid #333', borderRadius: 8 }}
                  labelStyle={{ color: '#b0bec5' }}
                  formatter={v => fmt(v)}
                />
                <Legend />
                <Area type="monotone" dataKey="actual" name="Actual" stroke="#00bcd4" fill="url(#gradActual)" strokeWidth={2} />
                <Area type="monotone" dataKey="projected" name="Projected" stroke="#ff9800" fill="url(#gradProjected)" strokeWidth={2} strokeDasharray="5 3" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
