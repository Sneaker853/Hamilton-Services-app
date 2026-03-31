import React from 'react';
import { FiTrendingUp, FiShield, FiActivity, FiBarChart2, FiGrid, FiBriefcase } from 'react-icons/fi';
import './Landing.css';

const FEATURES = [
  {
    icon: FiTrendingUp,
    title: 'Portfolio Optimizer',
    description: 'Generate diversified portfolios using persona-based risk profiles powered by Fama-French 5-factor models.',
  },
  {
    icon: FiBriefcase,
    title: 'Portfolio Builder',
    description: 'Manually select stocks, ETFs, and bonds with real-time weight optimization and constraint controls.',
  },
  {
    icon: FiActivity,
    title: 'Advanced Analytics',
    description: 'Benchmark comparison, backtesting, stress tests, risk decomposition, and drift monitoring.',
  },
  {
    icon: FiBarChart2,
    title: 'Market Data',
    description: 'Browse and search thousands of stocks, ETFs, and bonds with sector, market, and fundamental filters.',
  },
  {
    icon: FiShield,
    title: 'Institutional-Grade Models',
    description: 'Walk-forward backtesting, Ledoit-Wolf covariance estimation, and Almgren-Chriss market impact modeling.',
  },
  {
    icon: FiGrid,
    title: 'Portfolio Comparison',
    description: 'Compare saved portfolios side-by-side across returns, risk, holdings, and sector allocations.',
  },
];

const Landing = ({ onContinueAsGuest, onLogin }) => {
  return (
    <div className="landing-root">
      <div className="landing-hero">
        <p className="landing-overline">Hamilton Services</p>
        <h1 className="landing-title">
          Institutional-Grade<br />
          <span className="landing-highlight">Portfolio Analytics</span>
        </h1>
        <p className="landing-subtitle">
          Build, optimize, and analyze diversified investment portfolios
          with professional quantitative tools — free for individual investors.
        </p>
        <div className="landing-cta-row">
          <button className="landing-btn primary" onClick={onContinueAsGuest}>
            Explore as Guest
          </button>
          <button className="landing-btn secondary" onClick={onLogin}>
            Sign In
          </button>
        </div>
      </div>

      <div className="landing-features-grid">
        {FEATURES.map((feature) => {
          const Icon = feature.icon;
          return (
            <div key={feature.title} className="landing-feature-card">
              <div className="landing-feature-icon">
                <Icon size={22} />
              </div>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </div>
          );
        })}
      </div>

      <footer className="landing-footer">
        <p>Built with React, FastAPI, PostgreSQL &amp; modern quantitative methods.</p>
      </footer>
    </div>
  );
};

export default Landing;
