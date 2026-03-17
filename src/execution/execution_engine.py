"""Execution engine for processing trading signals."""
import logging
import signal
import time
from datetime import datetime
from typing import Dict, List, Optional

import yaml
from zoneinfo import ZoneInfo

from config import config
from src.broker.broker_factory import BrokerFactory
from src.risk.risk_manager import RiskManager
from src.risk.position_sizer import PositionSizer
from src.utils.logger import setup_logging
from src.utils.notifications import NotificationManager

logger = logging.getLogger(__name__)

# Optional modules — gracefully degrade if not available
try:
    from src.data.iv_analyzer import IVAnalyzer
except ImportError:
    IVAnalyzer = None

try:
    from src.data.greeks import GreeksMonitor
except ImportError:
    GreeksMonitor = None

try:
    from src.data.ml_signals import MLSignalEnhancer
except ImportError:
    MLSignalEnhancer = None

try:
    from src.dashboard.app import DashboardServer
except ImportError:
    DashboardServer = None

# Strategy registry — avoids repeated if/elif chains
# Includes aliases so agent specs ("the_wheel") and code ("wheel_strategy") both work
STRATEGY_REGISTRY = {
    "iron_condor": "src.strategies.iron_condor.IronCondorStrategy",
    "credit_spread": "src.strategies.credit_spread.CreditSpreadStrategy",
    "wheel_strategy": "src.strategies.wheel_strategy.WheelStrategy",
    "the_wheel": "src.strategies.wheel_strategy.WheelStrategy",  # alias used by agent specs
}


def _import_strategy_class(dotted_path: str):
    """Dynamically import a strategy class from a dotted module path."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class ExecutionEngine:
    """Main execution engine that coordinates trading."""

    def __init__(self, strategy_name: str, mode: str = "paper",
                 enable_dashboard: bool = False, dashboard_port: int = 8080):
        self.strategy_name = strategy_name
        self.mode = mode
        self.running = False
        self._last_daily_reset: Optional[str] = None

        # Load strategy config FIRST so it's available when initializing strategy
        with open("config/strategies.yaml", "r") as f:
            strategies_config = yaml.safe_load(f)
        self.strategy_config = strategies_config.get(strategy_name, {})

        # Initialize broker via factory
        self.broker = self._init_broker()

        # Core components
        self.risk_manager = RiskManager(broker=self.broker)
        self.position_sizer = PositionSizer()
        self.notifier = NotificationManager()
        self.strategy = self._init_strategy()

        # Optional analytics modules
        self.iv_analyzer = IVAnalyzer() if IVAnalyzer else None
        self.greeks_monitor = GreeksMonitor() if GreeksMonitor else None
        self.ml_enhancer = self._init_ml_enhancer()

        # Dashboard
        self.dashboard = None
        if enable_dashboard and DashboardServer:
            self.dashboard = DashboardServer(
                risk_manager=self.risk_manager,
                broker=self.broker,
                iv_analyzer=self.iv_analyzer,
                greeks_monitor=self.greeks_monitor,
                ml_enhancer=self.ml_enhancer,
                port=dashboard_port,
            )
            symbols = self.strategy_config.get("symbols", [])
            self.dashboard.set_symbols(symbols)

        # Market hours (configurable)
        self._tz = ZoneInfo(config.TIMEZONE)

    def _init_broker(self):
        """Initialize the appropriate broker client via the factory.

        For paper mode, prefer Alpaca paper trading when API keys are
        configured (real market simulation). Fall back to the local
        PaperTradingSimulator only if keys are missing.
        """
        if self.mode == "paper":
            # Try Alpaca paper trading first
            import os
            if os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY"):
                broker = BrokerFactory.create("alpaca")
                if broker.connect():
                    logger.info("Using Alpaca paper trading API")
                    return broker
                logger.warning("Alpaca paper connection failed — falling back to local simulator")
            else:
                logger.info("No Alpaca API keys found — using local paper simulator")
            broker_name = "paper"
        else:
            broker_name = self.mode

        broker = BrokerFactory.create(broker_name)
        if not broker.connect():
            raise RuntimeError(f"Failed to connect to broker: {broker_name}")
        return broker

    def _init_ml_enhancer(self):
        """Initialize ML signal enhancer if available, loading persisted model."""
        if MLSignalEnhancer is None:
            return None
        enhancer = MLSignalEnhancer()
        from pathlib import Path
        model_path = Path("models/signal_model.joblib")
        if model_path.exists():
            try:
                enhancer.load_model(str(model_path))
                logger.info("Loaded ML signal model from disk")
            except Exception as e:
                logger.warning(f"Could not load ML model: {e}")
        return enhancer

    def _init_strategy(self):
        """Initialize the selected strategy using the registry."""
        dotted_path = STRATEGY_REGISTRY.get(self.strategy_name)
        if dotted_path is None:
            raise ValueError(
                f"Unknown strategy: {self.strategy_name}. "
                f"Available: {list(STRATEGY_REGISTRY.keys())}"
            )
        strategy_cls = _import_strategy_class(dotted_path)
        return strategy_cls(self.strategy_config)

    # ------------------------------------------------------------------
    # Market hours helpers
    # ------------------------------------------------------------------
    def _is_market_hours(self) -> bool:
        """Check if current time is within configured market hours."""
        now = datetime.now(self._tz)
        open_h, open_m = map(int, config.MARKET_OPEN_TIME.split(":"))
        close_h, close_m = map(int, config.MARKET_CLOSE_TIME.split(":"))

        market_open = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
        market_close = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)

        # Also skip weekends
        if now.weekday() >= 5:
            return False

        return market_open <= now <= market_close

    def _maybe_reset_daily_pnl(self):
        """Reset daily P&L tracking at the start of each new trading day."""
        today = datetime.now(self._tz).strftime("%Y-%m-%d")
        if self._last_daily_reset != today:
            self.risk_manager.reset_daily_pnl()
            self._last_daily_reset = today
            logger.info(f"Daily P&L reset for {today}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self):
        """Main execution loop with graceful shutdown support."""
        logger.info(f"Starting execution engine: {self.strategy_name} ({self.mode} mode)")
        self.running = True

        # Start dashboard if configured
        if self.dashboard:
            self.dashboard.start(background=True)
            logger.info(f"Dashboard running at http://localhost:{self.dashboard._port}")

        # Register signal handlers for graceful shutdown
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, lambda *_: self.stop())
        signal.signal(signal.SIGTERM, lambda *_: self.stop())

        try:
            while self.running:
                self._maybe_reset_daily_pnl()

                if self._is_market_hours():
                    self._execute_cycle()
                else:
                    logger.debug("Outside market hours — sleeping")

                time.sleep(60)  # Run every minute
        except Exception as e:
            logger.exception("Fatal error in execution loop")
            self.notifier.send_alert(f"Execution Error: {e}")
            raise
        finally:
            # Restore original handlers
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)
            self._cleanup()

    def _execute_cycle(self):
        """Execute one trading cycle."""
        try:
            # Get market data
            data = self._get_market_data()

            # Get account info
            account = self.broker.get_account()

            # Generate signals
            signals = self.strategy.generate_signals(data)

            if signals:
                logger.info(f"Generated {len(signals)} signal(s)")

                for sig in signals:
                    self._process_signal(sig, account)

            # Check portfolio Greeks for adjustment recommendations
            self._check_greeks_adjustments()

        except Exception as e:
            logger.error(f"Error in execution cycle: {e}", exc_info=True)

    def _check_greeks_adjustments(self):
        """Check portfolio Greeks and log any adjustment recommendations."""
        if not self.greeks_monitor or not self.risk_manager.positions:
            return
        try:
            pg = self.greeks_monitor.get_portfolio_greeks(self.risk_manager.positions)
            recommendations = self.greeks_monitor.check_adjustments(pg, {})
            for rec in recommendations:
                level = logging.WARNING if rec.urgency == "high" else logging.INFO
                logger.log(
                    level,
                    f"Greeks adjustment [{rec.urgency}]: {rec.action} - {rec.reason}"
                )
                if rec.urgency == "high":
                    self.notifier.send_alert(
                        f"Greeks Alert [{rec.urgency}]: {rec.action} - {rec.reason}"
                    )
        except Exception as e:
            logger.debug(f"Greeks check failed: {e}")

    def _get_market_data(self) -> Dict:
        """Fetch current market data using yfinance for real prices."""
        symbols = self.strategy_config.get("symbols", ["SPY"])

        prices: Dict[str, float] = {}
        price_history: Dict[str, list] = {}

        try:
            import yfinance as yf

            tickers = yf.Tickers(" ".join(symbols))
            for symbol in symbols:
                ticker = tickers.tickers.get(symbol)
                if ticker is None:
                    continue
                hist = ticker.history(period="1mo")
                if hist.empty:
                    continue
                prices[symbol] = float(hist["Close"].iloc[-1])
                price_history[symbol] = hist["Close"].tolist()
        except Exception as e:
            logger.warning(f"yfinance fetch failed, using broker fallback: {e}")
            # Fallback: use broker positions for price info (limited)

        # Enrich with IV data if available
        iv_data: Dict[str, Dict] = {}
        if self.iv_analyzer:
            for symbol in symbols:
                try:
                    iv = self.iv_analyzer.get_iv_data(symbol)
                    iv_data[symbol] = {
                        "iv_rank": iv.iv_rank,
                        "iv_percentile": iv.iv_percentile,
                        "current_iv": iv.current_iv,
                        "hv_20": iv.hv_20,
                        "hv_50": iv.hv_50,
                        "regime": self.iv_analyzer.get_iv_regime(symbol),
                    }
                except Exception as e:
                    logger.debug(f"IV fetch failed for {symbol}: {e}")

        return {
            "price": prices,
            "price_history": price_history,
            "positions": self.broker.get_positions(),
            "account": self.broker.get_account(),
            "iv_data": iv_data,
        }

    def _process_signal(self, sig, account: Dict):
        """Process a single trading signal through IV filter, ML enhancement, risk checks, and execution."""

        # --- IV rank filter ---
        if self.iv_analyzer and self.risk_manager._global_constraints:
            iv_range = self.risk_manager._global_constraints.get("iv_rank_range")
            if not iv_range:
                # Try risk posture config directly
                from src.risk.risk_manager import _load_risk_posture
                posture = _load_risk_posture()
                if posture:
                    iv_range = posture.get("iv_rank_range")
            if iv_range:
                min_rank = iv_range.get("min", 0) / 100.0
                max_rank = iv_range.get("max", 100) / 100.0
                if not self.iv_analyzer.filter_by_iv(sig.symbol, min_rank, max_rank):
                    logger.info(
                        f"IV filter rejected {sig.symbol}: rank outside [{min_rank:.0%}, {max_rank:.0%}]"
                    )
                    return

        # --- ML confidence enhancement ---
        original_confidence = sig.confidence
        if self.ml_enhancer and self.ml_enhancer.is_trained():
            try:
                result = self.ml_enhancer.enhance_signal({
                    "confidence": sig.confidence,
                    "iv_rank": sig.metadata.get("iv_rank", 0.5),
                    "iv_percentile": sig.metadata.get("iv_percentile", 0.5),
                    "price_history": [],  # Would pass from market data
                    "dte": sig.metadata.get("dte", 30),
                    "spread_width": sig.metadata.get("spread_width", 5),
                    "underlying_price": sig.metadata.get("short_strike", 100),
                })
                sig.confidence = result.get("adjusted_confidence", sig.confidence)
                logger.info(
                    f"ML adjusted confidence for {sig.symbol}: "
                    f"{original_confidence:.2f} -> {sig.confidence:.2f}"
                )
            except Exception as e:
                logger.debug(f"ML enhancement failed, using original confidence: {e}")

        # --- Risk check ---
        if not self.risk_manager.can_open_position(
            {"symbol": sig.symbol, "confidence": sig.confidence, "metadata": sig.metadata},
            account,
        ):
            logger.warning(f"Risk check failed for {sig.symbol}")
            return

        # Calculate position size (reuse the engine-level sizer)
        size = self.position_sizer.calculate_options_position(
            account["portfolio_value"],
            {
                "metadata": sig.metadata,
                "confidence": sig.confidence,
                "max_concurrent": self.strategy_config.get("max_concurrent_positions", 3),
            },
        )

        if size <= 0:
            logger.warning(f"Position size is 0 for {sig.symbol}")
            return

        # Execute orders for each leg
        executed_legs = []
        for leg in sig.legs:
            try:
                order = self.broker.submit_order(
                    symbol=sig.symbol,
                    qty=size,
                    side=leg["side"],
                    order_type="limit" if leg.get("premium") else "market",
                    price=leg.get("premium", 0),
                )
                logger.info(f"Order executed: {order}")
                executed_legs.append(order)
            except Exception as e:
                logger.error(f"Failed to execute leg {leg}: {e}")

        if not executed_legs:
            logger.error(f"No legs executed for {sig.symbol} — skipping position tracking")
            return

        # Notify
        self.notifier.send_notification(
            f"New Position: {sig.strategy} on {sig.symbol} ({len(executed_legs)}/{len(sig.legs)} legs)"
        )

        # Track position
        self.risk_manager.add_position({
            "symbol": sig.symbol,
            "strategy": sig.strategy,
            "size": size,
            "max_loss": sig.metadata.get("max_loss", 0),
            "max_profit": sig.metadata.get("max_profit", 0),
            "market_value": 0,
            "opened_at": datetime.now(self._tz).isoformat(),
        })

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def stop(self):
        """Stop the execution engine gracefully."""
        self.running = False
        logger.info("Execution engine stop requested")

    def _cleanup(self):
        """Clean up resources on shutdown."""
        if self.dashboard:
            try:
                self.dashboard.stop()
            except Exception:
                pass
        try:
            self.broker.disconnect()
        except Exception as e:
            logger.warning(f"Error during broker disconnect: {e}")
        logger.info("Execution engine shut down cleanly")
