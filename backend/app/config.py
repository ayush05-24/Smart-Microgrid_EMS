from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
SYNTHETIC_DATA_DIR = DATA_DIR / "synthetic"
OUTPUT_DIR = DATA_DIR / "outputs"
PLOTS_DIR = OUTPUT_DIR / "plots"
EXPORT_DIR = DATA_DIR / "exports"
REPORT_DIR = DATA_DIR / "reports"
MODEL_DIR = PROJECT_ROOT / "models"
FORECAST_MODEL_DIR = MODEL_DIR / "forecast"
PPO_MODEL_DIR = MODEL_DIR / "ppo"
SCALER_DIR = MODEL_DIR / "scalers"

RAW_DATASET = RAW_DATA_DIR / "Dataset_5yrs.csv"
CLEANED_DATASET = PROCESSED_DATA_DIR / "cleaned_nasa_power.csv"
NORMALIZED_DATASET = PROCESSED_DATA_DIR / "cleaned_nasa_power_normalized.csv"
EMS_DATASET = PROCESSED_DATA_DIR / "ems_dataset.csv"

LOCAL_TIMEZONE = "Asia/Kolkata"
RANDOM_SEED = 42


@dataclass(frozen=True)
class BatteryConfig:
    capacity_kwh: float = 180.0
    min_soc_pct: float = 20.0
    max_soc_pct: float = 90.0
    initial_soc_pct: float = 55.0
    roundtrip_efficiency: float = 0.93
    max_charge_kw: float = 55.0
    max_discharge_kw: float = 58.0
    degradation_cost_inr_per_kwh: float = 0.08

    @property
    def charge_efficiency(self) -> float:
        return self.roundtrip_efficiency**0.5

    @property
    def discharge_efficiency(self) -> float:
        return self.roundtrip_efficiency**0.5


@dataclass(frozen=True)
class MicrogridConfig:
    pv_capacity_kw: float = 140.0
    pv_performance_ratio: float = 0.82
    wind_capacity_kw: float = 30.0
    load_min_kw: float = 24.0
    load_max_kw: float = 175.0
    peak_load_risk_kw: float = 145.0
    renewable_drop_kw: float = 28.0
    forecast_horizon_hours: int = 24



BATTERY = BatteryConfig()
MICROGRID = MicrogridConfig()


def ensure_project_dirs() -> None:
    for path in (
        RAW_DATA_DIR,
        PROCESSED_DATA_DIR,
        SYNTHETIC_DATA_DIR,
        OUTPUT_DIR,
        PLOTS_DIR,
        EXPORT_DIR,
        REPORT_DIR,
        FORECAST_MODEL_DIR,
        PPO_MODEL_DIR,
        SCALER_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
