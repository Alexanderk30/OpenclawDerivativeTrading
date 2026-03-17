"""Alpaca API client wrapper."""
from abc import ABC, abstractmethod
from typing import Optional
import logging

from config import config

logger = logging.getLogger(__name__)


class BaseBroker(ABC):
    """Abstract base class for broker implementations."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to broker."""
        pass
    
    @abstractmethod
    def get_account(self) -> dict:
        """Get account information."""
        pass
    
    @abstractmethod
    def get_positions(self) -> list:
        """Get current positions."""
        pass
    
    @abstractmethod
    def submit_order(self, symbol: str, qty: int, side: str, 
                     order_type: str = "market", **kwargs) -> dict:
        """Submit an order."""
        pass
    
    @abstractmethod
    def get_options_chain(self, symbol: str) -> list:
        """Get options chain for symbol."""
        pass


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
    
    def get_positions(self) -> list:
        """Get current positions."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        
        positions = self.api.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "qty": int(p.qty),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc)
            }
            for p in positions
        ]
    
    def submit_order(self, symbol: str, qty: int, side: str,
                     order_type: str = "market", **kwargs) -> dict:
        """Submit an order."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        
        order_data = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
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
    
    def get_options_chain(self, symbol: str) -> list:
        """Get options chain - requires Alpaca options API access."""
        # This is a placeholder - implement based on Alpaca's options API
        logger.warning("Options chain not yet implemented")
        return []
