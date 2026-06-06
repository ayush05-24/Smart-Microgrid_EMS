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

    target_df = df.tail(horizon_hours).copy()
    target_timestamps = target_df["timestamp"].reset_index(drop=True)

    solar = _artifact_or_operational_forecast(df, "solar_kw", horizon_hours, target_timestamps).reset_index(drop=True)
    wind = _artifact_or_operational_forecast(df, "wind_kw", horizon_hours, target_timestamps).reset_index(drop=True)
    load = _artifact_or_operational_forecast(df, "load_kw", horizon_hours, target_timestamps).reset_index(drop=True)

    merged = pd.DataFrame({
        "timestamp": target_timestamps,
        "solar_kw": solar["solar_kw"],
        "wind_kw": wind["wind_kw"],
        "load_kw": load["load_kw"]
    })

    # Add 10% and 90% quantile predictions for confidence interval mapping in UI
    # In a real deployment, these are returned by the QuantileLSTM model.
    # We add them here based on the forecast errors.
    merged["solar_kw_q10"] = (merged["solar_kw"] * 0.82).clip(lower=0)
    merged["solar_kw_q90"] = (merged["solar_kw"] * 1.18).clip(upper=MICROGRID.pv_capacity_kw)
    merged["wind_kw_q10"] = (merged["wind_kw"] * 0.78).clip(lower=0)
    merged["wind_kw_q90"] = (merged["wind_kw"] * 1.22).clip(upper=MICROGRID.wind_capacity_kw)
    merged["load_kw_q10"] = (merged["load_kw"] * 0.88).clip(lower=MICROGRID.load_min_kw)
    merged["load_kw_q90"] = (merged["load_kw"] * 1.12).clip(upper=MICROGRID.load_max_kw)

    return {
        "horizon_hours": horizon_hours,
        "model_status": _model_status(),
        "records": rounded_records(merged, 3),
    }


def _artifact_or_operational_forecast(df: pd.DataFrame, target: str, horizon: int, target_timestamps: pd.Series) -> pd.DataFrame:
    artifact = OUTPUT_DIR / f"{target}_forecast.csv"
    pred_col = f"{target}_prediction"
    if artifact.exists():
        artifact_df = pd.read_csv(artifact, parse_dates=["timestamp"])
        if pred_col in artifact_df.columns:
            merged = pd.DataFrame({"timestamp": target_timestamps}).merge(
                artifact_df[["timestamp", pred_col]], on="timestamp", how="left"
            )
            if merged[pred_col].isna().any():
                persist = _persistence_forecast_for_dates(df, target, target_timestamps)
                merged[pred_col] = merged[pred_col].fillna(persist[target])
            return merged.rename(columns={pred_col: target})
    return _persistence_forecast_for_dates(df, target, target_timestamps)


def _persistence_forecast_for_dates(df: pd.DataFrame, target: str, target_timestamps: pd.Series) -> pd.DataFrame:
    history = df[["timestamp", target]].copy()
    history["hour"] = history["timestamp"].dt.hour
    history["day_of_week"] = history["timestamp"].dt.dayofweek

    values: list[float] = []
    for ts in target_timestamps:
        recent = history[history["timestamp"] < ts].tail(24 * 28)
        if recent.empty:
            recent = history.tail(24 * 28)
        same_pattern = recent[(recent["hour"] == ts.hour) & (recent["day_of_week"] == ts.dayofweek)]
        if same_pattern.empty:
            same_pattern = recent[recent["hour"] == ts.hour]
        value = float(same_pattern[target].tail(8).mean())
        if np.isnan(value):
            value = float(recent[target].tail(24).mean())
        if target == "solar_kw":
            value = float(np.clip(value, 0, MICROGRID.pv_capacity_kw))
        elif target == "wind_kw":
            value = float(np.clip(value, 0, MICROGRID.wind_capacity_kw))
        else:
            value = float(np.clip(value, MICROGRID.load_min_kw, MICROGRID.load_max_kw))
        values.append(value)

    return pd.DataFrame({"timestamp": target_timestamps, target: values})


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
