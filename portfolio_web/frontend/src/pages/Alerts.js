import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { FiBell, FiPlus, FiTrash2, FiToggleLeft, FiToggleRight, FiRefreshCw } from 'react-icons/fi';
import { useLanguage } from '../components';
import './Alerts.css';

export default function Alerts({ apiBase }) {
  const { tt } = useLanguage();
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [formTicker, setFormTicker] = useState('');
  const [formCondition, setFormCondition] = useState('above');
  const [formThreshold, setFormThreshold] = useState('');
  const [formNotes, setFormNotes] = useState('');
  const [creating, setCreating] = useState(false);
  const [checking, setChecking] = useState(false);

  const fetchAlerts = useCallback(async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${apiBase}/alerts`);
      setAlerts(res.data.items || []);
      setError('');
    } catch (err) {
      if (err.response?.status === 401) {
        setError(tt('Please log in to manage price alerts.'));
      } else {
        setError(tt('Failed to load alerts.'));
      }
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => { fetchAlerts(); }, [fetchAlerts]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!formTicker.trim() || !formThreshold) return;
    try {
      setCreating(true);
      await axios.post(`${apiBase}/alerts`, {
        ticker: formTicker.trim().toUpperCase(),
        condition: formCondition,
        threshold: parseFloat(formThreshold),
        notes: formNotes.trim() || null,
      });
      setFormTicker('');
      setFormThreshold('');
      setFormNotes('');
      setShowForm(false);
      fetchAlerts();
    } catch (err) {
      setError(err.response?.data?.detail || tt('Failed to create alert.'));
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await axios.delete(`${apiBase}/alerts/${id}`);
      setAlerts(prev => prev.filter(a => a.id !== id));
    } catch {
      setError(tt('Failed to delete alert.'));
    }
  };

  const handleToggle = async (id) => {
    try {
      const res = await axios.patch(`${apiBase}/alerts/${id}/toggle`);
      setAlerts(prev => prev.map(a => a.id === id ? { ...a, is_active: res.data.is_active } : a));
    } catch {
      setError(tt('Failed to toggle alert.'));
    }
  };

  const handleCheck = async () => {
    try {
      setChecking(true);
      const res = await axios.post(`${apiBase}/alerts/check`);
      if (res.data.triggered.length > 0) {
        fetchAlerts();
      }
    } catch {
      setError(tt('Failed to check alerts.'));
    } finally {
      setChecking(false);
    }
  };

  const conditionLabel = (c, threshold, refPrice) => {
    if (c === 'above') return `Price ≥ $${threshold.toFixed(2)}`;
    if (c === 'below') return `Price ≤ $${threshold.toFixed(2)}`;
    if (c === 'pct_change') return `±${threshold.toFixed(1)}% from $${refPrice ? refPrice.toFixed(2) : '?'}`;
    return c;
  };

  if (loading) return <div className="alerts-page"><div className="alerts-loading">{tt('Loading alerts...')}</div></div>;
  if (error && alerts.length === 0) return <div className="alerts-page"><div className="alerts-error">{error}</div></div>;

  return (
    <div className="alerts-page">
      <div className="alerts-header">
        <h2><FiBell /> {tt('Price Alerts')}</h2>
        <div className="alerts-actions">
          <button className="alerts-btn alerts-check-btn" onClick={handleCheck} disabled={checking}>
            <FiRefreshCw className={checking ? 'spin' : ''} /> {checking ? tt('Checking...') : tt('Check Now')}
          </button>
          <button className="alerts-btn alerts-add-btn" onClick={() => setShowForm(!showForm)}>
            <FiPlus /> {tt('New Alert')}
          </button>
        </div>
      </div>

      {error && <div className="alerts-error">{error}</div>}

      {showForm && (
        <form className="alerts-form" onSubmit={handleCreate}>
          <div className="alerts-form-row">
            <input
              type="text"
              placeholder={tt('Ticker (e.g. AAPL)')}
              value={formTicker}
              onChange={e => setFormTicker(e.target.value)}
              maxLength={10}
              required
            />
            <select value={formCondition} onChange={e => setFormCondition(e.target.value)}>
              <option value="above">{tt('Price Above')}</option>
              <option value="below">{tt('Price Below')}</option>
              <option value="pct_change">{tt('% Change')}</option>
            </select>
            <input
              type="number"
              step="0.01"
              placeholder={formCondition === 'pct_change' ? tt('% (e.g. 5)') : tt('Price (e.g. 150)')}
              value={formThreshold}
              onChange={e => setFormThreshold(e.target.value)}
              required
            />
          </div>
          <div className="alerts-form-row">
            <input
              type="text"
              placeholder={tt('Notes (optional)')}
              value={formNotes}
              onChange={e => setFormNotes(e.target.value)}
              maxLength={500}
              className="alerts-notes-input"
            />
            <button type="submit" className="alerts-btn alerts-submit-btn" disabled={creating}>
              {creating ? tt('Creating...') : tt('Create Alert')}
            </button>
          </div>
        </form>
      )}

      {alerts.length === 0 ? (
        <div className="alerts-empty">
          <FiBell size={48} />
          <p>{tt('No price alerts yet.')}</p>
          <p>{tt('Create an alert to get notified when a stock hits your target price.')}</p>
        </div>
      ) : (
        <div className="alerts-list">
          {alerts.map(a => (
            <div key={a.id} className={`alert-card ${a.is_triggered ? 'triggered' : ''} ${!a.is_active ? 'inactive' : ''}`}>
              <div className="alert-main">
                <span className="alert-ticker">{a.ticker}</span>
                <span className="alert-condition">{conditionLabel(a.condition, a.threshold, a.reference_price)}</span>
                {a.current_price != null && (
                  <span className="alert-current">{tt('Now')}: ${a.current_price.toFixed(2)}</span>
                )}
              </div>
              <div className="alert-meta">
                {a.is_triggered && <span className="alert-badge triggered">{tt('Triggered')}</span>}
                {!a.is_active && <span className="alert-badge paused">{tt('Paused')}</span>}
                {a.notes && <span className="alert-notes">{a.notes}</span>}
                <span className="alert-date">{tt('Created')} {new Date(a.created_at).toLocaleDateString()}</span>
              </div>
              <div className="alert-actions">
                <button className="alert-toggle-btn" onClick={() => handleToggle(a.id)} title={a.is_active ? tt('Pause') : tt('Resume')}>
                  {a.is_active ? <FiToggleRight size={20} /> : <FiToggleLeft size={20} />}
                </button>
                <button className="alert-delete-btn" onClick={() => handleDelete(a.id)} title={tt('Delete')}>
                  <FiTrash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
