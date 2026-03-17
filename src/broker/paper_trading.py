"""Paper trading simulator for testing strategies."""
import logging
from datetime import datetime
from typing import Optional

from .base_broker import BaseBroker

logger = logging.getLogger(__name__)


class PaperTradingSimulator(BaseBroker):
    """Paper trading simulator that mimics broker behavior."""
    
    def __init__(self, initial_balance: float = 100000.0):
        self.balance = initial_balance
        self.positions = {}
        self.orders = []
        self._connected = False
    
    def connect(self) -> bool:
        """Connect to simulator."""
        self._connected = True
        logger.info(f"Paper trading simulator connected. Balance: ${self.balance:,.2f}")
        return True
    
    def get_account(self) -> dict:
        """Get simulated account info."""
        portfolio_value = self.balance + sum(
            p.get("market_value", 0) for p in self.positions.values()
        )
        return {
            "id": "paper_account",
            "cash": self.balance,
            "portfolio_value": portfolio_value,
            "buying_power": self.balance * 2,  # 2x margin
            "equity": portfolio_value,
            "status": "ACTIVE"
        }
    
    def get_positions(self) -> list:
        """Get simulated positions."""
        return list(self.positions.values())
    
    def submit_order(self, symbol: str, qty: int, side: str,
                     order_type: str = "market", **kwargs) -> dict:
        """Submit a simulated order."""
        order = {
            "id": f"paper_{len(self.orders) + 1}",
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "status": "filled",
            "filled_at": datetime.now().isoformat(),
            "fill_price": kwargs.get("price", 1.0)  # Would get from market data
        }
        
        self.orders.append(order)
        
        # Update positions
        if side.lower() == "buy":
            cost = qty * order["fill_price"]
            self.balance -= cost
            
            if symbol in self.positions:
                self.positions[symbol]["qty"] += qty
            else:
                self.positions[symbol] = {
                    "symbol": symbol,
                    "qty": qty,
                    "market_value": qty * order["fill_price"],
                    "unrealized_pl": 0.0,
                    "unrealized_plpc": 0.0
                }
        else:
            proceeds = qty * order["fill_price"]
            self.balance += proceeds
            
            if symbol in self.positions:
                self.positions[symbol]["qty"] -= qty
                if self.positions[symbol]["qty"] <= 0:
                    del self.positions[symbol]
        
        logger.info(f"[PAPER] Order filled: {side} {qty} {symbol} @ ${order['fill_price']}")
        return order
    
    def get_options_chain(self, symbol: str) -> list:
        """Get mock options chain."""
        # Return mock data for testing
        return [
            {
                "symbol": f"{symbol}_CALL_100_30D",
                "strike": 100.0,
                "expiration": "2024-04-19",
                "type": "call",
                "bid": 2.50,
                "ask": 2.70
            },
            {
                "symbol": f"{symbol}_PUT_95_30D",
                "strike": 95.0,
                "expiration": "2024-04-19",
                "type": "put",
                "bid": 1.80,
                "ask": 2.00
            }
        ]
