import React from 'react';
import { render, screen } from '@testing-library/react';

import AnalyticsPanel from './AnalyticsPanel';

jest.mock('../components', () => ({
  Card: ({ children }) => <div>{children}</div>,
  CardHeader: ({ children }) => <div>{children}</div>,
  CardBody: ({ children }) => <div>{children}</div>,
  PerformanceLineChart: () => <div>Performance chart</div>,
  EfficientFrontierChart: () => <div>Frontier chart</div>,
  CorrelationHeatmap: () => <div>Correlation heatmap</div>,
}));

describe('AnalyticsPanel empty states', () => {
  const baseProps = {
    activeTab: 'frontier',
    onTabChange: jest.fn(),
    benchmarkData: null,
    backtestData: null,
    stressData: null,
    riskDecompData: null,
    driftData: null,
    frontierData: [],
    correlation: { labels: [], matrix: [] },
    isBackendFrontierActive: false,
    frontierFallbackReason: 'insufficient market data',
    onRun: jest.fn(),
    loading: false,
    costBps: 5,
    onCostBpsChange: jest.fn(),
  };

  test('shows empty frontier guidance when data unavailable', () => {
    render(<AnalyticsPanel {...baseProps} activeTab="frontier" />);
    expect(screen.getByText(/Add at least 2 holdings to view the efficient frontier/i)).toBeInTheDocument();
  });

  test('shows empty benchmark run prompt when not computed', () => {
    render(<AnalyticsPanel {...baseProps} activeTab="benchmark" />);
    expect(screen.getByText(/Click "Run" to compute benchmark-relative metrics/i)).toBeInTheDocument();
  });
});
