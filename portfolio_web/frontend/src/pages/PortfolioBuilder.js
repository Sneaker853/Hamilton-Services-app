import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './PortfolioBuilder.css';

// Extracted sub-components and utilities
import {
  toFiniteNumber,
  normalizePercentValue,
  clamp,
  getHoldingExpectedReturnPct,
  getHoldingVolatilityPct,
  buildCorrelationMatrix,
  buildHoldingsSignature,
} from './portfolioBuilderUtils';
import AssetSearchSection from './AssetSearchSection';
import HoldingsTable from './HoldingsTable';
import ChartsPanel from './ChartsPanel';
import AnalyticsPanel from './AnalyticsPanel';

const PortfolioSummary = ({ holdingsCount, investmentAmount, totalWeight }) => (
  <div className="portfolio-summary pb-summary-wrap">
    <div className="summary-item">
      <span>Holdings:</span>
      <strong>{holdingsCount}</strong>
    </div>
    <div className="summary-item">
      <span>Investment:</span>
      <strong>${investmentAmount.toLocaleString()}</strong>
    </div>
    <div className="summary-item">
      <span>Allocated:</span>
      <strong className={Math.abs(totalWeight - 100) > 0.1 ? 'negative' : 'positive'}>
        {totalWeight.toFixed(1)}%
      </strong>
      {Math.abs(totalWeight - 100) > 0.1 && (
        <span className="pb-warning-inline">
          Not 100%
        </span>
      )}
    </div>
  </div>
);

const MetricsPanel = ({ metrics }) => (
  <div className="portfolio-metrics pb-metrics-wrap">
    <h3 className="pb-sub-title">Portfolio Metrics</h3>
    <div className="metrics-grid">
      <div className="metric-item">
        <span className="metric-label">Expected Return</span>
        <span className="metric-value">{metrics.expected_return.toFixed(2)}%</span>
      </div>
      <div className="metric-item">
        <span className="metric-label">Volatility</span>
        <span className="metric-value">{metrics.volatility.toFixed(2)}%</span>
      </div>
      <div className="metric-item">
        <span className="metric-label">Sharpe Ratio</span>
        <span className="metric-value">{metrics.sharpe_ratio.toFixed(2)}</span>
      </div>
    </div>
  </div>
);

const PortfolioBuilder = ({ apiBase }) => {
  const [allSecurities, setAllSecurities] = useState([]);
  const [portfolio, setPortfolio] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [assetFilter, setAssetFilter] = useState('all');
  const [marketFilter, setMarketFilter] = useState('all');
  const [financialSectorFilter, setFinancialSectorFilter] = useState('all');
  const [investmentAmount, setInvestmentAmount] = useState(100000);
  const [error, setError] = useState(null);
  const [filteredSecurities, setFilteredSecurities] = useState([]);
  const [optimizing, setOptimizing] = useState(false);
  const [autoOptimize, setAutoOptimize] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState(null);
  const [loadingSecurities, setLoadingSecurities] = useState(true);
  const [draggedTicker, setDraggedTicker] = useState(null);
  const [draftBaselineMetrics, setDraftBaselineMetrics] = useState(null);
  const [backendMetrics, setBackendMetrics] = useState(null);
  const [backendFrontier, setBackendFrontier] = useState(null);
  const [frontierFallbackReason, setFrontierFallbackReason] = useState('insufficient assets');
  const [historicalPerformance, setHistoricalPerformance] = useState(null);

  // Practical constraint settings
  const [minActiveWeight, setMinActiveWeight] = useState(1);     // % — positions below this are zeroed
  const [maxTurnover, setMaxTurnover] = useState(null);          // % — null means unconstrained
  const [constraintsApplied, setConstraintsApplied] = useState([]);
  const previousWeightsRef = useRef(null);

  // Phase 3 — Advanced analytics state
  const [analyticsTab, setAnalyticsTab] = useState('frontier');
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [benchmarkData, setBenchmarkData] = useState(null);
  const [backtestData, setBacktestData] = useState(null);
  const [stressData, setStressData] = useState(null);
  const [riskDecompData, setRiskDecompData] = useState(null);
  const [driftData, setDriftData] = useState(null);
  const [costBps, setCostBps] = useState(5); // default: 5 bps one-way

  const normalizeAssetClass = (value, fallback = 'stock') => {
    const normalized = String(value || fallback).trim().toLowerCase();
    if (['etf', 'fund'].includes(normalized)) return 'etf';
    if (['bond', 'fixed_income', 'fixed-income'].includes(normalized)) return 'bond';
    if (['crypto', 'cryptocurrency'].includes(normalized)) return 'crypto';
    if (['commodity', 'commodities'].includes(normalized)) return 'commodity';
    return 'stock';
  };

  const normalizeMarket = (value) => {
    const normalized = String(value || '').trim();
    return normalized || 'Unknown';
  };

  // Fetch all securities (stocks, ETFs, bonds)
  useEffect(() => {
    const fetchAllSecurities = async () => {
        setLoadingSecurities(true);
      try {
        const [stocksRes, etfsRes, bondsRes] = await Promise.all([
          axios.get(`${apiBase}/stocks/all`).catch(e => ({ data: { stocks: [] }, error: e })),
          axios.get(`${apiBase}/etfs/all`).catch(e => ({ data: { etfs: [] }, error: e })),
          axios.get(`${apiBase}/bonds/all`).catch(e => ({ data: { bonds: [] }, error: e }))
        ]);
        
        const stocks = stocksRes.data?.stocks || [];
        const etfs = etfsRes.data?.etfs || [];
        const bonds = bondsRes.data?.bonds || [];
        
        const normalizedSecurities = [
          ...stocks.map((security) => ({
            ...security,
            asset_class: normalizeAssetClass(security.asset_class, 'stock'),
            exchange: normalizeMarket(security.exchange),
            sector: security.sector || 'Unknown',
          })),
          ...etfs.map((security) => ({
            ...security,
            asset_class: normalizeAssetClass(security.asset_class, 'etf'),
            exchange: normalizeMarket(security.exchange),
            sector: security.sector || 'Unknown',
          })),
          ...bonds.map((security) => ({
            ...security,
            asset_class: normalizeAssetClass(security.asset_class, 'bond'),
            exchange: normalizeMarket(security.exchange),
            sector: security.sector || 'Unknown',
          }))
        ];

        const uniqueByTicker = new Map();
        normalizedSecurities.forEach((security) => {
          const key = String(security.ticker || '').toUpperCase();
          if (!key) return;
          uniqueByTicker.set(key, security);
        });

        setAllSecurities(Array.from(uniqueByTicker.values()));
        
        if (stocks.length === 0 && etfs.length === 0 && bonds.length === 0) {
          setError('No securities are currently available. Please try again later.');
        }
      } catch (error) {
        console.error('Error fetching securities:', error);
        setError('Unable to load securities. Please refresh the page and try again.');
        } finally {
          setLoadingSecurities(false);
      }
    };

    fetchAllSecurities();
  }, [apiBase]);

  useEffect(() => {
    const draftRaw = localStorage.getItem('builderDraftPortfolio');
    if (!draftRaw) return;

    try {
      const draft = JSON.parse(draftRaw);
      const draftHoldings = (draft.holdings || []).map((holding) => {
        const inferredPrice = holding.current_price || (holding.shares ? holding.value / holding.shares : null);
        return {
          ...holding,
          current_price: inferredPrice
        };
      });
      if (draftHoldings.length > 0) {
        const draftSummary = draft.summary || {};
        const draftMetrics = draft.metrics || {};
        const baselineExpectedReturn = normalizePercentValue(
          draftSummary.expected_return ?? draftMetrics.expected_return
        );
        const baselineVolatility = normalizePercentValue(
          draftSummary.volatility ?? draftMetrics.volatility
        );
        const baselineSharpe = toFiniteNumber(
          draftSummary.sharpe_ratio ?? draftMetrics.sharpe_ratio
        );

        if (baselineExpectedReturn !== null && baselineVolatility !== null) {
          setDraftBaselineMetrics({
            signature: buildHoldingsSignature(draftHoldings),
            expected_return: baselineExpectedReturn,
            volatility: baselineVolatility,
            sharpe_ratio:
              baselineSharpe !== null
                ? baselineSharpe
                : (baselineExpectedReturn - 2) / Math.max(baselineVolatility, 0.0001)
          });
        }

        setInvestmentAmount(draft.investment_amount || investmentAmount);
        setPortfolio(draftHoldings);
        if (draft.name) {
          setSaveName(draft.name);
        }
        // Portfolio loaded silently — no banner needed
      }
    } catch (err) {
      console.error('Failed to load draft portfolio:', err);
    } finally {
      localStorage.removeItem('builderDraftPortfolio');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Filter securities by type, market, sector, and search term
  useEffect(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    const byClass = allSecurities.filter((security) => {
      const currentClass = normalizeAssetClass(security.asset_class, 'stock');
      if (assetFilter === 'all') return true;
      return currentClass === assetFilter;
    });

    const byFinancialSector = byClass.filter((security) => {
      if (marketFilter !== 'all' && normalizeMarket(security.exchange) !== marketFilter) return false;
      if (financialSectorFilter === 'all') return true;
      if (normalizeAssetClass(security.asset_class, 'stock') !== 'stock') return false;
      return String(security.sector || '').toLowerCase() === financialSectorFilter;
    });

    const filtered = byFinancialSector
      .filter((security) => {
        if (!normalizedSearch) return true;
        return (
          String(security.ticker || '').toLowerCase().includes(normalizedSearch) ||
          String(security.name || '').toLowerCase().includes(normalizedSearch)
        );
      })
;

    setFilteredSecurities(filtered);
  }, [searchTerm, assetFilter, marketFilter, financialSectorFilter, allSecurities]);

  // Recalculate portfolio values when investment amount changes
  useEffect(() => {
    if (portfolio.length === 0) return;
    
    const updatedPortfolio = portfolio.map(p => {
      const value = (p.weight / 100) * investmentAmount;
      const shares = p.current_price ? value / p.current_price : 0;
      return { ...p, value, shares };
    });
    setPortfolio(updatedPortfolio);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [investmentAmount]);

  const activeHoldingsForMetrics = portfolio.filter((holding) => holding.weight > 0 && !!holding.ticker);
  const activeHoldingsSignature = buildHoldingsSignature(activeHoldingsForMetrics);

  useEffect(() => {
    const holdingsForMetrics = portfolio.filter((holding) => holding.weight > 0 && !!holding.ticker);

    if (!holdingsForMetrics.length) {
      setBackendMetrics(null);
      return;
    }

    if (draftBaselineMetrics && draftBaselineMetrics.signature === activeHoldingsSignature) {
      setBackendMetrics(null);
      return;
    }

    let cancelled = false;

    const fetchCovarianceMetrics = async () => {
      try {
        const payload = {
          holdings: holdingsForMetrics.map((holding) => ({
            ticker: holding.ticker,
            weight: holding.weight
          }))
        };

        const response = await axios.post(`${apiBase}/portfolio/covariance-metrics`, payload);
        const apiMetrics = response?.data?.metrics || null;

        const expectedReturn = normalizePercentValue(apiMetrics?.expected_return);
        const volatility = normalizePercentValue(apiMetrics?.volatility);
        const sharpe = toFiniteNumber(apiMetrics?.sharpe_ratio);

        if (!cancelled && expectedReturn !== null && volatility !== null) {
          setBackendMetrics({
            signature: activeHoldingsSignature,
            expected_return: expectedReturn,
            volatility: volatility,
            sharpe_ratio: sharpe !== null ? sharpe : (expectedReturn - 2) / Math.max(volatility, 0.0001)
          });
        }
      } catch (err) {
        if (!cancelled) {
          setBackendMetrics(null);
        }
      }
    };

    fetchCovarianceMetrics();

    return () => {
      cancelled = true;
    };
  }, [apiBase, activeHoldingsSignature, draftBaselineMetrics, portfolio]);

  useEffect(() => {
    const holdingsForFrontier = portfolio.filter((holding) => holding.weight > 0 && !!holding.ticker);
    if (holdingsForFrontier.length < 2) {
      setBackendFrontier(null);
      setFrontierFallbackReason('insufficient assets');
      return;
    }

    let cancelled = false;

    const fetchEfficientFrontier = async () => {
      try {
        const payload = {
          holdings: holdingsForFrontier.map((holding) => ({
            ticker: holding.ticker,
            weight: holding.weight
          }))
        };

        const response = await axios.post(`${apiBase}/portfolio/efficient-frontier`, payload);
        const frontier = Array.isArray(response?.data?.frontier)
          ? response.data.frontier.filter((point) => Number.isFinite(point?.risk) && Number.isFinite(point?.return))
          : [];
        const assetPoints = Array.isArray(response?.data?.asset_points)
          ? response.data.asset_points.filter((point) => Number.isFinite(point?.risk) && Number.isFinite(point?.return))
          : [];

        if (!cancelled && frontier.length > 0) {
          setBackendFrontier({
            signature: activeHoldingsSignature,
            frontier,
            assetPoints
          });
          setFrontierFallbackReason(null);
        } else if (!cancelled) {
          setBackendFrontier(null);
          setFrontierFallbackReason('insufficient frontier data');
        }
      } catch (err) {
        if (!cancelled) {
          setBackendFrontier(null);
          const detail = String(err?.response?.data?.detail || '');
          if (/insufficient|need at least two|no price data|aligned/i.test(detail)) {
            setFrontierFallbackReason('insufficient market data');
          } else {
            setFrontierFallbackReason('backend unavailable');
          }
        }
      }
    };

    fetchEfficientFrontier();

    return () => {
      cancelled = true;
    };
  }, [apiBase, activeHoldingsSignature, portfolio]);

  // Fetch historical portfolio performance from backend
  useEffect(() => {
    const holdingsForHistory = portfolio.filter((h) => h.weight > 0 && !!h.ticker);
    if (holdingsForHistory.length < 1) {
      setHistoricalPerformance(null);
      return;
    }

    let cancelled = false;

    const fetchHistorical = async () => {
      try {
        const payload = {
          holdings: holdingsForHistory.map((h) => ({
            ticker: h.ticker,
            weight: h.weight
          })),
          period: '1Y',
          initial_value: investmentAmount
        };
        const response = await axios.post(`${apiBase}/portfolio/historical-performance`, payload);
        const series = Array.isArray(response?.data?.series) ? response.data.series : [];
        if (!cancelled && series.length >= 2) {
          // Thin the series down to ~60 points max for chart readability
          const maxPoints = 60;
          let thinned = series;
          if (series.length > maxPoints) {
            const step = Math.ceil(series.length / maxPoints);
            thinned = series.filter((_, i) => i % step === 0 || i === series.length - 1);
          }
          // Shorten date labels for readability
          setHistoricalPerformance(thinned.map((pt) => ({
            date: pt.date.length > 7 ? pt.date.slice(5) : pt.date, // e.g. "02-28" from "2026-02-28"
            value: pt.value
          })));
        } else if (!cancelled) {
          setHistoricalPerformance(null);
        }
      } catch (err) {
        if (!cancelled) {
          setHistoricalPerformance(null);
        }
      }
    };

    fetchHistorical();

    return () => {
      cancelled = true;
    };
  }, [apiBase, activeHoldingsSignature, investmentAmount, portfolio]);

  // Optimize weights using the portfolio engine
  const optimizeWeights = async (tickers) => {
    if (!tickers || tickers.length === 0) return null;

    setOptimizing(true);
    try {
      // Build constraint payload
      const payload = {
        tickers: tickers,
        optimize_sharpe: autoOptimize
      };
      if (minActiveWeight > 0) {
        payload.min_active_weight = minActiveWeight / 100;   // convert % → decimal
      }
      if (maxTurnover !== null && maxTurnover > 0 && previousWeightsRef.current) {
        payload.max_turnover = maxTurnover / 100;            // convert % → decimal
        payload.previous_weights = previousWeightsRef.current;
      }

      const response = await axios.post(`${apiBase}/portfolio/optimize-weights`, payload);

      // Track which constraints the backend actually applied
      if (response.data.constraints_applied) {
        setConstraintsApplied(response.data.constraints_applied);
      }

      if (autoOptimize && response.data.optimized === false) {
        setError(response.data.message || 'Optimization failed, using equal weights.');
      }

      return response.data.weights;
    } catch (error) {
      console.error('Error optimizing weights:', error);
      if (autoOptimize) {
        const apiMessage = error?.response?.data?.message || error?.response?.data?.error || error?.response?.data?.detail;
        setError(apiMessage || 'Optimization failed. Showing equal weights.');
      }
      // Fallback to equal weights
      const equalWeight = 100 / tickers.length;
      return tickers.map(ticker => ({ ticker, weight: equalWeight }));
    } finally {
      setOptimizing(false);
    }
  };

  // Add stock to portfolio with optimized or equal weight
  const addToPortfolio = async (stock) => {
    // Check if already in portfolio
    if (portfolio.some(p => p.ticker === stock.ticker)) {
      setError(`${stock.ticker} is already in your portfolio`);
      return;
    }

    setError(null); // Clear any previous errors
    
    // Get all tickers including the new one
    const allTickers = [...portfolio.map(p => p.ticker), stock.ticker];
    
    try {
      // If optimization disabled OR only 1 stock total, just add with equal weight
      if (!autoOptimize || portfolio.length === 0) {
        const equalWeight = 100 / allTickers.length;
        const newPortfolio = allTickers.map(ticker => {
          const stockData = ticker === stock.ticker ? stock : portfolio.find(p => p.ticker === ticker);
          const value = (equalWeight / 100) * investmentAmount;
          const shares = stockData?.current_price ? value / stockData.current_price : 0;
          
          return {
            ...stockData,
            weight: equalWeight,
            shares: shares,
            value: value
          };
        });
        setPortfolio(newPortfolio);
        return;
      }

      // Optimize weights for all tickers
      const optimizedWeights = await optimizeWeights(allTickers);
      
      if (!optimizedWeights || optimizedWeights.length === 0) {
        throw new Error('Failed to get weights from optimizer');
      }

      // Build new portfolio with optimized weights
      const newPortfolio = allTickers.map(ticker => {
        const weightData = optimizedWeights.find(w => w.ticker === ticker);
        const weight = weightData?.weight || (100 / allTickers.length);
        const value = (weight / 100) * investmentAmount;
        
        const stockData = ticker === stock.ticker ? stock : portfolio.find(p => p.ticker === ticker);
        const shares = stockData?.current_price ? value / stockData.current_price : 0;

        return {
          ...stockData,
          weight: weight,
          expected_return: weightData?.expected_return ?? stockData?.expected_return,
          volatility: weightData?.volatility ?? stockData?.volatility,
          shares: shares,
          value: value
        };
      });

      setPortfolio(newPortfolio);
    } catch (err) {
      console.error('Error adding stock:', err);
      setError(`Failed to add ${stock.ticker}: ${err.message || 'Unknown error'}`);
    }
  };

  // Remove stock from portfolio and reoptimize if enabled
  const removeFromPortfolio = async (ticker) => {
    const remaining = portfolio.filter(p => p.ticker !== ticker);
    
    if (remaining.length === 0) {
      setPortfolio([]);
      setError(null);
      return;
    }

    if (!autoOptimize || remaining.length === 1) {
      // Just remove and use equal weights for remaining
      const equalWeight = 100 / remaining.length;
      const updated = remaining.map(p => ({
        ...p,
        weight: equalWeight,
        value: (equalWeight / 100) * investmentAmount,
        shares: ((equalWeight / 100) * investmentAmount) / (p.current_price || 1)
      }));
      setPortfolio(updated);
      setError(null);
      return;
    }

    try {
      // Reoptimize weights for remaining stocks
      const remainingTickers = remaining.map(p => p.ticker);
      const optimizedWeights = await optimizeWeights(remainingTickers);
      
      if (!optimizedWeights || optimizedWeights.length === 0) {
        throw new Error('Failed to reoptimize portfolio');
      }

      // Update portfolio with new optimized weights
      const updatedPortfolio = remaining.map(p => {
        const weightData = optimizedWeights.find(w => w.ticker === p.ticker);
        const weight = weightData?.weight || p.weight;
        const value = (weight / 100) * investmentAmount;
        const shares = p.current_price ? value / p.current_price : 0;
        
        return {
          ...p,
          weight: weight,
          expected_return: weightData?.expected_return ?? p.expected_return,
          volatility: weightData?.volatility ?? p.volatility,
          shares: shares,
          value: value
        };
      });

      setPortfolio(updatedPortfolio);
      setError(null);
    } catch (err) {
      console.error('Error removing stock:', err);
      // Fallback: just remove it with equal weights
      const equalWeight = 100 / remaining.length;
      const fallback = remaining.map(p => ({
        ...p,
        weight: equalWeight,
        value: (equalWeight / 100) * investmentAmount,
        shares: ((equalWeight / 100) * investmentAmount) / (p.current_price || 1)
      }));
      setPortfolio(fallback);
      setError(`Removed ${ticker}. Note: weights reset to equal.`);
    }
  };

  // Update stock weight in portfolio
  const updateWeight = (ticker, weight) => {
    const weightNum = parseFloat(weight) || 0;
    
    // Prevent negative weights
    if (weightNum < 0) {
      setError('Weight cannot be negative');
      return;
    }
    
    const updatedPortfolio = portfolio.map(p => {
      if (p.ticker === ticker) {
        const value = (weightNum / 100) * investmentAmount;
        const shares = value / (p.current_price || 1);
        return { ...p, weight: weightNum, value, shares };
      }
      return p;
    });
    
    // Check if total exceeds 100%
    const total = updatedPortfolio.reduce((sum, p) => sum + p.weight, 0);
    if (total > 100) {
      setError(`Total allocation is ${total.toFixed(1)}%. Please normalize or adjust weights.`);
    } else {
      setError(null);
    }
    
    setPortfolio(updatedPortfolio);
  };

  // Normalize weights to sum to 100%
  const normalizeWeights = () => {
    const totalWeight = portfolio.reduce((sum, p) => sum + p.weight, 0);
    if (totalWeight === 0) return;

    const normalized = portfolio.map(p => ({
      ...p,
      weight: (p.weight / totalWeight) * 100
    }));

    setPortfolio(normalized.map(p => ({
      ...p,
      value: (p.weight / 100) * investmentAmount,
      shares: ((p.weight / 100) * investmentAmount) / (p.current_price || 1)
    })));
  };

  // Reoptimize all weights using the engine
  const reoptimizePortfolio = async () => {
    if (portfolio.length === 0) return;
    
    const tickers = portfolio.map(p => p.ticker);
    const optimizedWeights = await optimizeWeights(tickers);
    
    if (!optimizedWeights) return;

    // Update portfolio with new optimized weights
    const updatedPortfolio = portfolio.map(p => {
      const weightData = optimizedWeights.find(w => w.ticker === p.ticker);
      const weight = weightData ? weightData.weight : p.weight;
      const value = (weight / 100) * investmentAmount;
      const shares = p.current_price ? value / p.current_price : 0;
      
      return {
        ...p,
        weight: weight,
        expected_return: weightData?.expected_return ?? p.expected_return,
        volatility: weightData?.volatility ?? p.volatility,
        shares: shares,
        value: value
      };
    });

    setPortfolio(updatedPortfolio);
  };

  // When auto-optimize is turned on, reoptimize current holdings
  useEffect(() => {
    if (autoOptimize && portfolio.length > 1) {
      reoptimizePortfolio();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoOptimize]);

  // Track previous weights for turnover constraint
  useEffect(() => {
    if (portfolio.length === 0) {
      previousWeightsRef.current = null;
      return;
    }
    const weightMap = {};
    portfolio.forEach((h) => {
      if (h.ticker && Number.isFinite(h.weight)) {
        weightMap[h.ticker] = h.weight / 100; // store as decimal
      }
    });
    if (Object.keys(weightMap).length > 0) {
      previousWeightsRef.current = weightMap;
    }
  }, [portfolio]);

  // Calculate portfolio metrics
  const calculateFallbackMetrics = () => {
    const holdings = portfolio.filter(p => p.weight > 0);
    if (holdings.length === 0) return { expected_return: 0, volatility: 0, sharpe_ratio: 0 };

    const currentSignature = buildHoldingsSignature(holdings);
    if (draftBaselineMetrics && currentSignature === draftBaselineMetrics.signature) {
      return {
        expected_return: draftBaselineMetrics.expected_return,
        volatility: draftBaselineMetrics.volatility,
        sharpe_ratio: draftBaselineMetrics.sharpe_ratio
      };
    }

    const weights = holdings.map((holding) => holding.weight / 100);
    const expectedReturns = holdings.map((holding) => getHoldingExpectedReturnPct(holding) / 100);
    const volatilities = holdings.map((holding) => getHoldingVolatilityPct(holding) / 100);
    const correlation = buildCorrelationMatrix(holdings);

    const covariance = volatilities.map((sigmaI, rowIdx) => (
      volatilities.map((sigmaJ, colIdx) => sigmaI * sigmaJ * correlation[rowIdx][colIdx])
    ));

    const expectedReturnDecimal = weights.reduce((sum, weight, idx) => sum + weight * expectedReturns[idx], 0);

    let variance = 0;
    for (let rowIdx = 0; rowIdx < weights.length; rowIdx += 1) {
      for (let colIdx = 0; colIdx < weights.length; colIdx += 1) {
        variance += weights[rowIdx] * covariance[rowIdx][colIdx] * weights[colIdx];
      }
    }

    const volatilityDecimal = Math.sqrt(Math.max(variance, 0));
    const expectedReturn = expectedReturnDecimal * 100;
    const volatility = volatilityDecimal * 100;

    return {
      expected_return: expectedReturn,
      volatility: volatility,
      sharpe_ratio: volatility > 0 ? (expectedReturn - 2) / volatility : 0
    };
  };

  // Get sector distribution
  const getSectorDistribution = () => {
    const sectors = {};
    portfolio.filter(p => p.weight > 0).forEach(holding => {
      const sector = holding.sector || 'Unknown';
      sectors[sector] = (sectors[sector] || 0) + holding.weight;
    });

    const entries = Object.entries(sectors).map(([name, value]) => ({
      name,
      value: parseFloat(value.toFixed(2))
    }));
    return entries
      .sort((a, b) => b.value - a.value);
  };

  // Format asset type for display
  const formatAssetType = (type) => {
    const typeMap = { 'stock': 'Stock', 'etf': 'ETF', 'bond': 'Bond' };
    return typeMap[type] || 'Stock';
  };

  // Get asset allocation
  const getAssetAllocation = () => {
    const allocation = {};
    portfolio.filter(p => p.weight > 0).forEach(holding => {
      const assetClass = (holding.asset_class?.toLowerCase() || 'stock');
      const displayType = formatAssetType(assetClass);
      allocation[displayType] = (allocation[displayType] || 0) + holding.weight;
    });

    const entries = Object.entries(allocation).map(([name, value]) => ({
      name,
      value: parseFloat(value.toFixed(2))
    }));
    return entries
      .sort((a, b) => b.value - a.value);
  }

  const reorderHoldings = (sourceTicker, targetTicker) => {
    if (!sourceTicker || !targetTicker || sourceTicker === targetTicker) return;
    const current = [...portfolio];
    const sourceIndex = current.findIndex((item) => item.ticker === sourceTicker);
    const targetIndex = current.findIndex((item) => item.ticker === targetTicker);
    if (sourceIndex === -1 || targetIndex === -1) return;

    const [moved] = current.splice(sourceIndex, 1);
    current.splice(targetIndex, 0, moved);
    setPortfolio(current);
  };

  const moveHolding = (ticker, direction) => {
    const current = [...portfolio];
    const sourceIndex = current.findIndex((item) => item.ticker === ticker);
    if (sourceIndex === -1) return;

    const targetIndex = direction === 'up' ? sourceIndex - 1 : sourceIndex + 1;
    if (targetIndex < 0 || targetIndex >= current.length) return;

    const [moved] = current.splice(sourceIndex, 1);
    current.splice(targetIndex, 0, moved);
    setPortfolio(current);
  };

  const getPerformanceSeries = () => {
    if (!Number.isFinite(metrics.expected_return) || metrics.expected_return <= -95) return [];

    const annualReturn = clamp(metrics.expected_return, -80, 120) / 100;
    const monthlyRate = Math.pow(1 + annualReturn, 1 / 12) - 1;
    let value = Number.isFinite(investmentAmount) && investmentAmount > 0 ? investmentAmount : 100;

    return Array.from({ length: 12 }, (_, idx) => {
      value *= 1 + monthlyRate;
      return { date: `M${idx + 1}`, value: Number(value.toFixed(2)) };
    });
  };

  const getCorrelationData = () => {
    const frontierUniverse = portfolio.filter((holding) => !!holding?.ticker);
    const labels = frontierUniverse.map((holding) => holding.ticker);
    if (labels.length < 2) return { labels, matrix: [] };

    return { labels, matrix: buildCorrelationMatrix(frontierUniverse) };
  };

  const getRiskReturnData = () => {
    if (backendFrontier && backendFrontier.signature === activeHoldingsSignature && backendFrontier.assetPoints.length > 0) {
      return backendFrontier.assetPoints;
    }

    const frontierUniverse = portfolio.filter((holding) => !!holding?.ticker);

    return frontierUniverse
      .map((holding) => {
        const expectedReturn = getHoldingExpectedReturnPct(holding);
        const volatility = getHoldingVolatilityPct(holding);

        return {
          name: holding.ticker,
          return: expectedReturn,
          risk: volatility,
          weight: holding.weight
        };
      })
      .filter((point) => Number.isFinite(point.return) && Number.isFinite(point.risk));
  };

  const getEfficientFrontierData = () => {
    if (backendFrontier && backendFrontier.signature === activeHoldingsSignature && backendFrontier.frontier.length > 1) {
      return backendFrontier.frontier;
    }

    // DEPRECATED: Heuristic Monte-Carlo frontier fallback.  Used only when
    // the backend empirical frontier hasn't loaded yet.
    console.warn('[DEPRECATED] Falling back to heuristic correlation-based frontier');

    const points = getRiskReturnData();
    if (points.length < 2) return [];

    const frontierUniverse = portfolio.filter((holding) => !!holding?.ticker);
    if (frontierUniverse.length < 2) return [];

    const expectedReturns = points.map((point) => point.return / 100);
    const volatilities = points.map((point) => point.risk / 100);
    const correlation = buildCorrelationMatrix(frontierUniverse);
    const covariance = volatilities.map((sigmaI, rowIdx) => (
      volatilities.map((sigmaJ, colIdx) => sigmaI * sigmaJ * correlation[rowIdx][colIdx])
    ));

    const portfolioStats = (weights) => {
      const portfolioReturn = weights.reduce((sum, weight, idx) => sum + weight * expectedReturns[idx], 0);
      let variance = 0;
      for (let rowIdx = 0; rowIdx < weights.length; rowIdx += 1) {
        for (let colIdx = 0; colIdx < weights.length; colIdx += 1) {
          variance += weights[rowIdx] * covariance[rowIdx][colIdx] * weights[colIdx];
        }
      }
      return {
        risk: Math.sqrt(Math.max(variance, 0)),
        return: portfolioReturn
      };
    };

    const randomWeights = () => {
      const values = points.map(() => Math.random());
      const total = values.reduce((sum, value) => sum + value, 0) || 1;
      return values.map((value) => value / total);
    };

    const candidates = [];

    const equalWeights = points.map(() => 1 / points.length);
    candidates.push(portfolioStats(equalWeights));

    points.forEach((_, idx) => {
      const unit = points.map((__, unitIdx) => (unitIdx === idx ? 1 : 0));
      candidates.push(portfolioStats(unit));
    });

    const sampleCount = Math.max(1400, points.length * 450);
    for (let sampleIdx = 0; sampleIdx < sampleCount; sampleIdx += 1) {
      candidates.push(portfolioStats(randomWeights()));
    }

    const returns = candidates.map((entry) => entry.return);
    const minReturn = Math.min(...returns);
    const maxReturn = Math.max(...returns);

    if (!Number.isFinite(minReturn) || !Number.isFinite(maxReturn) || maxReturn <= minReturn) {
      return [];
    }

    const bins = 24;
    const step = (maxReturn - minReturn) / bins;
    const bestPerBin = new Map();

    candidates.forEach((candidate) => {
      const bin = Math.min(bins - 1, Math.max(0, Math.floor((candidate.return - minReturn) / (step || 1))));
      const existing = bestPerBin.get(bin);
      if (!existing || candidate.risk < existing.risk) {
        bestPerBin.set(bin, candidate);
      }
    });

    const sorted = Array.from(bestPerBin.values()).sort((left, right) => left.return - right.return);

    return sorted.map((point) => ({
      risk: Number((point.risk * 100).toFixed(2)),
      return: Number((point.return * 100).toFixed(2))
    }));
  };

  const fallbackMetrics = calculateFallbackMetrics();
  const metrics =
    backendMetrics && backendMetrics.signature === activeHoldingsSignature
      ? backendMetrics
      : fallbackMetrics;
  const isBackendFrontierActive =
    backendFrontier &&
    backendFrontier.signature === activeHoldingsSignature &&
    backendFrontier.frontier.length > 1;
  const frontierModelLabel = isBackendFrontierActive
    ? 'Frontier: Backend covariance model'
    : `Frontier: Local fallback model (${frontierFallbackReason || 'backend unavailable'})`;
  const totalWeight = portfolio.reduce((sum, p) => sum + p.weight, 0);
  const allocationGap = Math.abs(totalWeight - 100);
  const holdings = portfolio.filter(p => p.weight > 0);
  const selectedTickers = new Set(portfolio.map(p => p.ticker));
  const marketOptions = Array.from(
    new Set(
      allSecurities
        .map((security) => normalizeMarket(security.exchange))
        .filter((market) => market && market !== 'Unknown')
    )
  ).sort((left, right) => left.localeCompare(right));
  const financialSectorOptions = Array.from(
    new Set(
      allSecurities
        .filter((security) => normalizeAssetClass(security.asset_class, 'stock') === 'stock')
        .map((security) => String(security.sector || '').trim())
        .filter((sector) => sector && sector !== 'Unknown')
    )
  ).sort((left, right) => left.localeCompare(right));

  const handleSavePortfolio = async () => {
    const authUser = localStorage.getItem('authUser');
    if (!authUser) {
      setSaveMessage('Please sign in to save your portfolio.');
      return;
    }

    if (holdings.length === 0) {
      setSaveMessage('Add holdings before saving.');
      return;
    }

    const name = saveName.trim() || `Builder Portfolio ${new Date().toLocaleDateString()}`;
    const payload = {
      name,
      source: 'builder',
      data: {
        investment_amount: investmentAmount,
        holdings: holdings,
        summary: {
          total_holdings: holdings.length,
          expected_return: metrics.expected_return,
          volatility: metrics.volatility,
          sharpe_ratio: metrics.sharpe_ratio
        },
        metrics: metrics
      }
    };

    setSaving(true);
    setSaveMessage(null);
    try {
      await axios.post(`${apiBase}/portfolios/save`, payload, { withCredentials: true });
      setSaveMessage('Portfolio saved.');
    } catch (err) {
      const apiMessage = err?.response?.data?.message || err?.response?.data?.error || err?.response?.data?.detail;
      setSaveMessage(apiMessage || 'Failed to save portfolio.');
    } finally {
      setSaving(false);
    }
  };

  // Phase 3 — Analytics run handler
  const runAnalytics = async (tab) => {
    if (holdings.length === 0) return;
    setAnalyticsLoading(true);
    try {
      const holdingsPayload = holdings.map((h) => ({
        ticker: h.ticker,
        weight: h.weight / 100,
      }));

      if (tab === 'benchmark') {
        const res = await axios.post(`${apiBase}/portfolio/benchmark-analytics`, {
          holdings: holdingsPayload,
          benchmark_ticker: 'SPY',
          period: '1Y',
        });
        setBenchmarkData(res.data);
      } else if (tab === 'backtest') {
        const res = await axios.post(`${apiBase}/portfolio/backtest`, {
          holdings: holdingsPayload,
          period: '1Y',
          rebalance_frequency: 'monthly',
          initial_value: investmentAmount,
          cost_bps: costBps,
        });
        setBacktestData(res.data);
      } else if (tab === 'stress') {
        const res = await axios.post(`${apiBase}/portfolio/stress-test`, {
          holdings: holdingsPayload,
        });
        setStressData(res.data);
      } else if (tab === 'riskDecomp') {
        const res = await axios.post(`${apiBase}/portfolio/risk-decomposition`, {
          holdings: holdingsPayload,
        });
        setRiskDecompData(res.data);
      } else if (tab === 'drift') {
        const res = await axios.post(`${apiBase}/portfolio/drift-monitor`, {
          holdings: holdingsPayload,
          rebalance_threshold: 5.0,
        });
        setDriftData(res.data);
      }
    } catch (err) {
      console.error(`Analytics error (${tab}):`, err);
    } finally {
      setAnalyticsLoading(false);
    }
  };

  return (
    <div className="page-container portfolio-builder-root">
      <div className="page-header">
        <h1 className="pb-page-title">Portfolio Builder</h1>
        <p className="page-subtitle pb-page-subtitle">
          Customize your portfolio by selecting stocks and setting weights
        </p>
      </div>

      <div className={`pb-layout-grid ${holdings.length > 0 ? 'with-results' : 'single-column'}`}>
        {/* Step 1 + 2 */}
        <div>
          <div className="form-section pb-form-section">
            <div className="pb-step-head">
              <span className="pb-step-index">1</span>
              <h2 className="pb-section-title">Set Portfolio Preferences</h2>
            </div>

            <div className="form-group pb-compact-group">
              <label>Investment Amount ($)</label>
              <input
                type="number"
                value={investmentAmount}
                onChange={(e) => setInvestmentAmount(parseFloat(e.target.value))}
                min="1000"
                step="1000"
                className="form-control"
              />
            </div>

            <div className="form-group pb-compact-group">
              <label
                className="pb-label-row pb-check-row"
                title={autoOptimize
                  ? 'Weights automatically optimize for best return/volatility ratio when you add or remove stocks'
                  : 'Manual mode — set your own weights freely'}
              >
                <input
                  type="checkbox"
                  checked={autoOptimize}
                  onChange={(e) => setAutoOptimize(e.target.checked)}
                  className="pb-check-input"
                />
                <span className="pb-check-title">Auto-Optimize Weights</span>
              </label>
            </div>

            {autoOptimize && (
              <div className="pb-constraints-panel">
                <div className="pb-constraints-row">
                  <div className="pb-constraint-field">
                    <label className="pb-constraint-label">Min Position (%)</label>
                    <input
                      type="number"
                      value={minActiveWeight}
                      onChange={(e) => setMinActiveWeight(Math.max(0, parseFloat(e.target.value) || 0))}
                      min="0"
                      max="20"
                      step="0.5"
                      className="form-control pb-constraint-input"
                      title="Positions below this weight are zeroed out"
                    />
                  </div>
                  <div className="pb-constraint-field">
                    <label className="pb-constraint-label">
                      <input
                        type="checkbox"
                        checked={maxTurnover !== null}
                        onChange={(e) => setMaxTurnover(e.target.checked ? 50 : null)}
                        className="pb-check-input"
                      />
                      Max Turnover (%)
                    </label>
                    <input
                      type="number"
                      value={maxTurnover ?? ''}
                      onChange={(e) => setMaxTurnover(Math.max(5, Math.min(100, parseFloat(e.target.value) || 50)))}
                      min="5"
                      max="100"
                      step="5"
                      disabled={maxTurnover === null}
                      className="form-control pb-constraint-input"
                      title="Max total weight change vs current portfolio"
                    />
                  </div>
                </div>
                {constraintsApplied.length > 0 && (
                  <small className="pb-constraints-applied">
                    Applied: {constraintsApplied.join(', ')}
                  </small>
                )}
              </div>
            )}

            {optimizing && (
              <div className="pb-optimizing-banner">
                Optimizing weights...
              </div>
            )}

            <AssetSearchSection
              searchValue={searchTerm}
              onSearchChange={setSearchTerm}
              assetFilter={assetFilter}
              onFilterChange={setAssetFilter}
              marketFilter={marketFilter}
              onMarketChange={setMarketFilter}
              marketOptions={marketOptions}
              financialSectorFilter={financialSectorFilter}
              onFinancialSectorChange={setFinancialSectorFilter}
              financialSectorOptions={financialSectorOptions}
              items={filteredSecurities}
              onSelect={addToPortfolio}
              loading={loadingSecurities}
              selectedTickers={selectedTickers}
            />

            {error && <div className="error-message pb-error-inline">{error}</div>}
          </div>
        </div>

        {/* Step 3 */}
        {holdings.length > 0 && (
          <div>
            <div className="results-section">
              <div className={`pb-health-bar ${allocationGap > 0.1 ? 'warning' : 'healthy'}`}>
                <div className="pb-health-items">
                  <span><strong>{holdings.length}</strong> holdings</span>
                  <span><strong>${investmentAmount.toLocaleString()}</strong> investment</span>
                  <span>
                    Allocation <strong>{totalWeight.toFixed(1)}%</strong>
                  </span>
                </div>
                {allocationGap > 0.1 ? (
                  <button onClick={normalizeWeights} className="pb-health-fix-btn">
                    Normalize to 100%
                  </button>
                ) : (
                  <span className="pb-health-ok">Balanced</span>
                )}
              </div>

              <div className="pb-results-head">
                <div className="pb-step-head pb-inline-head">
                  <span className="pb-step-index">3</span>
                  <h2 className="pb-section-title">Review & Save</h2>
                  <span className={`pb-model-badge ${isBackendFrontierActive ? 'backend' : 'fallback'}`}>
                    {frontierModelLabel}
                  </span>
                </div>
                <div className="pb-results-actions">
                  <input
                    type="text"
                    value={saveName}
                    onChange={(e) => setSaveName(e.target.value)}
                    placeholder="Portfolio name"
                    className="form-control pb-name-input"
                  />
                  <button
                    onClick={handleSavePortfolio}
                    disabled={saving}
                    className="pb-action-btn pb-save-btn"
                  >
                    {saving ? 'Saving...' : 'Save'}
                  </button>
                  <button
                    onClick={reoptimizePortfolio}
                    disabled={optimizing || !autoOptimize}
                    className={`pb-action-btn secondary ${(optimizing || !autoOptimize) ? 'disabled' : ''}`}
                    title={!autoOptimize ? 'Enable Auto-Optimize to use this' : 'Re-run weight optimization'}
                  >
                    {optimizing ? 'Optimizing...' : 'Re-Optimize'}
                  </button>
                </div>
              </div>
              {saveMessage && (
                <div className={`pb-save-message ${saveMessage.includes('saved') ? 'success' : 'error'}`}>
                  {saveMessage}
                </div>
              )}
              <PortfolioSummary
                holdingsCount={holdings.length}
                investmentAmount={investmentAmount}
                totalWeight={totalWeight}
              />

              <MetricsPanel metrics={metrics} />

              <ChartsPanel
                sectorData={getSectorDistribution()}
                assetData={getAssetAllocation()}
                riskReturnData={getRiskReturnData()}
                performanceData={getPerformanceSeries()}
                historicalPerformance={historicalPerformance}
                isBackendFrontierActive={isBackendFrontierActive}
                frontierFallbackReason={frontierFallbackReason}
                showSector={true}
                showAsset={true}
                showPerformance={false}
                showRiskReturn={false}
                className="pb-chart-grid-top"
              />
            </div>
          </div>
        )}
      </div>

      {holdings.length > 0 && (
        <div className="results-section pb-results-section-bottom">
          <ChartsPanel
            sectorData={getSectorDistribution()}
            assetData={getAssetAllocation()}
            riskReturnData={getRiskReturnData()}
            performanceData={getPerformanceSeries()}
            historicalPerformance={historicalPerformance}
            isBackendFrontierActive={isBackendFrontierActive}
            frontierFallbackReason={frontierFallbackReason}
            showSector={false}
            showAsset={false}
            showPerformance={true}
            showRiskReturn={true}
          />

          {holdings.length >= 2 && (
            <AnalyticsPanel
              activeTab={analyticsTab}
              onTabChange={setAnalyticsTab}
              benchmarkData={benchmarkData}
              backtestData={backtestData}
              stressData={stressData}
              riskDecompData={riskDecompData}
              driftData={driftData}
              frontierData={getEfficientFrontierData()}
              correlation={getCorrelationData()}
              isBackendFrontierActive={isBackendFrontierActive}
              frontierFallbackReason={frontierFallbackReason}
              onRun={runAnalytics}
              loading={analyticsLoading}
              costBps={costBps}
              onCostBpsChange={setCostBps}
            />
          )}

          <HoldingsTable
            holdings={holdings}
            onWeightChange={updateWeight}
            onRemove={removeFromPortfolio}
            onMoveUp={(ticker) => moveHolding(ticker, 'up')}
            onMoveDown={(ticker) => moveHolding(ticker, 'down')}
            onDragStart={(ticker) => setDraggedTicker(ticker)}
            onDrop={(ticker) => {
              reorderHoldings(draggedTicker, ticker);
              setDraggedTicker(null);
            }}
            onDragEnd={() => setDraggedTicker(null)}
          />
        </div>
      )}
    </div>
  );
};

export default PortfolioBuilder;
