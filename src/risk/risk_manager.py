"""Risk management module with risk posture support."""
import json
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)

# Default fallbacks (overridden by risk_posture.json when available)
DEFAULT_MAX_POSITIONS_PER_SYMBOL = 3
DEFAULT_PORTFOLIO_HEAT_PERCENT = 0.30
DEFAULT_MIN_CONFIDENCE = 0.60

# Path to risk posture config (relative to project root)
RISK_POSTURE_PATH = Path(__file__).parent.parent.parent / "config" / "risk_posture.json"


def _load_risk_posture() -> Optional[Dict]:
    """Load risk posture configuration if available."""
    try:
        if RISK_POSTURE_PATH.exists():
            with open(RISK_POSTURE_PATH, "r") as f:
                data = json.load(f)
            active = data.get("active_posture", "moderate")
            posture = data.get("postures", {}).get(active)
            if posture:
                logger.info(f"Loaded risk posture: {active}")
                return {**posture, "_posture_name": active, "_global": data.get("global_constraints", {})}
            logger.warning(f"Active posture '{active}' not found in risk_posture.json")
    except Exception as e:
        logger.warning(f"Could not load risk_posture.json: {e}")
    return None


class RiskManager:
    """Manages portfolio-level risk with thread-safe position tracking and risk posture support."""

    def __init__(self, broker=None):
        self._broker = broker
        self._lock = threading.Lock()
        self.daily_pnl = 0.0
        self.positions: List[Dict] = []

        # Load risk posture first; fall back to settings.py defaults
        posture = _load_risk_posture()
        if posture:
            self.max_portfolio_risk = posture.get("max_portfolio_risk_per_trade", config.MAX_PORTFOLIO_RISK)
            self.max_position_size = posture.get("max_position_size_percent", config.MAX_POSITION_SIZE)
            self.max_daily_loss = posture.get("max_daily_loss_percent", config.MAX_DAILY_LOSS)
            self.max_positions_per_symbol = posture.get("max_positions_per_symbol", DEFAULT_MAX_POSITIONS_PER_SYMBOL)
            self.max_portfolio_heat = posture.get("max_portfolio_heat_percent", DEFAULT_PORTFOLIO_HEAT_PERCENT)
            self.min_confidence = posture.get("min_confidence_threshold", DEFAULT_MIN_CONFIDENCE)
            self._posture_name = posture.get("_posture_name", "unknown")
            self._global_constraints = posture.get("_global", {})
        else:
            self.max_portfolio_risk = config.MAX_PORTFOLIO_RISK
            self.max_position_size = config.MAX_POSITION_SIZE
            self.max_daily_loss = config.MAX_DAILY_LOSS
            self.max_positions_per_symbol = DEFAULT_MAX_POSITIONS_PER_SYMBOL
            self.max_portfolio_heat = DEFAULT_PORTFOLIO_HEAT_PERCENT
            self.min_confidence = DEFAULT_MIN_CONFIDENCE
            self._posture_name = "default"
            self._global_constraints = {}

    def can_open_position(self, signal: Dict, account: Dict) -> bool:
        """
        Check if a new position can be opened against all risk constraints.

        Args:
            signal: Trading signal with position details (symbol, metadata, confidence)
            account: Account information (portfolio_value, etc.)

        Returns:
            True if position can be opened
        """
        portfolio_value = account["portfolio_value"]

        # Check daily loss limit
        if self.daily_pnl < -portfolio_value * self.max_daily_loss:
            logger.warning("Daily loss limit reached. No new positions.")
            return False

        # Check confidence threshold (from risk posture)
        confidence = signal.get("metadata", {}).get("confidence") or signal.get("confidence", 1.0)
        if confidence < self.min_confidence:
            logger.warning(
                f"Signal confidence {confidence:.2f} below minimum {self.min_confidence:.2f} "
                f"(posture: {self._posture_name})"
            )
            return False

        # Check position count per symbol
        symbol = signal.get("symbol")
        with self._lock:
            existing_positions = [p for p in self.positions if p["symbol"] == symbol]
        if len(existing_positions) >= self.max_positions_per_symbol:
            logger.warning(f"Max positions ({self.max_positions_per_symbol}) reached for {symbol}")
            return False

        # Check individual position size limit
        if not self.check_position_limits(signal, account):
            return False

        # Check total portfolio heat (uses posture-driven heat limit)
        total_risk = self.calculate_portfolio_heat(account)
        new_position_risk = signal.get("metadata", {}).get("max_loss", 0)
        heat_limit = portfolio_value * self.max_portfolio_heat

        if total_risk + new_position_risk > heat_limit:
            logger.warning(
                f"Portfolio heat limit would be exceeded: "
                f"current={total_risk:.2f} + new={new_position_risk:.2f} > limit={heat_limit:.2f}"
            )
            return False

        return True

    def calculate_portfolio_heat(self, account: Dict) -> float:
        """Calculate total risk exposure across all positions."""
        total_risk = 0.0

        with self._lock:
            for position in self.positions:
                market_value = position.get("market_value", 0)

                # For defined risk strategies, use max loss
                if "max_loss" in position and position["max_loss"] > 0:
                    total_risk += position["max_loss"]
                else:
                    # For undefined risk, estimate based on position value
                    total_risk += abs(market_value) * 0.10

        return total_risk

    def check_position_limits(self, signal: Dict, account: Dict) -> bool:
        """Check if position size is within limits."""
        position_value = signal.get("metadata", {}).get("max_loss", 0)
        max_allowed = account["portfolio_value"] * self.max_position_size

        if position_value > max_allowed:
            logger.warning(f"Position risk ${position_value:.2f} exceeds limit ${max_allowed:.2f}")
            return False

        return True

    def update_daily_pnl(self, pnl: float):
        """Update daily P&L tracking."""
        self.daily_pnl += pnl
        logger.info(f"Daily P&L updated: ${self.daily_pnl:.2f}")

        if self.daily_pnl < 0:
            acct_value = self.get_account_value()
            if acct_value > 0:
                loss_pct = abs(self.daily_pnl) / acct_value
                if loss_pct > self.max_daily_loss:
                    logger.warning(f"Daily loss at {loss_pct:.1%} — exceeds {self.max_daily_loss:.1%} limit.")

    def reset_daily_pnl(self):
        """Reset daily P&L at the start of a new trading day."""
        old_pnl = self.daily_pnl
        self.daily_pnl = 0.0
        logger.info(f"Daily P&L reset (previous: ${old_pnl:.2f})")

    def add_position(self, position: Dict):
        """Track a new position with a unique ID."""
        if "id" not in position:
            position["id"] = str(uuid.uuid4())[:8]
        with self._lock:
            self.positions.append(position)
        logger.info(f"Position added: {position['symbol']} (id={position['id']})")

    def remove_position(self, position_id: str = None, symbol: str = None):
        """
        Remove a tracked position by ID (preferred) or by symbol.
        When removing by symbol, only the first matching position is removed.
        """
        with self._lock:
            if position_id:
                self.positions = [p for p in self.positions if p.get("id") != position_id]
                logger.info(f"Position removed by id: {position_id}")
            elif symbol:
                # Remove only the first match to avoid wiping all positions for a symbol
                for i, p in enumerate(self.positions):
                    if p["symbol"] == symbol:
                        removed = self.positions.pop(i)
                        logger.info(f"Position removed: {symbol} (id={removed.get('id', 'N/A')})")
                        return
                logger.warning(f"No position found for symbol: {symbol}")
            else:
                logger.warning("remove_position called with no identifier")

    def get_account_value(self) -> float:
        """Get current account value from broker or fallback."""
        if self._broker:
            try:
                return self._broker.get_account()["portfolio_value"]
            except Exception as e:
                logger.warning(f"Could not fetch account value from broker: {e}")
        return 100000.0  # Fallback for testing

    def get_risk_report(self) -> Dict:
        """Generate risk report including active posture information."""
        acct_value = self.get_account_value()
        heat = self.calculate_portfolio_heat({"portfolio_value": acct_value})
        heat_limit = acct_value * self.max_portfolio_heat

        return {
            "daily_pnl": self.daily_pnl,
            "open_positions": len(self.positions),
            "portfolio_heat": heat,
            "portfolio_heat_limit": heat_limit,
            "heat_utilization_pct": (heat / heat_limit * 100) if heat_limit > 0 else 0,
            "account_value": acct_value,
            "active_posture": self._posture_name,
            "risk_limits": {
                "max_portfolio_risk_per_trade": self.max_portfolio_risk,
                "max_position_size": self.max_position_size,
                "max_daily_loss": self.max_daily_loss,
                "max_portfolio_heat": self.max_portfolio_heat,
                "max_positions_per_symbol": self.max_positions_per_symbol,
                "min_confidence": self.min_confidence,
            },
        }

    def emergency_stop(self):
        """Emergency stop - close all positions via broker."""
        logger.error("EMERGENCY STOP ACTIVATED — Closing all positions immediately!")
        if self._broker:
            try:
                positions = self._broker.get_positions()
                for pos in positions:
                    side = "sell" if pos["qty"] > 0 else "buy"
                    self._broker.submit_order(
                        symbol=pos["symbol"],
                        qty=abs(pos["qty"]),
                        side=side,
                    )
                    logger.info(f"Emergency close: {side} {abs(pos['qty'])} {pos['symbol']}")
            except Exception as e:
                logger.error(f"Error during emergency stop: {e}")

        with self._lock:
            self.positions.clear()

        return True
