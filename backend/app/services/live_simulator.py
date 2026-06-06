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
        self._soh = 100.0
        self._resistance_growth = 1.0
        self._cell_temp_c = 25.0
        self._cloud_factor = 0.88
        self._override_mode = "auto"
        self._tick = 0

    def start(self, interval_seconds: float = 1.5, reset: bool = False) -> dict[str, Any]:
        with self._lock:
            self._config.interval_seconds = float(np.clip(interval_seconds, 0.5, 30.0))
            self._records = deque(self._records, maxlen=self._config.max_records)
            if reset or not self._records:
                self._records.clear()
                self._soc_pct = BATTERY.initial_soc_pct
                self._soh = 100.0
                self._resistance_growth = 1.0
                self._cell_temp_c = 25.0
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
                                    "battery_soh_pct": float(row.get("battery_soh_pct", 100.0)),
                                    "battery_resistance_growth": float(row.get("battery_resistance_growth", 1.0)),
                                    "battery_energy_kwh": float(row.get("battery_energy_kwh", BATTERY.capacity_kwh * float(row["battery_soc_pct"]) / 100.0)),
                                    "battery_power_kw": batt_power,
                                    "battery_violation": int(row.get("battery_violation", 0)),
                                    "grid_kw": grid_val,
                                    "load_shed_kw": float(row.get("load_shed_kw", 0.0)),
                                    "operator_action": row.get("operator_action", "idle"),
                                    "override_mode": row.get("override_mode", "auto"),
                                    "hour_of_day": dt_local.hour,
                                    "day_of_week": dt_local.weekday(),
                                    "is_weekend": int(dt_local.weekday() >= 5),
                                    "month": dt_local.month,
                                    "hour_sin": math.sin(2 * math.pi * dt_local.hour / 24),
                                    "hour_cos": math.cos(2 * math.pi * dt_local.hour / 24),
                                    "day_sin": math.sin(2 * math.pi * dt_local.weekday() / 7),
                                    "day_cos": math.cos(2 * math.pi * dt_local.weekday() / 7),
                                    "cost_inr": 0.0,
                                    "cell_temperature_c": float(row.get("temperature_c", 20.0)),
                                    "carbon_intensity_kg_kwh": 0.5,
                                    "carbon_emissions_kg": 0.0,
                                    "degradation_cost_inr": 0.0,
                                    "action": row.get("operator_action", "idle"),
                                    "reason": f"Pre-population record. Mode: {row.get('override_mode', 'auto').upper()}.",
                                    "decision_entropy": 0.12,
                                    "ig_attributions": [0.0] * 9,
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

        # Dynamic dispatch using PIS-PPO model equations
        from .dispatch_v2 import get_ppo_model
        from ..rl.xai_metrics import calculate_decision_entropy, calculate_integrated_gradients

        hour_sin = math.sin(2 * math.pi * timestamp.hour / 24)
        hour_cos = math.cos(2 * math.pi * timestamp.hour / 24)
        is_weekend = int(timestamp.weekday() >= 5)

        state = np.array(
            [
                solar_kw / 140.0,
                wind_kw / 30.0,
                load_kw / 180.0,
                self._soc_pct / 100.0,
                self._soh / 100.0,
                (tariff - 2.0) / 8.0,
                float(hour_sin + 1.0) / 2.0,
                float(hour_cos + 1.0) / 2.0,
                1.0 if is_weekend else 0.0,
            ],
            dtype=np.float32,
        )

        model = get_ppo_model()
        
        if self._override_mode == "auto":
            action, _ = model.predict(state, deterministic=True)
            act_val = float(action[0])
        elif self._override_mode == "force_charge":
            act_val = -1.0
        elif self._override_mode in {"force_discharge", "island"}:
            act_val = 1.0
        else:
            act_val = 0.0

        # 1. Thermal Derating
        T_warn, T_crit = 45.0, 55.0
        derate = max(0.0, min(1.0, (T_crit - self._cell_temp_c) / (T_crit - T_warn)))
        max_charge = BATTERY.max_charge_kw * derate
        max_discharge = BATTERY.max_discharge_kw * derate

        # 2. Efficiency Degradation
        eta_ch = BATTERY.charge_efficiency
        eta_dis = BATTERY.discharge_efficiency
        eta_ch_t = eta_ch / (self._resistance_growth ** 0.1)
        eta_dis_t = eta_dis / (self._resistance_growth ** 0.1)
        C_max = BATTERY.capacity_kwh
        S_min = BATTERY.min_soc_pct
        S_max = BATTERY.max_soc_pct
        dt = 1.0

        # 3. Action Projection
        P_hat = 0.5 * (max_discharge + max_charge) * act_val + 0.5 * (max_discharge - max_charge)
        P_soc_min = - ((S_max - self._soc_pct) * C_max * (self._soh / 100.0)) / (100.0 * dt * eta_ch_t)
        P_soc_max = ((self._soc_pct - S_min) * C_max * (self._soh / 100.0) * eta_dis_t) / (100.0 * dt)
        
        P_min = max(-max_charge, P_soc_min)
        P_max = min(max_discharge, P_soc_max, max(0.0, load_kw - solar_kw - wind_kw))
        
        if P_min > P_max:
            P_min, P_max = P_max, P_min
            
        P_bat = float(np.clip(P_hat, P_min, P_max))

        # 4. Update battery aging & resistance
        P_loss_base = (1.0 - eta_ch_t) * max(-P_bat, 0.0) + (1.0 / eta_dis_t - 1.0) * max(P_bat, 0.0)
        P_loss = P_loss_base * self._resistance_growth
        cell_temp_k = (temperature_c + 273.15) + 0.05 * P_loss
        self._cell_temp_c = cell_temp_k - 273.15
        
        # Arrhenius
        E_a = 50000.0
        R = 8.314
        T_ref = 298.15
        xi = np.exp((E_a / R) * (1.0 / T_ref - 1.0 / cell_temp_k))

        # Degradation
        k_cal = 1.48e-6
        mu = 0.8
        d_cal = k_cal * xi * ((self._soc_pct / 100.0) ** mu) * dt
        
        delta_t = max(1.0 - self._soc_pct / 100.0, 1e-4)
        a_cyc = 3251.0
        b_cyc = 1.05
        N_f = a_cyc * (delta_t ** -b_cyc)
        d_cyc = (abs(P_bat) * dt) / (2.0 * N_f * C_max * (self._soh / 100.0) * delta_t) * xi

        self._soh = max(self._soh - (d_cyc + d_cal) * 100.0, 80.0)
        self._resistance_growth = min(self._resistance_growth + 1.2 * (d_cyc + d_cal) * 100.0, 2.0)

        if P_bat >= 0.0:
            energy_change = P_bat / eta_dis_t
        else:
            energy_change = P_bat * eta_ch_t
            
        energy_kwh = np.clip(
            (C_max * (self._soh / 100.0) * (self._soc_pct / 100.0)) - energy_change * dt,
            S_min * C_max / 100.0 * (self._soh / 100.0),
            S_max * C_max / 100.0 * (self._soh / 100.0)
        )
        self._soc_pct = (energy_kwh / (C_max * (self._soh / 100.0))) * 100.0

        grid_kw = max(load_kw - solar_kw - wind_kw - P_bat, 0.0)
        load_shed_kw = 0.0
        if self._override_mode == "island":
            available_supply = solar_kw + wind_kw + max(P_bat, 0.0)
            load_shed_kw = max(load_kw - available_supply, 0.0)
            grid_kw = 0.0

        # Action descriptions
        if P_bat > 0.5:
            action_desc = "discharge"
            reason_desc = f"PIS-PPO: Discharge {P_bat:.1f} kW to cover HVAC load surge and avoid peak tariff. Temp: {self._cell_temp_c:.1f}°C."
        elif P_bat < -0.5:
            action_desc = "charge"
            reason_desc = f"PIS-PPO: Charge {-P_bat:.1f} kW exploiting off-peak tariff. Temp: {self._cell_temp_c:.1f}°C."
        else:
            action_desc = "idle"
            reason_desc = f"PIS-PPO: BESS idle. Directing green power to facility load. Temp: {self._cell_temp_c:.1f}°C."

        if self._override_mode != "auto":
            reason_desc = f"Operator override: BESS {action_desc} (Mode: {self._override_mode.upper()}). Temp: {self._cell_temp_c:.1f}°C."

        ig = calculate_integrated_gradients(model, state)
        std_val = 0.15
        entropy = float(calculate_decision_entropy(std_val))

        # Combined cost including carbon price and carbon weight
        kappa = 0.5 + 0.2 * np.sin(2.0 * np.pi * (timestamp.hour - 6) / 24.0) + 0.15 * np.cos(4.0 * np.pi * (timestamp.hour - 18) / 24.0)
        carbon_em = kappa * grid_kw * dt
        electricity_cost = grid_kw * tariff * dt
        carbon_cost = carbon_em * 2.0
        combined_cost = electricity_cost + 0.1 * carbon_cost # Use default carbon weight 0.1

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
            "battery_soh_pct": round(self._soh, 3),
            "battery_resistance_growth": round(self._resistance_growth, 3),
            "battery_energy_kwh": round(BATTERY.capacity_kwh * (self._soh / 100.0) * (self._soc_pct / 100.0), 3),
            "battery_power_kw": round(P_bat, 3),
            "battery_violation": 0,
            "grid_kw": round(grid_kw, 3),
            "load_shed_kw": round(load_shed_kw, 3),
            "operator_action": action_desc,
            "override_mode": self._override_mode,
            "hour_of_day": timestamp.hour,
            "day_of_week": timestamp.weekday(),
            "is_weekend": int(timestamp.weekday() >= 5),
            "month": timestamp.month,
            "hour_sin": math.sin(2 * math.pi * timestamp.hour / 24),
            "hour_cos": math.cos(2 * math.pi * timestamp.hour / 24),
            "day_sin": math.sin(2 * math.pi * timestamp.weekday() / 7),
            "day_cos": math.cos(2 * math.pi * timestamp.weekday() / 7),
            "cost_inr": round(combined_cost, 3),
            "cell_temperature_c": round(self._cell_temp_c, 2),
            "carbon_intensity_kg_kwh": round(kappa, 3),
            "carbon_emissions_kg": round(carbon_em, 3),
            "degradation_cost_inr": round((2500000.0 / 20.0) * (d_cyc + d_cal) * 100.0, 3),
            "action": action_desc,
            "reason": reason_desc,
            "decision_entropy": round(entropy, 3),
            "ig_attributions": [round(float(val), 4) for val in ig],
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

    def _append_record(self, record: dict[str, Any]) -> None:
        LIVE_DIR.mkdir(parents=True, exist_ok=True)
        with LIVE_JSONL.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")


live_simulator = LiveTelemetrySimulator()

