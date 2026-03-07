import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { ResponsiveContainer, Area, AreaChart, CartesianGrid, Tooltip, XAxis, YAxis } from 'recharts';
import { FiBarChart2, FiSearch, FiTrendingDown, FiTrendingUp } from 'react-icons/fi';
import './MarketData.css';

const periods = ['1D', '1W', '1M', '3M', '6M', '1Y', '5Y', 'MAX'];

const MarketData = ({ apiBase }) => {
  const [stocks, setStocks] = useState([]);
  const [selectedStock, setSelectedStock] = useState(null);
  const [stockDetails, setStockDetails] = useState(null);
  const [priceHistory, setPriceHistory] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState('1Y');
  const [error, setError] = useState(null);
  const [selectedSector, setSelectedSector] = useState('');
  const [selectedExchange, setSelectedExchange] = useState('');
  const [sectors, setSectors] = useState([]);
  const [exchanges, setExchanges] = useState([]);

  const fetchAllStocks = useCallback(async () => {
    try {
      const response = await axios.get(`${apiBase}/stocks/all`);
      setStocks(response.data.stocks || []);
    } catch (fetchError) {
      console.error('Error fetching stocks:', fetchError);
      setError('Failed to load stocks');
    }
  }, [apiBase]);

  const fetchFilterOptions = useCallback(async () => {
    try {
      const response = await axios.get(`${apiBase}/stocks/filters/options`);
      setSectors(response.data.sectors || []);
      setExchanges(response.data.exchanges || []);
    } catch (fetchError) {
      console.error('Error fetching filter options:', fetchError);
    }
  }, [apiBase]);

  const fetchStockDetails = useCallback(async (ticker) => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${apiBase}/stocks/${ticker}`);
      setStockDetails(response.data);
    } catch (fetchError) {
      console.error('Error fetching stock details:', fetchError);
      setError('Failed to load stock details');
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  const fetchPriceHistory = useCallback(async (ticker, period) => {
    setLoading(true);
    try {
      const response = await axios.get(`${apiBase}/stocks/${ticker}/history?period=${period}`);
      setPriceHistory(response.data.data || []);
    } catch (fetchError) {
      console.error('Error fetching price history:', fetchError);
      setError('Failed to load price history');
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    fetchAllStocks();
    fetchFilterOptions();
  }, [fetchAllStocks, fetchFilterOptions]);

  useEffect(() => {
    if (!selectedStock) return;
    fetchStockDetails(selectedStock);
    fetchPriceHistory(selectedStock, selectedPeriod);
  }, [selectedStock, selectedPeriod, fetchStockDetails, fetchPriceHistory]);

  const filteredStocks = useMemo(() => (
    stocks.filter((stock) => {
      const matchesSearch = stock.ticker.toLowerCase().includes(searchTerm.toLowerCase())
        || stock.name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesSector = !selectedSector || stock.sector === selectedSector;
      const matchesExchange = !selectedExchange || stock.exchange === selectedExchange;
      return matchesSearch && matchesSector && matchesExchange;
    })
  ), [stocks, searchTerm, selectedSector, selectedExchange]);

  const formatPrice = (price) => (price ? `$${parseFloat(price).toFixed(2)}` : 'N/A');
  const formatPercent = (value) => (value ? `${parseFloat(value).toFixed(2)}%` : 'N/A');

  const formatLargeNumber = (num) => {
    if (!num) return 'N/A';
    const value = parseFloat(num);
    if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
    return `$${value.toLocaleString()}`;
  };

  const priceChange = useMemo(() => {
    if (priceHistory.length < 2) return { change: 0, percent: 0 };
    const first = priceHistory[0].close;
    const last = priceHistory[priceHistory.length - 1].close;
    const change = last - first;
    const percent = (change / first) * 100;
    return { change, percent };
  }, [priceHistory]);

  return (
    <div className="market-root">
      <div className="market-header">
        <div className="market-head-left">
          <div className="market-icon-wrap"><FiBarChart2 /></div>
          <div>
            <h2>Market Data</h2>
            <p>Explore stocks, fundamentals, and historical price action.</p>
          </div>
        </div>
      </div>

      <div className="market-layout">
        <section className="market-left-panel market-glass">
          <div className="market-search-wrap">
            <FiSearch />
            <input
              type="text"
              placeholder="Search ticker or name..."
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
            />
          </div>

          <div className="market-filters">
            <select value={selectedSector} onChange={(event) => setSelectedSector(event.target.value)}>
              <option value="">All Sectors</option>
              {sectors.map((sector) => (
                <option key={sector} value={sector}>{sector}</option>
              ))}
            </select>
            <select value={selectedExchange} onChange={(event) => setSelectedExchange(event.target.value)}>
              <option value="">All Exchanges</option>
              {exchanges.map((exchange) => (
                <option key={exchange} value={exchange}>{exchange}</option>
              ))}
            </select>
          </div>

          <p className="market-stock-count">Showing {filteredStocks.length} of {stocks.length} stocks</p>

          <div className="market-stock-list">
            {filteredStocks.map((stock) => (
              <button
                key={stock.ticker}
                type="button"
                className={`market-stock-item ${selectedStock === stock.ticker ? 'active' : ''}`}
                onClick={() => setSelectedStock(stock.ticker)}
              >
                <div>
                  <strong>{stock.ticker}</strong>
                  <span>{stock.name}</span>
                </div>
                <em>{stock.exchange}</em>
              </button>
            ))}
          </div>
        </section>

        <section className="market-main-panel">
          {!selectedStock && (
            <div className="market-glass market-empty-state">
              <h3>Select a stock to view details</h3>
              <p>Choose from {stocks.length} stocks in your database.</p>
            </div>
          )}

          {selectedStock && stockDetails && (
            <>
              <article className="market-glass market-summary-card">
                <div className="market-summary-head">
                  <div>
                    <h3>{stockDetails.ticker}</h3>
                    <p>{stockDetails.name}</p>
                    <small>{stockDetails.exchange} · {stockDetails.sector}</small>
                  </div>
                  <div className="market-price-area">
                    <strong>{formatPrice(stockDetails.current_price)}</strong>
                    <span className={priceChange.change >= 0 ? 'positive' : 'negative'}>
                      {priceChange.change >= 0 ? <FiTrendingUp /> : <FiTrendingDown />}
                      {formatPrice(Math.abs(priceChange.change))} ({priceChange.percent.toFixed(2)}%)
                    </span>
                  </div>
                </div>

                <div className="market-metrics-grid">
                  <div><p>Market Cap</p><strong>{formatLargeNumber(stockDetails.market_cap)}</strong></div>
                  <div><p>P/E Ratio</p><strong>{stockDetails.pe_ratio ? stockDetails.pe_ratio.toFixed(2) : 'N/A'}</strong></div>
                  <div><p>Beta</p><strong>{stockDetails.beta ? stockDetails.beta.toFixed(2) : 'N/A'}</strong></div>
                  <div><p>ROE</p><strong>{formatPercent(stockDetails.roe)}</strong></div>
                  <div><p>Dividend Yield</p><strong>{formatPercent(stockDetails.dividend_yield)}</strong></div>
                  <div><p>Debt/Equity</p><strong>{stockDetails.debt_to_equity ? stockDetails.debt_to_equity.toFixed(2) : 'N/A'}</strong></div>
                </div>
              </article>

              <article className="market-glass market-chart-card">
                <div className="market-period-controls">
                  {periods.map((period) => (
                    <button
                      key={period}
                      type="button"
                      className={selectedPeriod === period ? 'active' : ''}
                      onClick={() => setSelectedPeriod(period)}
                    >
                      {period}
                    </button>
                  ))}
                </div>

                {loading ? (
                  <div className="market-loading">Loading chart...</div>
                ) : priceHistory.length > 0 ? (
                  <div className="market-chart-wrap">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={priceHistory} margin={{ top: 8, right: 14, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="marketAreaGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.2} />
                            <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(100, 116, 139, 0.2)" />
                        <XAxis
                          dataKey="date"
                          tick={{ fill: '#64748b', fontSize: 11 }}
                          tickFormatter={(date) => {
                            const value = new Date(date);
                            if (selectedPeriod === '1D') {
                              return value.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                            }
                            if (selectedPeriod === '1W') {
                              return value.toLocaleDateString([], { month: 'short', day: 'numeric' });
                            }
                            return value.toLocaleDateString([], { month: 'short', year: '2-digit' });
                          }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fill: '#64748b', fontSize: 11 }}
                          tickFormatter={(value) => `$${value.toFixed(0)}`}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          contentStyle={{
                            background: 'rgba(13, 19, 33, 0.95)',
                            border: '1px solid rgba(100, 116, 139, 0.28)',
                            borderRadius: 10,
                            color: '#e2e8f0',
                            fontSize: 12,
                          }}
                          formatter={(value) => [`$${parseFloat(value).toFixed(2)}`, 'Price']}
                          labelFormatter={(date) => new Date(date).toLocaleDateString([], {
                            month: 'long', day: 'numeric', year: 'numeric',
                          })}
                        />
                        <Area type="monotone" dataKey="close" stroke="#22d3ee" strokeWidth={2} fill="url(#marketAreaGrad)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="market-loading">No price data available.</div>
                )}
              </article>

              <article className="market-glass market-financials-card">
                <h4>Financial Metrics</h4>
                <div className="market-metrics-grid financials">
                  <div><p>Revenue</p><strong>{formatLargeNumber(stockDetails.revenue)}</strong></div>
                  <div><p>Net Income</p><strong>{formatLargeNumber(stockDetails.net_income)}</strong></div>
                  <div><p>EPS Growth</p><strong>{formatPercent(stockDetails.eps_growth)}</strong></div>
                  <div><p>Operating Margin</p><strong>{formatPercent(stockDetails.operating_margin)}</strong></div>
                  <div><p>Current Ratio</p><strong>{stockDetails.current_ratio ? stockDetails.current_ratio.toFixed(2) : 'N/A'}</strong></div>
                  <div><p>Volume</p><strong>{stockDetails.volume ? stockDetails.volume.toLocaleString() : 'N/A'}</strong></div>
                </div>
              </article>
            </>
          )}

          {error && <div className="market-error">{error}</div>}
        </section>
      </div>
    </div>
  );
};

export default MarketData;
