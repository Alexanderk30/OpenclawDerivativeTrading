"""Abstract base class for broker implementations."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import logging

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

    def disconnect(self):
        """Disconnect from broker. Override in subclasses if needed."""
        logger.info(f"{self.__class__.__name__} disconnected")
