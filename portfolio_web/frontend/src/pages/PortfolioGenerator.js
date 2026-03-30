import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { FiTrendingUp, FiDollarSign, FiLayers, FiPieChart, FiBarChart2, FiSettings } from 'react-icons/fi';
import { Button, Card, CardHeader, CardBody, LoadingSkeleton, CardSkeleton, HelpIcon } from '../components';
import './PortfolioGenerator.css';

const PERSONA_DESCRIPTIONS = {
  conservative: 'Low risk tolerance. Prioritizes capital preservation with stable, income-generating assets. Expected returns: 4–6% annually.',
  moderate_conservative: 'Below-average risk. Balances stability with modest growth. Expected returns: 5–7% annually.',
  balanced: 'Medium risk tolerance. Equal emphasis on growth and stability. Expected returns: 6–9% annually.',
  moderate_aggressive: 'Above-average risk. Tilts toward growth with higher volatility tolerance. Expected returns: 8–12% annually.',
  aggressive: 'High risk tolerance. Maximizes growth potential, accepts significant drawdowns. Expected returns: 10–15% annually.',
};

const PortfolioGenerator = ({ apiBase }) => {
  const [personas, setPersonas] = useState([]);
  const [formData, setFormData] = useState({
    persona_name: 'balanced',
    investment_amount: 100000,
    min_holdings: 10,
    max_holdings: 20,
    max_position_pct: 10,
    max_sector_pct: 25,
    include_bonds: false,
    include_etfs: false,
    rebalance_threshold: 5
  });
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [saveName, setSaveName] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState(null);
  const [personasLoading, setPersonasLoading] = useState(true);

  const COLORS = ['#22d3ee', '#818cf8', '#f472b6', '#34d399', '#fb923c', '#a78bfa', '#38bdf8', '#fbbf24', '#f87171', '#4ade80'];

  const pieLegendStyle = {
    fontSize: '11px',
    color: '#94a3b8',
    paddingTop: '8px',
    lineHeight: '20px',
  };

  const renderPieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
    if (percent < 0.05) return null;
    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);
    return (
      <text x={x} y={y} fill="#fff" textAnchor="middle" dominantBaseline="central"
        fontSize={11} fontWeight={600}>
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  const toFiniteNumber = (value) => {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
  };

  const toDecimal = (value) => {
    const numeric = toFiniteNumber(value);
    if (numeric === null) return null;
    return Math.abs(numeric) > 1.5 ? numeric / 100 : numeric;
  };

  const formatPercent = (value, digits = 2) => {
    const decimalValue = toDecimal(value);
    if (decimalValue === null) return 'N/A';
    return `${(decimalValue * 100).toFixed(digits)}%`;
  };

  const buildDisplayMetrics = () => {
    if (!portfolio) return [];

    const summary = portfolio.summary || {};
    const metrics = portfolio.metrics || {};

    const expectedReturn =
      toDecimal(summary.expected_return) ??
      toDecimal(metrics.expected_return);

    const volatility =
      toDecimal(summary.volatility) ??
      toDecimal(metrics.volatility);

    const sharpeRatio =
      toFiniteNumber(metrics.sharpe_ratio) ??
      (expectedReturn !== null && volatility && volatility > 0
        ? (expectedReturn - 0.02) / volatility
        : null);

    const herfindahl = toFiniteNumber(metrics.herfindahl_index);

    return [
      { label: 'Expected Return', value: formatPercent(expectedReturn) },
      { label: 'Volatility', value: formatPercent(volatility) },
      { label: 'Sharpe Ratio', value: sharpeRatio !== null ? sharpeRatio.toFixed(2) : 'N/A' },
      { label: 'Concentration (HHI)', value: herfindahl !== null ? herfindahl.toFixed(4) : 'N/A' }
    ];
  };

  const renderPieTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null;

    const item = payload[0];
    const percent = typeof item.percent === 'number' ? (item.percent * 100).toFixed(1) : null;
    const color = item.color || item.payload?.fill || '#22d3ee';
    return (
      <div className="pg-tooltip-card">
        <div className="pg-tooltip-row">
          <span className="pg-tooltip-dot" style={{ background: color }} />
          <span className="pg-tooltip-name">{item.name}</span>
        </div>
        <div className="pg-tooltip-value">
          {percent !== null ? `${percent}%` : `${item.value}`}
        </div>
      </div>
    );
  };

  useEffect(() => {
    const fetchPersonas = async () => {
      setPersonasLoading(true);
      try {
        const response = await axios.get(`${apiBase}/personas`);
        setPersonas(response.data);
      } catch (error) {
        console.error('Error fetching personas:', error);
        setError('Unable to load investment profiles. Please refresh the page.');
      } finally {
        setPersonasLoading(false);
      }
    };

    fetchPersonas();
  }, [apiBase]);

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : 
              name === 'investment_amount' ? parseFloat(value) :
              name.includes('_') && name !== 'persona_name' ? parseInt(value) : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${apiBase}/portfolio/generate`, formData);
      setPortfolio(response.data);
    } catch (error) {
      console.error('Error generating portfolio:', error);
      setError(error.response?.data?.message || error.response?.data?.error || error.response?.data?.detail || 'Unable to generate your portfolio. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Separate holdings by asset type
  const getStocks = () => portfolio?.holdings?.filter(h => h.type === 'stock' || !h.type) || [];
  const getETFs = () => portfolio?.holdings?.filter(h => h.type === 'etf') || [];
  const getBonds = () => portfolio?.holdings?.filter(h => h.type === 'bond') || [];

  const getAssetTypeDistribution = () => {
    if (!portfolio?.holdings) return [];
    
    const stocks = getStocks();
    const etfs = getETFs();
    const bonds = getBonds();

    const data = [];
    if (stocks.length > 0) data.push({ name: 'Stocks', value: stocks.length });
    if (etfs.length > 0) data.push({ name: 'ETFs', value: etfs.length });
    if (bonds.length > 0) data.push({ name: 'Bonds', value: bonds.length });
    
    return data;
  };

  // Get sector distribution
  const getSectorDistribution = () => {
    if (!portfolio.holdings) return [];
    
    const sectorMap = {};
    portfolio.holdings.forEach(holding => {
      const sector = holding.sector || 'Unknown';
      sectorMap[sector] = (sectorMap[sector] || 0) + holding.weight;
    });

    const entries = Object.entries(sectorMap).map(([name, value]) => ({
      name,
      value: parseFloat(value.toFixed(2))
    }));
    return entries;
  };

  const renderHoldingsTable = (holdings, title) => {
    if (!holdings || holdings.length === 0) return null;

    return (
      <div className="holdings-table-wrapper" key={title}>
        <h3 className="pg-sub-title pg-holdings-title">{title}</h3>
        <div className="holdings-table">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Market</th>
              <th>Shares</th>
              <th>Value</th>
              <th>Weight</th>
              <th>Sector</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((holding, idx) => (
              <tr key={idx}>
                <td className="ticker">{holding.ticker}</td>
                <td className="pg-market-cell">{holding.exchange || 'N/A'}</td>
                <td>{holding.shares?.toFixed(2) || 'N/A'}</td>
                <td>${holding.value?.toLocaleString() || 'N/A'}</td>
                <td className="percentage">{holding.weight?.toFixed(2)}%</td>
                <td>{holding.sector}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
    );
  };

  const handleSavePortfolio = async () => {
    const authUser = localStorage.getItem('authUser');
    if (!authUser) {
      setSaveMessage('Please sign in to save your portfolio.');
      return;
    }

    if (!portfolio) {
      setSaveMessage('Generate a portfolio before saving.');
      return;
    }

    const name = saveName.trim() || `${portfolio.persona || 'Optimized'} Portfolio`;
    const payload = {
      name,
      source: 'optimizer',
      data: {
        ...portfolio
      }
    };

    setSaving(true);
    setSaveMessage(null);
    try {
      await axios.post(`${apiBase}/portfolios/save`, payload, { withCredentials: true });
      setSaveMessage('Portfolio saved.');
    } catch (err) {
      const apiMessage = err?.response?.data?.message || err?.response?.data?.error || err?.response?.data?.detail;
      setSaveMessage(apiMessage || 'Unable to save your portfolio. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const displayMetrics = buildDisplayMetrics();

  return (
    <div className="page-container portfolio-generator-root">
      <div className="page-header">
        <h1 className="pg-page-title">Portfolio Generator</h1>
        <p className="page-subtitle pg-page-subtitle">Build a diversified portfolio based on your risk profile and constraints</p>
      </div>

      <div className={`pg-layout-grid ${portfolio ? 'with-results' : 'single-column'}`}>
        {/* Form Section */}
        <div>
          <form className="form-section" onSubmit={handleSubmit}>
            <h2 className="pg-section-title">Portfolio Parameters</h2>

            <div className="form-group">
              <label className="pg-label-row">
                <FiSettings size={16} />
                Portfolio Persona
              </label>
              {personasLoading ? (
                <LoadingSkeleton height="44px" borderRadius="8px" />
              ) : (
                <select 
                  name="persona_name" 
                  value={formData.persona_name}
                  onChange={handleInputChange}
                  className="form-control pg-input-lg"
                >
                  {personas.map(p => (
                    <option key={p.name} value={p.name}>
                      {p.display_name} {p.risk_tolerance && `(${p.risk_tolerance})`}
                    </option>
                  ))}
                </select>
                {PERSONA_DESCRIPTIONS[formData.persona_name] && (
                  <p className="pg-persona-desc">{PERSONA_DESCRIPTIONS[formData.persona_name]}</p>
                )}
              )}
            </div>

            <div className="form-group">
              <label className="pg-label-row">
                <FiDollarSign size={16} />
                Investment Amount
              </label>
              <input
                type="number"
                name="investment_amount"
                value={formData.investment_amount}
                onChange={handleInputChange}
                min="1000"
                step="1000"
                className="form-control pg-input-lg"
                placeholder="e.g., 100000"
              />
            </div>

            <div className="pg-two-col-grid">
              <div className="form-group">
                <label>Min Holdings</label>
                <input
                  type="number"
                  name="min_holdings"
                  value={formData.min_holdings}
                  onChange={handleInputChange}
                  min="5"
                  max="50"
                  className="form-control"
                />
              </div>
              <div className="form-group">
                <label>Max Holdings</label>
                <input
                  type="number"
                  name="max_holdings"
                  value={formData.max_holdings}
                  onChange={handleInputChange}
                  min="5"
                  max="50"
                  className="form-control"
                />
              </div>
            </div>

            <div className="pg-two-col-grid">
              <div className="form-group">
                <label>Max Position (%) <HelpIcon text="Maximum percentage of the portfolio that any single holding can represent. Lower values increase diversification." /></label>
                <input
                  type="number"
                  name="max_position_pct"
                  value={formData.max_position_pct}
                  onChange={handleInputChange}
                  min="1"
                  max="100"
                  step="0.5"
                  className="form-control"
                />
              </div>
              <div className="form-group">
                <label>Max Sector (%) <HelpIcon text="Maximum percentage of the portfolio allocated to any single sector (e.g., Technology, Healthcare). Helps avoid concentration risk." /></label>
                <input
                  type="number"
                  name="max_sector_pct"
                  value={formData.max_sector_pct}
                  onChange={handleInputChange}
                  min="1"
                  max="100"
                  step="0.5"
                  className="form-control"
                />
              </div>
            </div>

            <div className="form-group pg-compact-group">
              <label className="pg-check-row">
                <input
                  type="checkbox"
                  name="include_etfs"
                  checked={formData.include_etfs}
                  onChange={handleInputChange}
                  className="form-check-input pg-check-input"
                />
                <span>Include ETFs</span>
              </label>
            </div>

            <div className="form-group pg-loose-group">
              <label className="pg-check-row">
                <input
                  type="checkbox"
                  name="include_bonds"
                  checked={formData.include_bonds}
                  onChange={handleInputChange}
                  className="form-check-input pg-check-input"
                />
                <span>Include Bonds</span>
              </label>
            </div>

            {error && (
              <div className="error-message pg-form-error">
                {error}
                <button type="button" className="pg-retry-btn" onClick={() => { setError(null); }}>Dismiss</button>
              </div>
            )}

            <Button 
              type="submit" 
              variant="primary"
              size="large"
              loading={loading}
              fullWidth
              icon={<FiTrendingUp />}
            >
              Generate Portfolio
            </Button>
          </form>
        </div>

        {/* Results Section */}
        {loading && (
          <div>
            <Card>
              <CardHeader>
                <div className="pg-loading-head">
                  <FiPieChart size={20} className="pg-icon-cyan" />
                  <h2 className="pg-card-title">Generating Portfolio...</h2>
                </div>
              </CardHeader>
              <CardBody>
                <div className="pg-loading-grid">
                  <CardSkeleton />
                  <LoadingSkeleton height="300px" borderRadius="12px" />
                  <LoadingSkeleton height="200px" borderRadius="12px" />
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {portfolio && !loading && (
          <div>
            <div className="results-section">
              <div className="pg-results-head">
                <h2 className="pg-card-title">Portfolio Results</h2>
                <div className="pg-results-actions">
                  <input
                    type="text"
                    value={saveName}
                    onChange={(e) => setSaveName(e.target.value)}
                    placeholder="Portfolio name"
                    className="form-control pg-name-input"
                  />
                  <Button
                    variant="secondary"
                    size="small"
                    onClick={() => {
                      if (!portfolio) return;
                      const draftName = saveName.trim() || `${portfolio.persona || 'Optimized'} Portfolio`;
                      localStorage.setItem('builderDraftPortfolio', JSON.stringify({
                        name: draftName,
                        investment_amount: portfolio.investment_amount,
                        holdings: portfolio.holdings,
                        summary: portfolio.summary || null,
                        metrics: portfolio.metrics || null
                      }));
                      window.location.href = '/portfolio-builder';
                    }}
                  >
                    Edit in Builder
                  </Button>
                  <Button
                    variant="primary"
                    size="small"
                    loading={saving}
                    onClick={handleSavePortfolio}
                  >
                    Save
                  </Button>
                </div>
              </div>
              {saveMessage && (
                <div className={`pg-save-message ${saveMessage.includes('saved') ? 'success' : 'error'}`}>
                  {saveMessage}
                </div>
              )}
              
              <div className="portfolio-summary">
                <div className="summary-item">
                  <span>Portfolio:</span>
                  <strong>{portfolio.persona}</strong>
                </div>
                <div className="summary-item">
                  <span>Investment:</span>
                  <strong>${portfolio.investment_amount?.toLocaleString()}</strong>
                </div>
                <div className="summary-item">
                  <span>Holdings:</span>
                  <strong>{portfolio.holdings?.length || 0}</strong>
                </div>
              </div>

              {/* Asset Type & Sector Charts */}
              {portfolio.holdings && portfolio.holdings.length > 0 && (
                <div className="pg-chart-grid">
                  {/* Asset Type Distribution */}
                  {getAssetTypeDistribution().length > 0 && (
                      <Card variant="default">
                        <CardHeader>
                          <div className="pg-chart-title-row">
                            <FiLayers size={18} className="pg-icon-cyan" />
                            <h3 className="pg-sub-title">Asset Type Distribution</h3>
                          </div>
                        </CardHeader>
                        <CardBody>
                      <ResponsiveContainer width="100%" height={300}>
                        <PieChart>
                          <Pie
                            data={getAssetTypeDistribution()}
                            cx="50%"
                            cy="45%"
                            innerRadius={60}
                            outerRadius={100}
                            paddingAngle={3}
                            cornerRadius={4}
                            stroke="rgba(10, 14, 26, 0.6)"
                            strokeWidth={2}
                            dataKey="value"
                            label={renderPieLabel}
                            labelLine={false}
                          >
                            {getAssetTypeDistribution().map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip content={renderPieTooltip} cursor={{ fill: 'rgba(255, 255, 255, 0.04)' }} />
                          <Legend wrapperStyle={pieLegendStyle} iconType="circle" iconSize={8} />
                        </PieChart>
                      </ResponsiveContainer>
                        </CardBody>
                      </Card>
                  )}

                  {/* Sector Distribution */}
                  {getSectorDistribution().length > 0 && (
                      <Card variant="default">
                        <CardHeader>
                          <div className="pg-chart-title-row">
                            <FiBarChart2 size={18} className="pg-icon-cyan" />
                            <h3 className="pg-sub-title">Sector Distribution</h3>
                          </div>
                        </CardHeader>
                        <CardBody>
                      <ResponsiveContainer width="100%" height={300}>
                        <PieChart>
                          <Pie
                            data={getSectorDistribution()}
                            cx="50%"
                            cy="45%"
                            innerRadius={60}
                            outerRadius={100}
                            paddingAngle={3}
                            cornerRadius={4}
                            stroke="rgba(10, 14, 26, 0.6)"
                            strokeWidth={2}
                            dataKey="value"
                            label={renderPieLabel}
                            labelLine={false}
                          >
                            {getSectorDistribution().map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip content={renderPieTooltip} cursor={{ fill: 'rgba(255, 255, 255, 0.04)' }} />
                          <Legend wrapperStyle={pieLegendStyle} iconType="circle" iconSize={8} />
                        </PieChart>
                      </ResponsiveContainer>
                        </CardBody>
                      </Card>
                  )}
                </div>
              )}

              {/* Holdings Tables */}
              {portfolio.holdings && portfolio.holdings.length > 0 && (
                <div className="pg-holdings-stack">
                  {renderHoldingsTable(getStocks(), `📈 Stocks (${getStocks().length})`)}
                  {getETFs().length > 0 && renderHoldingsTable(getETFs(), `🏢 ETFs (${getETFs().length})`)}
                  {getBonds().length > 0 && renderHoldingsTable(getBonds(), `📊 Bonds (${getBonds().length})`)}
                </div>
              )}

              {/* Portfolio Metrics */}
              {displayMetrics.length > 0 && (
                <div className="portfolio-metrics">
                  <h3 className="pg-sub-title">Portfolio Metrics</h3>
                  <div className="metrics-grid">
                    {displayMetrics.map((metric) => (
                        <div key={metric.label} className="metric-item">
                          <span className="metric-label">{metric.label}</span>
                          <span className="metric-value">{metric.value}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PortfolioGenerator;
