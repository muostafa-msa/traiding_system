from __future__ import annotations

import os
import pickle

from core.config import AppConfig
from core.logger import get_logger
from core.types import FeatureVector

logger = get_logger(__name__)


class XGBoostWrapper:
    def __init__(self, config: AppConfig):
        self._config = config
        self._model = None
        self._classifier = None
        self._load_if_available()

    def _load_if_available(self) -> None:
        model_dir = self._config.xgboost_model_path
        clf_file = os.path.join(model_dir, "classifier.pkl")

        if os.path.exists(clf_file):
            try:
                with open(clf_file, "rb") as f:
                    self._classifier = pickle.load(f)
                logger.info("XGBClassifier loaded from %s", clf_file)
            except Exception as e:
                logger.warning("Failed to load XGBClassifier: %s", e)

        model_file = os.path.join(model_dir, "model.json")
        if os.path.exists(model_file) and self._classifier is None:
            try:
                import xgboost

                self._model = xgboost.Booster()
                self._model.load_model(model_file)
                logger.info("XGBoost model loaded from %s", model_file)
            except Exception as e:
                logger.warning("Failed to load XGBoost model: %s", e)

    def predict(self, features: FeatureVector) -> float:
        if self._classifier is not None:
            try:
                import numpy as np

                arr = np.array([features.to_array()], dtype=np.float32)
                prob = float(self._classifier.predict_proba(arr)[0, 1])
                return max(0.0, min(1.0, prob))
            except Exception as e:
                logger.warning("Classifier prediction failed: %s", e)

        if self._model is not None:
            try:
                import numpy as np
                import xgboost

                arr = np.array([features.to_array()], dtype=np.float32)
                dmatrix = xgboost.DMatrix(arr, feature_names=features.feature_names())
                raw = self._model.predict(dmatrix)
                prob = float(raw[0])
                return max(0.0, min(1.0, prob))
            except Exception as e:
                logger.warning("XGBoost prediction failed: %s", e)

        return 0.0

    def train(self, feature_vectors: list[FeatureVector], labels: list[int]) -> dict:
        import numpy as np
        from sklearn.metrics import accuracy_score, log_loss
        from xgboost import XGBClassifier

        if len(feature_vectors) != len(labels):
            raise ValueError("feature_vectors and labels must have same length")
        if len(feature_vectors) < 20:
            raise ValueError(
                f"Need at least 20 samples for training, got {len(feature_vectors)}"
            )

        X = np.array([fv.to_array() for fv in feature_vectors], dtype=np.float32)
        y = np.array(labels, dtype=np.int32)

        split = int(len(X) * 0.8)
        X_train, y_train = X[:split], y[:split]
        X_val, y_val = X[split:], y[split:]

        xgb_clf = XGBClassifier(
            max_depth=6,
            n_estimators=200,
            learning_rate=0.1,
            subsample=0.8,
            objective="binary:logistic",
            eval_metric="logloss",
            verbosity=0,
        )
        xgb_clf.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        model_dir = self._config.xgboost_model_path
        os.makedirs(model_dir, exist_ok=True)

        xgb_clf.get_booster().save_model(os.path.join(model_dir, "model.json"))

        with open(os.path.join(model_dir, "classifier.pkl"), "wb") as f:
            pickle.dump(xgb_clf, f)

        self._model = xgb_clf.get_booster()
        self._classifier = xgb_clf

        val_pred = xgb_clf.predict_proba(X_val)[:, 1]
        val_loss = log_loss(y_val, val_pred)
        val_acc = accuracy_score(y_val, (val_pred >= 0.5).astype(int))

        return {
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "val_logloss": val_loss,
            "val_accuracy": val_acc,
            "model_path": os.path.join(model_dir, "model.json"),
        }

    def is_trained(self) -> bool:
        return self._model is not None or self._classifier is not None


if __name__ == "__main__":
    import argparse

    import numpy as np
    import pandas as pd

    from analysis.indicators import compute_indicators
    from analysis.pattern_detection import detect_patterns
    from core.config import load_config
    from core.types import OHLCBar, FeatureVector, PatternDetectionResult

    parser = argparse.ArgumentParser(description="XGBoost model training")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--data", type=str)
    args = parser.parse_args()

    if args.train and args.data:
        config = load_config()
        df = pd.read_csv(args.data)

        bars: list[OHLCBar] = []
        for _, row in df.iterrows():
            ts = None
            for col in ("timestamp", "date", "Date", "Datetime"):
                if col in row.index:
                    ts = pd.to_datetime(row[col])
                    break
            if ts is None:
                ts = pd.to_datetime(row.iloc[0])

            bars.append(
                OHLCBar(
                    timestamp=ts,
                    open=float(row.get("open", row.get("Open", 0))),
                    high=float(row.get("high", row.get("High", 0))),
                    low=float(row.get("low", row.get("Low", 0))),
                    close=float(row.get("close", row.get("Close", 0))),
                    volume=float(row.get("volume", row.get("Volume", 0))),
                )
            )

        horizon = 12
        feature_vectors: list[FeatureVector] = []
        labels: list[int] = []

        for i in range(200, len(bars) - horizon):
            window = bars[max(0, i - 250) : i + 1]
            if len(window) < 200:
                continue

            indicators = compute_indicators(window)
            patterns = detect_patterns(window[-50:] if len(window) >= 50 else window)
            close = bars[i].close

            fv = FeatureVector(
                indicator_features={
                    "rsi": indicators.rsi / 100.0,
                    "macd_line": indicators.macd_line,
                    "macd_signal": indicators.macd_signal,
                    "macd_hist": indicators.macd_hist,
                    "ema_ratio_20": close / indicators.ema_20
                    if indicators.ema_20
                    else 0.0,
                    "ema_ratio_50": close / indicators.ema_50
                    if indicators.ema_50
                    else 0.0,
                    "ema_ratio_200": close / indicators.ema_200
                    if indicators.ema_200
                    else 0.0,
                    "bb_position": (close - indicators.bb_lower)
                    / (indicators.bb_upper - indicators.bb_lower)
                    if (indicators.bb_upper - indicators.bb_lower) > 0
                    else 0.5,
                    "atr_normalized": indicators.atr / close if close else 0.0,
                },
                pattern_features={
                    "breakout": 0.0,
                    "triangle": 0.0,
                    "double_top": 0.0,
                    "double_bottom": 0.0,
                    "head_shoulders": 0.0,
                    "range": 0.0,
                },
                sentiment_features={
                    "macro_score": 0.0,
                    "headline_count": 0.0,
                    "is_blackout": 0.0,
                },
                prediction_features={
                    "direction_encoded": 0.0,
                    "confidence": 0.0,
                    "volatility": 0.0,
                    "trend_strength": 0.0,
                },
                derived_features={
                    "indicator_agreement": 0.5,
                    "trend_encoded": 1.0
                    if indicators.trend_direction == "bullish"
                    else (-1.0 if indicators.trend_direction == "bearish" else 0.0),
                    "price_vs_support": close / indicators.support
                    if indicators.support
                    else 0.0,
                    "price_vs_resistance": close / indicators.resistance
                    if indicators.resistance
                    else 0.0,
                },
            )

            for pat in patterns.patterns:
                fv.pattern_features[pat.pattern_type] = pat.confidence

            change = (bars[i + horizon].close - bars[i].close) / bars[i].close
            label = 1 if change > 0 else 0

            feature_vectors.append(fv)
            labels.append(label)

        print(f"Generated {len(feature_vectors)} training samples")

        wrapper = XGBoostWrapper(config)
        metrics = wrapper.train(feature_vectors, labels)

        print("XGBoost training complete:")
        for k, v in metrics.items():
            print(f"  {k}: {v}")
    else:
        print("Usage: python -m models.xgboost_model --train --data <csv_path>")
