"""Main entry point for the trading bot."""
import argparse
import logging
import sys
from pathlib import Path

from config import config
from utils.logger import setup_logging


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="OpenClaw Derivative Trading Bot")
    parser.add_argument(
        "--mode",
        choices=["backtest", "paper", "live"],
        default="paper",
        help="Trading mode"
    )
    parser.add_argument(
        "--strategy",
        default="iron_condor",
        help="Strategy to run"
    )
    parser.add_argument(
        "--symbol",
        help="Symbol to trade"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Validate config
    errors = config.validate()
    if errors:
        logger.error("Configuration errors:")
        for error in errors:
            logger.error(f"  - {error}")
        sys.exit(1)
    
    # Safety check for live trading
    if args.mode == "live":
        if config.is_paper_trading():
            logger.warning("Running in paper mode despite --mode=live")
            logger.info("Set PAPER_TRADING=false and update ALPACA_BASE_URL for live trading")
        else:
            logger.warning("⚠️  LIVE TRADING MODE ENABLED ⚠️")
            logger.warning("Real money is at risk. Press Ctrl+C within 5 seconds to cancel...")
            import time
            time.sleep(5)
    
    logger.info(f"Starting trading bot in {args.mode} mode")
    logger.info(f"Strategy: {args.strategy}")
    
    # Import and run based on mode
    if args.mode == "backtest":
        from scripts.backtest import run_backtest
        run_backtest(args.strategy, args.symbol)
    else:
        from src.execution.execution_engine import ExecutionEngine
        engine = ExecutionEngine(args.strategy, args.mode)
        engine.run()


if __name__ == "__main__":
    main()
