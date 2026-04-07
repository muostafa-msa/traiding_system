from __future__ import annotations

import os
from typing import Callable

import numpy as np
import torch
import torch.nn as nn

from core.config import AppConfig
from core.logger import get_logger
from core.types import OHLCBar, IndicatorResult, PricePrediction
from models.model_manager import ModelManager


def _compute_per_bar_features(bars: list[OHLCBar]) -> np.ndarray:
    import pandas as pd
    import ta as ta_lib

    df = pd.DataFrame(
        [
            {
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars
        ]
    )

    rsi = ta_lib.momentum.RSIIndicator(df["close"], window=14).rsi().fillna(50.0)
    macd_obj = ta_lib.trend.MACD(df["close"])
    macd_line = macd_obj.macd().fillna(0.0)
    macd_sig = macd_obj.macd_signal().fillna(0.0)
    macd_hist = macd_obj.macd_diff().fillna(0.0)
    e20 = ta_lib.trend.ema_indicator(df["close"], window=20).fillna(df["close"])
    e50 = ta_lib.trend.ema_indicator(df["close"], window=50).fillna(df["close"])
    e200 = ta_lib.trend.ema_indicator(df["close"], window=200).fillna(df["close"])
    bb_obj = ta_lib.volatility.BollingerBands(df["close"], window=20, window_dev=2)
    bb_up = bb_obj.bollinger_hband().fillna(df["close"])
    bb_lo = bb_obj.bollinger_lband().fillna(df["close"])
    atr_s = (
        ta_lib.volatility.AverageTrueRange(
            df["high"], df["low"], df["close"], window=14
        )
        .average_true_range()
        .fillna(0.0)
    )

    features = np.zeros((len(bars), INPUT_FEATURES), dtype=np.float32)
    for i in range(len(bars)):
        c = float(df["close"].iloc[i])
        bb_range = float(bb_up.iloc[i]) - float(bb_lo.iloc[i])
        bb_pos = (c - float(bb_lo.iloc[i])) / bb_range if bb_range > 0 else 0.5

        features[i] = [
            float(df["open"].iloc[i]),
            float(df["high"].iloc[i]),
            float(df["low"].iloc[i]),
            c,
            float(rsi.iloc[i]) / 100.0,
            float(macd_line.iloc[i]),
            float(macd_sig.iloc[i]),
            float(macd_hist.iloc[i]),
            c / float(e20.iloc[i]) if float(e20.iloc[i]) != 0 else 1.0,
            c / float(e50.iloc[i]) if float(e50.iloc[i]) != 0 else 1.0,
            c / float(e200.iloc[i]) if float(e200.iloc[i]) != 0 else 1.0,
            bb_pos,
            float(atr_s.iloc[i]) / c if c > 0 else 0.0,
            float(df["volume"].iloc[i]),
            0.0,
        ]

    return features


logger = get_logger(__name__)

INPUT_FEATURES = 15
OUTPUT_DIM = 3


class LSTMNet(nn.Module):
    def __init__(
        self,
        input_size: int = INPUT_FEATURES,
        hidden_size: int = 64,
        num_layers: int = 1,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, OUTPUT_DIM)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        lstm_out, _ = self.lstm(x)
        last_step = lstm_out[:, -1, :]
        dropped = self.dropout(last_step)
        output = self.fc(dropped)
        return output


def prepare_features_from_bar(bar: OHLCBar, indicators: IndicatorResult) -> list[float]:
    return [
        bar.open,
        bar.high,
        bar.low,
        bar.close,
        indicators.rsi / 100.0,
        indicators.macd_line,
        indicators.macd_signal,
        indicators.macd_hist,
        bar.close / indicators.ema_20 if indicators.ema_20 else 0.0,
        bar.close / indicators.ema_50 if indicators.ema_50 else 0.0,
        bar.close / indicators.ema_200 if indicators.ema_200 else 0.0,
        _bb_pos(indicators, bar.close),
        indicators.atr / bar.close if bar.close else 0.0,
        bar.volume,
        indicators.breakout_probability,
    ]


def _bb_pos(indicators: IndicatorResult, close: float) -> float:
    bb_range = indicators.bb_upper - indicators.bb_lower
    if bb_range <= 0:
        return 0.5
    return (close - indicators.bb_lower) / bb_range


def build_sequences(
    bars: list[OHLCBar],
    indicators: IndicatorResult,
    seq_length: int,
) -> np.ndarray | None:
    if len(bars) < seq_length:
        return None
    window = bars[-seq_length:]
    features = []
    for bar in window:
        features.append(prepare_features_from_bar(bar, indicators))
    return np.array(features, dtype=np.float32)


def _parse_output(raw: np.ndarray, direction_threshold: float) -> PricePrediction:
    direction_logit = float(raw[0])
    volatility = max(0.0, float(raw[1]))
    trend_strength = max(0.0, min(1.0, float(raw[2])))

    if direction_logit > direction_threshold:
        direction = "BUY"
        confidence = min(direction_logit, 1.0)
    elif direction_logit < -direction_threshold:
        direction = "SELL"
        confidence = min(abs(direction_logit), 1.0)
    else:
        direction = "NEUTRAL"
        confidence = 1.0 - abs(direction_logit)

    confidence = max(0.0, min(1.0, confidence))

    return PricePrediction(
        direction=direction,
        confidence=confidence,
        volatility=volatility,
        trend_strength=trend_strength,
        horizon_bars=12,
    )


def _neutral_prediction() -> PricePrediction:
    return PricePrediction(
        direction="NEUTRAL",
        confidence=0.0,
        volatility=0.0,
        trend_strength=0.0,
        horizon_bars=12,
    )


class LSTMWrapper:
    def __init__(self, config: AppConfig, model_manager: ModelManager):
        self._config = config
        self._model_manager = model_manager
        self._model: LSTMNet | None = None
        self._device = model_manager.detect_device()
        self._load_if_available()

    def _load_if_available(self) -> None:
        model_dir = self._config.lstm_model_path
        model_file = os.path.join(model_dir, "lstm.pt")
        if not os.path.exists(model_file):
            logger.info("No trained LSTM model found at %s", model_file)
            return
        try:
            self._model = LSTMNet().to(self._device)
            state_dict = torch.load(
                model_file, map_location=self._device, weights_only=True
            )
            self._model.load_state_dict(state_dict)
            self._model.eval()
            logger.info("LSTM model loaded from %s", model_file)
        except Exception as e:
            logger.warning("Failed to load LSTM model: %s", e)
            self._model = None

    def predict(
        self, bars: list[OHLCBar], indicators: IndicatorResult
    ) -> PricePrediction:
        if not self.is_trained():
            logger.debug("LSTM not trained, returning neutral prediction")
            return _neutral_prediction()

        seq_length = self._config.lstm_sequence_length
        sequences = build_sequences(bars, indicators, seq_length)
        if sequences is None:
            logger.warning(
                "Insufficient data for LSTM: %d bars, need %d", len(bars), seq_length
            )
            return _neutral_prediction()

        try:
            input_tensor = torch.tensor(sequences, dtype=torch.float32).unsqueeze(0)
            input_tensor = input_tensor.to(self._device)

            with torch.no_grad():
                output = self._model(input_tensor)
                raw = output.cpu().numpy()[0]

            return _parse_output(raw, self._config.lstm_direction_threshold)
        except Exception as e:
            logger.warning("LSTM prediction failed: %s", e)
            return _neutral_prediction()

    def train(self, bars: list[OHLCBar], indicators_fn: Callable) -> dict:
        seq_length = self._config.lstm_sequence_length
        horizon = 12
        min_bars = seq_length + horizon + 10

        if len(bars) < min_bars:
            raise ValueError(
                f"Need at least {min_bars} bars for training, got {len(bars)}"
            )

        per_bar_features = _compute_per_bar_features(bars)

        X_list: list[np.ndarray] = []
        y_list: list[list[float]] = []

        for i in range(seq_length, len(bars) - horizon):
            seq = per_bar_features[i - seq_length : i]

            current_close = bars[i].close
            future_close = bars[i + horizon].close
            change = (future_close - current_close) / current_close

            threshold = 0.001
            if change > threshold:
                direction = 1.0
            elif change < -threshold:
                direction = -1.0
            else:
                direction = 0.0

            returns: list[float] = []
            for j in range(i, min(i + horizon, len(bars) - 1)):
                ret = (bars[j + 1].close - bars[j].close) / bars[j].close
                returns.append(ret)
            volatility = float(np.std(returns)) if returns else 0.0

            total_path = sum(abs(r) for r in returns)
            trend = min(abs(change) / total_path, 1.0) if total_path > 0 else 0.0

            X_list.append(seq)
            y_list.append([direction, volatility, trend])

        if not X_list:
            raise ValueError("Could not create any training samples from provided data")

        X = torch.tensor(np.array(X_list), dtype=torch.float32)
        y = torch.tensor(np.array(y_list), dtype=torch.float32)

        split = int(len(X) * 0.8)
        X_train, y_train = X[:split], y[:split]
        X_val, y_val = X[split:], y[split:]

        model = LSTMNet().to(self._device)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        criterion = nn.MSELoss()

        best_val_loss = float("inf")
        patience_counter = 0
        best_state: dict | None = None
        epoch_reached = 0

        for epoch in range(100):
            model.train()
            perm = torch.randperm(len(X_train))
            for start in range(0, len(X_train), 32):
                idx = perm[start : start + 32]
                batch_X = X_train[idx].to(self._device)
                batch_y = y_train[idx].to(self._device)
                optimizer.zero_grad()
                pred = model(batch_X)
                loss = criterion(pred, batch_y)
                loss.backward()
                optimizer.step()

            model.eval()
            with torch.no_grad():
                val_pred = model(X_val.to(self._device))
                val_loss = float(criterion(val_pred, y_val.to(self._device)))

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            else:
                patience_counter += 1
                if patience_counter >= 10:
                    break

            epoch_reached = epoch + 1

        if best_state is not None:
            model.load_state_dict(best_state)
        model.eval()

        model_dir = self._config.lstm_model_path
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, "lstm.pt")
        torch.save(model.state_dict(), model_path)

        self._model = model

        return {
            "epochs_trained": epoch_reached,
            "best_val_loss": best_val_loss,
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "model_path": model_path,
        }

    def is_trained(self) -> bool:
        return self._model is not None


if __name__ == "__main__":
    import argparse

    import pandas as pd

    from analysis.indicators import compute_indicators
    from core.config import load_config

    parser = argparse.ArgumentParser(description="LSTM model training")
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

        mm = ModelManager(config)
        wrapper = LSTMWrapper(config, mm)
        metrics = wrapper.train(bars, compute_indicators)

        print("LSTM training complete:")
        for k, v in metrics.items():
            print(f"  {k}: {v}")
    else:
        print("Usage: python -m models.lstm_model --train --data <csv_path>")
