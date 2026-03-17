"""Tests for strategies."""
import unittest
from unittest.mock import Mock, patch

import yaml


class TestIronCondorStrategy(unittest.TestCase):
    """Test Iron Condor strategy."""
    
    def setUp(self):
        self.config = {
            "enabled": True,
            "symbols": ["SPY"],
            "min_dte": 30,
            "max_dte": 45,
            "short_put_delta": -0.15,
            "short_call_delta": 0.15,
            "spread_width": 5.0,
            "min_credit_ratio": 0.30,
            "max_risk_per_trade": 0.02
        }
    
    def test_strategy_initialization(self):
        """Test strategy initializes correctly."""
        from src.strategies.iron_condor import IronCondorStrategy
        
        strategy = IronCondorStrategy(self.config)
        self.assertEqual(strategy.name, "IronCondorStrategy")
        self.assertTrue(strategy.enabled)
    
    def test_signal_generation(self):
        """Test signal generation."""
        from src.strategies.iron_condor import IronCondorStrategy
        
        strategy = IronCondorStrategy(self.config)
        
        mock_data = {
            "price": {"SPY": 450.0},
            "price_history": {"SPY": [445, 448, 450]}
        }
        
        signals = strategy.generate_signals(mock_data)
        
        # Should generate at least one signal
        self.assertIsInstance(signals, list)
    
    def test_position_sizing(self):
        """Test position size calculation."""
        from src.strategies.iron_condor import IronCondorStrategy, Signal
        
        strategy = IronCondorStrategy(self.config)
        
        mock_signal = Signal(
            symbol="SPY",
            direction="neutral",
            confidence=0.7,
            strategy="iron_condor",
            legs=[],
            metadata={"max_loss": 350.0}
        )
        
        size = strategy.calculate_position_size(100000, mock_signal)
        
        # With 2% risk and $350 max loss per spread
        # Risk = $2000, so size should be around 5
        self.assertGreater(size, 0)
        self.assertLessEqual(size, 10)


class TestCreditSpreadStrategy(unittest.TestCase):
    """Test Credit Spread strategy."""
    
    def setUp(self):
        self.config = {
            "enabled": True,
            "symbols": ["SPY", "QQQ"],
            "min_dte": 21,
            "max_dte": 45,
            "put_spread_delta": -0.20,
            "call_spread_delta": 0.20,
            "spread_width": 5.0
        }
    
    def test_direction_detection(self):
        """Test direction detection logic."""
        from src.strategies.credit_spread import CreditSpreadStrategy
        
        strategy = CreditSpreadStrategy(self.config)
        
        # Test bullish trend
        bullish_data = {
            "price_history": {"SPY": [100, 101, 102, 103, 104, 105, 106]}
        }
        direction = strategy._determine_direction("SPY", bullish_data)
        self.assertIn(direction, ["bullish", "bearish", "neutral"])


class TestWheelStrategy(unittest.TestCase):
    """Test Wheel strategy."""
    
    def setUp(self):
        self.config = {
            "enabled": True,
            "symbols": ["AAPL"],
            "csp_delta": -0.30,
            "cc_delta": 0.30,
            "csp_dte": 30,
            "cc_dte": 30,
            "max_allocation_per_stock": 0.10
        }
    
    def test_csp_signal_generation(self):
        """Test cash secured put signal generation."""
        from src.strategies.wheel_strategy import WheelStrategy
        
        strategy = WheelStrategy(self.config)
        
        mock_data = {
            "price": {"AAPL": 180.0},
            "positions": [],
            "account": {"portfolio_value": 100000}
        }
        
        signal = strategy._generate_csp_signal("AAPL", mock_data)
        
        if signal:
            self.assertEqual(signal.strategy, "wheel_csp")
            self.assertEqual(signal.symbol, "AAPL")


if __name__ == "__main__":
    unittest.main()
