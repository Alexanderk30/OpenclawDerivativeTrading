"""Execution engine for processing trading signals."""
import logging
import time
from typing import Dict, List

from config import config
from src.broker.alpaca_client import AlpacaClient
from src.broker.paper_trading import PaperTradingSimulator
from src.risk.risk_manager import RiskManager
from src.utils.logger import setup_logging
from src.utils.notifications import NotificationManager

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Main execution engine that coordinates trading."""
    
    def __init__(self, strategy_name: str, mode: str = "paper"):
        self.strategy_name = strategy_name
        self.mode = mode
        self.running = False
        
        # Initialize components
        self.broker = self._init_broker()
        self.risk_manager = RiskManager()
        self.notifier = NotificationManager()
        self.strategy = self._init_strategy()
        
        # Load strategy config
        import yaml
        with open("config/strategies.yaml", "r") as f:
            strategies_config = yaml.safe_load(f)
        self.strategy_config = strategies_config.get(strategy_name, {})
    
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
        """Initialize the selected strategy."""
        if self.strategy_name == "iron_condor":
            from src.strategies.iron_condor import IronCondorStrategy
            return IronCondorStrategy(self.strategy_config)
        elif self.strategy_name == "credit_spread":
            from src.strategies.credit_spread import CreditSpreadStrategy
            return CreditSpreadStrategy(self.strategy_config)
        elif self.strategy_name == "wheel_strategy":
            from src.strategies.wheel_strategy import WheelStrategy
            return WheelStrategy(self.strategy_config)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy_name}")
    
    def run(self):
        """Main execution loop."""
        logger.info(f"Starting execution engine: {self.strategy_name} ({self.mode} mode)")
        self.running = True
        
        try:
            while self.running:
                self._execute_cycle()
                time.sleep(60)  # Run every minute
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.stop()
        except Exception as e:
            logger.exception("Fatal error in execution loop")
            self.notifier.send_alert(f"🚨 Execution Error: {e}")
            raise
    
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
                logger.info(f"Generated {len(signals)} signals")
                
                for signal in signals:
                    self._process_signal(signal, account)
            
        except Exception as e:
            logger.error(f"Error in execution cycle: {e}")
    
    def _get_market_data(self) -> Dict:
        """Fetch current market data."""
        # Simplified - would fetch real data
        return {
            "price": {"SPY": 450.0, "QQQ": 380.0, "IWM": 200.0},
            "price_history": {"SPY": [445, 448, 450, 449, 450]},
            "positions": self.broker.get_positions(),
            "account": self.broker.get_account()
        }
    
    def _process_signal(self, signal, account: Dict):
        """Process a single trading signal."""
        # Check risk limits
        if not self.risk_manager.can_open_position(
            {"symbol": signal.symbol, "metadata": signal.metadata},
            account
        ):
            logger.warning(f"Risk check failed for {signal.symbol}")
            return
        
        # Calculate position size
        from src.risk.position_sizer import PositionSizer
        sizer = PositionSizer()
        size = sizer.calculate_options_position(
            account["portfolio_value"],
            {
                "metadata": signal.metadata,
                "confidence": signal.confidence,
                "max_concurrent": self.strategy_config.get("max_concurrent_positions", 3)
            }
        )
        
        if size <= 0:
            logger.warning(f"Position size is 0 for {signal.symbol}")
            return
        
        # Execute orders for each leg
        for leg in signal.legs:
            try:
                order = self.broker.submit_order(
                    symbol=signal.symbol,  # Would use option symbol
                    qty=size,
                    side=leg["side"],
                    price=leg.get("premium", 0)
                )
                logger.info(f"Order executed: {order}")
            except Exception as e:
                logger.error(f"Failed to execute order: {e}")
        
        # Notify
        self.notifier.send_notification(
            f"📊 New Position: {signal.strategy} on {signal.symbol}"
        )
        
        # Track position
        self.risk_manager.add_position({
            "symbol": signal.symbol,
            "strategy": signal.strategy,
            "max_loss": signal.metadata.get("max_loss", 0),
            "market_value": 0  # Would calculate actual
        })
    
    def stop(self):
        """Stop the execution engine."""
        self.running = False
        logger.info("Execution engine stopped")
