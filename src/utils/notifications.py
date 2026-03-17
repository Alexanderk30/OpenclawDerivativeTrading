"""Notification system for alerts and updates."""
import logging
from typing import Optional

from config import config

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manages notifications via webhooks, email, etc."""
    
    def __init__(self):
        self.enabled = config.ENABLE_NOTIFICATIONS
        self.webhook_url = config.NOTIFICATION_WEBHOOK_URL
    
    def send_notification(self, message: str):
        """Send a regular notification."""
        if not self.enabled:
            logger.info(f"[NOTIFY] {message}")
            return
        
        try:
            if self.webhook_url:
                import requests
                requests.post(
                    self.webhook_url,
                    json={"text": message},
                    timeout=5
                )
            logger.info(f"Notification sent: {message}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    def send_alert(self, message: str):
        """Send an alert (higher priority)."""
        alert_message = f"🚨 {message}"
        self.send_notification(alert_message)
        logger.warning(alert_message)
    
    def send_trade_notification(self, order: dict, pnl: Optional[float] = None):
        """Send trade execution notification."""
        msg = f"📊 Trade: {order.get('side', 'N/A').upper()} {order.get('qty', 0)} {order.get('symbol', 'N/A')}"
        if pnl is not None:
            emoji = "✅" if pnl >= 0 else "❌"
            msg += f" | P&L: {emoji} ${pnl:,.2f}"
        self.send_notification(msg)
    
    def send_daily_summary(self, account: dict, positions: list):
        """Send daily summary notification."""
        portfolio_value = account.get("portfolio_value", 0)
        cash = account.get("cash", 0)
        
        msg = f"📈 Daily Summary\n"
        msg += f"Portfolio Value: ${portfolio_value:,.2f}\n"
        msg += f"Cash: ${cash:,.2f}\n"
        msg += f"Open Positions: {len(positions)}"
        
        self.send_notification(msg)
