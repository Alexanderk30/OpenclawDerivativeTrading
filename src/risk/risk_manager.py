"""Risk management module."""
import logging
from typing import Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)


class RiskManager:
    """Manages portfolio-level risk."""
    
    def __init__(self):
        self.max_portfolio_risk = config.MAX_PORTFOLIO_RISK
        self.max_position_size = config.MAX_POSITION_SIZE
        self.max_daily_loss = config.MAX_DAILY_LOSS
        self.daily_pnl = 0.0
        self.positions = []
    
    def can_open_position(self, signal: Dict, account: Dict) -> bool:
        """
        Check if a new position can be opened.
        
        Args:
            signal: Trading signal with position details
            account: Account information
            
        Returns:
            True if position can be opened
        """
        # Check daily loss limit
        if self.daily_pnl < -account["portfolio_value"] * self.max_daily_loss:
            logger.warning("Daily loss limit reached. No new positions.")
            return False
        
        # Check position count
        symbol = signal.get("symbol")
        existing_positions = [p for p in self.positions if p["symbol"] == symbol]
        if len(existing_positions) >= 3:
            logger.warning(f"Max positions reached for {symbol}")
            return False
        
        # Check total portfolio heat
        total_risk = self.calculate_portfolio_heat(account)
        new_position_risk = signal.get("metadata", {}).get("max_loss", 0)
        
        if total_risk + new_position_risk > account["portfolio_value"] * self.max_portfolio_risk * 5:
            logger.warning("Portfolio heat limit would be exceeded")
            return False
        
        return True
    
    def calculate_portfolio_heat(self, account: Dict) -> float:
        """Calculate total risk exposure across all positions."""
        total_risk = 0.0
        
        for position in self.positions:
            # Calculate risk for each position
            unrealized_pl = position.get("unrealized_pl", 0)
            market_value = position.get("market_value", 0)
            
            # For defined risk strategies, use max loss
            if "max_loss" in position:
                total_risk += position["max_loss"]
            else:
                # For undefined risk, estimate based on position value
                total_risk += market_value * 0.10  # Assume 10% risk
        
        return total_risk
    
    def check_position_limits(self, signal: Dict, account: Dict) -> bool:
        """Check if position size is within limits."""
        position_value = signal.get("metadata", {}).get("max_loss", 0)
        max_allowed = account["portfolio_value"] * self.max_position_size
        
        if position_value > max_allowed:
            logger.warning(f"Position size {position_value} exceeds limit {max_allowed}")
            return False
        
        return True
    
    def update_daily_pnl(self, pnl: float):
        """Update daily P&L tracking."""
        self.daily_pnl += pnl
        logger.info(f"Daily P&L updated: ${self.daily_pnl:.2f}")
        
        if self.daily_pnl < 0:
            loss_pct = abs(self.daily_pnl) / self.get_account_value()
            if loss_pct > self.max_daily_loss:
                logger.warning(f"⚠️ Daily loss at {loss_pct:.1%}. Consider stopping.")
    
    def add_position(self, position: Dict):
        """Track a new position."""
        self.positions.append(position)
        logger.info(f"Position added: {position['symbol']}")
    
    def remove_position(self, symbol: str):
        """Remove a closed position."""
        self.positions = [p for p in self.positions if p["symbol"] != symbol]
        logger.info(f"Position removed: {symbol}")
    
    def get_account_value(self) -> float:
        """Get current account value estimate."""
        # This would come from broker in practice
        return 100000.0  # Placeholder
    
    def get_risk_report(self) -> Dict:
        """Generate risk report."""
        return {
            "daily_pnl": self.daily_pnl,
            "open_positions": len(self.positions),
            "portfolio_heat": self.calculate_portfolio_heat({"portfolio_value": self.get_account_value()}),
            "risk_limits": {
                "max_portfolio_risk": self.max_portfolio_risk,
                "max_position_size": self.max_position_size,
                "max_daily_loss": self.max_daily_loss
            }
        }
    
    def emergency_stop(self):
        """Emergency stop - close all positions."""
        logger.error("🚨 EMERGENCY STOP ACTIVATED 🚨")
        logger.error("Closing all positions immediately!")
        # Implementation would close all positions via broker
        return True
