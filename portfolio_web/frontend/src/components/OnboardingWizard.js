import React, { useState } from 'react';
import { FiTrendingUp, FiBarChart2, FiBriefcase, FiArrowRight, FiCheck } from 'react-icons/fi';
import './OnboardingWizard.css';

const STEPS = [
  {
    icon: FiTrendingUp,
    title: 'Generate a Portfolio',
    description: 'Choose a risk persona (Conservative to Aggressive) and set constraints like investment amount, max position size, and sector limits. The optimizer uses a Fama-French 5-factor model to build a diversified portfolio.',
    tip: 'Start with the "Balanced" persona if you\'re unsure.',
  },
  {
    icon: FiBriefcase,
    title: 'Build Manually',
    description: 'Search and add individual stocks, ETFs, and bonds. The Builder provides real-time weight optimization, efficient frontier analysis, and advanced analytics including backtesting and stress tests.',
    tip: 'Enable "Auto-Optimize Weights" for automatic Sharpe ratio optimization.',
  },
  {
    icon: FiBarChart2,
    title: 'Analyze & Compare',
    description: 'View detailed metrics for each portfolio, run benchmark comparisons against the S&P 500, and use the comparison page to evaluate multiple portfolios side-by-side.',
    tip: 'Save portfolios to track them on your Dashboard over time.',
  },
];

const OnboardingWizard = ({ onClose }) => {
  const [step, setStep] = useState(0);

  const handleFinish = () => {
    localStorage.setItem('onboardingComplete', 'true');
    onClose();
  };

  const currentStep = STEPS[step];
  const Icon = currentStep.icon;
  const isLast = step === STEPS.length - 1;

  return (
    <div className="onboarding-overlay" onClick={handleFinish}>
      <div className="onboarding-panel" onClick={(e) => e.stopPropagation()}>
        {/* Progress dots */}
        <div className="onboarding-progress">
          {STEPS.map((_, i) => (
            <span
              key={i}
              className={`onboarding-dot ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`}
            />
          ))}
        </div>

        <div className="onboarding-icon-wrap">
          <Icon size={28} />
        </div>

        <h2 className="onboarding-title">{currentStep.title}</h2>
        <p className="onboarding-desc">{currentStep.description}</p>
        <div className="onboarding-tip">
          <strong>Tip:</strong> {currentStep.tip}
        </div>

        <div className="onboarding-actions">
          <button className="onboarding-skip" onClick={handleFinish}>
            Skip
          </button>
          {isLast ? (
            <button className="onboarding-next primary" onClick={handleFinish}>
              <FiCheck size={16} /> Get Started
            </button>
          ) : (
            <button className="onboarding-next primary" onClick={() => setStep(step + 1)}>
              Next <FiArrowRight size={16} />
            </button>
          )}
        </div>

        <p className="onboarding-step-label">Step {step + 1} of {STEPS.length}</p>
      </div>
    </div>
  );
};

export default OnboardingWizard;
