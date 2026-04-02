import React from 'react';
import { FiBarChart2, FiPieChart } from 'react-icons/fi';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useLanguage } from '../components';
import {
  Card,
  CardHeader,
  CardBody,
  PerformanceLineChart,
  RiskReturnScatter,
} from '../components';
import { COLORS, renderPieTooltip, renderPieLabel, pieLegendStyle } from './portfolioBuilderUtils';

const ChartsPanel = ({
  sectorData,
  assetData,
  riskReturnData,
  performanceData,
  historicalPerformance,
  isBackendFrontierActive,
  frontierFallbackReason,
  showSector = true,
  showAsset = true,
  showPerformance = true,
  showRiskReturn = true,
  className = ''
}) => {
  const { tt } = useLanguage();
  return (
  <div className={`pb-chart-grid ${className}`.trim()}>
    {showSector && sectorData.length > 0 && (
      <Card variant="default">
        <CardHeader>
          <div className="pb-chart-title-row">
            <FiBarChart2 size={18} className="pb-icon-cyan" />
            <h3 className="pb-sub-title">{tt('Sector Distribution')}</h3>
          </div>
        </CardHeader>
        <CardBody>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={sectorData}
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
                {sectorData.map((entry, index) => (
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

    {showAsset && assetData.length > 0 && (
      <Card variant="default">
        <CardHeader>
          <div className="pb-chart-title-row">
            <FiPieChart size={18} className="pb-icon-cyan" />
            <h3 className="pb-sub-title">{tt('Asset Allocation')}</h3>
          </div>
        </CardHeader>
        <CardBody>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={assetData}
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
                {assetData.map((entry, index) => (
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

    {showPerformance && (
      <Card variant="default">
      <CardHeader>
        <div className="pb-chart-title-row">
          <FiBarChart2 size={18} className="pb-icon-cyan" />
          <h3 className="pb-sub-title">{tt('Performance Over Time')}</h3>
          <span className={`pb-model-badge ${historicalPerformance ? 'backend' : 'fallback'}`}>
            {historicalPerformance ? tt('Historical + Projected') : tt('Projected only')}
          </span>
        </div>
      </CardHeader>
      <CardBody>
        <PerformanceLineChart data={performanceData} historicalData={historicalPerformance} height={300} />
      </CardBody>
      </Card>
    )}

    {showRiskReturn && riskReturnData.length > 0 && (
      <Card variant="default">
        <CardHeader>
          <div className="pb-chart-title-row">
            <FiBarChart2 size={18} className="pb-icon-cyan" />
            <h3 className="pb-sub-title">{tt('Risk vs Return')}</h3>
            <span className={`pb-model-badge ${isBackendFrontierActive ? 'backend' : 'fallback'}`}>
              {isBackendFrontierActive
                ? tt('Advanced covariance model')
                : tt('Estimated model')}
            </span>
          </div>
        </CardHeader>
        <CardBody>
          <RiskReturnScatter data={riskReturnData} height={300} />
        </CardBody>
      </Card>
    )}
  </div>
  );
};

export default ChartsPanel;
