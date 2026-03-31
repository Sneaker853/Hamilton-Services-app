"""
Compute expected return and volatility for each asset using FF5 factors (monthly)
and GARCH(1,1)/EWMA volatility blend (daily). Stores results in asset_metrics.
"""

import io
import zipfile
from datetime import datetime, timezone
import urllib.request
import json

import numpy as np
import pandas as pd
import psycopg2
from sklearn.covariance import LedoitWolf, OAS
from sklearn.linear_model import RidgeCV
from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "portfolio_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

FF5_ZIP_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip"

DEFAULT_ASSET_PRIOR_RETURNS = {
    "stock": 0.08,
    "etf": 0.07,
    "bond": 0.04,
    "crypto": 0.14,
    "commodity": 0.06,
}

DEFAULT_RETURN_BOUNDS = {
    "stock": (-0.15, 0.30),
    "etf": (-0.10, 0.20),
    "bond": (-0.02, 0.12),
    "crypto": (-0.40, 0.80),
    "commodity": (-0.20, 0.35),
}

DEFAULT_VOL_BOUNDS = {
    "stock": (0.08, 0.65),
    "etf": (0.04, 0.45),
    "bond": (0.02, 0.25),
    "crypto": (0.25, 1.50),
    "commodity": (0.10, 0.80),
}

ASSET_PRIOR_RETURNS = DEFAULT_ASSET_PRIOR_RETURNS.copy()
RETURN_BOUNDS = DEFAULT_RETURN_BOUNDS.copy()
VOL_BOUNDS = DEFAULT_VOL_BOUNDS.copy()
ESTIMATION_CONFIG_VERSION = "default-v1"
COVARIANCE_METHOD = "ledoit_wolf"  # "sample", "ledoit_wolf", "oas"
RETURN_ESTIMATOR = "ff5_blend"      # "ff5_blend", "ema_historical", "capm", "black_litterman_lite"


def _normalize_bound_map(raw_map: dict, fallback_map: dict) -> dict:
    normalized = fallback_map.copy()
    if not isinstance(raw_map, dict):
        return normalized

    for asset_class, bounds in raw_map.items():
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            continue
        low = float(bounds[0])
        high = float(bounds[1])
        if high <= low:
            continue
        normalized[str(asset_class)] = (low, high)

    return normalized


def _load_estimation_config(config_path: str) -> tuple[str, dict, dict, dict, str, str]:
    version = "default-v1"
    priors = DEFAULT_ASSET_PRIOR_RETURNS.copy()
    return_bounds = DEFAULT_RETURN_BOUNDS.copy()
    vol_bounds = DEFAULT_VOL_BOUNDS.copy()
    cov_method = "ledoit_wolf"
    return_estimator = "ff5_blend"

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        return version, priors, return_bounds, vol_bounds, cov_method, return_estimator

    estimation_cfg = config.get("estimation", {}) if isinstance(config, dict) else {}
    version = str(estimation_cfg.get("version", version))
    cov_method = str(estimation_cfg.get("covariance_method", cov_method))
    if cov_method not in ("sample", "ledoit_wolf", "oas"):
        cov_method = "ledoit_wolf"
    return_estimator = str(estimation_cfg.get("return_estimator", return_estimator))
    if return_estimator not in ("ff5_blend", "ema_historical", "capm", "black_litterman_lite"):
        return_estimator = "ff5_blend"

    raw_priors = estimation_cfg.get("asset_class_priors", {})
    if isinstance(raw_priors, dict):
        for asset_class, prior in raw_priors.items():
            try:
                priors[str(asset_class)] = float(prior)
            except (TypeError, ValueError):
                continue

    return_bounds = _normalize_bound_map(estimation_cfg.get("return_bounds", {}), DEFAULT_RETURN_BOUNDS)
    vol_bounds = _normalize_bound_map(estimation_cfg.get("vol_bounds", {}), DEFAULT_VOL_BOUNDS)

    return version, priors, return_bounds, vol_bounds, cov_method, return_estimator


def _asset_prior_return(asset_class: str) -> float:
    """Config-driven prior return for Bayesian blending.

    The ASSET_PRIOR_RETURNS map is populated from config.json at startup.
    The 0.08 default applies only to asset classes not covered by config —
    this is a deliberate Bayesian anchor, not a hardcoded production fallback.
    """
    return ASSET_PRIOR_RETURNS.get(asset_class, 0.08)


def _clip_return(asset_class: str, value: float) -> float:
    low, high = RETURN_BOUNDS.get(asset_class, (-0.15, 0.25))
    return float(np.clip(value, low, high))


def _clip_vol(asset_class: str, value: float) -> float:
    low, high = VOL_BOUNDS.get(asset_class, (0.06, 0.70))
    return float(np.clip(value, low, high))


def _winsorize(values: np.ndarray, lower_q: float = 0.01, upper_q: float = 0.99) -> np.ndarray:
    if values.size == 0:
        return values
    lower = float(np.nanquantile(values, lower_q))
    upper = float(np.nanquantile(values, upper_q))
    return np.clip(values, lower, upper)


def _geometric_annualized_from_monthly(monthly_returns: np.ndarray) -> float:
    if monthly_returns.size == 0:
        return float("nan")
    monthly_returns = np.clip(monthly_returns, -0.95, 2.0)
    growth = np.prod(1.0 + monthly_returns)
    periods = monthly_returns.size
    if growth <= 0 or periods == 0:
        return float("nan")
    return float(growth ** (12.0 / periods) - 1.0)


def _ridge_fit_factor_model(x: np.ndarray, y: np.ndarray, ridge_lambda: float = 1e-3) -> tuple[np.ndarray, float]:
    """Fit FF5 factor model with cross-validated ridge regression.

    Returns (coef_with_intercept, best_alpha) where coef[0] is the intercept (alpha).
    The ridge_lambda parameter is ignored — kept for API compatibility.
    Cross-validation selects the best regularisation strength automatically.
    """
    # x already has intercept column at index 0 — strip it for RidgeCV (which fits its own)
    x_no_intercept = x[:, 1:]
    alphas = np.logspace(-4, 2, 50)
    try:
        ridge = RidgeCV(alphas=alphas, fit_intercept=True, scoring="r2")
        ridge.fit(x_no_intercept, y)
        coef = np.concatenate([[ridge.intercept_], ridge.coef_])
        best_alpha = float(ridge.alpha_)
    except Exception:
        # Fallback to lstsq if CV fails
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        best_alpha = ridge_lambda
    return coef, best_alpha


def _blended_expected_return(
    asset_class: str,
    monthly_returns: pd.Series,
    ff5_annual_return: float | None,
    sample_months: int,
    r2: float | None,
) -> float:
    """FF5 blend: weighted combination of prior, historical, and FF5 model."""
    prior = _asset_prior_return(asset_class)

    hist_window = monthly_returns.tail(36).to_numpy(dtype=float)
    hist_window = _winsorize(hist_window, 0.05, 0.95)
    hist_annual = _geometric_annualized_from_monthly(hist_window)
    if not np.isfinite(hist_annual):
        hist_annual = prior

    ff5_valid = ff5_annual_return is not None and np.isfinite(ff5_annual_return)
    ff5_component = float(ff5_annual_return) if ff5_valid else prior

    sample_conf = float(np.clip((sample_months - 36) / 48.0, 0.0, 1.0))
    r2_conf = float(np.clip(r2 if r2 is not None and np.isfinite(r2) else 0.0, 0.0, 1.0))
    model_conf = sample_conf * (0.5 + 0.5 * r2_conf)

    if sample_months < 12:
        w_hist = 0.15
        w_model = 0.0
    else:
        w_hist = 0.35
        w_model = 0.20 * model_conf
    w_prior = 1.0 - w_hist - w_model

    blended = w_prior * prior + w_hist * hist_annual + w_model * ff5_component
    return _clip_return(asset_class, blended)


def _ema_historical_return(
    asset_class: str,
    monthly_returns: pd.Series,
    sample_months: int,
    half_life_months: int = 24,
) -> float:
    """EMA historical: exponentially-weighted historical annualised return."""
    prior = _asset_prior_return(asset_class)
    if sample_months < 6 or monthly_returns.dropna().shape[0] < 6:
        return prior

    rets = monthly_returns.dropna().to_numpy(dtype=float)
    rets = _winsorize(rets, 0.02, 0.98)

    lam = np.exp(np.log(0.5) / half_life_months)
    n = rets.size
    weights = (1 - lam) * lam ** np.arange(n - 1, -1, -1)
    weights /= weights.sum()

    ema_monthly = float(np.dot(weights, rets))
    ema_annual = float((1.0 + ema_monthly) ** 12 - 1.0)
    if not np.isfinite(ema_annual):
        return prior

    # Blend with prior for stability
    conf = float(np.clip(sample_months / 60.0, 0.15, 0.85))
    blended = conf * ema_annual + (1.0 - conf) * prior
    return _clip_return(asset_class, blended)


def _capm_return(
    asset_class: str,
    beta_mkt: float | None,
    rf_annual: float = 0.04,
    market_premium: float = 0.055,
) -> float:
    """CAPM: Rf + β × (E[Rm] - Rf)."""
    prior = _asset_prior_return(asset_class)
    if beta_mkt is None or not np.isfinite(beta_mkt):
        return prior
    capm = rf_annual + float(beta_mkt) * market_premium
    return _clip_return(asset_class, capm)


def _black_litterman_lite_return(
    asset_class: str,
    monthly_returns: pd.Series,
    ff5_annual_return: float | None,
    sample_months: int,
    r2: float | None,
    tau: float = 0.05,
) -> float:
    """
    Simplified Black-Litterman: shrink the implied equilibrium return
    (approximated by prior) toward the model view (FF5 or historical),
    weighted by view confidence.
    """
    prior = _asset_prior_return(asset_class)

    # View = FF5 if valid, else EMA historical
    ff5_valid = ff5_annual_return is not None and np.isfinite(ff5_annual_return)
    if ff5_valid:
        view = float(ff5_annual_return)
    else:
        view = _ema_historical_return(asset_class, monthly_returns, sample_months)

    # Uncertainty of the view — lower R² or fewer months = less confident
    r2_val = float(np.clip(r2 if r2 is not None and np.isfinite(r2) else 0.0, 0.0, 1.0))
    sample_conf = float(np.clip((sample_months - 12) / 60.0, 0.0, 1.0))
    omega = 1.0 / max(0.01, r2_val * sample_conf)  # view uncertainty

    # BL posterior = (Σ⁻¹ π + τ⁻¹ Ω⁻¹ q) / (Σ⁻¹ + τ⁻¹ Ω⁻¹)   — scalar simplification
    inv_sigma = 1.0 / max(tau, 0.001)
    inv_omega = 1.0 / max(omega * tau, 0.001)
    posterior = (inv_sigma * prior + inv_omega * view) / (inv_sigma + inv_omega)
    return _clip_return(asset_class, float(posterior))


def _estimate_expected_return(
    method: str,
    asset_class: str,
    monthly_returns: pd.Series,
    ff5_annual_return: float | None,
    sample_months: int,
    r2: float | None,
    beta_mkt: float | None = None,
) -> float:
    """Dispatch to the configured return estimator."""
    if method == "ema_historical":
        return _ema_historical_return(asset_class, monthly_returns, sample_months)
    elif method == "capm":
        return _capm_return(asset_class, beta_mkt)
    elif method == "black_litterman_lite":
        return _black_litterman_lite_return(
            asset_class, monthly_returns, ff5_annual_return, sample_months, r2
        )
    else:  # default: ff5_blend
        return _blended_expected_return(
            asset_class, monthly_returns, ff5_annual_return, sample_months, r2
        )


def load_ff5_monthly() -> pd.DataFrame:
    """Load FF5 monthly factors from Kenneth French data library."""
    with urllib.request.urlopen(FF5_ZIP_URL) as response:
        content = response.read()

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        csv_name = zf.namelist()[0]
        with zf.open(csv_name) as f:
            raw = pd.read_csv(f, skiprows=3)

    raw = raw.rename(columns={raw.columns[0]: "date"})
    raw["date"] = raw["date"].astype(str).str.strip()

    # Keep only monthly rows (YYYYMM)
    raw = raw[raw["date"].str.match(r"^\d{6}$", na=False)]

    raw["date"] = pd.to_datetime(raw["date"], format="%Y%m")
    raw = raw.set_index(raw["date"].dt.to_period("M")).drop(columns=["date"])

    # Convert percent to decimal
    for col in raw.columns:
        raw[col] = pd.to_numeric(raw[col], errors="coerce") / 100.0

    return raw[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]].dropna()


def ewma_volatility(returns: np.ndarray, half_life: int) -> float:
    """Compute EWMA volatility from daily returns."""
    if returns.size < 30:
        return float(np.nan)

    lam = np.exp(np.log(0.5) / half_life)
    weights = (1 - lam) * lam ** np.arange(returns.size - 1, -1, -1)
    var = np.sum(weights * (returns ** 2))
    return float(np.sqrt(var))


def garch11_volatility(returns: np.ndarray) -> float:
    """Estimate conditional volatility via GARCH(1,1) using MLE.

    Model: σ²_t = ω + α·r²_{t-1} + β·σ²_{t-2}
    Constraints: ω > 0, α ≥ 0, β ≥ 0, α + β < 1 (stationarity).
    Returns the final conditional daily standard deviation.
    """
    from scipy.optimize import minimize

    n = returns.size
    if n < 60:
        return float(np.nan)

    r = returns - returns.mean()
    sample_var = float(np.var(r, ddof=1))
    if sample_var < 1e-14:
        return float(np.nan)

    def neg_log_likelihood(params):
        omega, alpha, beta = params
        T = r.size
        sigma2 = np.empty(T)
        sigma2[0] = sample_var
        for t in range(1, T):
            sigma2[t] = omega + alpha * r[t - 1] ** 2 + beta * sigma2[t - 1]
            if sigma2[t] < 1e-14:
                sigma2[t] = 1e-14
        ll = -0.5 * np.sum(np.log(sigma2) + r ** 2 / sigma2)
        return -ll

    omega0 = sample_var * 0.05
    alpha0 = 0.08
    beta0 = 0.88
    x0 = [omega0, alpha0, beta0]

    bounds = [(1e-10, sample_var * 10), (1e-6, 0.5), (0.5, 0.9999)]
    constraints = [{"type": "ineq", "fun": lambda p: 0.9999 - p[1] - p[2]}]

    try:
        res = minimize(
            neg_log_likelihood,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 300, "ftol": 1e-10},
        )
        if not res.success:
            return float(np.nan)

        omega, alpha, beta = res.x
        sigma2 = np.empty(n)
        sigma2[0] = sample_var
        for t in range(1, n):
            sigma2[t] = omega + alpha * r[t - 1] ** 2 + beta * sigma2[t - 1]
        return float(np.sqrt(sigma2[-1]))
    except Exception:
        return float(np.nan)


def annualize_return(monthly_return: float) -> float:
    """Annualize a monthly return."""
    return float((1.0 + monthly_return) ** 12 - 1.0)


def ensure_asset_metrics_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS asset_metrics (
            ticker TEXT PRIMARY KEY,
            expected_return DOUBLE PRECISION,
            volatility DOUBLE PRECISION,
            beta_mkt DOUBLE PRECISION,
            beta_smb DOUBLE PRECISION,
            beta_hml DOUBLE PRECISION,
            beta_rmw DOUBLE PRECISION,
            beta_cma DOUBLE PRECISION,
            alpha DOUBLE PRECISION,
            r2 DOUBLE PRECISION,
            sample_months INTEGER,
            confidence_score DOUBLE PRECISION,
            residual_std DOUBLE PRECISION,
            return_estimator TEXT,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """
    )
    # Add new columns if table already exists (idempotent)
    for col_def in [
        "confidence_score DOUBLE PRECISION",
        "residual_std DOUBLE PRECISION",
        "return_estimator TEXT",
    ]:
        col_name = col_def.split()[0]
        cur.execute(
            f"""
            DO $$
            BEGIN
                ALTER TABLE asset_metrics ADD COLUMN IF NOT EXISTS {col_def};
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$;
            """
        )
    conn.commit()
    cur.close()


def _compute_confidence_score(sample_months: int, r2: float | None, residual_std: float | None, beta_se_penalty: float = 0.0) -> float:
    """
    Composite expected-return confidence score ∈ [0, 1].
    Factors: sample depth, model R², residual noise level, beta SE penalty.
    """
    # Sample depth component: 0 at 6 months, 1 at 84+ months
    depth = float(np.clip((sample_months - 6) / 78.0, 0.0, 1.0))

    # Model fit component
    r2_val = float(np.clip(r2 if r2 is not None and np.isfinite(r2) else 0.0, 0.0, 1.0))

    # Residual noise component (lower is better): monthly residual std
    if residual_std is not None and np.isfinite(residual_std) and residual_std > 0:
        noise_penalty = float(np.clip(1.0 - residual_std / 0.15, 0.0, 1.0))
    else:
        noise_penalty = 0.3

    # Weighted combination
    score = 0.40 * depth + 0.35 * r2_val + 0.25 * noise_penalty
    # Apply beta SE penalty (reduces confidence when beta estimate is imprecise)
    score = float(np.clip(score - beta_se_penalty, 0.0, 1.0))
    return score


def main() -> None:
    global ASSET_PRIOR_RETURNS, RETURN_BOUNDS, VOL_BOUNDS, ESTIMATION_CONFIG_VERSION, COVARIANCE_METHOD, RETURN_ESTIMATOR

    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    (
        ESTIMATION_CONFIG_VERSION,
        ASSET_PRIOR_RETURNS,
        RETURN_BOUNDS,
        VOL_BOUNDS,
        COVARIANCE_METHOD,
        RETURN_ESTIMATOR,
    ) = _load_estimation_config(config_path)

    print(f"Using estimation config version: {ESTIMATION_CONFIG_VERSION}")
    print(f"Covariance method: {COVARIANCE_METHOD}")
    print(f"Return estimator: {RETURN_ESTIMATOR}")

    conn = psycopg2.connect(DB_URL)
    ensure_asset_metrics_table(conn)

    print("Loading FF5 factors...")
    factors = load_ff5_monthly()

    print("Loading price history...")
    prices = pd.read_sql(
        "SELECT ticker, date, close FROM price_history ORDER BY ticker, date",
        conn,
        parse_dates=["date"],
    )

    print("Loading asset classes...")
    asset_classes = pd.read_sql("SELECT ticker, COALESCE(asset_class, 'stock') AS asset_class FROM stocks", conn)
    asset_class_map = dict(zip(asset_classes["ticker"], asset_classes["asset_class"]))

    prices = prices.dropna(subset=["close"]).sort_values(["ticker", "date"])
    prices["daily_return"] = prices.groupby("ticker")["close"].pct_change()

    prices["month"] = prices["date"].dt.to_period("M")
    month_end = prices.groupby(["ticker", "month"], as_index=False)["close"].last()
    month_end = month_end.sort_values(["ticker", "month"])
    month_end["monthly_return"] = month_end.groupby("ticker")["close"].pct_change()

    metrics_rows = []

    print("Computing metrics...")
    for ticker, group in month_end.groupby("ticker"):
        monthly_returns = group.set_index("month")["monthly_return"].dropna()
        if monthly_returns.empty:
            continue

        aligned = pd.concat([monthly_returns, factors], axis=1, join="inner").dropna()
        sample_months = int(aligned.shape[0])

        expected_return = None
        alpha = None
        betas = [None, None, None, None, None]
        r2 = None
        ff5_annual = None
        residual_std = None
        beta_se_penalty = 0.0

        if sample_months >= 36:
            y = aligned["monthly_return"] - aligned["RF"]
            x = aligned[["Mkt-RF", "SMB", "HML", "RMW", "CMA"]].values
            x = np.column_stack([np.ones(len(x)), x])

            coef, _best_alpha = _ridge_fit_factor_model(x, y.values, ridge_lambda=1e-3)
            alpha = float(np.clip(coef[0], -0.2, 0.2))
            betas = [float(np.clip(v, -3.0, 3.0)) for v in coef[1:]]

            y_hat = x @ coef
            ss_res = float(np.sum((y.values - y_hat) ** 2))
            ss_tot = float(np.sum((y.values - y.values.mean()) ** 2))
            r2_val = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
            r2 = float(np.clip(r2_val, 0.0, 1.0)) if np.isfinite(r2_val) else None

            # Residual standard deviation (monthly)
            residuals = y.values - y_hat
            residual_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else None

            # Beta standard error penalty: penalise confidence when 95% CI
            # width > 50% of the beta_mkt point estimate
            beta_se_penalty = 0.0
            if residual_std is not None and betas[0] is not None and len(y) > 6:
                mse = float(ss_res / max(len(y) - 6, 1))  # 6 params: intercept + 5 factors
                try:
                    xtx_inv = np.linalg.inv(x.T @ x)
                    se_beta_mkt = float(np.sqrt(mse * xtx_inv[1, 1]))
                    ci_width = 2 * 1.96 * se_beta_mkt
                    beta_abs = abs(betas[0]) if abs(betas[0]) > 0.01 else 0.01
                    if ci_width > 0.5 * beta_abs:
                        beta_se_penalty = float(np.clip((ci_width / beta_abs - 0.5) / 1.5, 0.0, 0.4))
                except np.linalg.LinAlgError:
                    pass

            factor_means = aligned[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]].mean()
            mu_monthly = float(
                factor_means["RF"]
                + np.dot(
                    np.array(betas),
                    factor_means[["Mkt-RF", "SMB", "HML", "RMW", "CMA"]].values,
                )
            )
            ff5_annual = annualize_return(mu_monthly)

        # Volatility from EWMA daily returns
        daily_returns = prices.loc[prices["ticker"] == ticker, "daily_return"].dropna().to_numpy()
        asset_class = asset_class_map.get(ticker, "stock")

        expected_return = _estimate_expected_return(
            method=RETURN_ESTIMATOR,
            asset_class=asset_class,
            monthly_returns=aligned["monthly_return"],
            ff5_annual_return=ff5_annual,
            sample_months=sample_months,
            r2=r2,
            beta_mkt=betas[0],
        )

        daily_returns = _winsorize(daily_returns, 0.01, 0.99)

        if asset_class in {"crypto", "commodity"}:
            half_life = 20
            trading_days = 365
        else:
            half_life = 60
            trading_days = 252

        daily_vol = ewma_volatility(daily_returns, half_life=half_life)
        garch_vol_daily = garch11_volatility(daily_returns)
        realized_vol = float(np.nanstd(daily_returns, ddof=1) * np.sqrt(trading_days)) if daily_returns.size >= 30 else float("nan")

        # Blend: 50% GARCH, 30% EWMA, 20% realized (GARCH preferred)
        # Fall back gracefully when a model fails to converge
        garch_ann = float(garch_vol_daily * np.sqrt(trading_days)) if np.isfinite(garch_vol_daily) else float("nan")
        ewma_ann = float(daily_vol * np.sqrt(trading_days)) if np.isfinite(daily_vol) else float("nan")

        vol_estimates = []
        vol_weights = []
        if np.isfinite(garch_ann):
            vol_estimates.append(garch_ann)
            vol_weights.append(0.50)
        if np.isfinite(ewma_ann):
            vol_estimates.append(ewma_ann)
            vol_weights.append(0.30)
        if np.isfinite(realized_vol):
            vol_estimates.append(realized_vol)
            vol_weights.append(0.20)

        if vol_estimates:
            w = np.array(vol_weights)
            w = w / w.sum()  # re-normalize if some models missing
            volatility = float(np.dot(w, vol_estimates))
        else:
            volatility = VOL_BOUNDS.get(asset_class, (0.06, 0.70))[0] * 1.5

        volatility = _clip_vol(asset_class, float(volatility))

        confidence_score = _compute_confidence_score(sample_months, r2, residual_std, beta_se_penalty)

        metrics_rows.append(
            (
                ticker,
                expected_return,
                volatility,
                betas[0],
                betas[1],
                betas[2],
                betas[3],
                betas[4],
                alpha,
                r2,
                sample_months,
                confidence_score,
                residual_std,
                RETURN_ESTIMATOR,
                datetime.now(timezone.utc),
            )
        )

    print(f"Saving metrics for {len(metrics_rows)} tickers...")
    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO asset_metrics (
            ticker, expected_return, volatility,
            beta_mkt, beta_smb, beta_hml, beta_rmw, beta_cma,
            alpha, r2, sample_months,
            confidence_score, residual_std, return_estimator,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker) DO UPDATE SET
            expected_return = EXCLUDED.expected_return,
            volatility = EXCLUDED.volatility,
            beta_mkt = EXCLUDED.beta_mkt,
            beta_smb = EXCLUDED.beta_smb,
            beta_hml = EXCLUDED.beta_hml,
            beta_rmw = EXCLUDED.beta_rmw,
            beta_cma = EXCLUDED.beta_cma,
            alpha = EXCLUDED.alpha,
            r2 = EXCLUDED.r2,
            sample_months = EXCLUDED.sample_months,
            confidence_score = EXCLUDED.confidence_score,
            residual_std = EXCLUDED.residual_std,
            return_estimator = EXCLUDED.return_estimator,
            updated_at = EXCLUDED.updated_at
        """,
        metrics_rows,
    )
    conn.commit()
    cur.close()
    conn.close()

    print("Done.")


if __name__ == "__main__":
    main()
