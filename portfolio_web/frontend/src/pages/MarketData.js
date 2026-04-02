import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { ResponsiveContainer, Area, AreaChart, CartesianGrid, Tooltip, XAxis, YAxis } from 'recharts';
import { FiBarChart2, FiSearch, FiTrendingDown, FiTrendingUp } from 'react-icons/fi';
import { HelpIcon, useLanguage } from '../components';
import './MarketData.css';

const periods = ['1W', '1M', '3M', '6M', '1Y', '5Y', 'MAX'];

const MarketData = ({ apiBase }) => {
  const { tt } = useLanguage();
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
  const [latestPriceDate, setLatestPriceDate] = useState(null);
  const [latestPriceTickerCount, setLatestPriceTickerCount] = useState(0);
  const [tickersWithPrice, setTickersWithPrice] = useState(0);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const searchRef = React.useRef(null);

  const fetchAllStocks = useCallback(async () => {
    try {
      const response = await axios.get(`${apiBase}/stocks/all`);
      setStocks(response.data.stocks || []);
      setLatestPriceDate(response.data.latest_price_date || null);
      setLatestPriceTickerCount(response.data.latest_price_ticker_count || 0);
      setTickersWithPrice(response.data.tickers_with_price || 0);
    } catch (fetchError) {
      console.error('Error fetching stocks:', fetchError);
      setError(tt('Unable to load market data. Please try again.'));
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
      setError(tt('Unable to load security details. Please try again.'));
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
      setError(tt('Unable to load price history. Please try again.'));
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    fetchAllStocks();
    fetchFilterOptions();
  }, [fetchAllStocks, fetchFilterOptions]);

  useEffect(() => {
    if (!searchTerm || searchTerm.length < 1) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const response = await axios.get(`${apiBase}/stocks/search`, { params: { q: searchTerm, limit: 8 } });
        setSuggestions(response.data.results || []);
        setShowSuggestions(true);
      } catch { /* ignore */ }
    }, 200);
    return () => clearTimeout(timer);
  }, [searchTerm, apiBase]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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

  const priceDomain = useMemo(() => {
    const closes = priceHistory
      .map((point) => Number(point.close))
      .filter((value) => Number.isFinite(value));

    if (closes.length === 0) {
      return ['auto', 'auto'];
    }

    const min = Math.min(...closes);
    const max = Math.max(...closes);

    if (min === max) {
      const flatPadding = Math.max(min * 0.02, 1);
      return [Math.max(0, min - flatPadding), max + flatPadding];
    }

    const paddingByPeriod = {
      '1W': 0.16,
      '1M': 0.12,
      '3M': 0.1,
      '6M': 0.08,
      '1Y': 0.06,
      '5Y': 0.05,
      MAX: 0.04,
    };

    const range = max - min;
    const padding = range * (paddingByPeriod[selectedPeriod] ?? 0.08);
    const lower = Math.max(0, min - padding);
    const upper = max + padding;

    return [Number(lower.toFixed(2)), Number(upper.toFixed(2))];
  }, [priceHistory, selectedPeriod]);

  const formatAxisPrice = useCallback((value) => {
    if (!Number.isFinite(value)) return value;
    if (Math.abs(value) >= 1000) {
      return `$${value.toLocaleString([], { maximumFractionDigits: 0 })}`;
    }
    if (Math.abs(value) >= 100) {
      return `$${value.toFixed(0)}`;
    }
    if (Math.abs(value) >= 10) {
      return `$${value.toFixed(1)}`;
    }
    return `$${value.toFixed(2)}`;
  }, []);

  const latestPriceDateLabel = useMemo(() => {
    if (!latestPriceDate) return null;
    const value = new Date(latestPriceDate);
    if (Number.isNaN(value.getTime())) return null;
    return value.toLocaleDateString([], { month: 'long', day: 'numeric', year: 'numeric' });
  }, [latestPriceDate]);

  return (
    <div className="market-root">
      <div className="market-header">
        <div className="market-head-left">
          <div className="market-icon-wrap"><FiBarChart2 /></div>
          <div>
            <h2>{tt('Market Data')}</h2>
            <p>{tt('Explore stocks, fundamentals, and historical price action.')}</p>
            {latestPriceDateLabel && (
              <p>
                Price data as of {latestPriceDateLabel}
                {tickersWithPrice > 0 && ` (${latestPriceTickerCount}/${tickersWithPrice} tickers at latest date)`}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="market-layout">
        <section className="market-left-panel market-glass">
          <div className="market-search-wrap" ref={searchRef} style={{ position: 'relative' }}>
            <FiSearch />
            <input
              type="text"
              placeholder={tt('Search ticker or name...')}
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
            />
            {showSuggestions && suggestions.length > 0 && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 20,
                background: 'rgba(13, 19, 33, 0.97)', border: '1px solid rgba(100, 116, 139, 0.28)',
                borderRadius: '0 0 8px 8px', maxHeight: '280px', overflowY: 'auto',
              }}>
                {suggestions.map((s) => (
                  <button
                    key={s.ticker}
                    type="button"
                    onClick={() => {
                      setSelectedStock(s.ticker);
                      setSearchTerm(s.ticker);
                      setShowSuggestions(false);
                    }}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      width: '100%', padding: '8px 12px', border: 'none', background: 'transparent',
                      color: '#e2e8f0', cursor: 'pointer', fontSize: '13px', textAlign: 'left',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(34, 211, 238, 0.08)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                  >
                    <span><strong>{s.ticker}</strong> — {s.name}</span>
                    <em style={{ fontSize: '11px', color: '#64748b' }}>{s.exchange}</em>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="market-filters">
            <select value={selectedSector} onChange={(event) => setSelectedSector(event.target.value)}>
              <option value="">{tt('All Sectors')}</option>
              {sectors.map((sector) => (
                <option key={sector} value={sector}>{sector}</option>
              ))}
            </select>
            <select value={selectedExchange} onChange={(event) => setSelectedExchange(event.target.value)}>
              <option value="">{tt('All Exchanges')}</option>
              {exchanges.map((exchange) => (
                <option key={exchange} value={exchange}>{exchange}</option>
              ))}
            </select>
          </div>

          <p className="market-stock-count">{tt('Showing')} {filteredStocks.length} {tt('of')} {stocks.length} {tt('stocks')}</p>

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
              <h3>{tt('Select a stock to view details')}</h3>
              <p>{tt('Choose from')} {stocks.length} {tt('stocks in your database.')}</p>
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
                  <div><p>Market Cap <HelpIcon text="Total market value of a company's outstanding shares. Calculated as share price × total shares outstanding." /></p><strong>{formatLargeNumber(stockDetails.market_cap)}</strong></div>
                  <div><p>P/E Ratio <HelpIcon text="Price-to-Earnings ratio. Compares a stock's price to its earnings per share. Lower P/E may indicate better value; higher P/E may reflect growth expectations." /></p><strong>{stockDetails.pe_ratio ? stockDetails.pe_ratio.toFixed(2) : 'N/A'}</strong></div>
                  <div><p>Beta <HelpIcon text="Measures a stock's volatility relative to the overall market. Beta of 1 = moves with market. Above 1 = more volatile. Below 1 = less volatile." /></p><strong>{stockDetails.beta ? stockDetails.beta.toFixed(2) : 'N/A'}</strong></div>
                  <div><p>ROE <HelpIcon text="Return on Equity. Measures how effectively a company uses shareholder money to generate profit. Higher ROE generally indicates better management efficiency." /></p><strong>{formatPercent(stockDetails.roe)}</strong></div>
                  <div><p>Dividend Yield <HelpIcon text="Annual dividend payment as a percentage of the stock price. Shows how much income you earn per dollar invested, before any price changes." /></p><strong>{formatPercent(stockDetails.dividend_yield)}</strong></div>
                  <div><p>Debt/Equity <HelpIcon text="Ratio of total debt to shareholder equity. Shows how much a company relies on borrowed money. Lower is generally safer; high ratios may signal financial risk." /></p><strong>{stockDetails.debt_to_equity ? stockDetails.debt_to_equity.toFixed(2) : 'N/A'}</strong></div>
                  <div><p>Expected Return <HelpIcon text="Annualized expected return estimated by the Fama-French 5-factor model. Reflects the stock's factor exposures, not a guarantee of future performance." /></p><strong className={stockDetails.expected_return >= 0 ? 'positive' : 'negative'}>{stockDetails.expected_return != null ? `${(stockDetails.expected_return * 100).toFixed(2)}%` : 'N/A'}</strong></div>
                  <div><p>Volatility <HelpIcon text="Annualized standard deviation of the stock's daily returns. Higher values indicate larger price swings and greater uncertainty." /></p><strong>{stockDetails.volatility != null ? `${(stockDetails.volatility * 100).toFixed(2)}%` : 'N/A'}</strong></div>
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
                            const d = new Date(date);
                            if (!d || isNaN(d)) return '';
                            if (selectedPeriod === '1W') {
                              return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                            }
                            if (selectedPeriod === '1M') {
                              return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                            }
                            if (selectedPeriod === '3M' || selectedPeriod === '6M') {
                              return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                            }
                            // 1Y, 5Y, MAX: show "Jan '25" style
                            return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
                          }}
                          axisLine={false}
                          tickLine={false}
                          minTickGap={selectedPeriod === '1W' || selectedPeriod === '1M' ? 30 : 50}
                          interval="preserveStartEnd"
                        />
                        <YAxis
                          tick={{ fill: '#64748b', fontSize: 11 }}
                          domain={priceDomain}
                          tickFormatter={formatAxisPrice}
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
                  <div><p>Revenue <HelpIcon text="Total money a company earns from selling its products or services before any expenses are deducted." /></p><strong>{formatLargeNumber(stockDetails.revenue)}</strong></div>
                  <div><p>Net Income <HelpIcon text="A company's total profit after all expenses, taxes, and costs have been subtracted from revenue. Also called the 'bottom line'." /></p><strong>{formatLargeNumber(stockDetails.net_income)}</strong></div>
                  <div><p>EPS Growth <HelpIcon text="Earnings Per Share growth. Shows how fast a company's profit per share is increasing. Higher growth often signals a company expanding its business." /></p><strong>{formatPercent(stockDetails.eps_growth)}</strong></div>
                  <div><p>Operating Margin <HelpIcon text="Percentage of revenue remaining after paying operating costs (wages, materials, etc.). Higher margin = more efficient business." /></p><strong>{formatPercent(stockDetails.operating_margin)}</strong></div>
                  <div><p>Current Ratio <HelpIcon text="Company's ability to pay short-term debts. Calculated as current assets ÷ current liabilities. Above 1.0 means the company can cover its near-term obligations." /></p><strong>{stockDetails.current_ratio ? stockDetails.current_ratio.toFixed(2) : 'N/A'}</strong></div>
                  <div><p>Volume <HelpIcon text="Number of shares traded in a given period. Higher volume means more market interest and usually easier buying/selling (liquidity)." /></p><strong>{stockDetails.volume ? stockDetails.volume.toLocaleString() : 'N/A'}</strong></div>
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
