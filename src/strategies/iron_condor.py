"""Iron Condor options strategy implementation."""
import logging
from typing import Dict, List

from .base_strategy import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class IronCondorStrategy(BaseStrategy):
    """
    Iron Condor Strategy - Collect premium in range-bound markets.
    
    Structure:
    - Sell OTM Put (bullish side)
    - Buy further OTM Put (protection)
    - Sell OTM Call (bearish side)
    - Buy further OTM Call (protection)
    
    Risk: Limited to width of spread minus credit received
    Reward: Limited to credit received
    """
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.min_dte = config.get("min_dte", 30)
        self.max_dte = config.get("max_dte", 45)
        self.short_put_delta = config.get("short_put_delta", -0.15)
        self.short_call_delta = config.get("short_call_delta", 0.15)
        self.spread_width = config.get("spread_width", 5.0)
        self.min_credit_ratio = config.get("min_credit_ratio", 0.30)
    
    def generate_signals(self, data: Dict) -> List[Signal]:
        """Generate Iron Condor signals."""
        signals = []
        
        for symbol in self.config.get("symbols", []):
            try:
                signal = self._analyze_symbol(symbol, data)
                if signal and self.validate_signal(signal):
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
        
        return signals
    
    def _analyze_symbol(self, symbol: str, data: Dict) -> Signal:
        """Analyze a single symbol for Iron Condor opportunity."""
        # This is a simplified implementation
        # In production, you'd:
        # 1. Get options chain
        # 2. Calculate deltas
        # 3. Find strikes matching delta targets
        # 4. Verify credit meets minimum
        # 5. Check IV rank/percentile
        
        current_price = data.get("price", {}).get(symbol, 0)
        if current_price == 0:
            return None
        
        # Mock calculation - replace with real options analysis
        put_strike = current_price * 0.95  # 5% OTM
        call_strike = current_price * 1.05  # 5% OTM
        
        credit_estimate = current_price * 0.01  # ~1% of stock price
        max_risk = self.spread_width - credit_estimate
        
        # Check if meets criteria
        if credit_estimate / max_risk < self.min_credit_ratio:
            return None
        
        legs = [
            {
                "type": "put",
                "side": "sell",
                "strike": put_strike,
                "expiration": "30D",
                "delta": self.short_put_delta
            },
            {
                "type": "put",
                "side": "buy",
                "strike": put_strike - self.spread_width,
                "expiration": "30D"
            },
            {
                "type": "call",
                "side": "sell",
                "strike": call_strike,
                "expiration": "30D",
                "delta": self.short_call_delta
            },
            {
                "type": "call",
                "side": "buy",
                "strike": call_strike + self.spread_width,
                "expiration": "30D"
            }
        ]
        
        return Signal(
            symbol=symbol,
            direction="neutral",
            confidence=0.7,  # Would calculate based on setup quality
            strategy="iron_condor",
            legs=legs,
            metadata={
                "max_profit": credit_estimate,
                "max_loss": max_risk,
                "breakevens": [put_strike - credit_estimate, call_strike + credit_estimate],
                "credit_received": credit_estimate
            }
        )
    
    def calculate_position_size(self, account_value: float, 
                                signal: Signal) -> int:
        """Calculate number of Iron Condors to sell."""
        max_risk = self.config.get("max_risk_per_trade", 0.02)
        risk_per_spread = signal.metadata["max_loss"]
        
        # Calculate based on risk, not notional
        max_risk_amount = account_value * max_risk
        position_size = int(max_risk_amount / risk_per_spread)
        
        # Limit to max concurrent positions
        max_positions = self.config.get("max_concurrent_positions", 3)
        position_size = min(position_size, max_positions)
        
        return max(1, position_size)  # At least 1
