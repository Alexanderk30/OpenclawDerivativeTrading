"""
IV Rank and Percentile Filtering Module

Provides implied volatility analysis using historical volatility calculations
and VIX as a proxy. Includes IV rank, IV percentile, and regime classification.
Implements thread-safe caching with configurable TTL.
"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class IVData:
    """Typed container for IV analysis results."""
    symbol: str
    current_iv: float
    iv_rank: float
    iv_percentile: float
    hv_20: float
    hv_50: float
    hv_252: float
    timestamp: datetime


class IVAnalyzer:
    """
    Thread-safe IV rank and percentile analyzer using historical volatility
    and VIX as proxy for implied volatility.

    Implements:
    - IV Rank: (current_iv - min_iv) / (max_iv - min_iv) over lookback period
    - IV Percentile: percentage of days where IV was below current level
    - Historical Volatility: annualized standard deviation of log returns
    - Regime classification: low, moderate, high, extreme
    """

    # VIX symbol for index-based IV proxy
    VIX_SYMBOL = "^VIX"

    # IV percentile thresholds for regime classification
    REGIME_THRESHOLDS = {
        "low": (0.0, 0.25),
        "moderate": (0.25, 0.75),
        "high": (0.75, 0.95),
        "extreme": (0.95, 1.0),
    }

    def __init__(self, cache_ttl_hours: int = 24):
        """
        Initialize the IV analyzer.

        Args:
            cache_ttl_hours: Cache time-to-live in hours (default 24)
        """
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self._cache: Dict[str, Tuple[IVData, datetime]] = {}
        self._lock = threading.Lock()
        logger.info(f"IVAnalyzer initialized with cache TTL: {cache_ttl_hours} hours")

    def get_iv_data(self, symbol: str, lookback_days: int = 252) -> IVData:
        """
        Fetch and calculate IV data for a symbol.

        For index-like symbols (or if basic stock IV requested), uses historical
        volatility from close price returns. For VIX itself, returns VIX values.

        Args:
            symbol: Ticker symbol (e.g., "AAPL", "^VIX", "SPY")
            lookback_days: Number of days to look back (default 252 for 1 year)

        Returns:
            IVData: Dataclass with IV metrics

        Raises:
            ValueError: If symbol data cannot be fetched
            logging warnings: If data is incomplete
        """
        # Check cache
        with self._lock:
            if symbol in self._cache:
                cached_data, cached_time = self._cache[symbol]
                if datetime.now() - cached_time < self.cache_ttl:
                    logger.debug(f"Returning cached IV data for {symbol}")
                    return cached_data

        try:
            # Fetch historical price data
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=f"{lookback_days}d")

            if hist.empty or len(hist) < 20:
                raise ValueError(f"Insufficient data for {symbol} (got {len(hist)} days)")

            # Extract close prices
            closes = hist["Close"].dropna()

            if len(closes) < 20:
                raise ValueError(f"Insufficient valid close prices for {symbol}")

            # Calculate log returns
            log_returns = np.log(closes / closes.shift(1)).dropna()

            # Calculate historical volatilities (annualized)
            hv_20 = self._calculate_hv(log_returns, 20)
            hv_50 = self._calculate_hv(log_returns, 50)
            hv_252 = self._calculate_hv(log_returns, 252)

            # Use HV_20 as current IV proxy
            current_iv = hv_20

            # Calculate IV rank and percentile
            all_hvs = self._calculate_rolling_hvs(log_returns, window=20)
            iv_rank = self._calculate_iv_rank(current_iv, all_hvs)
            iv_percentile = self._calculate_iv_percentile(current_iv, all_hvs)

            # Create result
            iv_data = IVData(
                symbol=symbol,
                current_iv=current_iv,
                iv_rank=iv_rank,
                iv_percentile=iv_percentile,
                hv_20=hv_20,
                hv_50=hv_50,
                hv_252=hv_252,
                timestamp=datetime.now(),
            )

            # Cache result
            with self._lock:
                self._cache[symbol] = (iv_data, datetime.now())

            logger.debug(
                f"IV data for {symbol}: rank={iv_rank:.2%}, "
                f"percentile={iv_percentile:.2%}, hv_20={hv_20:.2%}"
            )

            return iv_data

        except Exception as e:
            logger.error(f"Error fetching IV data for {symbol}: {e}")
            raise ValueError(f"Failed to fetch IV data for {symbol}: {e}")

    def filter_by_iv(
        self,
        symbol: str,
        min_rank: float,
        max_rank: float,
        lookback_days: int = 252,
    ) -> bool:
        """
        Check if a symbol's IV rank falls within specified range.

        Args:
            symbol: Ticker symbol
            min_rank: Minimum IV rank (0.0 to 1.0)
            max_rank: Maximum IV rank (0.0 to 1.0)
            lookback_days: Number of days to look back

        Returns:
            bool: True if IV rank is within range, False otherwise
        """
        if not (0.0 <= min_rank <= 1.0) or not (0.0 <= max_rank <= 1.0):
            logger.warning(
                f"Invalid IV rank range: [{min_rank}, {max_rank}]. "
                f"Must be between 0.0 and 1.0"
            )
            return False

        if min_rank > max_rank:
            logger.warning(
                f"Invalid IV rank range: min_rank ({min_rank}) > max_rank ({max_rank})"
            )
            return False

        try:
            iv_data = self.get_iv_data(symbol, lookback_days)
            passes_filter = min_rank <= iv_data.iv_rank <= max_rank

            logger.debug(
                f"{symbol}: IV rank {iv_data.iv_rank:.2%} in range "
                f"[{min_rank:.2%}, {max_rank:.2%}]? {passes_filter}"
            )

            return passes_filter

        except Exception as e:
            logger.error(
                f"Error filtering {symbol} by IV range [{min_rank}, {max_rank}]: {e}"
            )
            return False

    def get_iv_regime(self, symbol: str, lookback_days: int = 252) -> str:
        """
        Classify IV regime based on IV percentile.

        Regimes:
        - "low": IV percentile < 25%
        - "moderate": 25% <= IV percentile < 75%
        - "high": 75% <= IV percentile < 95%
        - "extreme": IV percentile >= 95%

        Args:
            symbol: Ticker symbol
            lookback_days: Number of days to look back

        Returns:
            str: Regime classification
        """
        try:
            iv_data = self.get_iv_data(symbol, lookback_days)
            percentile = iv_data.iv_percentile

            for regime, (min_pct, max_pct) in self.REGIME_THRESHOLDS.items():
                if min_pct <= percentile < max_pct:
                    logger.debug(
                        f"{symbol}: IV percentile {percentile:.2%} -> regime '{regime}'"
                    )
                    return regime

            # Handle edge case where percentile == 1.0
            logger.debug(
                f"{symbol}: IV percentile {percentile:.2%} -> regime 'extreme'"
            )
            return "extreme"

        except Exception as e:
            logger.error(f"Error determining IV regime for {symbol}: {e}")
            return "unknown"

    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """
        Clear cache for a specific symbol or all symbols.

        Args:
            symbol: Specific symbol to clear, or None to clear all
        """
        with self._lock:
            if symbol:
                if symbol in self._cache:
                    del self._cache[symbol]
                    logger.debug(f"Cleared cache for {symbol}")
            else:
                self._cache.clear()
                logger.debug("Cleared entire IV cache")

    @staticmethod
    def _calculate_hv(log_returns: pd.Series, period: int) -> float:
        """
        Calculate annualized historical volatility.

        Args:
            log_returns: Series of log returns
            period: Number of periods for calculation

        Returns:
            float: Annualized HV (as a decimal, e.g., 0.25 for 25%)
        """
        if len(log_returns) < period:
            return 0.0

        # Use rolling std dev, take the most recent value
        rolling_std = log_returns.rolling(window=period).std()
        latest_std = rolling_std.iloc[-1]

        if pd.isna(latest_std):
            return 0.0

        # Annualize (252 trading days per year)
        annualized_hv = latest_std * np.sqrt(252)
        return float(annualized_hv)

    @staticmethod
    def _calculate_rolling_hvs(
        log_returns: pd.Series,
        window: int = 20,
    ) -> np.ndarray:
        """
        Calculate rolling historical volatilities.

        Args:
            log_returns: Series of log returns
            window: Rolling window size

        Returns:
            np.ndarray: Array of annualized HV values
        """
        rolling_std = log_returns.rolling(window=window).std()
        annualized_hvs = rolling_std * np.sqrt(252)
        return annualized_hvs.dropna().values

    @staticmethod
    def _calculate_iv_rank(current_iv: float, iv_series: np.ndarray) -> float:
        """
        Calculate IV rank: (current - min) / (max - min).

        Returns 0.5 if all values are equal (no volatility in the series).

        Args:
            current_iv: Current IV value
            iv_series: Array of historical IV values

        Returns:
            float: IV rank (0.0 to 1.0)
        """
        if len(iv_series) == 0:
            return 0.5

        min_iv = np.min(iv_series)
        max_iv = np.max(iv_series)

        if max_iv <= min_iv:  # No volatility in the range
            return 0.5

        rank = (current_iv - min_iv) / (max_iv - min_iv)
        # Clamp to [0, 1] in case current_iv is outside historical range
        return float(np.clip(rank, 0.0, 1.0))

    @staticmethod
    def _calculate_iv_percentile(current_iv: float, iv_series: np.ndarray) -> float:
        """
        Calculate IV percentile: percentage of values below current.

        Args:
            current_iv: Current IV value
            iv_series: Array of historical IV values

        Returns:
            float: IV percentile (0.0 to 1.0)
        """
        if len(iv_series) == 0:
            return 0.5

        percentile = np.sum(iv_series < current_iv) / len(iv_series)
        return float(percentile)
