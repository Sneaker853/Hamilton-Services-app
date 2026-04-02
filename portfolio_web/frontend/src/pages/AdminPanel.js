import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { FiActivity, FiAlertTriangle, FiBarChart2, FiDatabase, FiRefreshCw, FiShield } from 'react-icons/fi';
import { ConfirmModal, useLanguage } from '../components';
import ProgressBar from '../components/ProgressBar';
import './AdminPanel.css';

const AdminPanel = ({ apiBase }) => {
  const { tt } = useLanguage();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);

  const formatDateTime = (value) => (value ? new Date(value).toLocaleString() : tt('Never'));
  const formatDateOnly = (value) => (value ? new Date(value).toLocaleDateString([], {
    month: 'long', day: 'numeric', year: 'numeric',
  }) : tt('Unknown'));

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

  const handleUpdateClick = () => {
    if (updating) return;
    setConfirmOpen(true);
  };

  const handleConfirmUpdate = async () => {
    setConfirmOpen(false);
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
      setMessage(apiMessage || tt('The update could not be started. Please try again.'));
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <div className="admin-root">
        <div className="admin-glass admin-loading">{tt('Loading admin panel...')}</div>
      </div>
    );
  }

  return (
    <div className="admin-root">
      <header className="admin-header">
        <div className="admin-title-wrap">
          <div className="admin-title-icon"><FiShield /></div>
          <div>
            <h2>{tt('Admin Panel')}</h2>
            <p>{tt('Data operations and update workflows')}</p>
          </div>
        </div>
      </header>

      {message && (
        <div className={`admin-message ${messageType}`}>
          {messageType === 'error' ? <FiAlertTriangle /> : <FiActivity />}
          <span>{message}</span>
          {messageType === 'error' && (
            <button type="button" className="admin-retry-btn" onClick={() => { setMessage(''); fetchUpdateStatus(); }}>
              {tt('Retry')}
            </button>
          )}
        </div>
      )}

      <div className="admin-kpi-grid">
        <article className="admin-glass admin-kpi-card">
          <header><span>{tt('Total Stocks')}</span><FiDatabase /></header>
          <strong>{status?.total_stocks || 0}</strong>
        </article>
        <article className="admin-glass admin-kpi-card">
          <header><span>{tt('With Fundamentals')}</span><FiBarChart2 /></header>
          <strong>{status?.stocks_with_data || 0}</strong>
        </article>
        <article className="admin-glass admin-kpi-card">
          <header><span>{tt('Data Coverage')}</span><FiActivity /></header>
          <strong>{status?.coverage_percent || 0}%</strong>
        </article>
      </div>

      <div className="admin-main-grid">
        <section className="admin-glass admin-section">
          <h3>{tt('Fundamentals Update')}</h3>
          <p className="admin-muted">
            Refreshes revenue, net income, operating margin, current ratio, and market cap from Yahoo Finance.
          </p>
          <div className="admin-stat-list">
            <div><span>{tt('Fundamentals Updated')}</span><strong>{formatDateTime(status?.last_updated)}</strong></div>
            <div>
              <span>{tt('Latest Price Date')}</span>
              <strong>
                {formatDateOnly(status?.latest_price_date)}
                {status?.tickers_with_price > 0 && ` (${status?.latest_price_ticker_count || 0}/${status?.tickers_with_price} tickers)`}
              </strong>
            </div>
            <div><span>{tt('Estimated Duration')}</span><strong>{tt('15-20 minutes')}</strong></div>
          </div>
          <button type="button" className="admin-update-btn" onClick={handleUpdateClick} disabled={updating}>
            <FiRefreshCw className={updating ? 'spinning' : ''} />
            {updating ? tt('Update In Progress...') : tt('Update Stock Data')}
          </button>
          {updating && (
            <div>
              <ProgressBar active={updating} estimatedMs={900000} label={tt('Updating 900+ stocks from Yahoo Finance...')} />
              <p className="admin-muted">{tt('You can keep using the platform during update.')}</p>
            </div>
          )}
        </section>

        <section className="admin-glass admin-section">
          <h3>{tt('Update Notes')}</h3>
          <ul className="admin-notes">
            <li>Source: Yahoo Finance API</li>
            <li>Safe to run multiple times</li>
            <li>Existing records are refreshed in place</li>
            <li>Status auto-refreshes every 30 seconds</li>
          </ul>
        </section>
      </div>

      <ConfirmModal
        open={confirmOpen}
        title={tt('Update Stock Data')}
        message={tt('This will update stock fundamentals from Yahoo Finance. This process takes 15-20 minutes. Continue?')}
        confirmLabel={tt('Start Update')}
        cancelLabel={tt('Cancel')}
        onConfirm={handleConfirmUpdate}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
};

export default AdminPanel;
