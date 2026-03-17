"""
Configuration loader - reads from environment variables.
NEVER hardcode secrets in this file.
"""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file if it exists
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


class Config:
    """Configuration class that loads from environment variables."""
    
    # Alpaca API Configuration
    ALPACA_API_KEY: str = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY", "")
    ALPACA_BASE_URL: str = os.getenv(
        "ALPACA_BASE_URL", 
        "https://paper-api.alpaca.markets"  # Default to paper trading
    )
    
    # Trading Mode
    PAPER_TRADING: bool = os.getenv("PAPER_TRADING", "true").lower() == "true"
    
    # Risk Management
    MAX_PORTFOLIO_RISK: float = float(os.getenv("MAX_PORTFOLIO_RISK", "0.02"))
    MAX_POSITION_SIZE: float = float(os.getenv("MAX_POSITION_SIZE", "0.10"))
    MAX_DAILY_LOSS: float = float(os.getenv("MAX_DAILY_LOSS", "0.05"))
    DEFAULT_QUANTITY: int = int(os.getenv("DEFAULT_QUANTITY", "1"))
    
    # Notifications
    ENABLE_NOTIFICATIONS: bool = os.getenv("ENABLE_NOTIFICATIONS", "false").lower() == "true"
    NOTIFICATION_WEBHOOK_URL: Optional[str] = os.getenv("NOTIFICATION_WEBHOOK_URL")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/trading.log")
    
    # Market Hours
    MARKET_OPEN_TIME: str = os.getenv("MARKET_OPEN_TIME", "09:30")
    MARKET_CLOSE_TIME: str = os.getenv("MARKET_CLOSE_TIME", "16:00")
    TIMEZONE: str = os.getenv("TIMEZONE", "America/New_York")
    
    @classmethod
    def validate(cls) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        if not cls.ALPACA_API_KEY:
            errors.append("ALPACA_API_KEY not set")
        if not cls.ALPACA_SECRET_KEY:
            errors.append("ALPACA_SECRET_KEY not set")
        if cls.MAX_PORTFOLIO_RISK <= 0 or cls.MAX_PORTFOLIO_RISK > 1:
            errors.append("MAX_PORTFOLIO_RISK must be between 0 and 1")
        if cls.MAX_POSITION_SIZE <= 0 or cls.MAX_POSITION_SIZE > 1:
            errors.append("MAX_POSITION_SIZE must be between 0 and 1")
            
        return errors
    
    @classmethod
    def is_paper_trading(cls) -> bool:
        """Check if running in paper trading mode."""
        return "paper" in cls.ALPACA_BASE_URL.lower() or cls.PAPER_TRADING


# Global config instance
config = Config()
