"""The Wheel Strategy - CSPs + Covered Calls."""
import logging
from typing import Dict, List

from .base_strategy import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class WheelStrategy(BaseStrategy):
    """
    The Wheel Strategy - Income generation through options.
    
    Phase 1: Sell Cash Secured Puts (CSPs)
    - Collect premium while waiting to be assigned
    - Only on stocks you're willing to own
    
    Phase 2: Sell Covered Calls (after assignment)
    - Generate income on assigned shares
    - Continue until called away
    - Repeat Phase 1
    
    Risk: Stock ownership if puts are exercised
    """
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.symbols = config.get("symbols", [])
        self.csp_delta = config.get("csp_delta", -0.30)
        self.cc_delta = config.get("cc_delta", 0.30)
        self.csp_dte = config.get("csp_dte", 30)
        self.cc_dte = config.get("cc_dte", 30)
        self.max_allocation = config.get("max_allocation_per_stock", 0.10)
    
    def generate_signals(self, data: Dict) -> List[Signal]:
        """Generate wheel strategy signals."""
        signals = []
        
        # Get current positions to determine phase
        positions = data.get("positions", [])
        stock_positions = {p["symbol"]: p for p in positions if p["asset_class"] == "stock"}
        
        for symbol in self.symbols:
            try:
                if symbol in stock_positions:
                    # Phase 2: Sell covered calls
                    signal = self._generate_covered_call_signal(symbol, stock_positions[symbol], data)
                else:
                    # Phase 1: Sell cash secured puts
                    signal = self._generate_csp_signal(symbol, data)
                
                if signal and self.validate_signal(signal):
                    signals.append(signal)
                    
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
        
        return signals
    
    def _generate_csp_signal(self, symbol: str, data: Dict) -> Signal:
        """Generate Cash Secured Put signal."""
        current_price = data.get("price", {}).get(symbol, 0)
        if current_price == 0:
            return None
        
        # Calculate strike (30 delta typically ~0.5 std dev down)
        strike = current_price * 0.97
        
        # Check if we have enough cash
        account_value = data.get("account", {}).get("portfolio_value", 0)
        cash_required = strike * 100  # 100 shares per contract
        
        if cash_required > account_value * self.max_allocation:
            logger.debug(f"Insufficient allocation for {symbol} CSP")
            return None
        
        # Estimate premium (rough approximation)
        days_to_expiration = self.csp_dte
        annual_volatility = 0.30  # 30% assumption
        daily_vol = annual_volatility / (365 ** 0.5)
        price_range = current_price * daily_vol * (days_to_expiration ** 0.5)
        premium_estimate = max(price_range * 0.5, current_price * 0.005)
        
        return Signal(
            symbol=symbol,
            direction="neutral",  # Profit if stock stays above strike
            confidence=0.75,  # High confidence - we're willing to own
            strategy="wheel_csp",
            legs=[{
                "type": "put",
                "side": "sell",
                "strike": strike,
                "expiration": f"{self.csp_dte}D",
                "delta": self.csp_delta
            }],
            metadata={
                "phase": "csp",
                "premium": premium_estimate,
                "cash_required": cash_required,
                "break_even": strike - premium_estimate,
                "assignment_price": strike,
                "annualized_return": (premium_estimate / cash_required) * (365 / days_to_expiration)
            }
        )
    
    def _generate_covered_call_signal(self, symbol: str, position: Dict, 
                                      data: Dict) -> Signal:
        """Generate Covered Call signal."""
        current_price = data.get("price", {}).get(symbol, 0)
        cost_basis = position.get("avg_entry_price", current_price)
        shares_owned = position.get("qty", 0)
        
        # Determine strike
        # Usually slightly OTM (0.30 delta) or above cost basis
        target_strike = max(cost_basis * 1.03, current_price * 1.02)
        
        # Calculate how many contracts we can sell
        max_contracts = shares_owned // 100
        if max_contracts < 1:
            return None
        
        # Estimate premium
        days_to_expiration = self.cc_dte
        strike_distance = (target_strike / current_price) - 1
        premium_estimate = current_price * strike_distance * 0.5
        
        return Signal(
            symbol=symbol,
            direction="neutral",  # Profit if stock stays below strike
            confidence=0.70,
            strategy="wheel_cc",
            legs=[{
                "type": "call",
                "side": "sell",
                "strike": target_strike,
                "expiration": f"{self.cc_dte}D",
                "delta": self.cc_delta,
                "contracts": max_contracts
            }],
            metadata={
                "phase": "covered_call",
                "premium": premium_estimate * max_contracts,
                "contracts": max_contracts,
                "cost_basis": cost_basis,
                "target_strike": target_strike,
                "upside_if_called": (target_strike - cost_basis) * max_contracts * 100,
                "annualized_return": ((premium_estimate * 365 / days_to_expiration) / 
                                     (cost_basis * 100))
            }
        )
    
    def calculate_position_size(self, account_value: float,
                                signal: Signal) -> int:
        """Calculate position size for wheel strategy."""
        if signal.strategy == "wheel_csp":
            # One CSP per allocation slot
            return 1
        else:
            # Covered calls limited by shares owned
            return signal.legs[0].get("contracts", 1)
