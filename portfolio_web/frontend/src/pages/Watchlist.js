import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { FiStar, FiTrash2, FiPlus, FiSearch } from 'react-icons/fi';
import { Card, CardHeader, CardBody, HelpIcon } from '../components';
import './Watchlist.css';

const Watchlist = ({ apiBase }) => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [addNote, setAddNote] = useState('');
  const [message, setMessage] = useState(null);

  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await axios.get(`${apiBase}/watchlist`, { withCredentials: true });
      setItems(res.data.items || []);
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Please log in to use the watchlist.');
      } else {
        setError('Failed to load watchlist.');
      }
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  const searchStocks = useCallback(async (q) => {
    if (!q || q.length < 1) { setSearchResults([]); return; }
    setSearching(true);
    try {
      const res = await axios.get(`${apiBase}/stocks/search`, { params: { q, limit: 8 } });
      const existing = new Set(items.map(i => i.ticker));
      setSearchResults((res.data || []).filter(s => !existing.has(s.ticker)));
    } catch { setSearchResults([]); }
    finally { setSearching(false); }
  }, [apiBase, items]);

  useEffect(() => {
    const timer = setTimeout(() => searchStocks(searchTerm), 300);
    return () => clearTimeout(timer);
  }, [searchTerm, searchStocks]);

  const addToWatchlist = async (ticker) => {
    try {
      await axios.post(`${apiBase}/watchlist`, { ticker, notes: addNote || null }, { withCredentials: true });
      setMessage(`${ticker} added to watchlist`);
      setSearchTerm('');
      setSearchResults([]);
      setAddNote('');
      fetchWatchlist();
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Failed to add ticker');
      setTimeout(() => setMessage(null), 3000);
    }
  };

  const removeFromWatchlist = async (ticker) => {
    try {
      await axios.delete(`${apiBase}/watchlist/${ticker}`, { withCredentials: true });
      setItems(prev => prev.filter(i => i.ticker !== ticker));
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Failed to remove ticker');
      setTimeout(() => setMessage(null), 3000);
    }
  };

  if (loading) return <div className="page-container watchlist-root"><p>Loading watchlist...</p></div>;
  if (error) return <div className="page-container watchlist-root"><p className="wl-error">{error}</p></div>;

  return (
    <div className="page-container watchlist-root">
      <div className="page-header">
        <h1 className="wl-title"><FiStar className="wl-icon-accent" /> Watchlist</h1>
        <p className="wl-subtitle">Track your favorite stocks and monitor their performance.</p>
      </div>

      {message && <div className="wl-message">{message}</div>}

      <Card>
        <CardHeader>
          <div className="wl-add-header">
            <FiPlus size={16} />
            <span>Add to Watchlist</span>
            <HelpIcon text="Search for a stock ticker and click '+' to add it to your personal watchlist." />
          </div>
        </CardHeader>
        <CardBody>
          <div className="wl-search-row">
            <div className="wl-search-wrap">
              <FiSearch className="wl-search-icon" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search ticker or company name..."
                className="wl-search-input"
              />
            </div>
          </div>
          {searchResults.length > 0 && (
            <div className="wl-search-results">
              {searchResults.map(s => (
                <div key={s.ticker} className="wl-search-item">
                  <span className="wl-search-ticker">{s.ticker}</span>
                  <span className="wl-search-name">{s.name}</span>
                  <span className="wl-search-sector">{s.sector}</span>
                  <button className="wl-add-btn" onClick={() => addToWatchlist(s.ticker)} aria-label={`Add ${s.ticker}`}>
                    <FiPlus />
                  </button>
                </div>
              ))}
            </div>
          )}
          {searching && <p className="wl-muted">Searching...</p>}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <span>Your Watchlist ({items.length})</span>
        </CardHeader>
        <CardBody>
          {items.length === 0 ? (
            <p className="wl-empty">No stocks in your watchlist yet. Search above to add some!</p>
          ) : (
            <div className="wl-table-wrap">
              <table className="wl-table">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Name</th>
                    <th>Sector</th>
                    <th>Price</th>
                    <th>P/E</th>
                    <th>Beta</th>
                    <th>Div Yield</th>
                    <th>Added</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(item => (
                    <tr key={item.ticker}>
                      <td className="wl-ticker">{item.ticker}</td>
                      <td>{item.name || '—'}</td>
                      <td>{item.sector || '—'}</td>
                      <td>{item.current_price ? `$${item.current_price.toFixed(2)}` : '—'}</td>
                      <td>{item.pe_ratio ? item.pe_ratio.toFixed(1) : '—'}</td>
                      <td>{item.beta ? item.beta.toFixed(2) : '—'}</td>
                      <td>{item.dividend_yield ? `${(item.dividend_yield * 100).toFixed(2)}%` : '—'}</td>
                      <td className="wl-date">{item.added_at ? new Date(item.added_at).toLocaleDateString() : '—'}</td>
                      <td>
                        <button className="wl-remove-btn" onClick={() => removeFromWatchlist(item.ticker)} aria-label={`Remove ${item.ticker}`}>
                          <FiTrash2 />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
};

export default Watchlist;
