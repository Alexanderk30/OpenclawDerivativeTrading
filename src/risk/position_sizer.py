"""Position sizing calculations."""
import logging
from typing import Dict

from config import config

logger = logging.getLogger(__name__)


class PositionSizer:
    """Calculate appropriate position sizes based on risk parameters."""
    
    def __init__(self):
        self.max_risk_per_trade = config.MAX_PORTFOLIO_RISK
        self.max_position_pct = config.MAX_POSITION_SIZE
    
    def size_by_risk(self, account_value: float, max_loss_per_unit: float,
                     confidence: float = 0.5) -> int:
        """
        Size position based on maximum risk per trade.
        
        Args:
            account_value: Total account value
            max_loss_per_unit: Maximum loss per contract/spread
            confidence: Signal confidence (0-1)
            
        Returns:
            Number of units to trade
        """
        # Base risk amount
        max_risk_amount = account_value * self.max_risk_per_trade
        
        # Adjust for confidence
        adjusted_risk = max_risk_amount * confidence
        
        # Calculate units
        if max_loss_per_unit <= 0:
            return 0
        
        units = int(adjusted_risk / max_loss_per_unit)
        
        logger.info(f"Risk-based sizing: ${adjusted_risk:.2f} risk / "
                   f"${max_loss_per_unit:.2f} per unit = {units} units")
        
        return max(1, units)  # At least 1 if we pass validation
    
    def size_by_portfolio_pct(self, account_value: float, 
                              notional_per_unit: float) -> int:
        """
        Size position based on maximum portfolio allocation.
        
        Args:
            account_value: Total account value
            notional_per_unit: Notional value per contract
            
        Returns:
            Number of units to trade
        """
        max_notional = account_value * self.max_position_pct
        
        if notional_per_unit <= 0:
            return 0
        
        units = int(max_notional / notional_per_unit)
        
        logger.info(f"Allocation-based sizing: ${max_notional:.2f} max / "
                   f"${notional_per_unit:.2f} per unit = {units} units")
        
        return units
    
    def calculate_options_position(self, account_value: float, 
                                   signal: Dict) -> int:
        """
        Calculate options position size considering multiple factors.
        
        Args:
            account_value: Total account value
            signal: Trading signal with metadata
            
        Returns:
            Number of contracts/spreads
        """
        metadata = signal.get("metadata", {})
        
        # Method 1: Risk-based sizing (preferred for defined risk)
        if "max_loss" in metadata:
            risk_based = self.size_by_risk(
                account_value,
                metadata["max_loss"],
                signal.get("confidence", 0.5)
            )
        else:
            risk_based = float('inf')
        
        # Method 2: Allocation-based sizing
        if "notional" in metadata:
            allocation_based = self.size_by_portfolio_pct(
                account_value,
                metadata["notional"]
            )
        else:
            # Estimate notional from strike price
            strike = metadata.get("strike", 100)
            allocation_based = self.size_by_portfolio_pct(
                account_value,
                strike * 100  # 100 shares per contract
            )
        
        # Take the more conservative of the two
        position_size = min(risk_based, allocation_based)
        
        # Additional constraints
        max_positions = signal.get("max_concurrent", 10)
        position_size = min(position_size, max_positions)
        
        logger.info(f"Final position size: {position_size} (risk: {risk_based}, "
                   f"allocation: {allocation_based})")
        
        return max(0, position_size)
    
    def kelly_criterion(self, win_rate: float, avg_win: float, 
                        avg_loss: float) -> float:
        """
        Calculate Kelly Criterion optimal position size.
        
        f* = (p*b - q) / b
        where:
        p = probability of win
        q = probability of loss (1-p)
        b = avg win / avg loss (odds)
        
        Returns:
            Optimal fraction of portfolio to allocate (0-1)
        """
        if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
            return 0
        
        b = avg_win / avg_loss
        q = 1 - win_rate
        
        kelly = (win_rate * b - q) / b
        
        # Use half-Kelly for safety
        half_kelly = kelly / 2
        
        logger.info(f"Kelly criterion: {kelly:.2%} (using half: {half_kelly:.2%})")
        
        return max(0, half_kelly)
