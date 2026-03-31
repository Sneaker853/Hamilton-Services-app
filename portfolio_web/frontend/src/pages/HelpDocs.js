import React, { useState } from 'react';
import { FiChevronDown, FiChevronRight, FiBookOpen, FiHelpCircle, FiTool } from 'react-icons/fi';
import './HelpDocs.css';

const FAQ_SECTIONS = [
  {
    title: 'Getting Started',
    icon: FiBookOpen,
    items: [
      {
        q: 'What is Hamilton Services?',
        a: 'Hamilton Services is a professional portfolio analytics platform. It helps you build, optimize, and monitor investment portfolios using institutional-grade financial models including Fama-French 5-Factor analysis, mean-variance optimization, and walk-forward backtesting.',
      },
      {
        q: 'Do I need an account?',
        a: 'You can explore the platform in Guest mode without creating an account. To save portfolios, access the comparison tool, and change settings, you\'ll need to register with an email and password.',
      },
      {
        q: 'How do I create my first portfolio?',
        a: 'Go to the Optimizer page and select a persona (Conservative, Balanced, Growth, or Income). Adjust your investment amount and constraints, then click Generate. The engine will build a diversified portfolio using real market data.',
      },
      {
        q: 'What is the Portfolio Builder?',
        a: 'The Portfolio Builder lets you manually pick stocks, ETFs, and bonds, then run optimization, risk analysis, backtesting, and stress testing on your custom selection.',
      },
    ],
  },
  {
    title: 'Financial Concepts',
    icon: FiHelpCircle,
    items: [
      {
        q: 'What is the Sharpe Ratio?',
        a: 'The Sharpe Ratio measures risk-adjusted return: (Portfolio Return − Risk-Free Rate) ÷ Portfolio Volatility. A higher Sharpe means better return per unit of risk. Values above 1.0 are generally considered good.',
      },
      {
        q: 'What is Beta?',
        a: 'Beta measures a stock\'s sensitivity to market movements. A beta of 1.0 means it moves with the market. Beta > 1 means more volatile, beta < 1 means more defensive. Beta is estimated using the Fama-French 5-Factor model.',
      },
      {
        q: 'What is the HHI (Herfindahl-Hirschman Index)?',
        a: 'HHI measures portfolio concentration. It\'s the sum of squared weights. A lower HHI means more diversification. An equally-weighted 10-stock portfolio has HHI = 0.10, while a single-stock portfolio has HHI = 1.0.',
      },
      {
        q: 'What is Expected Shortfall (CVaR)?',
        a: 'Expected Shortfall (also called Conditional Value-at-Risk) is the average loss in the worst X% of scenarios. It\'s more conservative than VaR because it considers the severity of tail losses, not just the threshold.',
      },
      {
        q: 'What does "walk-forward backtesting" mean?',
        a: 'Walk-forward backtesting re-estimates model parameters (returns, covariance) at each rebalance date using only data available at that time — no future information. This eliminates look-ahead bias and gives more realistic performance estimates.',
      },
      {
        q: 'What are the Fama-French 5 Factors?',
        a: 'The FF5 model explains stock returns using five risk factors: Market (Mkt-RF), Size (SMB — small minus big), Value (HML — high minus low book-to-market), Profitability (RMW — robust minus weak), and Investment (CMA — conservative minus aggressive). Each stock\'s expected return is decomposed into exposure to these factors plus an alpha term.',
      },
      {
        q: 'What is portfolio drift?',
        a: 'Drift occurs when price movements cause your actual portfolio weights to deviate from target weights. For example, if a growth stock appreciates faster than the rest, its weight increases beyond your target allocation. The drift monitor tracks this and recommends rebalancing when thresholds are breached.',
      },
    ],
  },
  {
    title: 'Platform Features',
    icon: FiTool,
    items: [
      {
        q: 'How does the stress test work?',
        a: 'The stress test applies historically-calibrated shock scenarios (e.g., 2008 GFC, COVID-19, 2022 Rate Hike) to your portfolio. It uses each stock\'s market beta and volatility to estimate the portfolio-level impact under each scenario.',
      },
      {
        q: 'Can I export my data?',
        a: 'Yes. Most tables and analytics views have an "Export CSV" button that downloads the data as a spreadsheet-compatible CSV file. Portfolio comparisons and stock comparisons can also be exported.',
      },
      {
        q: 'What optimization objectives are available?',
        a: 'Four objectives: Max Sharpe (maximize risk-adjusted return), Min Volatility (minimize portfolio risk), Target Return (minimize risk for a specified return level), and Risk Parity (equalize risk contribution across assets).',
      },
      {
        q: 'How do I compare portfolios?',
        a: 'Save two or more portfolios, then go to the Compare page. Select the portfolios you want to compare and view their metrics side-by-side, including expected return, volatility, Sharpe ratio, sector weights, and top holdings.',
      },
      {
        q: 'What is the drift monitor\'s forecast feature?',
        a: 'The predictive drift forecast uses the past 90 days of price trends to project where your portfolio weights will be 30 days from now. It provides a rebalance urgency level (low, medium, high) to help you plan ahead.',
      },
      {
        q: 'How are liquidity constraints applied?',
        a: 'When you set a liquidity constraint (max % of 20-day average volume), the optimizer limits each position\'s weight so that your dollar allocation doesn\'t exceed that percentage of the stock\'s average daily trading volume. This prevents holding positions that would be difficult to exit.',
      },
    ],
  },
];

const AccordionItem = ({ question, answer }) => {
  const [open, setOpen] = useState(false);

  return (
    <div className={`faq-item ${open ? 'faq-item--open' : ''}`}>
      <button
        type="button"
        className="faq-question"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        {open ? <FiChevronDown size={16} /> : <FiChevronRight size={16} />}
        <span>{question}</span>
      </button>
      {open && <div className="faq-answer">{answer}</div>}
    </div>
  );
};

const HelpDocs = () => {
  return (
    <div className="page-container help-docs-root">
      <div className="page-header">
        <h1>Help &amp; FAQ</h1>
        <p className="page-subtitle">
          Learn about the platform, financial concepts, and how to get the most out of your portfolio analytics.
        </p>
      </div>

      {FAQ_SECTIONS.map((section) => {
        const Icon = section.icon;
        return (
          <div key={section.title} className="faq-section">
            <h2 className="faq-section-title">
              <Icon size={20} />
              {section.title}
            </h2>
            <div className="faq-list">
              {section.items.map((item) => (
                <AccordionItem key={item.q} question={item.q} answer={item.a} />
              ))}
            </div>
          </div>
        );
      })}

      <div className="faq-footer">
        <p>Can't find what you're looking for? <a href="/contact">Contact us</a> and we'll help.</p>
      </div>
    </div>
  );
};

export default HelpDocs;
