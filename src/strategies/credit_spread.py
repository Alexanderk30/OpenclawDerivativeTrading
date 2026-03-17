"""Credit Spread strategy implementation."""
import logging
from typing import Dict, List

from .base_strategy import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class CreditSpreadStrategy(BaseStrategy):
    """
    Credit Spread Strategy - Directional options strategy with defined risk.
    
    Bull Put Spread (bullish):
    - Sell OTM Put
    - Buy further OTM Put
    
    Bear Call Spread (bearish):
    - Sell OTM Call
    - Buy further OTM Call
    
    Risk: Limited to spread width minus credit
    Reward: Limited to credit received
    """
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.min_dte = config.get("min_dte", 21)
        self.max_dte = config.get("max_dte", 45)
        self.put_delta = config.get("put_spread_delta", -0.20)
        self.call_delta = config.get("call_spread_delta", 0.20)
        self.spread_width = config.get("spread_width", 5.0)
    
    def generate_signals(self, data: Dict) -> List[Signal]:
        """Generate credit spread signals."""
        signals = []
        
        for symbol in self.config.get("symbols", []):
            try:
                # Determine direction based on analysis
                direction = self._determine_direction(symbol, data)
                
                if direction != "neutral":
                    signal = self._create_spread_signal(symbol, direction, data)
                    if signal and self.validate_signal(signal):
                        signals.append(signal)
                        
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
        
        return signals
    
    def _determine_direction(self, symbol: str, data: Dict) -> str:
        """Determine market direction for symbol."""
        # Simplified - would use technical analysis
        # Return: "bullish", "bearish", or "neutral"
        
        price_data = data.get("price_history", {}).get(symbol, [])
        if len(price_data) < 20:
            return "neutral"
        
        # Simple moving average crossover
        sma_short = sum(price_data[-10:]) / 10
        sma_long = sum(price_data[-20:]) / 20
        
        if sma_short > sma_long * 1.01:
            return "bullish"
        elif sma_short < sma_long * 0.99:
            return "bearish"
        
        return "neutral"
    
    def _create_spread_signal(self, symbol: str, direction: str, 
                              data: Dict) -> Signal:
        """Create a credit spread signal."""
        current_price = data.get("price", {}).get(symbol, 0)
        
        if direction == "bullish":
            # Bull Put Spread
            short_strike = current_price * 0.95
            long_strike = short_strike - self.spread_width
            legs = [
                {"type": "put", "side": "sell", "strike": short_strike, "delta": self.put_delta},
                {"type": "put", "side": "buy", "strike": long_strike}
            ]
        else:
            # Bear Call Spread
            short_strike = current_price * 1.05
            long_strike = short_strike + self.spread_width
            legs = [
                {"type": "call", "side": "sell", "strike": short_strike, "delta": self.call_delta},
                {"type": "call", "side": "buy", "strike": long_strike}
            ]
        
        # Estimate credit (would be calculated from actual options chain)
        credit_estimate = self.spread_width * 0.25
        max_risk = self.spread_width - credit_estimate
        
        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=0.65,
            strategy="credit_spread",
            legs=legs,
            metadata={
                "spread_type": "put" if direction == "bullish" else "call",
                "max_profit": credit_estimate,
                "max_loss": max_risk,
                "credit_received": credit_estimate,
                "short_strike": short_strike,
                "long_strike": long_strike
            }
        )
    
    def calculate_position_size(self, account_value: float,
                                signal: Signal) -> int:
        """Calculate number of spreads."""
        max_risk = self.config.get("max_risk_per_trade", 0.02)
        max_position = self.config.get("max_position_size", 0.10)
        
        risk_per_spread = signal.metadata["max_loss"]
        
        # Risk-based sizing
        max_risk_amount = account_value * max_risk
        risk_based_size = int(max_risk_amount / risk_per_spread)
        
        # Position limit based on notional
        max_notional = account_value * max_position
        notional_per_spread = signal.metadata["short_strike"] * 100  # 100 shares per contract
        position_limit = int(max_notional / notional_per_spread)
        
        return min(risk_based_size, position_limit, 10)  # Cap at 10 spreads
