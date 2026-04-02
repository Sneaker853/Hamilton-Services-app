import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { FiCrosshair, FiPlus, FiTrash2, FiRefreshCw, FiSearch } from 'react-icons/fi';
import { useLanguage } from '../components';
import './Goals.css';

export default function Goals({ apiBase }) {
  const { tt } = useLanguage();
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formThreshold, setFormThreshold] = useState('5');
  const [formAllocations, setFormAllocations] = useState([{ ticker: '', weight: '' }]);
  const [tickerSuggestions, setTickerSuggestions] = useState([]);
  const [activeAllocIdx, setActiveAllocIdx] = useState(null);
  const tickerSearchTimer = useRef(null);
  const [creating, setCreating] = useState(false);
  const [rebalanceData, setRebalanceData] = useState({});
  const [portfolios, setPortfolios] = useState([]);
  const [formPortfolioId, setFormPortfolioId] = useState('');

  const fetchGoals = useCallback(async () => {
    try {
      const [goalsRes, portRes] = await Promise.all([
        axios.get(`${apiBase}/goals`),
        axios.get(`${apiBase}/portfolios`).catch(() => ({ data: { portfolios: [] } })),
      ]);
      setGoals(goalsRes.data.goals || []);
      setPortfolios(portRes.data.portfolios || []);
      setError('');
    } catch (err) {
      if (err.response?.status === 401) setError(tt('Please log in to manage goals.'));
      else setError(tt('Failed to load goals.'));
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => { fetchGoals(); }, [fetchGoals]);

  const addAllocationRow = () =>
    setFormAllocations(prev => [...prev, { ticker: '', weight: '' }]);

  const updateAllocation = (idx, field, val) => {
    setFormAllocations(prev => prev.map((r, i) => i === idx ? { ...r, [field]: val } : r));
    if (field === 'ticker') {
      clearTimeout(tickerSearchTimer.current);
      if (val.trim().length >= 1) {
        setActiveAllocIdx(idx);
        tickerSearchTimer.current = setTimeout(async () => {
          try {
            const res = await axios.get(`${apiBase}/stocks/search?q=${encodeURIComponent(val.trim())}&limit=6`);
            setTickerSuggestions(res.data?.stocks || res.data || []);
          } catch {
            setTickerSuggestions([]);
          }
        }, 300);
      } else {
        setTickerSuggestions([]);
        setActiveAllocIdx(null);
      }
    }
  };

  const selectTickerSuggestion = (idx, ticker) => {
    setFormAllocations(prev => prev.map((r, i) => i === idx ? { ...r, ticker } : r));
    setTickerSuggestions([]);
    setActiveAllocIdx(null);
  };

  const removeAllocation = (idx) =>
    setFormAllocations(prev => prev.filter((_, i) => i !== idx));

  const handleCreate = async (e) => {
    e.preventDefault();
    const allocations = {};
    for (const row of formAllocations) {
      if (row.ticker.trim() && row.weight) {
        allocations[row.ticker.trim().toUpperCase()] = parseFloat(row.weight);
      }
    }
    if (Object.keys(allocations).length < 1) return;
    try {
      setCreating(true);
      await axios.post(`${apiBase}/goals`, {
        name: formName,
        portfolio_id: formPortfolioId ? parseInt(formPortfolioId) : null,
        target_allocations: allocations,
        rebalance_threshold: parseFloat(formThreshold) || 5,
      });
      setFormName('');
      setFormAllocations([{ ticker: '', weight: '' }]);
      setFormPortfolioId('');
      setShowForm(false);
      fetchGoals();
    } catch (err) {
      setError(err.response?.data?.detail || tt('Failed to create goal.'));
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await axios.delete(`${apiBase}/goals/${id}`);
      setGoals(prev => prev.filter(g => g.id !== id));
    } catch {
      setError(tt('Failed to delete goal.'));
    }
  };

  const fetchRebalance = async (goalId) => {
    try {
      const res = await axios.get(`${apiBase}/goals/${goalId}/rebalance`);
      setRebalanceData(prev => ({ ...prev, [goalId]: res.data }));
    } catch {
      setError(tt('Failed to compute rebalance suggestions.'));
    }
  };

  if (loading) return <div className="goals-page"><div className="goals-loading">{tt('Loading goals...')}</div></div>;
  if (error && goals.length === 0) return <div className="goals-page"><div className="goals-error">{error}</div></div>;

  return (
    <div className="goals-page">
      <div className="goals-header">
        <h2><FiCrosshair /> {tt('Goals & Targets')}</h2>
        <button className="goals-btn goals-add-btn" onClick={() => setShowForm(!showForm)}>
          <FiPlus /> {tt('New Goal')}
        </button>
      </div>

      <div className="goals-explainer">
        <h3>{tt('What are Goals?')}</h3>
        <p>{tt('Goals let you define target portfolio allocations by ticker and weight. The platform then monitors how much your real holdings have drifted from those targets and tells you exactly what to buy or sell to rebalance. Link a goal to any saved portfolio for automatic drift tracking.')}</p>
        <ul>
          <li>{tt('Target Allocations - specify each ticker and its ideal weight (e.g. AAPL 30%, MSFT 20%).')}</li>
          <li>{tt('Drift Threshold - trigger a rebalance alert when any position drifts more than N% from target.')}</li>
          <li>{tt('Check Rebalance - see a trade-by-trade action plan (buy/sell/hold) with dollar amounts and share counts.')}</li>
        </ul>
      </div>

      {error && <div className="goals-error">{error}</div>}

      {showForm && (
        <form className="goals-form" onSubmit={handleCreate}>
          <div className="goals-form-row">
            <input type="text" placeholder={tt('Goal name')} value={formName} onChange={e => setFormName(e.target.value)} required />
            <input type="number" step="0.5" placeholder={tt('Drift threshold %')} value={formThreshold} onChange={e => setFormThreshold(e.target.value)} min="1" max="50" style={{ maxWidth: 140 }} />
            {portfolios.length > 0 && (
              <select value={formPortfolioId} onChange={e => setFormPortfolioId(e.target.value)}>
                <option value="">{tt('No linked portfolio')}</option>
                {portfolios.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            )}
          </div>
          <div className="goals-alloc-label">{tt('Target Allocations (must sum to 100%)')}</div>
          {formAllocations.map((row, i) => (
            <div key={i} className="goals-form-row goals-alloc-row">
              <div className="goals-ticker-wrap">
                <FiSearch className="goals-ticker-icon" size={13} />
                <input
                  type="text"
                  placeholder={tt('Ticker (e.g. AAPL)')}
                  value={row.ticker}
                  onChange={e => updateAllocation(i, 'ticker', e.target.value)}
                  onBlur={() => setTimeout(() => { setTickerSuggestions([]); setActiveAllocIdx(null); }, 150)}
                  maxLength={10}
                  autoComplete="off"
                  className="goals-ticker-input"
                />
                {activeAllocIdx === i && tickerSuggestions.length > 0 && (
                  <div className="goals-ticker-dropdown">
                    {tickerSuggestions.map(s => (
                      <button
                        key={s.ticker}
                        type="button"
                        className="goals-ticker-option"
                        onMouseDown={() => selectTickerSuggestion(i, s.ticker)}
                      >
                        <span className="goals-ticker-sym">{s.ticker}</span>
                        <span className="goals-ticker-name">{s.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <input type="number" step="0.1" placeholder={tt('Weight %')} value={row.weight} onChange={e => updateAllocation(i, 'weight', e.target.value)} min="0" max="100" />
              {formAllocations.length > 1 && (
                <button type="button" className="goals-remove-alloc" onClick={() => removeAllocation(i)}>&times;</button>
              )}
            </div>
          ))}
          <div className="goals-form-actions">
            <button type="button" className="goals-btn" onClick={addAllocationRow}>+ {tt('Add Ticker')}</button>
            <button type="submit" className="goals-btn goals-submit-btn" disabled={creating}>
              {creating ? tt('Creating...') : tt('Create Goal')}
            </button>
          </div>
        </form>
      )}

      {goals.length === 0 ? (
        <div className="goals-empty">
          <FiCrosshair size={48} />
          <p>{tt('No goals yet.')}</p>
          <p>{tt('Set target allocations and get automatic rebalancing suggestions.')}</p>
        </div>
      ) : (
        <div className="goals-list">
          {goals.map(g => {
            const rb = rebalanceData[g.id];
            const alloc = g.target_allocations || {};
            return (
              <div key={g.id} className="goal-card">
                <div className="goal-top">
                  <div>
                    <h3 className="goal-name">{g.name}</h3>
                    {g.portfolio_name && <span className="goal-portfolio">{tt('Linked')}: {g.portfolio_name}</span>}
                    <span className="goal-threshold">{tt('Rebalance if drift >')} {g.rebalance_threshold}%</span>
                  </div>
                  <div className="goal-actions">
                    <button className="goals-btn" onClick={() => fetchRebalance(g.id)} title={tt('Check rebalance')}>
                      <FiRefreshCw size={14} /> {tt('Check')}
                    </button>
                    <button className="goal-delete-btn" onClick={() => handleDelete(g.id)} title={tt('Delete')}>
                      <FiTrash2 size={14} />
                    </button>
                  </div>
                </div>

                <div className="goal-targets">
                  {Object.entries(alloc).map(([t, w]) => (
                    <span key={t} className="goal-chip">{t}: {w}%</span>
                  ))}
                </div>

                {rb && (
                  <div className={`goal-rebalance ${rb.needs_rebalance ? 'needs' : 'ok'}`}>
                    <div className="goal-rb-header">
                      {rb.needs_rebalance
                        ? <span className="goal-rb-badge needs">{tt('Rebalance Needed')}</span>
                        : <span className="goal-rb-badge ok">{tt('On Target')}</span>
                      }
                      <span className="goal-rb-drift">{tt('Max drift')}: {rb.max_drift_pct}%</span>
                    </div>
                    {rb.trades.filter(t => t.action !== 'hold').length > 0 && (
                      <table className="goal-trades-table">
                        <thead>
                          <tr><th>{tt('Ticker')}</th><th>{tt('Action')}</th><th>{tt('Drift')}</th><th>{tt('Amount')}</th><th>{tt('Shares')}</th></tr>
                        </thead>
                        <tbody>
                          {rb.trades.filter(t => t.action !== 'hold').map(t => (
                            <tr key={t.ticker}>
                              <td className="goal-trade-ticker">{t.ticker}</td>
                              <td className={`goal-trade-action ${t.action}`}>{t.action.toUpperCase()}</td>
                              <td>{t.drift_pct > 0 ? '+' : ''}{t.drift_pct}%</td>
                              <td>${t.trade_value.toLocaleString()}</td>
                              <td>{t.shares}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
