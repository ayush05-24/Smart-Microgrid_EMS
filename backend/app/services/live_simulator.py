from __future__ import annotations

import json
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ..config import BATTERY, DATA_DIR, LOCAL_TIMEZONE, MICROGRID, EMS_DATASET
from ..utils import rounded_records


LIVE_DIR = DATA_DIR / "runtime"
LIVE_JSONL = LIVE_DIR / "live_telemetry.jsonl"


@dataclass
class LiveConfig:
    interval_seconds: float = 1.5
    max_records: int = 720
    seed: int = 20260428


class LiveTelemetrySimulator:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: deque[dict[str, Any]] = deque(maxlen=720)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False
        self._config = LiveConfig()
        self._rng = np.random.default_rng(self._config.seed)
        self._soc_pct = BATTERY.initial_soc_pct
        self._cloud_factor = 0.88
        self._override_mode = "auto"
        self._tick = 0

    def start(self, interval_seconds: float = 1.5, reset: bool = False) -> dict[str, Any]:
        with self._lock:
            self._config.interval_seconds = float(np.clip(interval_seconds, 0.5, 30.0))
            self._records = deque(self._records, maxlen=self._config.max_records)
            if reset or not self._records:
                self._records.clear()
                try:
                    import pandas as pd
                    if EMS_DATASET.exists():
                        hist_df = pd.read_csv(EMS_DATASET)
                        if not hist_df.empty:
                            hist_df["dt"] = pd.to_datetime(hist_df["timestamp"])
                            tz = ZoneInfo(LOCAL_TIMEZONE)
                            target_start = datetime(2025, 12, 25, 0, 0, 0)
                            preceding_df = hist_df[hist_df["dt"] < target_start].tail(24)
                            for _, row in preceding_df.iterrows():
                                dt_naive = pd.to_datetime(row["timestamp"])
                                dt_local = dt_naive.replace(tzinfo=tz)
                                ts_str = dt_local.isoformat()
                                ts_utc_str = dt_local.astimezone(timezone.utc).isoformat()
                                solar_val = float(row["solar_kw"])
                                wind_val = float(row["wind_kw"])
                                load_val = float(row["load_kw"])
                                batt_power = float(row.get("battery_power_kw", 0.0))
                                grid_val = max(load_val - solar_val - wind_val - max(batt_power, 0.0) + max(-batt_power, 0.0), 0.0)
                                record = {
                                    "timestamp": ts_str,
                                    "timestamp_utc": ts_utc_str,
                                    "time": ts_str,
                                    "ghi": float(row.get("ghi", 0.0)),
                                    "dni": float(row.get("dni", 0.0)),
                                    "diffuse_irradiance": float(row.get("diffuse_irradiance", 0.0)),
                                    "temperature_c": float(row.get("temperature_c", 20.0)),
                                    "wind_speed_mps": float(row.get("wind_speed_mps", 0.0)),
                                    "humidity_pct": float(row.get("humidity_pct", 50.0)),
                                    "precipitation_mm": float(row.get("precipitation_mm", 0.0)),
                                    "solar_kw": solar_val,
                                    "wind_kw": wind_val,
                                    "load_kw": load_val,
                                    "tariff_inr_kwh": float(row["tariff_inr_kwh"]),
                                    "battery_soc_pct": float(row["battery_soc_pct"]),
                                    "battery_energy_kwh": float(row.get("battery_energy_kwh", BATTERY.capacity_kwh * float(row["battery_soc_pct"]) / 100.0)),
                                    "battery_power_kw": batt_power,
                                    "battery_violation": int(row.get("battery_violation", 0)),
                                    "grid_kw": grid_val,
                                    "load_shed_kw": float(row.get("load_shed_kw", 0.0)),
                                    "operator_action": row.get("operator_action", "idle"),
                                    "override_mode": row.get("override_mode", "auto"),
                                }
                                self._records.append(record)
                            last_row = preceding_df.iloc[-1] if not preceding_df.empty else hist_df.iloc[-1]
                            self._soc_pct = float(last_row["battery_soc_pct"])
                except Exception as e:
                    import sys
                    print(f"Pre-population failed: {e}", file=sys.stderr)
                    self._soc_pct = BATTERY.initial_soc_pct
                self._cloud_factor = 0.88
                self._tick = 0
            if self._running:
                return self.status()
            LIVE_DIR.mkdir(parents=True, exist_ok=True)
            self._stop_event.clear()
            self._running = True
            self._thread = threading.Thread(target=self._run, name="microgrid-live-simulator", daemon=True)
            self._thread.start()
            return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._running = False
            self._stop_event.set()
            return self.status()

    def set_override(self, mode: str) -> dict[str, Any]:
        mode = mode.strip().lower()
        if mode not in {"auto", "force_charge", "force_discharge", "island"}:
            raise ValueError("override mode must be auto, force_charge, force_discharge, or island")
        with self._lock:
            self._override_mode = mode
            return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            latest = self._records[-1] if self._records else None
            return {
                "running": self._running,
                "interval_seconds": self._config.interval_seconds,
                "records": len(self._records),
                "override_mode": self._override_mode,
                "jsonl_path": str(LIVE_JSONL),
                "latest": latest,
            }

    def has_live_data(self) -> bool:
        with self._lock:
            return self._running and bool(self._records)

    def window(self, count: int) -> pd.DataFrame:
        with self._lock:
            records = list(self._records)[-max(int(count), 1) :]
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed")
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, format="mixed")
        return df.reset_index(drop=True)

    def snapshot(self, count: int = 120) -> dict[str, Any]:
        df = self.window(count)
        return {
            **self.status(),
            "records_window": rounded_records(df, 3) if not df.empty else [],
        }

    def forecast(self, horizon: int = 24) -> dict[str, Any]:
        horizon = int(np.clip(horizon, 1, 168))
        now_row = self._latest_or_generate()
        start = pd.to_datetime(now_row["timestamp"])
        soc_pct = float(now_row["battery_soc_pct"])
        records: list[dict[str, Any]] = []
        cloud = self._cloud_factor
        for step in range(1, horizon + 1):
            ts = start + pd.Timedelta(minutes=15 * step)
            cloud = float(np.clip(cloud + self._rng.normal(0, 0.025), 0.38, 1.05))
            solar = self._solar_kw(ts, cloud)
            wind_speed = float(np.clip(2.8 + 1.4 * math.sin(ts.hour / 24 * 2 * math.pi) + self._rng.normal(0, 0.45), 0.2, 11))
            wind = 0.0
            if 1.5 <= wind_speed < 8.0:
                wind = MICROGRID.wind_capacity_kw * ((wind_speed - 1.5) / (8.0 - 1.5)) ** 3
            elif 8.0 <= wind_speed <= 20.0:
                wind = MICROGRID.wind_capacity_kw
            load = self._load_kw(ts, solar) + self._rng.normal(0, 1.2)
            tariff = self._tariff(ts)
            records.append(
                {
                    "timestamp": ts.isoformat(),
                    "time": ts.isoformat(),
                    "solar_kw": round(float(np.clip(solar, 0, MICROGRID.pv_capacity_kw)), 3),
                    "wind_kw": round(float(np.clip(wind, 0, MICROGRID.wind_capacity_kw)), 3),
                    "load_kw": round(float(np.clip(load, MICROGRID.load_min_kw, MICROGRID.load_max_kw)), 3),
                    "battery_soc_pct": round(soc_pct, 3),
                    "tariff_inr_kwh": round(tariff, 2),
                }
            )
        return {"horizon_hours": horizon, "model_status": {"source": "live_simulator"}, "records": records}

    def _run(self) -> None:
        while not self._stop_event.is_set():
            record = self._generate_record()
            with self._lock:
                self._records.append(record)
            self._append_record(record)
            self._stop_event.wait(self._config.interval_seconds)

    def _latest_or_generate(self) -> dict[str, Any]:
        with self._lock:
            if self._records:
                return self._records[-1]
        return self._generate_record()

    def _generate_record(self) -> dict[str, Any]:
        tz = ZoneInfo(LOCAL_TIMEZONE)
        # Advance simulation time by 1 hour on each tick to speed up time and show dynamic load/tariff cycles
        start_time = datetime(2025, 12, 25, 0, 0, 0, tzinfo=tz)
        timestamp = start_time + pd.Timedelta(hours=self._tick)
        self._tick += 1
        self._cloud_factor = float(np.clip(self._cloud_factor + self._rng.normal(0, 0.035), 0.32, 1.08))

        temperature_c = self._temperature(timestamp)
        humidity_pct = float(np.clip(72 + 18 * math.sin((timestamp.hour + 2) / 24 * 2 * math.pi) + self._rng.normal(0, 4), 35, 99))
        wind_speed_mps = float(np.clip(2.8 + 1.4 * math.sin(timestamp.hour / 24 * 2 * math.pi) + self._rng.normal(0, 0.45), 0.2, 11))
        precipitation_mm = float(max(0, self._rng.normal(1.5 if humidity_pct > 88 else 0.08, 0.35)))

        solar_kw = self._solar_kw(timestamp, self._cloud_factor)
        wind_kw = 0.0
        if 1.5 <= wind_speed_mps < 8.0:
            wind_kw = MICROGRID.wind_capacity_kw * ((wind_speed_mps - 1.5) / (8.0 - 1.5)) ** 3
        elif 8.0 <= wind_speed_mps <= 20.0:
            wind_kw = MICROGRID.wind_capacity_kw

        load_kw = self._load_kw(timestamp, solar_kw, temperature_c, humidity_pct)
        tariff = self._tariff(timestamp)
        dispatch = self._battery_dispatch(solar_kw, wind_kw, load_kw, tariff)

        grid_kw = max(load_kw - solar_kw - wind_kw - max(dispatch["battery_power_kw"], 0.0) + max(-dispatch["battery_power_kw"], 0.0), 0.0)
        load_shed_kw = 0.0
        if self._override_mode == "island":
            available_supply = solar_kw + wind_kw + max(dispatch["battery_power_kw"], 0.0)
            load_shed_kw = max(load_kw - available_supply, 0.0)
            grid_kw = 0.0

        return {
            "timestamp": timestamp.isoformat(),
            "timestamp_utc": timestamp.astimezone(timezone.utc).isoformat(),
            "time": timestamp.isoformat(),
            "ghi": round(max(solar_kw / max(MICROGRID.pv_capacity_kw * MICROGRID.pv_performance_ratio, 1) * 1000, 0), 3),
            "dni": round(max(solar_kw / max(MICROGRID.pv_capacity_kw, 1) * 980, 0), 3),
            "diffuse_irradiance": round(max(solar_kw / max(MICROGRID.pv_capacity_kw, 1) * 420, 0), 3),
            "temperature_c": round(temperature_c, 3),
            "wind_speed_mps": round(wind_speed_mps, 3),
            "humidity_pct": round(humidity_pct, 3),
            "precipitation_mm": round(precipitation_mm, 3),
            "solar_kw": round(solar_kw, 3),
            "wind_kw": round(wind_kw, 3),
            "load_kw": round(load_kw, 3),
            "tariff_inr_kwh": round(tariff, 2),
            "battery_soc_pct": round(self._soc_pct, 3),
            "battery_energy_kwh": round(BATTERY.capacity_kwh * self._soc_pct / 100.0, 3),
            "battery_power_kw": round(dispatch["battery_power_kw"], 3),
            "battery_violation": 0,
            "grid_kw": round(grid_kw, 3),
            "load_shed_kw": round(load_shed_kw, 3),
            "operator_action": dispatch["action"],
            "override_mode": self._override_mode,
            "hour_of_day": timestamp.hour,
            "day_of_week": timestamp.weekday(),
            "is_weekend": int(timestamp.weekday() >= 5),
            "month": timestamp.month,
            "hour_sin": math.sin(2 * math.pi * timestamp.hour / 24),
            "hour_cos": math.cos(2 * math.pi * timestamp.hour / 24),
            "day_sin": math.sin(2 * math.pi * timestamp.weekday() / 7),
            "day_cos": math.cos(2 * math.pi * timestamp.weekday() / 7),
        }

    def _temperature(self, timestamp: datetime) -> float:
        seasonal = 3.5 * math.sin((timestamp.timetuple().tm_yday - 75) / 365 * 2 * math.pi)
        daytime = 5.2 * math.sin((timestamp.hour - 8) / 24 * 2 * math.pi)
        return float(np.clip(27.0 + seasonal + daytime + self._rng.normal(0, 0.8), 18, 43))

    def _solar_kw(self, timestamp: datetime | pd.Timestamp, cloud_factor: float) -> float:
        hour = timestamp.hour + timestamp.minute / 60.0
        daylight = max(math.sin((hour - 6.0) / 12.0 * math.pi), 0.0)
        seasonal = 0.9 + 0.12 * math.sin((timestamp.timetuple().tm_yday - 45) / 365 * 2 * math.pi)
        solar = MICROGRID.pv_capacity_kw * MICROGRID.pv_performance_ratio * daylight**1.35 * seasonal * cloud_factor
        return float(np.clip(solar + self._rng.normal(0, 1.5 if daylight > 0 else 0.05), 0, MICROGRID.pv_capacity_kw))

    def _load_kw(
        self,
        timestamp: datetime | pd.Timestamp,
        solar_kw: float,
        temperature_c: float | None = None,
        humidity_pct: float | None = None,
    ) -> float:
        hour = timestamp.hour + timestamp.minute / 60.0
        morning = 26 * math.exp(-0.5 * ((hour - 8) / 1.8) ** 2)
        evening = 42 * math.exp(-0.5 * ((hour - 20) / 2.0) ** 2)
        daytime = 25 * math.exp(-0.5 * ((hour - 14) / 4.5) ** 2)
        temp = temperature_c if temperature_c is not None else 29
        humidity = humidity_pct if humidity_pct is not None else 75
        cooling = max(temp - 28, 0) * 2.1 + max(humidity - 82, 0) * 0.16
        weekend = 0.9 if timestamp.weekday() >= 5 else 1.0
        event_spike = self._rng.uniform(10, 24) if self._rng.random() < 0.025 else 0
        load = (42 + morning + evening + daytime + cooling + event_spike) * weekend + self._rng.normal(0, 2.5)
        return float(np.clip(load, MICROGRID.load_min_kw, MICROGRID.load_max_kw))

    def _tariff(self, timestamp: datetime | pd.Timestamp) -> float:
        hour = timestamp.hour
        if hour >= 22 or hour <= 5:
            return 2.6
        if 18 <= hour <= 21:
            return 9.2
        return 5.6

    def _battery_dispatch(self, solar_kw: float, wind_kw: float, load_kw: float, tariff: float) -> dict[str, Any]:
        min_energy = BATTERY.capacity_kwh * BATTERY.min_soc_pct / 100.0
        max_energy = BATTERY.capacity_kwh * BATTERY.max_soc_pct / 100.0
        energy = BATTERY.capacity_kwh * self._soc_pct / 100.0
        action = "idle"
        power_kw = 0.0

        surplus = solar_kw + wind_kw - load_kw
        if self._override_mode == "force_charge":
            charge_kw = min(BATTERY.max_charge_kw, (max_energy - energy) / BATTERY.charge_efficiency, max(surplus, 18.0))
            action = "charge"
            power_kw = -max(charge_kw, 0.0)
        elif self._override_mode in {"force_discharge", "island"}:
            discharge_kw = min(BATTERY.max_discharge_kw, (energy - min_energy) * BATTERY.discharge_efficiency, max(load_kw - solar_kw - wind_kw, 18.0))
            action = "discharge"
            power_kw = max(discharge_kw, 0.0)
        elif surplus > 6 and energy < max_energy:
            charge_kw = min(surplus, BATTERY.max_charge_kw, (max_energy - energy) / BATTERY.charge_efficiency)
            action = "charge"
            power_kw = -max(charge_kw, 0.0)
        elif (tariff >= 8 or load_kw > MICROGRID.peak_load_risk_kw) and energy > min_energy:
            discharge_kw = min(max(load_kw - solar_kw - wind_kw, 0), BATTERY.max_discharge_kw, (energy - min_energy) * BATTERY.discharge_efficiency)
            action = "discharge"
            power_kw = max(discharge_kw, 0.0)
        elif tariff <= 3.0 and energy < (max_energy * 0.75):
            charge_kw = min(18.0, BATTERY.max_charge_kw, (max_energy - energy) / BATTERY.charge_efficiency)
            action = "charge"
            power_kw = -max(charge_kw, 0.0)

        if power_kw < 0:
            energy += abs(power_kw) * BATTERY.charge_efficiency
        elif power_kw > 0:
            energy -= power_kw / BATTERY.discharge_efficiency
        energy = float(np.clip(energy, min_energy, max_energy))
        self._soc_pct = energy / BATTERY.capacity_kwh * 100.0
        if abs(power_kw) < 0.01:
            action = "idle"
            power_kw = 0.0
        return {"action": action, "battery_power_kw": power_kw}

    def _append_record(self, record: dict[str, Any]) -> None:
        LIVE_DIR.mkdir(parents=True, exist_ok=True)
        with LIVE_JSONL.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")


live_simulator = LiveTelemetrySimulator()

