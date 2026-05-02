from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..config import EMS_DATASET, FORECAST_MODEL_DIR, MICROGRID, OUTPUT_DIR
from ..services.live_simulator import live_simulator
from ..utils import rounded_records


def forecast_payload(horizon_hours: int = 24) -> dict[str, object]:
    horizon_hours = int(np.clip(horizon_hours, 1, 168))
    if live_simulator.has_live_data():
        return live_simulator.forecast(horizon_hours)
    if not EMS_DATASET.exists():
        from ..data.synthetic import generate_operational_dataset

        generate_operational_dataset()
    df = pd.read_csv(EMS_DATASET, parse_dates=["timestamp"]).sort_values("timestamp")

    solar = _artifact_or_operational_forecast(df, "solar_kw", horizon_hours)
    load = _artifact_or_operational_forecast(df, "load_kw", horizon_hours)
    merged = solar.merge(load, on="timestamp", how="outer").sort_values("timestamp")
    return {
        "horizon_hours": horizon_hours,
        "model_status": _model_status(),
        "records": rounded_records(merged, 3),
    }


def _artifact_or_operational_forecast(df: pd.DataFrame, target: str, horizon: int) -> pd.DataFrame:
    artifact = OUTPUT_DIR / f"{target}_forecast.csv"
    pred_col = f"{target}_prediction"
    if artifact.exists():
        artifact_df = pd.read_csv(artifact, parse_dates=["timestamp"])
        if pred_col in artifact_df.columns:
            return artifact_df[["timestamp", pred_col]].tail(horizon).rename(columns={pred_col: target})
    return _persistence_forecast(df, target, horizon)


def _persistence_forecast(df: pd.DataFrame, target: str, horizon: int) -> pd.DataFrame:
    history = df[["timestamp", target]].copy()
    history["hour"] = history["timestamp"].dt.hour
    history["day_of_week"] = history["timestamp"].dt.dayofweek
    last_timestamp = history["timestamp"].max()
    future_ts = pd.date_range(last_timestamp + pd.Timedelta(hours=1), periods=horizon, freq="h")
    recent = history.tail(24 * 28)

    values: list[float] = []
    for ts in future_ts:
        same_pattern = recent[(recent["hour"] == ts.hour) & (recent["day_of_week"] == ts.dayofweek)]
        if same_pattern.empty:
            same_pattern = recent[recent["hour"] == ts.hour]
        value = float(same_pattern[target].tail(8).mean())
        if np.isnan(value):
            value = float(recent[target].tail(24).mean())
        if target == "solar_kw":
            value = float(np.clip(value, 0, MICROGRID.pv_capacity_kw))
        else:
            value = float(np.clip(value, MICROGRID.load_min_kw, MICROGRID.load_max_kw))
        values.append(value)

    return pd.DataFrame({"timestamp": future_ts, target: values})


def _model_status() -> dict[str, bool | str]:
    solar_model = FORECAST_MODEL_DIR / "solar_kw_lstm.pt"
    load_model = FORECAST_MODEL_DIR / "load_kw_lstm.pt"
    if solar_model.exists() and load_model.exists():
        source = "lstm_artifacts"
    else:
        source = "operational_persistence_until_gpu_training"
    return {
        "solar_lstm_available": solar_model.exists(),
        "load_lstm_available": load_model.exists(),
        "source": source,
    }
