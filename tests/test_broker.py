"""Tests for broker connectivity."""
import unittest
from unittest.mock import Mock, patch


class TestAlpacaClient(unittest.TestCase):
    """Test Alpaca API client."""
    
    @patch("src.broker.alpaca_client.TradingClient")
    def test_connection(self, mock_client):
        """Test broker connection."""
        from src.broker.alpaca_client import AlpacaClient
        
        # Mock successful connection
        mock_account = Mock()
        mock_account.status = "ACTIVE"
        mock_client.return_value.get_account.return_value = mock_account
        
        client = AlpacaClient()
        result = client.connect()
        
        self.assertTrue(result)
    
    @patch("src.broker.alpaca_client.TradingClient")
    def test_get_account(self, mock_client):
        """Test getting account info."""
        from src.broker.alpaca_client import AlpacaClient
        
        mock_account = Mock()
        mock_account.id = "test_id"
        mock_account.cash = "50000.00"
        mock_account.portfolio_value = "100000.00"
        mock_account.buying_power = "100000.00"
        mock_account.equity = "100000.00"
        mock_account.status = "ACTIVE"
        
        mock_client.return_value.get_account.return_value = mock_account
        
        client = AlpacaClient()
        client._connected = True
        client.api = mock_client.return_value
        
        account = client.get_account()
        
        self.assertEqual(account["cash"], 50000.0)
        self.assertEqual(account["status"], "ACTIVE")


class TestPaperTrading(unittest.TestCase):
    """Test paper trading simulator."""
    
    def test_paper_trading_balance(self):
        """Test paper trading balance tracking."""
        from src.broker.paper_trading import PaperTradingSimulator
        
        simulator = PaperTradingSimulator(initial_balance=50000)
        simulator.connect()
        
        account = simulator.get_account()
        
        self.assertEqual(account["cash"], 50000)
        self.assertEqual(account["status"], "ACTIVE")
    
    def test_paper_order_execution(self):
        """Test paper order execution."""
        from src.broker.paper_trading import PaperTradingSimulator
        
        simulator = PaperTradingSimulator(initial_balance=100000)
        simulator.connect()
        
        order = simulator.submit_order("SPY", 10, "buy", price=450.0)
        
        self.assertEqual(order["status"], "filled")
        self.assertEqual(order["side"], "buy")
        
        # Check balance was reduced
        account = simulator.get_account()
        self.assertEqual(account["cash"], 100000 - (10 * 450.0))


if __name__ == "__main__":
    unittest.main()
