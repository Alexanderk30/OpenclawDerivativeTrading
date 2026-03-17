"""Tests for IV rank and percentile analyzer."""
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime


class TestIVAnalyzer(unittest.TestCase):
    """Test IVAnalyzer functionality."""

    def setUp(self):
        from src.data.iv_analyzer import IVAnalyzer
        self.analyzer = IVAnalyzer(cache_ttl_hours=0)  # Disable caching for tests

    @patch("src.data.iv_analyzer.yf")
    def test_get_iv_data_returns_valid_structure(self, mock_yf):
        """Test that get_iv_data returns a properly structured IVData object."""
        # Create mock price history (252 trading days)
        dates = pd.date_range(end=datetime.now(), periods=300, freq="B")
        prices = pd.Series(
            np.cumsum(np.random.randn(300) * 0.01 + 0.0005) + 5.0,
            index=dates,
        )
        prices = np.exp(prices)  # Make prices positive

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame({"Close": prices})
        mock_yf.Ticker.return_value = mock_ticker

        data = self.analyzer.get_iv_data("SPY", lookback_days=252)

        self.assertEqual(data.symbol, "SPY")
        self.assertIsInstance(data.iv_rank, float)
        self.assertIsInstance(data.iv_percentile, float)
        self.assertGreaterEqual(data.iv_rank, 0.0)
        self.assertLessEqual(data.iv_rank, 1.0)
        self.assertGreaterEqual(data.iv_percentile, 0.0)
        self.assertLessEqual(data.iv_percentile, 1.0)
        self.assertGreater(data.hv_20, 0.0)
        self.assertGreater(data.hv_50, 0.0)

    @patch("src.data.iv_analyzer.yf")
    def test_filter_by_iv(self, mock_yf):
        """Test IV rank filtering."""
        dates = pd.date_range(end=datetime.now(), periods=300, freq="B")
        prices = pd.Series(
            np.cumsum(np.random.randn(300) * 0.01) + 5.0,
            index=dates,
        )
        prices = np.exp(prices)

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame({"Close": prices})
        mock_yf.Ticker.return_value = mock_ticker

        # With wide range, should pass
        result = self.analyzer.filter_by_iv("SPY", min_rank=0.0, max_rank=1.0)
        self.assertTrue(result)

    @patch("src.data.iv_analyzer.yf")
    def test_get_iv_regime(self, mock_yf):
        """Test IV regime classification returns valid category."""
        dates = pd.date_range(end=datetime.now(), periods=300, freq="B")
        prices = pd.Series(
            np.cumsum(np.random.randn(300) * 0.01) + 5.0,
            index=dates,
        )
        prices = np.exp(prices)

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame({"Close": prices})
        mock_yf.Ticker.return_value = mock_ticker

        regime = self.analyzer.get_iv_regime("SPY")
        self.assertIn(regime, ["low", "moderate", "high", "extreme"])

    def test_insufficient_data_raises(self):
        """Test that insufficient data raises ValueError."""
        with patch("src.data.iv_analyzer.yf") as mock_yf:
            mock_ticker = MagicMock()
            mock_ticker.history.return_value = pd.DataFrame({"Close": []})
            mock_yf.Ticker.return_value = mock_ticker

            with self.assertRaises(ValueError):
                self.analyzer.get_iv_data("INVALID")


class TestGreeksMonitor(unittest.TestCase):
    """Test GreeksMonitor functionality."""

    def setUp(self):
        from src.data.greeks import GreeksMonitor
        self.monitor = GreeksMonitor()

    def test_call_greeks(self):
        """Test Black-Scholes call option Greeks."""
        result = self.monitor.calculate_greeks(
            underlying_price=100.0,
            strike=100.0,
            dte_days=30,
            iv=0.20,
            option_type="call",
        )
        # ATM call delta should be near 0.5
        self.assertGreater(result.delta, 0.4)
        self.assertLess(result.delta, 0.7)
        # Gamma should be positive
        self.assertGreater(result.gamma, 0)
        # Theta should be negative (time decay)
        self.assertLess(result.theta, 0)
        # Vega should be positive
        self.assertGreater(result.vega, 0)

    def test_put_greeks(self):
        """Test Black-Scholes put option Greeks."""
        result = self.monitor.calculate_greeks(
            underlying_price=100.0,
            strike=100.0,
            dte_days=30,
            iv=0.20,
            option_type="put",
        )
        # ATM put delta should be near -0.5
        self.assertLess(result.delta, -0.3)
        self.assertGreater(result.delta, -0.7)

    def test_portfolio_greeks_aggregation(self):
        """Test that portfolio greeks are correctly aggregated."""
        positions = [
            {
                "symbol": "SPY",
                "underlying_price": 450.0,
                "strike": 440.0,
                "dte_days": 30,
                "iv": 0.18,
                "option_type": "put",
                "side": "sell",
                "qty": 2,
            },
            {
                "symbol": "SPY",
                "underlying_price": 450.0,
                "strike": 460.0,
                "dte_days": 30,
                "iv": 0.18,
                "option_type": "call",
                "side": "sell",
                "qty": 2,
            },
        ]
        pg = self.monitor.get_portfolio_greeks(positions)
        # Iron condor-like: selling both sides, net delta should be near 0
        self.assertIsNotNone(pg.net_delta)
        self.assertIsNotNone(pg.net_theta)

    def test_adjustment_recommendations(self):
        """Test that adjustment checks produce valid recommendations."""
        from src.data.greeks import PortfolioGreeks
        pg = PortfolioGreeks(
            net_delta=150.0,  # Very high delta
            net_gamma=5.0,
            net_theta=-50.0,
            net_vega=20.0,
            net_rho=0.5,
            positions=[],
        )
        recs = self.monitor.check_adjustments(pg, {"max_portfolio_delta": 50})
        self.assertTrue(len(recs) > 0)
        self.assertEqual(recs[0].action, "hedge")

    def test_zero_dte_handling(self):
        """Test that expired options are handled gracefully."""
        result = self.monitor.calculate_greeks(
            underlying_price=100.0,
            strike=100.0,
            dte_days=0,
            iv=0.20,
            option_type="call",
        )
        self.assertIsNotNone(result)


class TestMLSignalEnhancer(unittest.TestCase):
    """Test MLSignalEnhancer functionality."""

    def setUp(self):
        from src.data.ml_signals import MLSignalEnhancer
        self.enhancer = MLSignalEnhancer()

    def test_untrained_returns_original_confidence(self):
        """Test graceful degradation when model is not trained."""
        result = self.enhancer.enhance_signal({
            "confidence": 0.72,
            "iv_rank": 0.5,
            "iv_percentile": 0.5,
            "dte": 30,
            "spread_width": 5,
            "underlying_price": 450,
        })
        self.assertEqual(result["adjusted_confidence"], 0.72)

    def test_train_and_predict(self):
        """Test training and prediction cycle."""
        # Generate synthetic training data matching _extract_features requirements:
        # Required fields: iv_rank, iv_percentile, price_history, hv20, hv50,
        #   days_to_expiration, spread_width, underlying_price, timestamp
        import random
        random.seed(42)
        historical = []
        for i in range(50):
            conf = random.uniform(0.5, 0.9)
            outcome = 1 if (conf > 0.65 and random.random() > 0.3) else 0
            # Generate a plausible price history
            base_price = random.uniform(100, 500)
            price_history = [base_price + random.gauss(0, 2) for _ in range(60)]
            historical.append({
                "data": {
                    "confidence": conf,
                    "iv_rank": random.uniform(10, 80),       # 0-100 scale
                    "iv_percentile": random.uniform(10, 80),  # 0-100 scale
                    "price_history": price_history,
                    "hv20": random.uniform(0.10, 0.40),
                    "hv50": random.uniform(0.10, 0.40),
                    "days_to_expiration": random.randint(15, 45),
                    "spread_width": random.choice([2.5, 5.0, 10.0]),
                    "underlying_price": base_price,
                    "timestamp": datetime.now().isoformat(),
                },
                "outcome": outcome,
            })

        self.enhancer.train(historical)
        self.assertTrue(self.enhancer.is_trained())

        result = self.enhancer.enhance_signal({
            "confidence": 0.70,
            "iv_rank": 45,
            "iv_percentile": 50,
            "price_history": [450 + random.gauss(0, 2) for _ in range(60)],
            "hv20": 0.20,
            "hv50": 0.18,
            "days_to_expiration": 30,
            "spread_width": 5,
            "underlying_price": 450,
            "timestamp": datetime.now().isoformat(),
        })
        self.assertIn("adjusted_confidence", result)
        self.assertGreaterEqual(result["adjusted_confidence"], 0)
        self.assertLessEqual(result["adjusted_confidence"], 1)

    def test_feature_importance(self):
        """Test feature importance retrieval."""
        # Not trained yet
        importance = self.enhancer.get_feature_importance()
        self.assertEqual(importance, {})


class TestBrokerFactory(unittest.TestCase):
    """Test BrokerFactory functionality."""

    def test_available_brokers(self):
        from src.broker.broker_factory import BrokerFactory
        brokers = BrokerFactory.get_available_brokers()
        self.assertIn("paper", brokers)
        self.assertIn("alpaca", brokers)
        self.assertIn("ibkr", brokers)

    def test_create_paper_broker(self):
        from src.broker.broker_factory import BrokerFactory
        broker = BrokerFactory.create("paper")
        self.assertIsNotNone(broker)
        broker.connect()
        account = broker.get_account()
        self.assertIn("portfolio_value", account)

    def test_validate_paper_config(self):
        from src.broker.broker_factory import BrokerFactory
        errors = BrokerFactory.validate_broker_config("paper")
        self.assertEqual(errors, [])

    def test_unknown_broker_raises(self):
        from src.broker.broker_factory import BrokerFactory
        with self.assertRaises(ValueError):
            BrokerFactory.create("nonexistent_broker")


class TestDashboardServer(unittest.TestCase):
    """Test DashboardServer initialization and API."""

    def test_dashboard_creates_flask_app(self):
        from src.dashboard.app import DashboardServer
        dashboard = DashboardServer()
        self.assertIsNotNone(dashboard._app)

    def test_api_status_returns_json(self):
        from src.dashboard.app import DashboardServer
        dashboard = DashboardServer()
        with dashboard._app.test_client() as client:
            resp = client.get("/api/status")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertIsInstance(data, dict)

    def test_dashboard_with_risk_manager(self):
        from src.dashboard.app import DashboardServer
        from src.risk.risk_manager import RiskManager
        from src.broker.paper_trading import PaperTradingSimulator

        broker = PaperTradingSimulator()
        broker.connect()
        rm = RiskManager(broker=broker)
        rm.add_position({"symbol": "SPY", "strategy": "iron_condor", "max_loss": 500})

        dashboard = DashboardServer(risk_manager=rm, broker=broker)
        with dashboard._app.test_client() as client:
            resp = client.get("/api/status")
            data = resp.get_json()
            self.assertEqual(len(data["positions"]), 1)
            self.assertEqual(data["positions"][0]["symbol"], "SPY")


if __name__ == "__main__":
    unittest.main()
