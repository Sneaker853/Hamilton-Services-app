from datetime import datetime
from typing import List, Dict, Optional

from pydantic import BaseModel, Field


class PortfolioRequest(BaseModel):
    persona_name: str = Field(..., description="Portfolio persona: conservative, balanced, growth, income, custom")
    investment_amount: float = Field(..., gt=0, description="Initial investment amount in USD")
    min_holdings: int = Field(10, ge=5, le=50, description="Minimum number of stocks")
    max_holdings: int = Field(20, ge=5, le=50, description="Maximum number of stocks")
    max_position_pct: float = Field(10.0, gt=0, le=100, description="Max position as % of portfolio")
    max_sector_pct: float = Field(25.0, gt=0, le=100, description="Max sector allocation as %")
    include_bonds: bool = Field(False, description="Include bonds in portfolio")
    include_etfs: bool = Field(False, description="Include ETFs in portfolio")
    rebalance_threshold: float = Field(5.0, gt=0, le=50, description="Rebalance when drift exceeds %")


class PortfolioResponse(BaseModel):
    id: str
    persona: str
    created_at: datetime
    investment_amount: float
    holdings: List[Dict]
    summary: Dict
    metrics: Dict


class PersonaInfo(BaseModel):
    name: str
    display_name: str
    description: str
    risk_level: str
    expected_return: str


class OptimizeWeightsRequest(BaseModel):
    tickers: List[str] = Field(..., description="List of stock tickers to optimize")
    optimize_sharpe: bool = Field(True, description="Optimize for maximum Sharpe ratio (return/volatility)")
    min_active_weight: float = Field(0.0, ge=0, le=0.2, description="Minimum weight (decimal) for active positions")
    max_turnover: Optional[float] = Field(None, gt=0, le=2.0, description="Maximum turnover vs previous weights (decimal)")
    previous_weights: Optional[Dict[str, float]] = Field(None, description="Previous portfolio weights by ticker (decimal or percent)")
    max_sector_active_weight: Optional[float] = Field(None, gt=0, le=1.0, description="Maximum absolute active sector deviation vs benchmark")
    benchmark_sector_weights: Optional[Dict[str, float]] = Field(None, description="Benchmark sector weights (decimal or percent)")
    hhi_penalty_lambda: float = Field(0.0, ge=0, le=10.0, description="HHI concentration penalty strength (0=off)")
    objective: str = Field("max_sharpe", description="Objective: max_sharpe, min_vol, target_return, risk_parity")
    target_return: Optional[float] = Field(None, description="Target annual return (decimal) for target_return objective")
    cost_bps: float = Field(0.0, ge=0, le=200, description="Trading cost in basis points per unit turnover")


class CovarianceMetricHolding(BaseModel):
    ticker: str
    weight: float


class CovarianceMetricsRequest(BaseModel):
    holdings: List[CovarianceMetricHolding] = Field(..., min_length=1)
    risk_free_rate: float = Field(0.02, ge=0, le=0.20)


class EfficientFrontierRequest(BaseModel):
    holdings: List[CovarianceMetricHolding] = Field(..., min_length=1)
    bins: int = Field(50, ge=8, le=80)
    sample_count: int = Field(5000, ge=200, le=10000)


class PortfolioHistoryRequest(BaseModel):
    holdings: List[CovarianceMetricHolding] = Field(..., min_length=1)
    period: str = Field("1Y", description="Lookback period: 1M, 3M, 6M, 1Y")
    initial_value: float = Field(100000, gt=0, description="Starting portfolio value for normalization")


class BenchmarkAnalyticsRequest(BaseModel):
    holdings: List[CovarianceMetricHolding] = Field(..., min_length=1)
    benchmark_ticker: str = Field("SPY", description="Benchmark ticker symbol")
    period: str = Field("1Y", description="Lookback period: 1M, 3M, 6M, 1Y")


class BacktestRequest(BaseModel):
    holdings: List[CovarianceMetricHolding] = Field(..., min_length=1)
    period: str = Field("1Y", description="Lookback period: 1M, 3M, 6M, 1Y, 3Y, 5Y")
    rebalance_frequency: str = Field("monthly", description="Rebalance schedule: daily, weekly, monthly, quarterly, none")
    initial_value: float = Field(100000, gt=0, description="Starting portfolio value")
    cost_bps: float = Field(0.0, ge=0, le=100, description="One-way transaction cost in basis points (e.g. 5 = 0.05%)")


class StressTestRequest(BaseModel):
    holdings: List[CovarianceMetricHolding] = Field(..., min_length=1)
    scenarios: Optional[List[str]] = Field(
        None, description="Scenario names to run; null = all defaults"
    )


class RiskDecompositionRequest(BaseModel):
    holdings: List[CovarianceMetricHolding] = Field(..., min_length=1)


class DriftMonitorRequest(BaseModel):
    holdings: List[CovarianceMetricHolding] = Field(..., min_length=1, description="Current holdings with target weights")
    current_values: Optional[Dict[str, float]] = Field(None, description="Current market values per ticker (optional)")
    rebalance_threshold: float = Field(5.0, gt=0, le=50, description="Drift % threshold to trigger rebalance recommendation")


class AuthRegisterRequest(BaseModel):
    email: str
    password: str


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: Dict


class MessageResponse(BaseModel):
    success: bool
    message: str
    debug_link: Optional[str] = None


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class VerifyEmailConfirmRequest(BaseModel):
    token: str


class SavePortfolioRequest(BaseModel):
    name: str
    source: str
    data: Dict


class SavedPortfolioResponse(BaseModel):
    id: int
    name: str
    source: str
    created_at: datetime
    data: Dict
