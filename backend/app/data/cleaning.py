from __future__ import annotations

from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from ..config import (
    CLEANED_DATASET,
    LOCAL_TIMEZONE,
    NORMALIZED_DATASET,
    PLOTS_DIR,
    RAW_DATASET,
    SCALER_DIR,
    ensure_project_dirs,
)
from ..utils import write_json, write_preview


NASA_COLUMN_MAP = {
    "YEAR": "year",
    "MO": "month",
    "DY": "day",
    "HR": "hour",
    "ALLSKY_SFC_SW_DWN": "ghi",
    "ALLSKY_SFC_SW_DNI": "dni",
    "ALLSKY_SFC_SW_DIFF": "diffuse_irradiance",
    "T2M": "temperature_c",
    "WS10M": "wind_speed_mps",
    "RH2M": "humidity_pct",
    "PRECTOTCORR": "precipitation_mm",
}

FEATURE_COLUMNS = [
    "ghi",
    "dni",
    "diffuse_irradiance",
    "temperature_c",
    "wind_speed_mps",
    "humidity_pct",
    "precipitation_mm",
]


def _power_header_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8") as csv_file:
        for index, line in enumerate(csv_file):
            if line.strip() == "-END HEADER-":
                return index + 1
    return 0


def load_raw_nasa_power(path: Path = RAW_DATASET) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"NASA POWER CSV not found at {path}")

    skiprows = _power_header_rows(path)
    raw = pd.read_csv(path, skiprows=skiprows)
    raw = raw.rename(columns=NASA_COLUMN_MAP)
    missing_columns = sorted(set(NASA_COLUMN_MAP.values()) - set(raw.columns))
    if missing_columns:
        raise ValueError(f"Missing expected NASA POWER columns: {missing_columns}")
    return raw


def clean_nasa_power_dataset(path: Path = RAW_DATASET) -> pd.DataFrame:
    ensure_project_dirs()
    df = load_raw_nasa_power(path)

    df = df.replace(-999, np.nan)
    timestamp_utc = pd.to_datetime(
        {
            "year": df["year"].astype(int),
            "month": df["month"].astype(int),
            "day": df["day"].astype(int),
            "hour": df["hour"].astype(int),
        },
        utc=True,
    )
    df.insert(0, "timestamp_utc", timestamp_utc)
    df.insert(1, "timestamp", timestamp_utc.dt.tz_convert(LOCAL_TIMEZONE).dt.tz_localize(None))

    df = df[["timestamp", "timestamp_utc", *FEATURE_COLUMNS]]
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    df = df.set_index("timestamp")

    numeric_cols = FEATURE_COLUMNS
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    df[numeric_cols] = df[numeric_cols].interpolate(method="time", limit_direction="both")
    df[numeric_cols] = df[numeric_cols].ffill().bfill()

    df["ghi"] = df["ghi"].clip(0, 1100)
    df["dni"] = df["dni"].clip(0, 1100)
    df["diffuse_irradiance"] = df["diffuse_irradiance"].clip(0, 900)
    df["temperature_c"] = df["temperature_c"].clip(-5, 55)
    df["wind_speed_mps"] = df["wind_speed_mps"].clip(0, 35)
    df["humidity_pct"] = df["humidity_pct"].clip(0, 100)
    df["precipitation_mm"] = df["precipitation_mm"].clip(0, 300)

    cleaned = df.reset_index()
    cleaned.to_csv(CLEANED_DATASET, index=False)
    write_preview(cleaned, CLEANED_DATASET.with_name("cleaned_preview.csv"))

    scaler = MinMaxScaler()
    normalized = cleaned.copy()
    normalized[FEATURE_COLUMNS] = scaler.fit_transform(cleaned[FEATURE_COLUMNS])
    normalized.to_csv(NORMALIZED_DATASET, index=False)
    joblib.dump(scaler, SCALER_DIR / "nasa_feature_minmax_scaler.joblib")

    _plot_cleaned_dataset(cleaned)
    _write_cleaning_report(cleaned)
    return cleaned


def _plot_cleaned_dataset(df: pd.DataFrame) -> None:
    plot_df = df.set_index("timestamp")
    daily = plot_df[FEATURE_COLUMNS].resample("D").mean()

    fig, ax = plt.subplots(figsize=(13, 5))
    daily[["ghi", "dni", "diffuse_irradiance"]].rolling(7).mean().plot(ax=ax)
    ax.set_title("Solar Irradiance Trends - 7 Day Rolling Mean")
    ax.set_ylabel("Irradiance (Wh/m2)")
    ax.set_xlabel("Date")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "solar_trends.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 5))
    daily["temperature_c"].rolling(7).mean().plot(ax=ax, color="#d9480f")
    ax.set_title("Temperature Trend - 7 Day Rolling Mean")
    ax.set_ylabel("Temperature (C)")
    ax.set_xlabel("Date")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "temperature_trends.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 5))
    daily["wind_speed_mps"].rolling(7).mean().plot(ax=ax, color="#0f766e")
    ax.set_title("Wind Speed Trend - 7 Day Rolling Mean")
    ax.set_ylabel("Wind Speed (m/s)")
    ax.set_xlabel("Date")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "wind_trends.png", dpi=150)
    plt.close(fig)


def _write_cleaning_report(df: pd.DataFrame) -> None:
    report = {
        "rows": int(len(df)),
        "start_timestamp": df["timestamp"].min(),
        "end_timestamp": df["timestamp"].max(),
        "duplicate_timestamps": int(df["timestamp"].duplicated().sum()),
        "missing_values_after_cleaning": df[FEATURE_COLUMNS].isna().sum().to_dict(),
        "feature_ranges": {
            column: {
                "min": round(float(df[column].min()), 4),
                "max": round(float(df[column].max()), 4),
                "mean": round(float(df[column].mean()), 4),
            }
            for column in FEATURE_COLUMNS
        },
        "outputs": {
            "cleaned_csv": str(CLEANED_DATASET),
            "normalized_csv": str(NORMALIZED_DATASET),
            "plots": [
                str(PLOTS_DIR / "solar_trends.png"),
                str(PLOTS_DIR / "temperature_trends.png"),
                str(PLOTS_DIR / "wind_trends.png"),
            ],
        },
    }
    write_json(CLEANED_DATASET.with_name("cleaning_report.json"), report)

