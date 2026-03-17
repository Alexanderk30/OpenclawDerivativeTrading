#!/usr/bin/env python3
"""Launch the trading dashboard as a standalone process."""
import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
from src.utils.logger import setup_logging
from src.broker.broker_factory import BrokerFactory
from src.risk.risk_manager import RiskManager
from src.dashboard.app import DashboardServer

setup_logging()
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="OpenClaw Trading Dashboard")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Port (default: 5000)")
    parser.add_argument("--broker", default="paper", choices=BrokerFactory.get_available_brokers(),
                        help="Broker to connect to (default: paper)")
    args = parser.parse_args()

    # Initialize broker
    broker = BrokerFactory.create(args.broker)
    broker.connect()

    # Initialize risk manager
    risk_manager = RiskManager(broker=broker)

    # Optional: IV analyzer
    iv_analyzer = None
    try:
        from src.data.iv_analyzer import IVAnalyzer
        iv_analyzer = IVAnalyzer()
    except ImportError:
        logger.warning("IV analyzer not available")

    # Optional: Greeks monitor
    greeks_monitor = None
    try:
        from src.data.greeks import GreeksMonitor
        greeks_monitor = GreeksMonitor()
    except ImportError:
        logger.warning("Greeks monitor not available")

    # Optional: ML enhancer
    ml_enhancer = None
    try:
        from src.data.ml_signals import MLSignalEnhancer
        ml_enhancer = MLSignalEnhancer()
        model_path = Path("models/signal_model.joblib")
        if model_path.exists():
            ml_enhancer.load_model(str(model_path))
    except ImportError:
        logger.warning("ML signal enhancer not available")

    # Build dashboard
    dashboard = DashboardServer(
        risk_manager=risk_manager,
        broker=broker,
        iv_analyzer=iv_analyzer,
        greeks_monitor=greeks_monitor,
        ml_enhancer=ml_enhancer,
        host=args.host,
        port=args.port,
    )

    # Set symbols from all strategy configs
    import yaml
    with open("config/strategies.yaml", "r") as f:
        strats = yaml.safe_load(f)
    symbols = set()
    for s in strats.values():
        if isinstance(s, dict):
            symbols.update(s.get("symbols", []))
    dashboard.set_symbols(sorted(symbols))

    logger.info(f"Starting dashboard at http://{args.host}:{args.port}")
    dashboard.start(background=False)


if __name__ == "__main__":
    main()
