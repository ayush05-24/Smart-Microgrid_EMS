from __future__ import annotations

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from ..config import (
    BATTERY,
    CLEANED_DATASET,
    EMS_DATASET,
    MICROGRID,
    PLOTS_DIR,
    PROCESSED_DATA_DIR,
    RANDOM_SEED,
    SCALER_DIR,
    SYNTHETIC_DATA_DIR,
    ensure_project_dirs,
)
from ..utils import write_json, write_preview


DERIVED_COLUMNS = [
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "month",
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


def load_cleaned_dataset() -> pd.DataFrame:
    if not CLEANED_DATASET.exists():
        from .cleaning import clean_nasa_power_dataset

        return clean_nasa_power_dataset()
    return pd.read_csv(CLEANED_DATASET, parse_dates=["timestamp", "timestamp_utc"])


def generate_operational_dataset(cleaned: pd.DataFrame | None = None) -> pd.DataFrame:
    ensure_project_dirs()
    rng = np.random.default_rng(RANDOM_SEED)
    df = cleaned.copy() if cleaned is not None else load_cleaned_dataset()
    df = df.sort_values("timestamp").reset_index(drop=True)

    df["solar_kw"] = _generate_solar_power(df)
    df["wind_kw"] = _generate_wind_power(df)
    df["load_kw"] = _generate_load(df, rng)
    df["tariff_inr_kwh"] = _generate_india_tou_tariff(df)
    battery_df = _simulate_safe_battery(df)
    df = pd.concat([df, battery_df], axis=1)
    df = _add_derived_features(df)

    df.to_csv(EMS_DATASET, index=False)
    df.to_csv(SYNTHETIC_DATA_DIR / "synthetic_operational_data.csv", index=False)
    write_preview(df, EMS_DATASET.with_name("ems_dataset_preview.csv"))
    _write_validation_report(df)
    _plot_synthetic_outputs(df)

    scaler = MinMaxScaler()
    train_cols = [
        "ghi",
        "dni",
        "diffuse_irradiance",
        "temperature_c",
        "wind_speed_mps",
        "humidity_pct",
        "precipitation_mm",
        "solar_kw",
        "wind_kw",
        "load_kw",
        "tariff_inr_kwh",
        "battery_soc_pct",
        *DERIVED_COLUMNS,
    ]
    normalized = df.copy()
    normalized[train_cols] = scaler.fit_transform(normalized[train_cols])
    normalized.to_csv(PROCESSED_DATA_DIR / "ems_dataset_normalized.csv", index=False)
    joblib.dump(scaler, SCALER_DIR / "ems_feature_minmax_scaler.joblib")
    return df


def _generate_solar_power(df: pd.DataFrame) -> pd.Series:
    solar_kw = (
        df["ghi"].clip(lower=0)
        / 1000.0
        * MICROGRID.pv_capacity_kw
        * MICROGRID.pv_performance_ratio
    )
    temp_derate = 1.0 - np.maximum(df["temperature_c"] - 25.0, 0.0) * 0.004
    humidity_derate = 1.0 - np.maximum(df["humidity_pct"] - 85.0, 0.0) * 0.001
    solar_kw = solar_kw * temp_derate.clip(0.84, 1.0) * humidity_derate.clip(0.94, 1.0)
    return solar_kw.clip(0, MICROGRID.pv_capacity_kw).round(3)


def _generate_wind_power(df: pd.DataFrame) -> pd.Series:
    ws = df["wind_speed_mps"].to_numpy()
    wind_kw = np.zeros_like(ws)
    mask_active = (ws >= 1.5) & (ws < 8.0)
    wind_kw[mask_active] = MICROGRID.wind_capacity_kw * ((ws[mask_active] - 1.5) / (8.0 - 1.5)) ** 3
    mask_rated = (ws >= 8.0) & (ws <= 20.0)
    wind_kw[mask_rated] = MICROGRID.wind_capacity_kw
    return pd.Series(wind_kw, index=df.index).round(3)


def _generate_load(df: pd.DataFrame, rng: np.random.Generator) -> pd.Series:
    timestamps = pd.to_datetime(df["timestamp"])
    hour = timestamps.dt.hour.to_numpy()
    month = timestamps.dt.month.to_numpy()
    day_of_week = timestamps.dt.dayofweek.to_numpy()

    night_base = 40.0 + 4.0 * np.cos((hour - 2) / 24 * 2 * np.pi)
    daytime_activity = 32.0 * np.exp(-0.5 * ((hour - 14) / 4.2) ** 2)
    morning_peak = 34.0 * np.exp(-0.5 * ((hour - 8) / 1.7) ** 2)
    evening_peak = 48.0 * np.exp(-0.5 * ((hour - 20) / 1.9) ** 2)
    seasonal = np.select(
        [
            np.isin(month, [3, 4, 5, 6]),
            np.isin(month, [11, 12, 1, 2]),
        ],
        [1.16, 0.91],
        default=1.0,
    )
    weekday_factor = np.where(day_of_week >= 5, 0.88, 1.0)
    temp = df["temperature_c"].to_numpy()
    cooling_load = np.maximum(temp - 28.0, 0.0) * 2.2
    humidity_load = np.maximum(df["humidity_pct"].to_numpy() - 80.0, 0.0) * 0.18
    noise = rng.normal(0.0, 3.5, len(df))

    load = (night_base + daytime_activity + morning_peak + evening_peak + cooling_load + humidity_load)
    load = load * seasonal * weekday_factor + noise

    spike_mask = rng.random(len(df)) < 0.012
    spike_magnitude = rng.uniform(12.0, 28.0, len(df))
    load = load + spike_mask * spike_magnitude

    return pd.Series(load).clip(MICROGRID.load_min_kw, MICROGRID.load_max_kw).round(3)


def _generate_india_tou_tariff(df: pd.DataFrame) -> pd.Series:
    hour = pd.to_datetime(df["timestamp"]).dt.hour
    tariff = np.select(
        [
            hour.between(22, 23) | hour.between(0, 5),
            hour.between(18, 21),
        ],
        [2.6, 9.2],
        default=5.6,
    )
    return pd.Series(tariff, index=df.index).round(2)


def _simulate_safe_battery(df: pd.DataFrame) -> pd.DataFrame:
    soc_pct = BATTERY.initial_soc_pct
    soc_values: list[float] = []
    battery_power: list[float] = []
    battery_energy_kwh: list[float] = []
    violations: list[int] = []

    min_energy = BATTERY.capacity_kwh * BATTERY.min_soc_pct / 100.0
    max_energy = BATTERY.capacity_kwh * BATTERY.max_soc_pct / 100.0
    energy = BATTERY.capacity_kwh * soc_pct / 100.0

    for row in df.itertuples(index=False):
        surplus = float(row.solar_kw + row.wind_kw - row.load_kw)
        tariff = float(row.tariff_inr_kwh)
        power = 0.0
        violation = 0

        if surplus > 4.0 and energy < max_energy:
            available_room = (max_energy - energy) / BATTERY.charge_efficiency
            charge_kw = min(surplus, BATTERY.max_charge_kw, available_room)
            energy += charge_kw * BATTERY.charge_efficiency
            power = -charge_kw
        elif tariff >= 8.0 and surplus < -4.0 and energy > min_energy:
            available_energy = (energy - min_energy) * BATTERY.discharge_efficiency
            discharge_kw = min(-surplus, BATTERY.max_discharge_kw, available_energy)
            energy -= discharge_kw / BATTERY.discharge_efficiency
            power = discharge_kw

        if energy < min_energy - 1e-9 or energy > max_energy + 1e-9:
            violation = 1
            energy = float(np.clip(energy, min_energy, max_energy))

        soc_pct = energy / BATTERY.capacity_kwh * 100.0
        soc_values.append(round(soc_pct, 3))
        battery_power.append(round(power, 3))
        battery_energy_kwh.append(round(energy, 3))
        violations.append(violation)

    return pd.DataFrame(
        {
            "battery_soc_pct": soc_values,
            "battery_energy_kwh": battery_energy_kwh,
            "battery_power_kw": battery_power,
            "battery_violation": violations,
        }
    )


def _add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    timestamp = pd.to_datetime(df["timestamp"])
    df["hour_of_day"] = timestamp.dt.hour
    df["day_of_week"] = timestamp.dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["month"] = timestamp.dt.month
    df["hour_sin"] = np.sin(2 * np.pi * df["hour_of_day"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour_of_day"] / 24)
    df["day_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["day_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

    df["load_lag_1h"] = df["load_kw"].shift(1)
    df["load_lag_24h"] = df["load_kw"].shift(24)
    df["solar_lag_1h"] = df["solar_kw"].shift(1)
    df["solar_lag_24h"] = df["solar_kw"].shift(24)
    df["load_roll_3h"] = df["load_kw"].rolling(3, min_periods=1).mean()
    df["load_roll_24h"] = df["load_kw"].rolling(24, min_periods=1).mean()
    df["solar_roll_3h"] = df["solar_kw"].rolling(3, min_periods=1).mean()
    df["solar_roll_24h"] = df["solar_kw"].rolling(24, min_periods=1).mean()
    df[DERIVED_COLUMNS] = df[DERIVED_COLUMNS].bfill().ffill()
    return df


def _write_validation_report(df: pd.DataFrame) -> None:
    report = {
        "rows": int(len(df)),
        "load_kw": {
            "min": round(float(df["load_kw"].min()), 3),
            "max": round(float(df["load_kw"].max()), 3),
            "mean": round(float(df["load_kw"].mean()), 3),
            "constraint_min": MICROGRID.load_min_kw,
            "constraint_max": MICROGRID.load_max_kw,
            "within_limits": bool(df["load_kw"].between(MICROGRID.load_min_kw, MICROGRID.load_max_kw).all()),
        },
        "tariff_inr_kwh": {
            "unique_values": sorted(df["tariff_inr_kwh"].unique().tolist()),
            "off_peak_range": [2.0, 3.0],
            "mid_peak_range": [5.0, 6.0],
            "peak_range": [8.0, 10.0],
        },
        "battery": {
            "capacity_kwh": BATTERY.capacity_kwh,
            "min_soc_pct": BATTERY.min_soc_pct,
            "max_soc_pct": BATTERY.max_soc_pct,
            "roundtrip_efficiency": BATTERY.roundtrip_efficiency,
            "max_charge_kw": BATTERY.max_charge_kw,
            "max_discharge_kw": BATTERY.max_discharge_kw,
            "soc_min_observed": round(float(df["battery_soc_pct"].min()), 3),
            "soc_max_observed": round(float(df["battery_soc_pct"].max()), 3),
            "violations": int(df["battery_violation"].sum()),
            "within_safe_soc": bool(df["battery_soc_pct"].between(BATTERY.min_soc_pct, BATTERY.max_soc_pct).all()),
        },
    }
    write_json(SYNTHETIC_DATA_DIR / "synthetic_validation_report.json", report)


def _plot_synthetic_outputs(df: pd.DataFrame) -> None:
    plot_df = df.set_index("timestamp").iloc[: 24 * 14]

    fig, ax = plt.subplots(figsize=(13, 5))
    plot_df["load_kw"].plot(ax=ax, color="#1f7a4d", label="Load demand")
    plot_df["solar_kw"].plot(ax=ax, color="#f59f00", label="Solar generation")
    plot_df["wind_kw"].plot(ax=ax, color="#0f766e", label="Wind generation")
    ax.set_title("Synthetic Load, Solar, and Wind Generation - First 14 Days")
    ax.set_ylabel("Power (kW)")
    ax.set_xlabel("Timestamp")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "load_curve.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 4))
    plot_df["tariff_inr_kwh"].plot(ax=ax, color="#7c3aed", drawstyle="steps-post")
    ax.set_title("India TOU Tariff Curve - First 14 Days")
    ax.set_ylabel("INR/kWh")
    ax.set_xlabel("Timestamp")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "tariff_curve.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 4))
    plot_df["battery_soc_pct"].plot(ax=ax, color="#0f766e")
    ax.axhline(BATTERY.min_soc_pct, color="#c92a2a", linestyle="--", linewidth=1, label="Min safe SoC")
    ax.axhline(BATTERY.max_soc_pct, color="#c92a2a", linestyle="--", linewidth=1, label="Max safe SoC")
    ax.set_title("Battery SoC Validation - First 14 Days")
    ax.set_ylabel("SoC (%)")
    ax.set_xlabel("Timestamp")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "battery_soc_validation.png", dpi=150)
    plt.close(fig)

