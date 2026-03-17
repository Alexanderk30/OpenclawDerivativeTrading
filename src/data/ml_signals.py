"""
Machine Learning Signal Enhancement Module

This module provides ML-based signal enhancement for options trading strategies.
It trains on historical signals to adjust confidence scores based on learned patterns
in market microstructure, volatility regimes, and other features.
"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import joblib
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
)

logger = logging.getLogger(__name__)


@dataclass
class ModelMetrics:
    """Model performance metrics and metadata."""

    accuracy: float
    precision: float
    recall: float
    f1: float
    auc_roc: float
    trained_at: str  # ISO timestamp
    sample_count: int

    def to_dict(self) -> Dict:
        """Convert metrics to dictionary."""
        return {
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "auc_roc": self.auc_roc,
            "trained_at": self.trained_at,
            "sample_count": self.sample_count,
        }


class MLSignalEnhancer:
    """
    ML-based signal enhancement for options trading strategies.

    Takes raw strategy signals and adjusts confidence scores based on learned
    patterns from historical data. Uses gradient boosting for robustness with
    small datasets and no GPU dependency.
    """

    # Feature names in extraction order (must match _extract_features)
    FEATURE_NAMES = [
        "iv_rank",
        "iv_percentile",
        "price_momentum",
        "volatility_regime",
        "days_to_exp_norm",
        "spread_width_norm",
        "day_of_week",
    ]

    def __init__(self, random_state: int = 42):
        """
        Initialize the ML signal enhancer.

        Args:
            random_state: Random seed for reproducibility
        """
        self.random_state = random_state
        self._model: Optional[GradientBoostingClassifier] = None
        self._scaler: Optional[StandardScaler] = None
        self._metrics: Optional[ModelMetrics] = None
        self._lock = threading.RLock()
        self._trained = False
        logger.info("MLSignalEnhancer initialized")

    def _extract_features(self, signal_data: Dict) -> np.ndarray:
        """
        Extract feature vector from signal data.

        Args:
            signal_data: Dictionary containing signal and market data

        Returns:
            1D numpy array of features

        Raises:
            ValueError: If required fields are missing
        """
        required_fields = [
            "iv_rank",
            "iv_percentile",
            "price_history",
            "hv20",
            "hv50",
            "days_to_expiration",
            "spread_width",
            "underlying_price",
            "timestamp",
        ]

        missing = [f for f in required_fields if f not in signal_data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        features = []

        # 1. IV Rank (0-100)
        features.append(signal_data["iv_rank"] / 100.0)

        # 2. IV Percentile (0-100)
        features.append(signal_data["iv_percentile"] / 100.0)

        # 3. Price Momentum (SMA ratios)
        price_history = signal_data["price_history"]
        if len(price_history) >= 20:
            sma20 = np.mean(price_history[-20:])
            sma50 = (
                np.mean(price_history[-50:])
                if len(price_history) >= 50
                else np.mean(price_history)
            )
            momentum = (sma20 - sma50) / sma50 if sma50 > 0 else 0
            features.append(np.clip(momentum, -1, 1))
        else:
            features.append(0.0)

        # 4. Volatility Regime (HV20/HV50 ratio)
        hv20 = signal_data["hv20"]
        hv50 = signal_data["hv50"]
        if hv50 > 0:
            vol_regime = hv20 / hv50
            features.append(np.clip(vol_regime, 0.5, 2.0) - 0.5)  # Normalize to ~[-0.5, 1.5]
        else:
            features.append(0.0)

        # 5. Days to Expiration (normalized, 0-1 for typical 0-60 DTE range)
        dte = signal_data["days_to_expiration"]
        features.append(np.clip(dte / 60.0, 0, 1))

        # 6. Spread Width Normalized by Underlying Price
        spread_width = signal_data["spread_width"]
        underlying = signal_data["underlying_price"]
        if underlying > 0:
            spread_norm = (spread_width / underlying) * 100  # As percentage
            features.append(np.clip(spread_norm, 0, 10))
        else:
            features.append(0.0)

        # 7. Day of Week (0-6, normalized to 0-1)
        timestamp = signal_data["timestamp"]
        if isinstance(timestamp, str):
            dt = datetime.fromisoformat(timestamp)
        else:
            dt = timestamp
        day_of_week = dt.weekday() / 6.0  # 0-1 range
        features.append(day_of_week)

        return np.array(features, dtype=np.float32)

    def train(self, historical_signals: List[Dict]) -> None:
        """
        Train the ML model on historical signals with known outcomes.

        Args:
            historical_signals: List of signal dicts with 'data' and 'outcome' keys
                               outcome should be 1 (profitable/correct) or 0 (unprofitable/incorrect)

        Raises:
            ValueError: If insufficient data or missing required fields
        """
        with self._lock:
            if len(historical_signals) < 10:
                logger.warning(
                    f"Insufficient training samples ({len(historical_signals)}), "
                    "need at least 10"
                )
                return

            X_list = []
            y_list = []

            for signal in historical_signals:
                try:
                    if "data" not in signal or "outcome" not in signal:
                        logger.debug("Skipping signal missing 'data' or 'outcome'")
                        continue

                    features = self._extract_features(signal["data"])
                    outcome = int(signal["outcome"])

                    X_list.append(features)
                    y_list.append(outcome)
                except (ValueError, KeyError) as e:
                    logger.debug(f"Skipping signal due to error: {e}")
                    continue

            if len(X_list) < 10:
                logger.warning(
                    f"Insufficient valid training samples ({len(X_list)}), "
                    "need at least 10"
                )
                return

            X = np.array(X_list, dtype=np.float32)
            y = np.array(y_list, dtype=np.int32)

            # Initialize and fit scaler
            self._scaler = StandardScaler()
            X_scaled = self._scaler.fit_transform(X)

            # Train model
            self._model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=4,
                min_samples_split=5,
                min_samples_leaf=2,
                subsample=0.8,
                random_state=self.random_state,
                verbose=0,
            )

            self._model.fit(X_scaled, y)

            # Calculate metrics
            y_pred = self._model.predict(X_scaled)
            y_pred_proba = self._model.predict_proba(X_scaled)[:, 1]

            # Handle edge cases for metrics
            n_samples = len(y)
            n_positive = int(np.sum(y))
            n_negative = n_samples - n_positive

            metrics_dict = {
                "accuracy": float(accuracy_score(y, y_pred)),
                "precision": (
                    float(precision_score(y, y_pred, zero_division=0))
                    if n_positive > 0
                    else 0.0
                ),
                "recall": (
                    float(recall_score(y, y_pred, zero_division=0))
                    if n_positive > 0
                    else 0.0
                ),
                "f1": (
                    float(f1_score(y, y_pred, zero_division=0)) if n_positive > 0 else 0.0
                ),
                "auc_roc": (
                    float(roc_auc_score(y, y_pred_proba))
                    if (n_positive > 0 and n_negative > 0)
                    else 0.0
                ),
            }

            self._metrics = ModelMetrics(
                accuracy=metrics_dict["accuracy"],
                precision=metrics_dict["precision"],
                recall=metrics_dict["recall"],
                f1=metrics_dict["f1"],
                auc_roc=metrics_dict["auc_roc"],
                trained_at=datetime.utcnow().isoformat(),
                sample_count=n_samples,
            )

            self._trained = True
            logger.info(
                f"Model trained on {n_samples} samples. "
                f"Accuracy: {metrics_dict['accuracy']:.3f}, "
                f"AUC-ROC: {metrics_dict['auc_roc']:.3f}"
            )

    def enhance_signal(self, signal_data: Dict) -> Dict:
        """
        Enhance a signal with ML-adjusted confidence and metadata.

        Args:
            signal_data: Dictionary with signal and market data

        Returns:
            Dictionary with:
              - adjusted_confidence: ML-adjusted confidence (0-1)
              - original_confidence: Original signal confidence
              - model_score: Raw model probability
              - feature_importance: Dict of feature -> importance
              - is_enhanced: Boolean indicating if model was used

        Raises:
            ValueError: If required fields are missing (only if model is trained)
        """
        with self._lock:
            # Extract original confidence
            original_confidence = signal_data.get("confidence", 0.5)

            # If model not trained, return original confidence
            if not self._trained or self._model is None or self._scaler is None:
                logger.debug("Model not trained, returning original confidence")
                return {
                    "adjusted_confidence": original_confidence,
                    "original_confidence": original_confidence,
                    "model_score": None,
                    "feature_importance": {},
                    "is_enhanced": False,
                }

            try:
                # Extract features
                features = self._extract_features(signal_data)
                features_scaled = self._scaler.transform(features.reshape(1, -1))[0]

                # Get model prediction
                model_score = float(self._model.predict_proba(features_scaled.reshape(1, -1))[0, 1])

                # Blend original confidence with model score (70/30 model/original)
                adjusted_confidence = 0.7 * model_score + 0.3 * original_confidence
                adjusted_confidence = float(np.clip(adjusted_confidence, 0, 1))

                # Get feature importance
                feature_importance = {
                    name: float(imp)
                    for name, imp in zip(self.FEATURE_NAMES, self._model.feature_importances_)
                }

                return {
                    "adjusted_confidence": adjusted_confidence,
                    "original_confidence": original_confidence,
                    "model_score": model_score,
                    "feature_importance": feature_importance,
                    "is_enhanced": True,
                }

            except (ValueError, KeyError) as e:
                logger.warning(f"Could not enhance signal: {e}, returning original confidence")
                return {
                    "adjusted_confidence": original_confidence,
                    "original_confidence": original_confidence,
                    "model_score": None,
                    "feature_importance": {},
                    "is_enhanced": False,
                }

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance scores from trained model.

        Returns:
            Dictionary mapping feature names to importance scores (0-1)
            Empty dict if model not trained
        """
        with self._lock:
            if not self._trained or self._model is None:
                return {}

            return {
                name: float(imp)
                for name, imp in zip(self.FEATURE_NAMES, self._model.feature_importances_)
            }

    def get_metrics(self) -> Optional[ModelMetrics]:
        """
        Get model performance metrics.

        Returns:
            ModelMetrics dataclass if trained, None otherwise
        """
        with self._lock:
            return self._metrics

    def is_trained(self) -> bool:
        """Check if model has been trained."""
        with self._lock:
            return self._trained

    def save_model(self, path: str) -> None:
        """
        Save trained model to disk using joblib.

        Args:
            path: File path to save model (typically .joblib extension)

        Raises:
            RuntimeError: If model not trained
            IOError: If file write fails
        """
        with self._lock:
            if not self._trained or self._model is None or self._scaler is None:
                raise RuntimeError("Model must be trained before saving")

            try:
                model_path = Path(path)
                model_path.parent.mkdir(parents=True, exist_ok=True)

                model_data = {
                    "model": self._model,
                    "scaler": self._scaler,
                    "metrics": self._metrics.to_dict() if self._metrics else None,
                    "feature_names": self.FEATURE_NAMES,
                }

                joblib.dump(model_data, path, compress=3)
                logger.info(f"Model saved to {path}")
            except Exception as e:
                logger.error(f"Failed to save model: {e}")
                raise IOError(f"Failed to save model to {path}: {e}")

    def load_model(self, path: str) -> None:
        """
        Load trained model from disk using joblib.

        Args:
            path: File path to load model from

        Raises:
            FileNotFoundError: If model file not found
            RuntimeError: If model data invalid
        """
        with self._lock:
            try:
                model_path = Path(path)
                if not model_path.exists():
                    raise FileNotFoundError(f"Model file not found: {path}")

                model_data = joblib.load(path)

                # Validate loaded data
                required_keys = {"model", "scaler", "feature_names"}
                if not all(key in model_data for key in required_keys):
                    raise RuntimeError("Invalid model file: missing required keys")

                self._model = model_data["model"]
                self._scaler = model_data["scaler"]

                # Load metrics if available
                if model_data.get("metrics"):
                    metrics_dict = model_data["metrics"]
                    self._metrics = ModelMetrics(
                        accuracy=metrics_dict["accuracy"],
                        precision=metrics_dict["precision"],
                        recall=metrics_dict["recall"],
                        f1=metrics_dict["f1"],
                        auc_roc=metrics_dict["auc_roc"],
                        trained_at=metrics_dict["trained_at"],
                        sample_count=metrics_dict["sample_count"],
                    )

                self._trained = True
                logger.info(f"Model loaded from {path}")

            except (FileNotFoundError, EOFError, joblib.externals.loky.process_executor.BrokenProcessPool) as e:
                logger.error(f"Failed to load model: {e}")
                raise FileNotFoundError(f"Failed to load model from {path}: {e}")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                raise RuntimeError(f"Invalid model file: {e}")
