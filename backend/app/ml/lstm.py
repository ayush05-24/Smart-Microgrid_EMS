from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import MinMaxScaler
from torch import nn
from torch.utils.data import DataLoader, Dataset

from ..config import EMS_DATASET, FORECAST_MODEL_DIR, OUTPUT_DIR, PLOTS_DIR, SCALER_DIR, ensure_project_dirs
from ..gpu import require_cuda_device
from ..utils import write_json


FORECAST_FEATURES = [
    "ghi",
    "dni",
    "diffuse_irradiance",
    "temperature_c",
    "wind_speed_mps",
    "humidity_pct",
    "precipitation_mm",
    "solar_kw",
    "load_kw",
    "tariff_inr_kwh",
    "battery_soc_pct",
    "hour_sin",
    "hour_cos",
    "day_sin",
    "day_cos",
    "load_lag_1h",
    "load_lag_24h",
    "solar_lag_1h",
    "solar_lag_24h",
    "load_roll_3h",
    "load_roll_24h",
    "solar_roll_3h",
    "solar_roll_24h",
]


@dataclass(frozen=True)
class TrainingConfig:
    sequence_length: int = 48
    batch_size: int = 128
    epochs: int = 30
    hidden_size: int = 96
    num_layers: int = 2
    dropout: float = 0.15
    learning_rate: float = 0.001


class SequenceDataset(Dataset):
    def __init__(self, x: np.ndarray, y: np.ndarray, sequence_length: int) -> None:
        self.x = x.astype(np.float32)
        self.y = y.astype(np.float32)
        self.sequence_length = sequence_length

    def __len__(self) -> int:
        return len(self.x) - self.sequence_length

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        end = index + self.sequence_length
        return torch.from_numpy(self.x[index:end]), torch.tensor(self.y[end])


class ForecastLSTM(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int, dropout: float) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.head = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Linear(hidden_size, 48),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(48, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        output, _ = self.lstm(x)
        return self.head(output[:, -1, :]).squeeze(-1)


def train_forecast_model(target_column: str, config: TrainingConfig = TrainingConfig()) -> dict[str, float | str]:
    ensure_project_dirs()
    if target_column not in {"solar_kw", "load_kw"}:
        raise ValueError("target_column must be 'solar_kw' or 'load_kw'")
    if not EMS_DATASET.exists():
        from ..data.synthetic import generate_operational_dataset

        generate_operational_dataset()

    device = require_cuda_device()
    df = pd.read_csv(EMS_DATASET, parse_dates=["timestamp"]).sort_values("timestamp")
    df = df.dropna(subset=FORECAST_FEATURES + [target_column]).reset_index(drop=True)

    train_end = int(len(df) * 0.78)
    val_end = int(len(df) * 0.90)
    train_df = df.iloc[:train_end].copy()
    val_df = df.iloc[train_end:val_end].copy()
    test_df = df.iloc[val_end:].copy()

    x_scaler = MinMaxScaler()
    y_scaler = MinMaxScaler()
    train_x = x_scaler.fit_transform(train_df[FORECAST_FEATURES])
    train_y = y_scaler.fit_transform(train_df[[target_column]]).ravel()
    val_x = x_scaler.transform(val_df[FORECAST_FEATURES])
    val_y = y_scaler.transform(val_df[[target_column]]).ravel()
    test_x = x_scaler.transform(test_df[FORECAST_FEATURES])
    test_y = y_scaler.transform(test_df[[target_column]]).ravel()

    train_loader = DataLoader(
        SequenceDataset(train_x, train_y, config.sequence_length),
        batch_size=config.batch_size,
        shuffle=True,
        drop_last=True,
        pin_memory=True,
    )
    val_loader = DataLoader(
        SequenceDataset(val_x, val_y, config.sequence_length),
        batch_size=config.batch_size,
        shuffle=False,
        pin_memory=True,
    )

    model = ForecastLSTM(
        input_size=len(FORECAST_FEATURES),
        hidden_size=config.hidden_size,
        num_layers=config.num_layers,
        dropout=config.dropout,
    ).to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", patience=4, factor=0.5)

    history: list[dict[str, float]] = []
    best_val = float("inf")
    best_path = FORECAST_MODEL_DIR / f"{target_column}_lstm.pt"

    for epoch in range(1, config.epochs + 1):
        model.train()
        train_losses: list[float] = []
        for batch_x, batch_y in train_loader:
            batch_x = batch_x.to(device, non_blocking=True)
            batch_y = batch_y.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            prediction = model(batch_x)
            loss = criterion(prediction, batch_y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_losses.append(float(loss.detach().cpu()))

        val_loss = _evaluate_loss(model, val_loader, criterion, device)
        scheduler.step(val_loss)
        train_loss = float(np.mean(train_losses))
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})
        if val_loss < best_val:
            best_val = val_loss
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "target_column": target_column,
                    "features": FORECAST_FEATURES,
                    "config": config.__dict__,
                },
                best_path,
            )

    model.load_state_dict(torch.load(best_path, map_location=device)["model_state"])
    metrics = _evaluate_predictions(model, test_x, test_y, test_df, target_column, y_scaler, device, config)
    pd.DataFrame(history).to_csv(OUTPUT_DIR / f"{target_column}_training_history.csv", index=False)
    _plot_loss_curve(history, target_column)

    joblib.dump(x_scaler, SCALER_DIR / f"{target_column}_x_scaler.joblib")
    joblib.dump(y_scaler, SCALER_DIR / f"{target_column}_y_scaler.joblib")
    report = {
        **metrics,
        "model_path": str(best_path),
        "x_scaler": str(SCALER_DIR / f"{target_column}_x_scaler.joblib"),
        "y_scaler": str(SCALER_DIR / f"{target_column}_y_scaler.joblib"),
        "device": str(device),
        "epochs": config.epochs,
        "sequence_length": config.sequence_length,
    }
    write_json(OUTPUT_DIR / f"{target_column}_training_report.json", report)
    return report


def train_all_forecasters(config: TrainingConfig = TrainingConfig()) -> dict[str, dict[str, float | str]]:
    return {
        "solar_kw": train_forecast_model("solar_kw", config),
        "load_kw": train_forecast_model("load_kw", config),
    }


def _evaluate_loss(model: nn.Module, loader: DataLoader, criterion: nn.Module, device: torch.device) -> float:
    model.eval()
    losses: list[float] = []
    with torch.no_grad():
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(device, non_blocking=True)
            batch_y = batch_y.to(device, non_blocking=True)
            losses.append(float(criterion(model(batch_x), batch_y).detach().cpu()))
    return float(np.mean(losses))


def _evaluate_predictions(
    model: nn.Module,
    test_x: np.ndarray,
    test_y: np.ndarray,
    test_df: pd.DataFrame,
    target_column: str,
    y_scaler: MinMaxScaler,
    device: torch.device,
    config: TrainingConfig,
) -> dict[str, float | str]:
    dataset = SequenceDataset(test_x, test_y, config.sequence_length)
    loader = DataLoader(dataset, batch_size=256, shuffle=False, pin_memory=True)
    predictions_scaled: list[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for batch_x, _ in loader:
            batch_x = batch_x.to(device, non_blocking=True)
            predictions_scaled.append(model(batch_x).detach().cpu().numpy())

    prediction_scaled = np.concatenate(predictions_scaled)
    actual_scaled = test_y[config.sequence_length :]
    prediction = y_scaler.inverse_transform(prediction_scaled.reshape(-1, 1)).ravel()
    actual = y_scaler.inverse_transform(actual_scaled.reshape(-1, 1)).ravel()
    timestamps = test_df["timestamp"].iloc[config.sequence_length :].reset_index(drop=True)

    forecast_df = pd.DataFrame(
        {
            "timestamp": timestamps,
            f"{target_column}_actual": actual,
            f"{target_column}_prediction": prediction,
        }
    )
    forecast_df.to_csv(OUTPUT_DIR / f"{target_column}_forecast.csv", index=False)

    fig, ax = plt.subplots(figsize=(13, 5))
    sample = forecast_df.head(24 * 14)
    ax.plot(sample["timestamp"], sample[f"{target_column}_actual"], label="Actual", linewidth=2)
    ax.plot(sample["timestamp"], sample[f"{target_column}_prediction"], label="Predicted", linewidth=2)
    ax.set_title(f"{target_column} LSTM Prediction vs Actual")
    ax.set_ylabel("kW")
    ax.set_xlabel("Timestamp")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / f"{target_column}_prediction_vs_actual.png", dpi=150)
    plt.close(fig)

    rmse = float(np.sqrt(mean_squared_error(actual, prediction)))
    mae = mean_absolute_error(actual, prediction)
    return {
        "rmse_kw": round(float(rmse), 4),
        "mae_kw": round(float(mae), 4),
        "forecast_csv": str(OUTPUT_DIR / f"{target_column}_forecast.csv"),
        "prediction_plot": str(PLOTS_DIR / f"{target_column}_prediction_vs_actual.png"),
    }


def _plot_loss_curve(history: list[dict[str, float]], target_column: str) -> None:
    history_df = pd.DataFrame(history)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(history_df["epoch"], history_df["train_loss"], label="Train loss")
    ax.plot(history_df["epoch"], history_df["val_loss"], label="Validation loss")
    ax.set_title(f"{target_column} LSTM Training Loss")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("MSE")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / f"{target_column}_loss_curve.png", dpi=150)
    plt.close(fig)
