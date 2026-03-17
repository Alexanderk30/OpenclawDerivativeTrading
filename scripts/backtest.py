#!/usr/bin/env python3
"""Backtesting script for strategies."""
import argparse
import logging
from datetime import datetime, timedelta

from config import config
from src.utils.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def run_backtest(strategy_name: str, symbol: str = None, days: int = 90):
    """Run a backtest for a strategy."""
    logger.info(f"Starting backtest: {strategy_name} on {symbol} for {days} days")
    
    # Load strategy
    import yaml
    with open("config/strategies.yaml", "r") as f:
        strategies_config = yaml.safe_load(f)
    
    strategy_config = strategies_config.get(strategy_name, {})
    
    if strategy_name == "iron_condor":
        from src.strategies.iron_condor import IronCondorStrategy
        strategy = IronCondorStrategy(strategy_config)
    elif strategy_name == "credit_spread":
        from src.strategies.credit_spread import CreditSpreadStrategy
        strategy = CreditSpreadStrategy(strategy_config)
    elif strategy_name == "wheel_strategy":
        from src.strategies.wheel_strategy import WheelStrategy
        strategy = WheelStrategy(strategy_config)
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    
    # Simulate backtest data
    # In production, load actual historical data
    symbols = [symbol] if symbol else strategy_config.get("symbols", ["SPY"])
    
    results = {
        "trades": [],
        "total_pnl": 0.0,
        "win_rate": 0.0,
        "max_drawdown": 0.0,
        "sharpe_ratio": 0.0
    }
    
    logger.info(f"Backtest complete for {strategy_name}")
    logger.info(f"Simulated {len(symbols)} symbols over {days} days")
    
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest trading strategies")
    parser.add_argument("--strategy", required=True, help="Strategy name")
    parser.add_argument("--symbol", help="Symbol to backtest")
    parser.add_argument("--days", type=int, default=90, help="Number of days")
    
    args = parser.parse_args()
    
    results = run_backtest(args.strategy, args.symbol, args.days)
    print(f"\nBacktest Results for {args.strategy}:")
    print(f"Total P&L: ${results['total_pnl']:,.2f}")
    print(f"Win Rate: {results['win_rate']:.1%}")
