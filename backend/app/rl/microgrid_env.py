from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:  # pragma: no cover - kept for older gym installations.
    import gym
    from gym import spaces

from ..config import BATTERY, EMS_DATASET


@dataclass(frozen=True)
class DispatchStep:
    action_name: str
    solar_kw: float
    wind_kw: float
    load_kw: float
    grid_kw: float
    battery_power_kw: float
    soc_pct: float
    cost_inr: float
    reward: float
    violation: bool


class MicrogridPPOEnv(gym.Env):
    metadata = {"render_modes": ["human"]}

    ACTIONS = {0: "idle", 1: "charge", 2: "discharge"}

    def __init__(self, dataset_path=EMS_DATASET, episode_length: int = 24 * 14) -> None:
        super().__init__()
        self.df = pd.read_csv(dataset_path, parse_dates=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        self.episode_length = min(episode_length, len(self.df) - 2)
        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(9,), dtype=np.float32)
        self.start_index = 0
        self.index = 0
        self.energy_kwh = BATTERY.capacity_kwh * BATTERY.initial_soc_pct / 100.0
        self.last_step: DispatchStep | None = None

    def reset(self, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        max_start = max(len(self.df) - self.episode_length - 1, 1)
        self.start_index = int(self.np_random.integers(0, max_start))
        self.index = self.start_index
        self.energy_kwh = BATTERY.capacity_kwh * BATTERY.initial_soc_pct / 100.0
        self.last_step = None
        return self._observation(), {}

    def step(self, action: int):
        row = self.df.iloc[self.index]
        solar_kw = float(row.solar_kw)
        wind_kw = float(row.wind_kw)
        load_kw = float(row.load_kw)
        tariff = float(row.tariff_inr_kwh)
        min_energy = BATTERY.capacity_kwh * BATTERY.min_soc_pct / 100.0
        max_energy = BATTERY.capacity_kwh * BATTERY.max_soc_pct / 100.0

        violation = False
        battery_power_kw = 0.0
        renewable_used_kw = min(solar_kw + wind_kw, load_kw)

        if action == 1:
            surplus_kw = max(solar_kw + wind_kw - load_kw, 0.0)
            room_kwh = max((max_energy - self.energy_kwh) / BATTERY.charge_efficiency, 0.0)
            charge_kw = min(BATTERY.max_charge_kw, room_kwh, surplus_kw if surplus_kw > 0 else 12.0)
            if charge_kw <= 0.0 or self.energy_kwh >= max_energy - 1e-6:
                violation = True
            self.energy_kwh += charge_kw * BATTERY.charge_efficiency
            battery_power_kw = -charge_kw
        elif action == 2:
            deficit_kw = max(load_kw - solar_kw - wind_kw, 0.0)
            available_kwh = max((self.energy_kwh - min_energy) * BATTERY.discharge_efficiency, 0.0)
            discharge_kw = min(BATTERY.max_discharge_kw, available_kwh, deficit_kw if deficit_kw > 0 else 10.0)
            if discharge_kw <= 0.0 or self.energy_kwh <= min_energy + 1e-6:
                violation = True
            self.energy_kwh -= discharge_kw / BATTERY.discharge_efficiency
            battery_power_kw = discharge_kw
            renewable_used_kw += discharge_kw

        self.energy_kwh = float(np.clip(self.energy_kwh, min_energy, max_energy))
        soc_pct = self.energy_kwh / BATTERY.capacity_kwh * 100.0
        grid_kw = max(load_kw - solar_kw - wind_kw - max(battery_power_kw, 0.0) + max(-battery_power_kw, 0.0), 0.0)
        cost_inr = grid_kw * tariff
        violation_penalty = 45.0 if violation else 0.0
        degradation_penalty = abs(battery_power_kw) * BATTERY.degradation_cost_inr_per_kwh
        peak_penalty = 0.06 * grid_kw if tariff >= 8.0 else 0.0
        renewable_reward = 0.018 * renewable_used_kw
        reward = -cost_inr / 24.0 - degradation_penalty - peak_penalty - violation_penalty + renewable_reward

        self.last_step = DispatchStep(
            action_name=self.ACTIONS[int(action)],
            solar_kw=solar_kw,
            wind_kw=wind_kw,
            load_kw=load_kw,
            grid_kw=grid_kw,
            battery_power_kw=battery_power_kw,
            soc_pct=soc_pct,
            cost_inr=cost_inr,
            reward=reward,
            violation=violation,
        )

        self.index += 1
        terminated = self.index >= self.start_index + self.episode_length
        truncated = self.index >= len(self.df) - 1
        return self._observation(), float(reward), terminated, truncated, self._info()

    def render(self):
        return self.last_step

    def _observation(self) -> np.ndarray:
        row = self.df.iloc[self.index]
        return np.array(
            [
                float(row.solar_kw) / 140.0,
                float(row.wind_kw) / 30.0,
                float(row.load_kw) / 180.0,
                (self.energy_kwh / BATTERY.capacity_kwh),
                (float(row.tariff_inr_kwh) - 2.0) / 8.0,
                (float(row.hour_of_day) % 24) / 23.0,
                float(row.hour_sin + 1.0) / 2.0,
                float(row.hour_cos + 1.0) / 2.0,
                1.0 if bool(row.is_weekend) else 0.0,
            ],
            dtype=np.float32,
        )

    def _info(self) -> dict[str, float | str | bool]:
        if self.last_step is None:
            return {}
        return self.last_step.__dict__

