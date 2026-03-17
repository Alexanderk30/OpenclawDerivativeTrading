"""Tests for risk management."""
import unittest
from unittest.mock import Mock


class TestRiskManager(unittest.TestCase):
    """Test RiskManager functionality."""
    
    def setUp(self):
        from src.risk.risk_manager import RiskManager
        self.risk_manager = RiskManager()
    
    def test_portfolio_heat_calculation(self):
        """Test portfolio heat calculation."""
        self.risk_manager.positions = [
            {"symbol": "SPY", "max_loss": 500, "market_value": 2000},
            {"symbol": "QQQ", "max_loss": 400, "market_value": 1500}
        ]
        
        heat = self.risk_manager.calculate_portfolio_heat(
            {"portfolio_value": 100000}
        )
        
        # Total max loss should be $900
        self.assertEqual(heat, 900)
    
    def test_daily_loss_limit(self):
        """Test daily loss limit enforcement."""
        account = {"portfolio_value": 100000}
        
        # Set daily P&L beyond limit (5%)
        self.risk_manager.daily_pnl = -6000
        
        can_trade = self.risk_manager.can_open_position(
            {"symbol": "SPY", "metadata": {"max_loss": 100}},
            account
        )
        
        self.assertFalse(can_trade)
    
    def test_position_count_limit(self):
        """Test position count limit."""
        account = {"portfolio_value": 100000}
        
        # Add max positions for a symbol
        self.risk_manager.positions = [
            {"symbol": "SPY"}, {"symbol": "SPY"}, {"symbol": "SPY"}
        ]
        
        can_trade = self.risk_manager.can_open_position(
            {"symbol": "SPY", "metadata": {"max_loss": 100}},
            account
        )
        
        self.assertFalse(can_trade)


class TestPositionSizer(unittest.TestCase):
    """Test PositionSizer functionality."""
    
    def setUp(self):
        from src.risk.position_sizer import PositionSizer
        self.sizer = PositionSizer()
    
    def test_risk_based_sizing(self):
        """Test risk-based position sizing."""
        account_value = 100000
        max_loss_per_unit = 500
        confidence = 0.7
        
        size = self.sizer.size_by_risk(
            account_value, max_loss_per_unit, confidence
        )
        
        # 2% risk = $2000, adjusted for confidence = $1400
        # $1400 / $500 = 2.8 → 2 units
        self.assertGreater(size, 0)
        self.assertLessEqual(size, 5)
    
    def test_kelly_criterion(self):
        """Test Kelly Criterion calculation."""
        win_rate = 0.6
        avg_win = 200
        avg_loss = 100
        
        kelly = self.sizer.kelly_criterion(win_rate, avg_win, avg_loss)
        
        # Kelly = (0.6 * 2 - 0.4) / 2 = 0.4 (40%)
        # Half-Kelly = 20%
        self.assertAlmostEqual(kelly, 0.2, places=2)


if __name__ == "__main__":
    unittest.main()
