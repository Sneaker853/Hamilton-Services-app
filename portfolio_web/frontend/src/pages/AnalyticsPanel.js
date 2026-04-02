import React from 'react';
import { FiTrendingUp, FiBarChart2, FiAlertTriangle, FiTarget, FiRefreshCw, FiShield, FiActivity, FiGrid, FiLayers, FiPieChart } from 'react-icons/fi';
import { Card, CardHeader, CardBody, PerformanceLineChart, EfficientFrontierChart, CorrelationHeatmap, HelpIcon, useLanguage } from '../components';
import { formatPct, formatNum } from './portfolioBuilderUtils';

const BenchmarkTab = ({ data, tt }) => {
  if (!data) return <p className="pb-analytics-empty">{tt('Click "Run" to compute benchmark-relative metrics.')}</p>;
  return (
    <div className="pb-analytics-result">
      <div className="pb-analytics-grid">
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Alpha (ann.)')} <HelpIcon text="Excess return of the portfolio above the benchmark after adjusting for market risk (beta). Positive alpha indicates outperformance." /></span><span className="pb-stat-value">{formatPct(data.alpha * 100)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Beta')} <HelpIcon text="Sensitivity of portfolio returns to market (benchmark) movements. Beta of 1.0 means the portfolio moves in line with the market; above 1.0 means more volatile." /></span><span className="pb-stat-value">{formatNum(data.beta)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Tracking Error')} <HelpIcon text="Standard deviation of the difference between portfolio and benchmark returns. Lower values mean the portfolio closely follows the benchmark." /></span><span className="pb-stat-value">{formatPct(data.tracking_error * 100)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Info Ratio')} <HelpIcon text="Information Ratio: Alpha divided by Tracking Error. Measures risk-adjusted outperformance vs. benchmark. Values above 0.5 are considered good." /></span><span className="pb-stat-value">{formatNum(data.information_ratio)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">R² <HelpIcon text="R-squared: proportion of portfolio return variance explained by the benchmark (0 to 1). Higher R² means the benchmark is a good predictor of portfolio behavior." /></span><span className="pb-stat-value">{formatNum(data.r_squared)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Observations')}</span><span className="pb-stat-value">{data.n_observations}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Portfolio Return')}</span><span className="pb-stat-value">{formatPct(data.ann_portfolio_return * 100)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Benchmark Return')}</span><span className="pb-stat-value">{formatPct(data.ann_benchmark_return * 100)}</span></div>
      </div>
      {data.tickers_missing?.length > 0 && (
        <p className="pb-analytics-warn">{tt('Missing price data')}: {data.tickers_missing.join(', ')}</p>
      )}
    </div>
  );
};

const BacktestTab = ({ data, tt }) => {
  if (!data) return <p className="pb-analytics-empty">{tt('Click "Run" to simulate a historical backtest.')}</p>;
  const s = data.summary || {};
  return (
    <div className="pb-analytics-result">
      <div className="pb-analytics-grid">
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Total Return')}</span><span className="pb-stat-value">{formatPct(s.total_return_pct)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Ann. Return')}</span><span className="pb-stat-value">{formatPct(s.annualised_return_pct)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Ann. Volatility')}</span><span className="pb-stat-value">{formatPct(s.annualised_volatility_pct)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">Sharpe <HelpIcon text="Risk-adjusted return: (Return − Risk-Free Rate) ÷ Volatility. Higher is better. Above 1.0 is good; above 2.0 is excellent." /></span><span className="pb-stat-value">{formatNum(s.sharpe_ratio)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Max Drawdown')} <HelpIcon text="Largest peak-to-trough decline during the backtest period. Represents the worst-case loss if you bought at the peak and sold at the trough." /></span><span className="pb-stat-value">{formatPct(s.max_drawdown_pct)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Final Value')}</span><span className="pb-stat-value">${s.final_value?.toLocaleString(undefined, { maximumFractionDigits: 0 }) || '—'}</span></div>
        {s.total_transaction_cost > 0 && (
          <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Txn Cost')}</span><span className="pb-stat-value pb-negative">${s.total_transaction_cost?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span></div>
        )}
        {s.cost_bps > 0 && (
          <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Cost Rate')}</span><span className="pb-stat-value">{s.cost_bps} bps</span></div>
        )}
      </div>
      <p className="pb-analytics-note">{tt('Rebalance')}: {data.rebalance_frequency} | {data.n_rebalances} {tt('events')} | {tt('Period')}: {data.period}</p>
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

const StressTab = ({ data, tt }) => {
  if (!data) return <p className="pb-analytics-empty">{tt('Click "Run" to apply stress scenarios.')}</p>;
  return (
    <div className="pb-analytics-result">
      <table className="pb-analytics-table">
        <thead><tr><th>{tt('Scenario')}</th><th>{tt('Portfolio Impact')}</th></tr></thead>
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

const RiskDecompTab = ({ data, tt }) => {
  if (!data) return <p className="pb-analytics-empty">{tt('Click "Run" to decompose portfolio risk.')}</p>;
  return (
    <div className="pb-analytics-result">
      <div className="pb-analytics-grid" style={{ marginBottom: 12 }}>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Portfolio Vol')}</span><span className="pb-stat-value">{formatPct(data.portfolio_volatility * 100)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Assets Aligned')}</span><span className="pb-stat-value">{data.n_assets}</span></div>
      </div>
      <table className="pb-analytics-table">
        <thead><tr><th>{tt('Ticker')}</th><th>{tt('Weight')}</th><th>{tt('Marginal CTR')} <HelpIcon text="Marginal Contribution to Risk: how much an incremental increase in this position's weight would change total portfolio volatility." /></th><th>{tt('% of Risk')}</th></tr></thead>
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

const DriftTab = ({ data, tt }) => {
  if (!data) return <p className="pb-analytics-empty">{tt('Click "Run" to check portfolio drift.')}</p>;
  return (
    <div className="pb-analytics-result">
      <div className="pb-analytics-grid" style={{ marginBottom: 12 }}>
        <div className="pb-analytics-stat">
          <span className="pb-stat-label">{tt('Drift Score')} <HelpIcon text="Measures how far current portfolio weights have drifted from target allocations due to market movements. Higher scores indicate a greater need to rebalance." /></span>
          <span className="pb-stat-value">{formatNum(data.drift_score, 2)}%</span>
        </div>
        <div className="pb-analytics-stat">
          <span className="pb-stat-label">{tt('Needs Rebalance')}</span>
          <span className={`pb-stat-value ${data.needs_rebalance ? 'pb-negative' : 'pb-positive'}`}>
            {data.needs_rebalance ? tt('YES') : tt('No')}
          </span>
        </div>
        <div className="pb-analytics-stat">
          <span className="pb-stat-label">{tt('Threshold')}</span>
          <span className="pb-stat-value">{data.rebalance_threshold_pct}%</span>
        </div>
      </div>
      {data.recommendations?.length > 0 && (
        <>
          <h4 className="pb-sub-title" style={{ margin: '10px 0 6px', fontSize: 13 }}>{tt('Rebalance Actions')}</h4>
          <table className="pb-analytics-table">
            <thead><tr><th>{tt('Ticker')}</th><th>{tt('Action')}</th><th>{tt('Drift')}</th><th>{tt('Target')}</th><th>{tt('Current')}</th></tr></thead>
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

const StyleAnalysisTab = ({ data, tt }) => {
  if (!data) return <p className="pb-analytics-empty">{tt('Click "Run" to analyze portfolio style (large/small, value/growth).')}</p>;
  const ps = data.portfolio_style || {};
  return (
    <div className="pb-analytics-result">
      <div className="pb-analytics-grid" style={{ marginBottom: 12 }}>
        <div className="pb-analytics-stat">
          <span className="pb-stat-label">{tt('Portfolio Style')} <HelpIcon text="Overall style classification based on factor loadings. Size: Small/Mid/Large via SMB beta. Value/Growth via HML beta." /></span>
          <span className="pb-stat-value">{ps.label || '—'}</span>
        </div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Size (SMB beta)')}</span><span className="pb-stat-value">{formatNum(ps.beta_smb)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Value (HML beta)')}</span><span className="pb-stat-value">{formatNum(ps.beta_hml)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Market (Mkt beta)')}</span><span className="pb-stat-value">{formatNum(ps.beta_mkt)}</span></div>
      </div>
      {data.style_composition?.length > 0 && (
        <>
          <h4 className="pb-sub-title" style={{ margin: '10px 0 6px', fontSize: 13 }}>{tt('Style Composition')}</h4>
          <table className="pb-analytics-table">
            <thead><tr><th>{tt('Style')}</th><th>{tt('Weight')}</th></tr></thead>
            <tbody>
              {data.style_composition.map((s) => (
                <tr key={s.style}>
                  <td>{s.style}</td>
                  <td>{formatPct(s.weight_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {data.assets?.length > 0 && (
        <>
          <h4 className="pb-sub-title" style={{ margin: '10px 0 6px', fontSize: 13 }}>{tt('Per-Asset Style')}</h4>
          <table className="pb-analytics-table">
            <thead><tr><th>{tt('Ticker')}</th><th>{tt('Weight')}</th><th>{tt('Size')}</th><th>{tt('Value/Growth')}</th><th>{tt('SMB beta')}</th><th>{tt('HML beta')}</th></tr></thead>
            <tbody>
              {data.assets.slice(0, 20).map((a) => (
                <tr key={a.ticker}>
                  <td>{a.ticker}</td>
                  <td>{(a.weight * 100).toFixed(1)}%</td>
                  <td>{a.size}</td>
                  <td>{a.value_growth}</td>
                  <td>{formatNum(a.beta_smb)}</td>
                  <td>{formatNum(a.beta_hml)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
};

const BrinsonTab = ({ data, tt }) => {
  if (!data) return <p className="pb-analytics-empty">{tt('Click "Run" to decompose performance into allocation vs. selection effects.')}</p>;
  return (
    <div className="pb-analytics-result">
      <div className="pb-analytics-grid" style={{ marginBottom: 12 }}>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Portfolio Return')}</span><span className="pb-stat-value">{formatPct(data.portfolio_return_pct)}</span></div>
        <div className="pb-analytics-stat"><span className="pb-stat-label">{tt('Benchmark Return')}</span><span className="pb-stat-value">{formatPct(data.benchmark_return_pct)}</span></div>
        <div className="pb-analytics-stat">
          <span className="pb-stat-label">{tt('Active Return')} <HelpIcon text="Difference between portfolio and benchmark returns. Positive = outperformance." /></span>
          <span className={`pb-stat-value ${data.active_return_pct < 0 ? 'pb-negative' : 'pb-positive'}`}>{formatPct(data.active_return_pct)}</span>
        </div>
        <div className="pb-analytics-stat">
          <span className="pb-stat-label">{tt('Allocation Effect')} <HelpIcon text="Return from overweighting/underweighting sectors that outperformed/underperformed the benchmark. Positive means good sector bets." /></span>
          <span className={`pb-stat-value ${data.total_allocation_pct < 0 ? 'pb-negative' : 'pb-positive'}`}>{formatPct(data.total_allocation_pct)}</span>
        </div>
        <div className="pb-analytics-stat">
          <span className="pb-stat-label">{tt('Selection Effect')} <HelpIcon text="Return from picking better-performing stocks within each sector vs. benchmark. Positive means good stock picks." /></span>
          <span className={`pb-stat-value ${data.total_selection_pct < 0 ? 'pb-negative' : 'pb-positive'}`}>{formatPct(data.total_selection_pct)}</span>
        </div>
        <div className="pb-analytics-stat">
          <span className="pb-stat-label">{tt('Interaction')} <HelpIcon text="Combined effect of both overweighting sectors and picking good stocks within them. Often small." /></span>
          <span className={`pb-stat-value ${data.total_interaction_pct < 0 ? 'pb-negative' : 'pb-positive'}`}>{formatPct(data.total_interaction_pct)}</span>
        </div>
      </div>
      {data.sectors?.length > 0 && (
        <>
          <h4 className="pb-sub-title" style={{ margin: '10px 0 6px', fontSize: 13 }}>{tt('By Sector')} ({data.period})</h4>
          <table className="pb-analytics-table">
            <thead><tr><th>{tt('Sector')}</th><th>{tt('Port Wt')}</th><th>{tt('Bench Wt')}</th><th>{tt('Port Ret')}</th><th>{tt('Alloc')}</th><th>{tt('Select')}</th></tr></thead>
            <tbody>
              {data.sectors.map((s) => (
                <tr key={s.sector}>
                  <td>{s.sector}</td>
                  <td>{formatPct(s.port_weight_pct)}</td>
                  <td>{formatPct(s.bench_weight_pct)}</td>
                  <td className={s.port_return_pct < 0 ? 'pb-negative' : ''}>{formatPct(s.port_return_pct)}</td>
                  <td className={s.allocation_pct < 0 ? 'pb-negative' : 'pb-positive'}>{formatPct(s.allocation_pct)}</td>
                  <td className={s.selection_pct < 0 ? 'pb-negative' : 'pb-positive'}>{formatPct(s.selection_pct)}</td>
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
  styleAnalysisData,
  brinsonData,
  frontierData,
  correlation,
  isBackendFrontierActive,
  frontierFallbackReason,
  onRun,
  loading,
  costBps,
  onCostBpsChange,
}) => {
  const { tt } = useLanguage();
  const analyticsTabs = [
    { key: 'frontier', label: tt('Frontier'), icon: FiActivity },
    { key: 'correlation', label: tt('Correlation'), icon: FiGrid },
    { key: 'benchmark', label: tt('Benchmark'), icon: FiTrendingUp },
    { key: 'backtest', label: tt('Backtest'), icon: FiBarChart2 },
    { key: 'stress', label: tt('Stress Test'), icon: FiAlertTriangle },
    { key: 'riskDecomp', label: tt('Risk Decomp'), icon: FiTarget },
    { key: 'drift', label: tt('Drift'), icon: FiRefreshCw },
    { key: 'styleAnalysis', label: tt('Style'), icon: FiLayers },
    { key: 'brinson', label: tt('Attribution'), icon: FiPieChart },
  ];
  const needsRun = !['frontier', 'correlation'].includes(activeTab);
  return (
  <Card variant="default" className="pb-analytics-card">
    <CardHeader>
      <div className="pb-chart-title-row">
        <FiShield size={18} className="pb-icon-cyan" />
        <h3 className="pb-sub-title">{tt('Advanced Analytics')}</h3>
        <span className="pb-model-badge backend">Phase 3</span>
      </div>
    </CardHeader>
    <CardBody>
      <div className="pb-analytics-tabs" role="tablist" aria-label={tt('Advanced analytics tabs')}>
        {analyticsTabs.map((tab) => {
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
            {tt('Txn Cost')} <HelpIcon text="Transaction cost in basis points (1 bps = 0.01%). Applied to each rebalance trade. Typical retail: 5–15 bps; institutional: 1–5 bps." />
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
            {loading ? tt('Running...') : tt('Run')}
          </button>
        )}
      </div>
      <div className="pb-analytics-body">
        {activeTab === 'frontier' && (
          <div id="analytics-panel-frontier" role="tabpanel" aria-labelledby="analytics-tab-frontier">
          {frontierData && frontierData.length > 1
            ? <EfficientFrontierChart data={frontierData} height={350} />
            : <p className="pb-analytics-empty">{tt('Add at least 2 holdings to view the efficient frontier.')}</p>
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
            : <p className="pb-analytics-empty">{tt('Add holdings to view the correlation heatmap.')}</p>
          }
          </div>
        )}
        {activeTab === 'benchmark' && <div id="analytics-panel-benchmark" role="tabpanel" aria-labelledby="analytics-tab-benchmark"><BenchmarkTab data={benchmarkData} tt={tt} /></div>}
        {activeTab === 'backtest' && <div id="analytics-panel-backtest" role="tabpanel" aria-labelledby="analytics-tab-backtest"><BacktestTab data={backtestData} tt={tt} /></div>}
        {activeTab === 'stress' && <div id="analytics-panel-stress" role="tabpanel" aria-labelledby="analytics-tab-stress"><StressTab data={stressData} tt={tt} /></div>}
        {activeTab === 'riskDecomp' && <div id="analytics-panel-riskDecomp" role="tabpanel" aria-labelledby="analytics-tab-riskDecomp"><RiskDecompTab data={riskDecompData} tt={tt} /></div>}
        {activeTab === 'drift' && <div id="analytics-panel-drift" role="tabpanel" aria-labelledby="analytics-tab-drift"><DriftTab data={driftData} tt={tt} /></div>}
        {activeTab === 'styleAnalysis' && <div id="analytics-panel-styleAnalysis" role="tabpanel" aria-labelledby="analytics-tab-styleAnalysis"><StyleAnalysisTab data={styleAnalysisData} tt={tt} /></div>}
        {activeTab === 'brinson' && <div id="analytics-panel-brinson" role="tabpanel" aria-labelledby="analytics-tab-brinson"><BrinsonTab data={brinsonData} tt={tt} /></div>}
      </div>
    </CardBody>
  </Card>
  );
};

export default AnalyticsPanel;
