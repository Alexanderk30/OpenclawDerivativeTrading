"""Factory for creating broker instances with registry pattern."""
import logging
import os
from typing import List

from .base_broker import BaseBroker

logger = logging.getLogger(__name__)

# Broker registry — maps broker names to their class paths
BROKER_REGISTRY = {
    "alpaca": "src.broker.alpaca_client.AlpacaClient",
    "ibkr": "src.broker.ibkr_client.IBKRClient",
    "paper": "src.broker.paper_trading.PaperTradingSimulator",
}

# Required environment variables for each broker
BROKER_ENV_REQUIREMENTS = {
    "alpaca": ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"],
    "ibkr": ["IBKR_HOST", "IBKR_PORT", "IBKR_CLIENT_ID"],
    "paper": [],  # No environment variables required for paper trading
}


def _import_broker_class(dotted_path: str):
    """Dynamically import a broker class from a dotted module path."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class BrokerFactory:
    """Factory for creating broker instances."""

    @staticmethod
    def create(broker_name: str, **kwargs) -> BaseBroker:
        """
        Create a broker instance by name.

        Args:
            broker_name: Name of the broker ("alpaca", "ibkr", "paper")
            **kwargs: Additional arguments passed to broker constructor

        Returns:
            BaseBroker: An initialized broker instance

        Raises:
            ValueError: If broker_name is unknown or configuration is invalid
            ImportError: If broker module cannot be imported
        """
        broker_name = broker_name.lower().strip()

        if broker_name not in BROKER_REGISTRY:
            available = ", ".join(BROKER_REGISTRY.keys())
            raise ValueError(
                f"Unknown broker: {broker_name}. "
                f"Available brokers: {available}"
            )

        dotted_path = BROKER_REGISTRY[broker_name]

        try:
            broker_cls = _import_broker_class(dotted_path)
            logger.info(f"Creating {broker_name} broker instance")
            return broker_cls(**kwargs)
        except Exception as e:
            logger.error(f"Failed to create {broker_name} broker: {e}")
            raise

    @staticmethod
    def get_available_brokers() -> List[str]:
        """
        Get list of available brokers.

        Returns:
            List[str]: List of broker names
        """
        return list(BROKER_REGISTRY.keys())

    @staticmethod
    def validate_broker_config(broker_name: str) -> List[str]:
        """
        Validate that all required environment variables are set for a broker.

        Args:
            broker_name: Name of the broker to validate

        Returns:
            List[str]: List of missing/invalid configuration errors (empty if valid)
        """
        broker_name = broker_name.lower().strip()

        if broker_name not in BROKER_REGISTRY:
            return [f"Unknown broker: {broker_name}"]

        required_vars = BROKER_ENV_REQUIREMENTS.get(broker_name, [])
        errors = []

        for var_name in required_vars:
            value = os.getenv(var_name)
            if not value or not value.strip():
                errors.append(f"Missing required environment variable: {var_name}")

        # Broker-specific validation
        if broker_name == "ibkr":
            try:
                port = os.getenv("IBKR_PORT", "7497")
                int(port)
            except ValueError:
                errors.append(f"IBKR_PORT must be a valid integer, got: {port}")

            try:
                client_id = os.getenv("IBKR_CLIENT_ID", "1")
                int(client_id)
            except ValueError:
                errors.append(f"IBKR_CLIENT_ID must be a valid integer, got: {client_id}")

        return errors
