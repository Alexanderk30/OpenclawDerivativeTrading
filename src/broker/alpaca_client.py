"""Alpaca API client wrapper."""
import logging
import time
from typing import Optional

from config import config
from .base_broker import BaseBroker

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


def _retry(func):
    """Decorator to retry broker API calls with exponential backoff."""
    def wrapper(*args, **kwargs):
        last_exception = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except RuntimeError:
                raise  # Don't retry "not connected" errors
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        f"Broker call {func.__name__} failed (attempt {attempt}/{MAX_RETRIES}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
        logger.error(f"Broker call {func.__name__} failed after {MAX_RETRIES} attempts: {last_exception}")
        raise last_exception
    return wrapper


class AlpacaClient(BaseBroker):
    """Alpaca API client for trading."""

    def __init__(self):
        self.api = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to Alpaca API."""
        try:
            from alpaca.trading.client import TradingClient

            self.api = TradingClient(
                api_key=config.ALPACA_API_KEY,
                secret_key=config.ALPACA_SECRET_KEY,
                paper=config.is_paper_trading()
            )

            # Test connection
            account = self.api.get_account()
            logger.info(f"Connected to Alpaca. Account status: {account.status}")
            self._connected = True
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            return False

    def disconnect(self):
        """Disconnect from Alpaca."""
        self._connected = False
        self.api = None
        logger.info("Disconnected from Alpaca")

    @_retry
    def get_account(self) -> dict:
        """Get account information."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        account = self.api.get_account()
        return {
            "id": account.id,
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "buying_power": float(account.buying_power),
            "equity": float(account.equity),
            "status": account.status
        }

    @_retry
    def get_positions(self) -> list:
        """Get current positions including asset_class for strategy routing."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        positions = self.api.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "qty": int(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
                "asset_class": getattr(p, "asset_class", "us_equity"),
            }
            for p in positions
        ]

    @_retry
    def submit_order(self, symbol: str, qty: int, side: str,
                     order_type: str = "market", **kwargs) -> dict:
        """Submit an order. Supports market and limit order types."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

        if order_type == "limit" and "price" in kwargs:
            order_data = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=TimeInForce.DAY,
                limit_price=kwargs["price"]
            )
        else:
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=TimeInForce.DAY
            )

        order = self.api.submit_order(order_data=order_data)
        logger.info(f"Order submitted: {side} {qty} {symbol}")

        return {
            "id": order.id,
            "symbol": order.symbol,
            "qty": order.qty,
            "side": order.side.value,
            "status": order.status.value
        }

    @_retry
    def get_options_chain(self, symbol: str) -> list:
        """Get options chain - requires Alpaca options API access."""
        logger.warning("Options chain not yet implemented for Alpaca")
        return []
