import React from 'react';
import { FiGlobe, FiShield, FiTarget, FiTrendingUp, FiUsers, FiZap } from 'react-icons/fi';
import './Mission.css';

const values = [
  {
    icon: FiTarget,
    title: 'Precision Analytics',
    description: 'Advanced portfolio analytics powered by modern quantitative methods, giving you institutional-grade insights.',
  },
  {
    icon: FiShield,
    title: 'Security First',
    description: 'Your financial data is encrypted and protected with strong security practices.',
  },
  {
    icon: FiZap,
    title: 'AI-Powered Optimization',
    description: 'Leverage optimization tooling to generate portfolios tailored to your risk profile.',
  },
  {
    icon: FiGlobe,
    title: 'Global Coverage',
    description: 'Access market data and analytics across major exchanges and core asset classes.',
  },
  {
    icon: FiTrendingUp,
    title: 'Performance Tracking',
    description: 'Track portfolio performance against benchmarks with clear, actionable summaries.',
  },
  {
    icon: FiUsers,
    title: 'Built for Investors',
    description: 'Every feature is crafted to help investors make better long-term decisions.',
  },
];

const Mission = () => (
  <div className="mission-root">
    <section className="mission-hero mission-glass">
      <div className="mission-hero-icon"><FiTarget /></div>
      <h1>Empowering Retail Investors</h1>
      <p>
        Hamilton Services bridges the gap between institutional-grade portfolio analytics and everyday investors.
        Everyone deserves access to sophisticated investment tools.
      </p>
    </section>

    <section className="mission-statement mission-glass">
      <h2>Our Mission</h2>
      <blockquote>
        To democratize portfolio analytics by providing every investor with intuitive tools to build,
        analyze, and optimize investments using clear, data-driven insights.
      </blockquote>
    </section>

    <section className="mission-values-section">
      <h3>What We Stand For</h3>
      <div className="mission-values-grid">
        {values.map((item) => {
          const Icon = item.icon;
          return (
            <article key={item.title} className="mission-glass mission-value-card">
              <Icon className="mission-value-icon" />
              <h4>{item.title}</h4>
              <p>{item.description}</p>
            </article>
          );
        })}
      </div>
    </section>

    <footer className="mission-footnote">
      Hamilton Services is built for educational and analytical purposes and does not constitute financial advice.
    </footer>
  </div>
);

export default Mission;
