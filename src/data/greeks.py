"""
Greeks Monitoring and Position Adjustment Module

Provides Black-Scholes Greeks calculation for options and portfolio-level
Greeks aggregation with intelligent position adjustment recommendations.
Includes fallback pure-Python normal CDF approximation for scipy compatibility.
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import math

logger = logging.getLogger(__name__)


class OptionType(Enum):
    """Option type enumeration."""
    CALL = "call"
    PUT = "put"


class Urgency(Enum):
    """Adjustment urgency levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Try to import scipy; fall back to pure Python if unavailable
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available; using pure-Python normal CDF approximation")


def _normal_cdf_python(x: float) -> float:
    """
    Pure Python approximation of the standard normal cumulative distribution function.
    Uses the error function approximation from Abramowitz and Stegun (1964).
    Accuracy: ~7 decimal places for most values.
    """
    # Constants for the approximation
    a1 =  0.254829592
    a2 = -0.284496736
    a3 =  1.421413741
    a4 = -1.453152027
    a5 =  1.061405429
    p  =  0.3275911

    # Handle edge cases
    if x >= 6:
        return 1.0
    if x <= -6:
        return 0.0

    # Save the sign of x
    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)

    # Abramowitz and Stegun approximation
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

    return 0.5 * (1.0 + sign * y)


def _normal_cdf(x: float) -> float:
    """
    Wrapper for normal CDF calculation using scipy if available, else pure Python.
    """
    if SCIPY_AVAILABLE:
        return float(stats.norm.cdf(x))
    else:
        return _normal_cdf_python(x)


def _normal_pdf(x: float) -> float:
    """Probability density function of standard normal distribution."""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


@dataclass
class GreeksResult:
    """
    Result of Black-Scholes Greeks calculation for a single option position.

    Attributes:
        delta: Rate of change of option price with respect to underlying price
        gamma: Rate of change of delta with respect to underlying price
        theta: Time decay (change in option value per day)
        vega: Sensitivity to implied volatility (per 1% change)
        rho: Sensitivity to interest rate (per 1% change)
        option_type: Whether this is a call or put option
        underlying_price: Current underlying asset price
        strike: Strike price of the option
        dte: Days to expiration
        iv: Implied volatility used in calculation
    """
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    option_type: str
    underlying_price: float
    strike: float
    dte: float
    iv: float


@dataclass
class PortfolioGreeks:
    """
    Aggregated Greeks for an entire portfolio of positions.

    Attributes:
        net_delta: Sum of deltas across all positions
        net_gamma: Sum of gammas across all positions
        net_theta: Sum of thetas across all positions
        net_vega: Sum of vegas across all positions
        net_rho: Sum of rhos across all positions
        positions: List of individual GreeksResult objects for each position
    """
    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float
    net_rho: float
    positions: List[GreeksResult] = field(default_factory=list)


@dataclass
class AdjustmentRecommendation:
    """
    Recommendation for position adjustment based on Greeks analysis.

    Attributes:
        position_id: Unique identifier for the position requiring adjustment
        action: Recommended action (e.g., "hedge", "close", "reduce", "monitor")
        reason: Explanation of why this action is recommended
        urgency: Priority level (low, medium, high)
    """
    position_id: str
    action: str
    reason: str
    urgency: str


class GreeksMonitor:
    """
    Thread-safe Greeks calculation and portfolio monitoring engine.

    Provides Black-Scholes Greeks calculation with automatic fallback to
    pure-Python normal CDF approximation. Supports portfolio aggregation
    and intelligent adjustment recommendations based on configurable thresholds.
    """

    def __init__(self):
        """Initialize the Greeks monitor with thread safety."""
        self._lock = threading.RLock()
        logger.info("GreeksMonitor initialized (scipy available: %s)", SCIPY_AVAILABLE)

    def calculate_greeks(
        self,
        underlying_price: float,
        strike: float,
        dte_days: float,
        iv: float,
        risk_free_rate: float = 0.05,
        option_type: str = "call",
        quantity: int = 1,
    ) -> GreeksResult:
        """
        Calculate Black-Scholes Greeks for a single option position.

        Args:
            underlying_price: Current price of the underlying asset
            strike: Strike price of the option
            dte_days: Days to expiration (fractional days supported)
            iv: Implied volatility as a decimal (e.g., 0.20 for 20%)
            risk_free_rate: Risk-free interest rate as a decimal (default 5%)
            option_type: "call" or "put"
            quantity: Number of contracts (for scaling, typically 1 per position)

        Returns:
            GreeksResult object containing all Greeks

        Raises:
            ValueError: If inputs are invalid (negative prices, dte, or iv)
        """
        # Input validation
        if underlying_price <= 0 or strike <= 0:
            raise ValueError("Underlying price and strike must be positive")
        if dte_days < 0 or iv < 0 or risk_free_rate < 0:
            raise ValueError("DTE, IV, and risk-free rate must be non-negative")

        with self._lock:
            try:
                # Handle expired options
                if dte_days == 0:
                    return self._handle_expired_option(
                        underlying_price, strike, option_type
                    )

                # Convert DTE to years
                t = dte_days / 365.0

                # Calculate d1 and d2 from Black-Scholes
                sqrt_t = math.sqrt(t)
                d1 = (
                    math.log(underlying_price / strike)
                    + (risk_free_rate + 0.5 * iv * iv) * t
                ) / (iv * sqrt_t)
                d2 = d1 - iv * sqrt_t

                # Get normal distribution values
                nd1 = _normal_cdf(d1)
                nd2 = _normal_cdf(d2)
                npd1 = _normal_pdf(d1)

                # Calculate Greeks based on option type
                if option_type.lower() == "call":
                    delta = nd1
                    rho = strike * math.exp(-risk_free_rate * t) * nd2 * t
                else:  # put
                    delta = nd1 - 1
                    rho = -strike * math.exp(-risk_free_rate * t) * _normal_cdf(-d2) * t

                # Greeks that are the same for calls and puts
                gamma = npd1 / (underlying_price * iv * sqrt_t)
                vega = underlying_price * npd1 * sqrt_t / 100  # Per 1% change in IV
                theta = self._calculate_theta(
                    underlying_price,
                    strike,
                    dte_days,
                    iv,
                    risk_free_rate,
                    option_type.lower(),
                    d1,
                    d2,
                    npd1,
                )

                # Scale by quantity
                delta *= quantity
                gamma *= quantity
                theta *= quantity
                vega *= quantity
                rho *= quantity

                logger.debug(
                    "Greeks calculated: type=%s, S=%.2f, K=%.2f, DTE=%.1f, "
                    "IV=%.4f, delta=%.4f, gamma=%.6f, theta=%.4f, vega=%.4f",
                    option_type,
                    underlying_price,
                    strike,
                    dte_days,
                    iv,
                    delta,
                    gamma,
                    theta,
                    vega,
                )

                return GreeksResult(
                    delta=delta,
                    gamma=gamma,
                    theta=theta,
                    vega=vega,
                    rho=rho,
                    option_type=option_type.lower(),
                    underlying_price=underlying_price,
                    strike=strike,
                    dte=dte_days,
                    iv=iv,
                )

            except Exception as e:
                logger.error("Error calculating Greeks: %s", str(e))
                raise

    def _calculate_theta(
        self,
        underlying_price: float,
        strike: float,
        dte_days: float,
        iv: float,
        risk_free_rate: float,
        option_type: str,
        d1: float,
        d2: float,
        npd1: float,
    ) -> float:
        """Calculate theta (time decay) component of Greeks."""
        t = dte_days / 365.0
        sqrt_t = math.sqrt(t)

        if t < 1e-6:  # Near expiration
            return 0.0

        # First term (common to both calls and puts)
        first_term = -underlying_price * npd1 * iv / (2 * sqrt_t)

        if option_type == "call":
            second_term = risk_free_rate * strike * math.exp(-risk_free_rate * t) * _normal_cdf(d2)
        else:  # put
            second_term = -risk_free_rate * strike * math.exp(-risk_free_rate * t) * _normal_cdf(-d2)

        # Theta per day (divide by 365)
        theta = (first_term + second_term) / 365.0
        return theta

    def _handle_expired_option(
        self, underlying_price: float, strike: float, option_type: str
    ) -> GreeksResult:
        """Handle Greeks for expired options."""
        if option_type.lower() == "call":
            delta = 1.0 if underlying_price > strike else 0.0
        else:  # put
            delta = -1.0 if underlying_price < strike else 0.0

        return GreeksResult(
            delta=delta,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            option_type=option_type.lower(),
            underlying_price=underlying_price,
            strike=strike,
            dte=0.0,
            iv=0.0,
        )

    def get_portfolio_greeks(
        self, positions: List[Dict]
    ) -> PortfolioGreeks:
        """
        Calculate aggregated Greeks across a portfolio of positions.

        Args:
            positions: List of position dicts with keys:
                - underlying_price: Current underlying price
                - strike: Strike price
                - dte_days: Days to expiration
                - iv: Implied volatility
                - option_type: "call" or "put"
                - quantity: Number of contracts (optional, default 1)
                - position_id: Unique position identifier (optional)
                - risk_free_rate: Risk-free rate (optional, default 0.05)

        Returns:
            PortfolioGreeks object with aggregated Greeks and individual position details

        Raises:
            ValueError: If positions list is empty or contains invalid data
        """
        if not positions:
            raise ValueError("Positions list cannot be empty")

        with self._lock:
            position_greeks_list = []
            net_delta = 0.0
            net_gamma = 0.0
            net_theta = 0.0
            net_vega = 0.0
            net_rho = 0.0

            for position in positions:
                try:
                    greeks = self.calculate_greeks(
                        underlying_price=position.get("underlying_price"),
                        strike=position.get("strike"),
                        dte_days=position.get("dte_days"),
                        iv=position.get("iv"),
                        risk_free_rate=position.get("risk_free_rate", 0.05),
                        option_type=position.get("option_type", "call"),
                        quantity=position.get("quantity", 1),
                    )
                    position_greeks_list.append(greeks)

                    # Aggregate
                    net_delta += greeks.delta
                    net_gamma += greeks.gamma
                    net_theta += greeks.theta
                    net_vega += greeks.vega
                    net_rho += greeks.rho

                except (KeyError, ValueError) as e:
                    logger.error(
                        "Error processing position %s: %s",
                        position.get("position_id", "unknown"),
                        str(e),
                    )
                    raise

            logger.info(
                "Portfolio Greeks calculated: delta=%.4f, gamma=%.6f, "
                "theta=%.4f, vega=%.4f, rho=%.4f",
                net_delta,
                net_gamma,
                net_theta,
                net_vega,
                net_rho,
            )

            return PortfolioGreeks(
                net_delta=net_delta,
                net_gamma=net_gamma,
                net_theta=net_theta,
                net_vega=net_vega,
                net_rho=net_rho,
                positions=position_greeks_list,
            )

    def check_adjustments(
        self,
        portfolio_greeks: PortfolioGreeks,
        config: Dict,
        positions_metadata: Optional[List[Dict]] = None,
    ) -> List[AdjustmentRecommendation]:
        """
        Analyze portfolio Greeks and generate adjustment recommendations.

        Args:
            portfolio_greeks: PortfolioGreeks object from get_portfolio_greeks()
            config: Configuration dict with thresholds:
                - max_portfolio_delta: Absolute delta threshold for portfolio (default: 0.3)
                - max_gamma_risk: Maximum acceptable gamma (default: 0.05)
                - min_theta_ratio: Minimum theta/premium ratio for acceptability (default: -0.001)
                - dte_gamma_warning: Days to expiration threshold for gamma warnings (default: 14)
            positions_metadata: Optional list of position dicts with position_id for linking

        Returns:
            List of AdjustmentRecommendation objects
        """
        with self._lock:
            recommendations = []

            # Set defaults for config
            max_delta = config.get("max_portfolio_delta", 0.3)
            max_gamma = config.get("max_gamma_risk", 0.05)
            min_theta_ratio = config.get("min_theta_ratio", -0.001)
            dte_gamma_warning = config.get("dte_gamma_warning", 14)

            # Check portfolio-level delta
            abs_delta = abs(portfolio_greeks.net_delta)
            if abs_delta > max_delta:
                direction = "positive" if portfolio_greeks.net_delta > 0 else "negative"
                recommendations.append(
                    AdjustmentRecommendation(
                        position_id="portfolio",
                        action="hedge",
                        reason=f"Portfolio delta exposure ({direction}, {abs_delta:.4f}) "
                               f"exceeds threshold ({max_delta})",
                        urgency=self._calculate_urgency(abs_delta, max_delta),
                    )
                )

            # Check position-level gamma near expiration
            for idx, greeks in enumerate(portfolio_greeks.positions):
                position_id = (
                    positions_metadata[idx].get("position_id", f"position_{idx}")
                    if positions_metadata and idx < len(positions_metadata)
                    else f"position_{idx}"
                )

                # Gamma warning near expiration
                if greeks.dte <= dte_gamma_warning and greeks.gamma > max_gamma:
                    recommendations.append(
                        AdjustmentRecommendation(
                            position_id=position_id,
                            action="review",
                            reason=f"High gamma risk near expiration (gamma={greeks.gamma:.6f}, "
                                   f"DTE={greeks.dte:.1f})",
                            urgency=Urgency.HIGH.value if greeks.dte <= 7 else Urgency.MEDIUM.value,
                        )
                    )

                # Theta decay check (if we can estimate premium collected)
                if greeks.theta < min_theta_ratio and greeks.dte <= 30:
                    recommendations.append(
                        AdjustmentRecommendation(
                            position_id=position_id,
                            action="close",
                            reason=f"Theta decay ({greeks.theta:.6f}) deteriorating with "
                                   f"insufficient premium benefit near expiration (DTE={greeks.dte:.1f})",
                            urgency=Urgency.MEDIUM.value,
                        )
                    )

            if recommendations:
                logger.info(
                    "Generated %d adjustment recommendations", len(recommendations)
                )
            else:
                logger.debug("No adjustment recommendations needed")

            return recommendations

    def _calculate_urgency(self, current: float, threshold: float) -> str:
        """
        Determine urgency level based on how far current exceeds threshold.

        Args:
            current: Current Greek value (absolute)
            threshold: Threshold value

        Returns:
            Urgency level as string
        """
        if current > threshold * 1.5:
            return Urgency.HIGH.value
        elif current > threshold * 1.2:
            return Urgency.MEDIUM.value
        else:
            return Urgency.LOW.value


# Module-level convenience function
def create_greeks_monitor() -> GreeksMonitor:
    """Factory function to create a GreeksMonitor instance."""
    return GreeksMonitor()
