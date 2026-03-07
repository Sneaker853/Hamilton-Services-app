import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { FiActivity, FiAlertTriangle, FiBarChart2, FiDatabase, FiRefreshCw, FiShield } from 'react-icons/fi';
import './AdminPanel.css';

const AdminPanel = ({ apiBase }) => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('');

  const fetchUpdateStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${apiBase}/admin/update-status`);
      setStatus(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching update status:', error);
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    fetchUpdateStatus();
    const interval = setInterval(fetchUpdateStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchUpdateStatus]);

  const handleUpdateClick = async () => {
    if (updating) return;

    const confirmed = window.confirm(
      'This will update stock fundamentals from Yahoo Finance.\nThis process takes 15-20 minutes.\nContinue?'
    );
    if (!confirmed) return;

    setUpdating(true);
    setMessage('');

    try {
      const response = await axios.post(`${apiBase}/admin/update-fundamentals`);
      setMessageType('info');
      setMessage(response.data.message);

      const pollInterval = setInterval(fetchUpdateStatus, 10000);
      setTimeout(() => clearInterval(pollInterval), 30 * 60 * 1000);
    } catch (error) {
      const apiMessage = error?.response?.data?.message || error?.response?.data?.error || error?.response?.data?.detail;
      setMessageType('error');
      setMessage(`Failed to start update: ${apiMessage || error.message}`);
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <div className="admin-root">
        <div className="admin-glass admin-loading">Loading admin panel...</div>
      </div>
    );
  }

  return (
    <div className="admin-root">
      <header className="admin-header">
        <div className="admin-title-wrap">
          <div className="admin-title-icon"><FiShield /></div>
          <div>
            <h2>Admin Panel</h2>
            <p>Data operations and update workflows</p>
          </div>
        </div>
      </header>

      {message && (
        <div className={`admin-message ${messageType}`}>
          {messageType === 'error' ? <FiAlertTriangle /> : <FiActivity />}
          <span>{message}</span>
        </div>
      )}

      <div className="admin-kpi-grid">
        <article className="admin-glass admin-kpi-card">
          <header><span>Total Stocks</span><FiDatabase /></header>
          <strong>{status?.total_stocks || 0}</strong>
        </article>
        <article className="admin-glass admin-kpi-card">
          <header><span>With Fundamentals</span><FiBarChart2 /></header>
          <strong>{status?.stocks_with_data || 0}</strong>
        </article>
        <article className="admin-glass admin-kpi-card">
          <header><span>Data Coverage</span><FiActivity /></header>
          <strong>{status?.coverage_percent || 0}%</strong>
        </article>
      </div>

      <div className="admin-main-grid">
        <section className="admin-glass admin-section">
          <h3>Fundamentals Update</h3>
          <p className="admin-muted">
            Refreshes revenue, net income, operating margin, current ratio, and market cap from Yahoo Finance.
          </p>
          <div className="admin-stat-list">
            <div><span>Last Updated</span><strong>{status?.last_updated ? new Date(status.last_updated).toLocaleString() : 'Never'}</strong></div>
            <div><span>Estimated Duration</span><strong>15-20 minutes</strong></div>
          </div>
          <button type="button" className="admin-update-btn" onClick={handleUpdateClick} disabled={updating}>
            <FiRefreshCw className={updating ? 'spinning' : ''} />
            {updating ? 'Update In Progress...' : 'Update Stock Data'}
          </button>
          {updating && <p className="admin-muted">Processing 900+ stocks. You can keep using the platform during update.</p>}
        </section>

        <section className="admin-glass admin-section">
          <h3>Update Notes</h3>
          <ul className="admin-notes">
            <li>Source: Yahoo Finance API</li>
            <li>Safe to run multiple times</li>
            <li>Existing records are refreshed in place</li>
            <li>Status auto-refreshes every 30 seconds</li>
          </ul>
        </section>
      </div>
    </div>
  );
};

export default AdminPanel;
