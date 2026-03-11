import React from 'react';
import { FiTrendingUp, FiBarChart2, FiAlertTriangle, FiTarget, FiRefreshCw, FiShield, FiActivity, FiGrid } from 'react-icons/fi';
import { Card, CardHeader, CardBody, PerformanceLineChart, EfficientFrontierChart, CorrelationHeatmap } from '../components';
import { formatPct, formatNum } from './portfolioBuilderUtils';

const ANALYTICS_TABS = [
  { key: 'frontier', label: 'Frontier', icon: FiActivity },
  { key: 'correlation', label: 'Correlation', icon: FiGrid },
  { key: 'benchmark', label: 'Benchmark', icon: FiTrendingUp },
  { key: 'backtest', label: 'Backtest', icon: FiBarChart2 },
  { key: 'stress', label: 'Stress Test', icon: FiAlertTriangle },
  { key: 'riskDecomp', label: 'Risk Decomp', icon: FiTarget },
  { key: 'drift', label: 'Drift', icon: FiRefreshCw },
];

const BenchmarkTab = ({ data }) => {
  if (!data) return <p className="pb-analytics-empty">Click "Run" to compute benchmark-relative metrics.</p>;
  return (
    <div className="pb-analytics-result">
      <div className="pb-analytics-grid">
        <div className="pb-analytics-stat"><span className="pb-stat-label">Alpha (ann.)</span><span className="pb-stat-value">{formatPct(data.alpha * 100)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Beta</span><span className="pb-stat-value">{formatNum(data.beta)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Tracking Error</span><span className="pb-stat-value">{formatPct(data.tracking_error * 100)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Info Ratio</span><span className="pb-stat-value">{formatNum(data.information_ratio)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">R²</span><span className="pb-stat-value">{formatNum(data.r_squared)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Observations</span><span className="pb-stat-value">{data.n_observations}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Portfolio Return</span><span className="pb-stat-value">{formatPct(data.ann_portfolio_return * 100)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Benchmark Return</span><span className="pb-stat-value">{formatPct(data.ann_benchmark_return * 100)}</span></div>
      </div>
      {data.tickers_missing?.length > 0 && (
        <p className="pb-analytics-warn">Missing price data: {data.tickers_missing.join(', ')}</p>
      )}
    </div>
  );
};

const BacktestTab = ({ data }) => {
  if (!data) return <p className="pb-analytics-empty">Click "Run" to simulate a historical backtest.</p>;
  const s = data.summary || {};
  return (
    <div className="pb-analytics-result">
      <div className="pb-analytics-grid">
        <div className="pb-analytics-stat"><span className="pb-stat-label">Total Return</span><span className="pb-stat-value">{formatPct(s.total_return_pct)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Ann. Return</span><span className="pb-stat-value">{formatPct(s.annualised_return_pct)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Ann. Volatility</span><span className="pb-stat-value">{formatPct(s.annualised_volatility_pct)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Sharpe</span><span className="pb-stat-value">{formatNum(s.sharpe_ratio)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Max Drawdown</span><span className="pb-stat-value">{formatPct(s.max_drawdown_pct)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Final Value</span><span className="pb-stat-value">${s.final_value?.toLocaleString(undefined, { maximumFractionDigits: 0 }) || '—'}</span></div>
        {s.total_transaction_cost > 0 && (
          <div className="pb-analytics-stat"><span className="pb-stat-label">Txn Cost</span><span className="pb-stat-value pb-negative">${s.total_transaction_cost?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span></div>
        )}
        {s.cost_bps > 0 && (
          <div className="pb-analytics-stat"><span className="pb-stat-label">Cost Rate</span><span className="pb-stat-value">{s.cost_bps} bps</span></div>
        )}
      </div>
      <p className="pb-analytics-note">Rebalance: {data.rebalance_frequency} | {data.n_rebalances} events | Period: {data.period}</p>
      {data.series?.length > 0 && (
        <div className="pb-backtest-chart">
          <PerformanceLineChart
            data={data.series.map(p => ({ label: p.date, value: p.value }))}
            height={220}
          />
        </div>
      )}
    </div>
  );
};

const StressTab = ({ data }) => {
  if (!data) return <p className="pb-analytics-empty">Click "Run" to apply stress scenarios.</p>;
  return (
    <div className="pb-analytics-result">
      <table className="pb-analytics-table">
        <thead><tr><th>Scenario</th><th>Portfolio Impact</th></tr></thead>
        <tbody>
          {(data.scenarios || []).map((sc) => (
            <tr key={sc.scenario}>
              <td>{sc.label}</td>
              <td className={sc.portfolio_impact_pct < 0 ? 'pb-negative' : 'pb-positive'}>
                {formatPct(sc.portfolio_impact_pct)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const RiskDecompTab = ({ data }) => {
  if (!data) return <p className="pb-analytics-empty">Click "Run" to decompose portfolio risk.</p>;
  return (
    <div className="pb-analytics-result">
      <div className="pb-analytics-grid" style={{ marginBottom: 12 }}>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Portfolio Vol</span><span className="pb-stat-value">{formatPct(data.portfolio_volatility * 100)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Assets Aligned</span><span className="pb-stat-value">{data.n_assets}</span></div>
      </div>
      <table className="pb-analytics-table">
        <thead><tr><th>Ticker</th><th>Weight</th><th>Marginal CTR</th><th>% of Risk</th></tr></thead>
        <tbody>
          {(data.assets || []).slice(0, 15).map((a) => (
            <tr key={a.ticker}>
              <td>{a.ticker}</td>
              <td>{(a.weight * 100).toFixed(1)}%</td>
              <td>{formatNum(a.marginal_contribution, 6)}</td>
              <td className={a.pct_contribution < 0 ? 'pb-negative' : ''}>{formatPct(a.pct_contribution)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const DriftTab = ({ data }) => {
  if (!data) return <p className="pb-analytics-empty">Click "Run" to check portfolio drift.</p>;
  return (
    <div className="pb-analytics-result">
      <div className="pb-analytics-grid" style={{ marginBottom: 12 }}>
        <div className="pb-analytics-stat">
          <span className="pb-stat-label">Drift Score</span>
          <span className="pb-stat-value">{formatNum(data.drift_score, 2)}%</span>
        </div>
        <div className="pb-analytics-stat">
          <span className="pb-stat-label">Needs Rebalance</span>
          <span className={`pb-stat-value ${data.needs_rebalance ? 'pb-negative' : 'pb-positive'}`}>
            {data.needs_rebalance ? 'YES' : 'No'}
          </span>
        </div>
        <div className="pb-analytics-stat">
          <span className="pb-stat-label">Threshold</span>
          <span className="pb-stat-value">{data.rebalance_threshold_pct}%</span>
        </div>
      </div>
      {data.recommendations?.length > 0 && (
        <>
          <h4 className="pb-sub-title" style={{ margin: '10px 0 6px', fontSize: 13 }}>Rebalance Actions</h4>
          <table className="pb-analytics-table">
            <thead><tr><th>Ticker</th><th>Action</th><th>Drift</th><th>Target</th><th>Current</th></tr></thead>
            <tbody>
              {data.recommendations.map((r) => (
                <tr key={r.ticker}>
                  <td>{r.ticker}</td>
                  <td className={r.action === 'BUY' ? 'pb-positive' : 'pb-negative'}>{r.action}</td>
                  <td>{formatPct(r.drift_pct)}</td>
                  <td>{formatPct(r.target_weight_pct)}</td>
                  <td>{formatPct(r.current_weight_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
};

const AnalyticsPanel = ({
  activeTab,
  onTabChange,
  benchmarkData,
  backtestData,
  stressData,
  riskDecompData,
  driftData,
  frontierData,
  correlation,
  isBackendFrontierActive,
  frontierFallbackReason,
  onRun,
  loading,
  costBps,
  onCostBpsChange,
}) => {
  const needsRun = !['frontier', 'correlation'].includes(activeTab);
  return (
  <Card variant="default" className="pb-analytics-card">
    <CardHeader>
      <div className="pb-chart-title-row">
        <FiShield size={18} className="pb-icon-cyan" />
        <h3 className="pb-sub-title">Advanced Analytics</h3>
        <span className="pb-model-badge backend">Phase 3</span>
      </div>
    </CardHeader>
    <CardBody>
      <div className="pb-analytics-tabs" role="tablist" aria-label="Advanced analytics tabs">
        {ANALYTICS_TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              className={`pb-analytics-tab ${isActive ? 'active' : ''}`}
              onClick={() => onTabChange(tab.key)}
              role="tab"
              aria-selected={isActive}
              aria-controls={`analytics-panel-${tab.key}`}
              id={`analytics-tab-${tab.key}`}
            >
              <Icon size={14} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>
      <div className="pb-analytics-actions">
        {activeTab === 'backtest' && (
          <label className="pb-cost-input-label">
            Txn Cost
            <input
              type="number"
              min="0" max="100" step="1"
              value={costBps}
              onChange={(e) => onCostBpsChange(Number(e.target.value) || 0)}
              className="pb-cost-input"
            />
            bps
          </label>
        )}
        {needsRun && (
          <button
            className="pb-analytics-run-btn"
            onClick={() => onRun(activeTab)}
            disabled={loading}
          >
            {loading ? 'Running…' : 'Run'}
          </button>
        )}
      </div>
      <div className="pb-analytics-body">
        {activeTab === 'frontier' && (
          <div id="analytics-panel-frontier" role="tabpanel" aria-labelledby="analytics-tab-frontier">
          {frontierData && frontierData.length > 1
            ? <EfficientFrontierChart data={frontierData} height={350} />
            : <p className="pb-analytics-empty">Add at least 2 holdings to view the efficient frontier.</p>
          }
          </div>
        )}
        {activeTab === 'correlation' && (
          <div id="analytics-panel-correlation" role="tabpanel" aria-labelledby="analytics-tab-correlation">
          {correlation && correlation.matrix && correlation.matrix.length > 0
            ? (
              <div className="pb-heatmap-scroll-wrap">
                <CorrelationHeatmap labels={correlation.labels} matrix={correlation.matrix} />
              </div>
            )
            : <p className="pb-analytics-empty">Add holdings to view the correlation heatmap.</p>
          }
          </div>
        )}
        {activeTab === 'benchmark' && <div id="analytics-panel-benchmark" role="tabpanel" aria-labelledby="analytics-tab-benchmark"><BenchmarkTab data={benchmarkData} /></div>}
        {activeTab === 'backtest' && <div id="analytics-panel-backtest" role="tabpanel" aria-labelledby="analytics-tab-backtest"><BacktestTab data={backtestData} /></div>}
        {activeTab === 'stress' && <div id="analytics-panel-stress" role="tabpanel" aria-labelledby="analytics-tab-stress"><StressTab data={stressData} /></div>}
        {activeTab === 'riskDecomp' && <div id="analytics-panel-riskDecomp" role="tabpanel" aria-labelledby="analytics-tab-riskDecomp"><RiskDecompTab data={riskDecompData} /></div>}
        {activeTab === 'drift' && <div id="analytics-panel-drift" role="tabpanel" aria-labelledby="analytics-tab-drift"><DriftTab data={driftData} /></div>}
      </div>
    </CardBody>
  </Card>
  );
};

export default AnalyticsPanel;
