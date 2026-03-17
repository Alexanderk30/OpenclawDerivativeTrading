"""Interactive Brokers (IBKR) client wrapper using ib_insync."""
import logging
import os
import time
from typing import Optional
from threading import Lock

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


class IBKRClient(BaseBroker):
    """Interactive Brokers API client for trading using ib_insync."""

    def __init__(self):
        self.ib = None
        self._connected = False
        self._lock = Lock()

        # Load configuration from environment variables
        self.host = os.getenv("IBKR_HOST", "127.0.0.1")
        self.port = int(os.getenv("IBKR_PORT", "7497"))
        self.client_id = int(os.getenv("IBKR_CLIENT_ID", "1"))

    def connect(self) -> bool:
        """Establish connection to Interactive Brokers TWS/Gateway."""
        try:
            from ib_insync import IB

            self.ib = IB()
            self.ib.connect(self.host, self.port, clientId=self.client_id)

            # Test connection by getting account summary
            account_summary = self.ib.accountSummary(account="")
            if not account_summary:
                logger.warning("Connected but no account summary returned")

            self._connected = True
            logger.info(f"Connected to Interactive Brokers at {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Interactive Brokers: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from Interactive Brokers."""
        try:
            if self.ib is not None:
                self.ib.disconnect()
        except Exception as e:
            logger.warning(f"Error during IBKR disconnect: {e}")
        finally:
            self._connected = False
            self.ib = None
            logger.info("Disconnected from Interactive Brokers")

    @_retry
    def get_account(self) -> dict:
        """Get account information from Interactive Brokers."""
        if not self._connected or self.ib is None:
            raise RuntimeError("Not connected to broker")

        try:
            with self._lock:
                # Get account summary
                account_summary = self.ib.accountSummary(account="")

                account_dict = {tag.value: tag.value for tag in account_summary}

                # Extract key account metrics
                cash = float(account_dict.get("CashBalance", 0))
                equity = float(account_dict.get("EquityWithLoanValue", 0))
                buying_power = float(account_dict.get("BuyingPower", 0))
                portfolio_value = float(account_dict.get("NetLiquidationValue", 0))

                return {
                    "id": account_dict.get("AccountCode", ""),
                    "cash": cash,
                    "portfolio_value": portfolio_value,
                    "buying_power": buying_power,
                    "equity": equity,
                    "status": "ACTIVE"
                }
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            raise

    @_retry
    def get_positions(self) -> list:
        """Get current positions including asset_class and avg_entry_price."""
        if not self._connected or self.ib is None:
            raise RuntimeError("Not connected to broker")

        try:
            with self._lock:
                positions = self.ib.positions()

                result = []
                for position in positions:
                    contract = position.contract

                    # Determine asset class from contract
                    asset_class = "us_equity"
                    if contract.secType == "OPT":
                        asset_class = "us_option"
                    elif contract.secType == "FUT":
                        asset_class = "us_future"
                    elif contract.secType == "CASH":
                        asset_class = "forex"

                    result.append({
                        "symbol": contract.symbol,
                        "qty": int(position.position),
                        "avg_entry_price": float(position.avgCost),
                        "market_value": float(position.marketValue),
                        "unrealized_pl": float(position.unrealizedPNL),
                        "unrealized_plpc": float(position.unrealizedPNLpct) if position.unrealizedPNLpct else 0.0,
                        "asset_class": asset_class,
                    })

                return result
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise

    @_retry
    def submit_order(self, symbol: str, qty: int, side: str,
                     order_type: str = "market", **kwargs) -> dict:
        """Submit an order to Interactive Brokers. Supports market and limit order types."""
        if not self._connected or self.ib is None:
            raise RuntimeError("Not connected to broker")

        try:
            from ib_insync import Stock, Order

            with self._lock:
                # Create contract
                contract = Stock(symbol, "SMART", "USD")

                # Create order
                order = Order()
                order.action = "BUY" if side.lower() == "buy" else "SELL"
                order.totalQuantity = qty

                if order_type == "limit" and "price" in kwargs:
                    order.orderType = "LMT"
                    order.lmtPrice = kwargs["price"]
                    logger.info(f"Submitting limit order: {side} {qty} {symbol} @ ${kwargs['price']}")
                else:
                    order.orderType = "MKT"
                    logger.info(f"Submitting market order: {side} {qty} {symbol}")

                # Submit order
                trade = self.ib.placeOrder(contract, order)

                # Wait for order to be acknowledged
                while not trade.isDone():
                    self.ib.sleep(0.1)

                return {
                    "id": str(trade.order.orderId),
                    "symbol": symbol,
                    "qty": qty,
                    "side": side.upper(),
                    "status": trade.orderStatus.status
                }
        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            raise

    @_retry
    def get_options_chain(self, symbol: str) -> list:
        """Get options chain for a symbol from Interactive Brokers."""
        if not self._connected or self.ib is None:
            raise RuntimeError("Not connected to broker")

        try:
            from ib_insync import Stock, Option

            with self._lock:
                # Get stock contract first
                stock = Stock(symbol, "SMART", "USD")

                # Request option chains
                chains = self.ib.reqSecDefOptParams(stock.symbol, "", stock.secType, stock.conId)

                if not chains:
                    logger.warning(f"No option chains found for {symbol}")
                    return []

                options_data = []

                # Get the first available chain
                chain = chains[0]

                # Get expirations and strikes
                expirations = chain.expirations[:3]  # Limit to first 3 expirations
                strikes = chain.strikes[-10:] + chain.strikes[:10]  # Get a range around ATM

                for expiration in expirations:
                    for strike in strikes:
                        for right in ["CALL", "PUT"]:
                            try:
                                contract = Option(symbol, expiration, strike, right, "SMART")
                                ticker = self.ib.reqMktData(contract)
                                self.ib.sleep(0.1)

                                if ticker.bid > 0 and ticker.ask > 0:
                                    options_data.append({
                                        "symbol": f"{symbol}_{right}_{strike}_{expiration}",
                                        "strike": strike,
                                        "expiration": expiration,
                                        "type": right.lower(),
                                        "bid": float(ticker.bid),
                                        "ask": float(ticker.ask),
                                    })

                                self.ib.cancelMktData(contract)
                            except Exception as e:
                                logger.debug(f"Failed to get data for {symbol} {strike} {right}: {e}")
                                continue

                return options_data
        except Exception as e:
            logger.error(f"Failed to get options chain: {e}")
            raise
