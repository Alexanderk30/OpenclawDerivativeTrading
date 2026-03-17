"""Execution engine for processing trading signals."""
import logging
import signal
import time
from datetime import datetime
from typing import Dict, List, Optional

import yaml
from zoneinfo import ZoneInfo

from config import config
from src.broker.alpaca_client import AlpacaClient
from src.broker.paper_trading import PaperTradingSimulator
from src.risk.risk_manager import RiskManager
from src.risk.position_sizer import PositionSizer
from src.utils.logger import setup_logging
from src.utils.notifications import NotificationManager

logger = logging.getLogger(__name__)

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

    def __init__(self, strategy_name: str, mode: str = "paper"):
        self.strategy_name = strategy_name
        self.mode = mode
        self.running = False
        self._last_daily_reset: Optional[str] = None

        # Load strategy config FIRST so it's available when initializing strategy
        with open("config/strategies.yaml", "r") as f:
            strategies_config = yaml.safe_load(f)
        self.strategy_config = strategies_config.get(strategy_name, {})

        # Initialize components
        self.broker = self._init_broker()
        self.risk_manager = RiskManager(broker=self.broker)
        self.position_sizer = PositionSizer()  # Reused across signals
        self.notifier = NotificationManager()
        self.strategy = self._init_strategy()

        # Market hours (configurable)
        self._tz = ZoneInfo(config.TIMEZONE)

    def _init_broker(self):
        """Initialize the appropriate broker client."""
        if self.mode == "paper":
            broker = PaperTradingSimulator()
            broker.connect()
            return broker
        else:
            broker = AlpacaClient()
            if not broker.connect():
                raise RuntimeError("Failed to connect to Alpaca")
            return broker

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

        except Exception as e:
            logger.error(f"Error in execution cycle: {e}", exc_info=True)

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

        return {
            "price": prices,
            "price_history": price_history,
            "positions": self.broker.get_positions(),
            "account": self.broker.get_account(),
        }

    def _process_signal(self, sig, account: Dict):
        """Process a single trading signal through risk checks and execution."""
        # Check risk limits
        if not self.risk_manager.can_open_position(
            {"symbol": sig.symbol, "metadata": sig.metadata},
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
        try:
            self.broker.disconnect()
        except Exception as e:
            logger.warning(f"Error during broker disconnect: {e}")
        logger.info("Execution engine shut down cleanly")
