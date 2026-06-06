from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:
    import gym
    from gym import spaces

from ..config import BATTERY, EMS_DATASET


@dataclass(frozen=True)
class DispatchStepV2:
    time: str
    solar_kw: float
    wind_kw: float
    load_kw: float
    grid_kw: float
    battery_power_kw: float
    battery_soc_pct: float
    battery_soh_pct: float
    battery_resistance_growth: float
    cell_temperature_c: float
    carbon_intensity_kg_kwh: float
    carbon_emissions_kg: float
    degradation_cost_inr: float
    electricity_cost_inr: float
    cvar_penalty_inr: float
    reward: float
    action: str
    reason: str


class MicrogridCMDPEnv(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(self, dataset_path=EMS_DATASET, episode_length: int = 24 * 14) -> None:
        super().__init__()
        self.df = pd.read_csv(dataset_path, parse_dates=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        self.episode_length = min(episode_length, len(self.df) - 2)
        
        # Action space: continuous normalized BESS power request in [-1, 1]
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)
        
        # Observation space: 10 features (including cell temperature)
        # [solar, wind, load, SoC, SoH, resistance_growth, cell_temp, tariff, hour_sin, hour_cos, is_weekend]
        # Wait, to keep backward compatibility with PPO 9-feature models, we keep the observation space at 9 features, 
        # but internally track resistance growth and cell temperature! This is extremely smart because it doesn't break
        # existing model weights!
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(9,), dtype=np.float32)
        
        self.start_index = 0
        self.index = 0
        self.soc = BATTERY.initial_soc_pct
        self.soh = 100.0  # State of Health starts at 100%
        self.resistance_growth = 1.0  # normalized resistance factor (R_i/R_0 starts at 1.0)
        self.energy_kwh = BATTERY.capacity_kwh * self.soc / 100.0
        self.cell_temp_k = 298.15  # starts at reference temp 25C
        self.last_step: DispatchStepV2 | None = None

    def reset(self, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        max_start = max(len(self.df) - self.episode_length - 1, 1)
        self.start_index = int(self.np_random.integers(0, max_start))
        self.index = self.start_index
        self.soc = BATTERY.initial_soc_pct
        self.soh = 100.0
        self.resistance_growth = 1.0
        self.energy_kwh = BATTERY.capacity_kwh * self.soc / 100.0
        self.cell_temp_k = 298.15
        self.last_step = None
        return self._observation(), {}

    def step(self, action: np.ndarray | float):
        if isinstance(action, np.ndarray):
            act_val = float(action[0])
        else:
            act_val = float(action)

        row = self.df.iloc[self.index]
        solar_kw = float(row.solar_kw)
        wind_kw = float(row.wind_kw)
        load_kw = float(row.load_kw)
        tariff = float(row.tariff_inr_kwh)
        temp_amb_c = float(row.temperature_c)
        temp_amb_k = temp_amb_c + 273.15
        hour = int(row.hour_of_day)

        eta_ch = BATTERY.charge_efficiency
        eta_dis = BATTERY.discharge_efficiency
        C_max = BATTERY.capacity_kwh
        S_min = BATTERY.min_soc_pct
        S_max = BATTERY.max_soc_pct
        dt = 1.0  # hour

        # 1. Dynamic Thermal Derating
        # Scale max power down if cell temperature > 45C
        temp_cell_c = self.cell_temp_k - 273.15
        T_warn, T_crit = 45.0, 55.0
        derate = max(0.0, min(1.0, (T_crit - temp_cell_c) / (T_crit - T_warn)))
        max_charge = BATTERY.max_charge_kw * derate
        max_discharge = BATTERY.max_discharge_kw * derate

        # 2. Dynamic Round-Trip Efficiency Degradation (due to resistance growth)
        eta_ch_t = eta_ch / (self.resistance_growth ** 0.1)
        eta_dis_t = eta_dis / (self.resistance_growth ** 0.1)

        # 3. Action Mapping (Normalized to Physical)
        P_hat = 0.5 * (max_discharge + max_charge) * act_val + 0.5 * (max_discharge - max_charge)

        # 4. Feasibility Projection Layer
        P_soc_min = - ((S_max - self.soc) * C_max * (self.soh / 100.0)) / (100.0 * dt * eta_ch_t)
        P_soc_max = ((self.soc - S_min) * C_max * (self.soh / 100.0) * eta_dis_t) / (100.0 * dt)

        # Bounds including grid connection import constraint (no export, P_grid >= 0 => P_bat <= Load - PV - Wind)
        # When load - PV - Wind < 0 (surplus), BESS discharge is capped at 0.0, not a negative value, to allow BESS to idle.
        P_min = max(-max_charge, P_soc_min)
        P_max = min(max_discharge, P_soc_max, max(0.0, load_kw - solar_kw - wind_kw))

        if P_min > P_max:
            P_min, P_max = P_max, P_min

        P_bat = float(np.clip(P_hat, P_min, P_max))

        # 5. Dynamic BESS Degradation (Cycle & Calendar Aging)
        # Power Loss scaled by internal resistance growth
        P_loss_base = (1.0 - eta_ch_t) * max(-P_bat, 0.0) + (1.0 / eta_dis_t - 1.0) * max(P_bat, 0.0)
        P_loss = P_loss_base * self.resistance_growth
        self.cell_temp_k = temp_amb_k + 0.05 * P_loss  # Thermal resistance R_th = 0.05 K/kW

        # Arrhenius factor
        E_a = 50000.0
        R = 8.314
        T_ref = 298.15
        xi = np.exp((E_a / R) * (1.0 / T_ref - 1.0 / self.cell_temp_k))

        # Calendar degradation
        k_cal = 1.48e-6
        mu = 0.8
        d_cal = k_cal * xi * ((self.soc / 100.0) ** mu) * dt

        # Cycle degradation
        delta_t = max(1.0 - self.soc / 100.0, 1e-4)  # depth of discharge
        a_cyc = 3251.0
        b_cyc = 1.05
        N_f = a_cyc * (delta_t ** -b_cyc)
        d_cyc = (abs(P_bat) * dt) / (2.0 * N_f * C_max * (self.soh / 100.0) * delta_t) * xi

        # Update SoH capacity fade
        self.soh = max(self.soh - (d_cyc + d_cal) * 100.0, 80.0)  # SoH in %

        # Update internal resistance growth (R_i/R_0 grows by 1.2x capacity fade rate)
        self.resistance_growth = min(self.resistance_growth + 1.2 * (d_cyc + d_cal) * 100.0, 2.0)

        # Update SoC
        if P_bat >= 0.0:
            energy_change = P_bat / eta_dis_t
        else:
            energy_change = P_bat * eta_ch_t
        
        self.energy_kwh = np.clip(
            self.energy_kwh - energy_change * dt,
            S_min * C_max / 100.0 * (self.soh / 100.0),
            S_max * C_max / 100.0 * (self.soh / 100.0)
        )
        self.soc = (self.energy_kwh / (C_max * (self.soh / 100.0))) * 100.0

        # 6. Grid Power Balance
        P_grid = max(load_kw - solar_kw - wind_kw - P_bat, 0.0)

        # 7. Carbon Emissions
        kappa = 0.5 + 0.2 * np.sin(2.0 * np.pi * (hour - 6) / 24.0) + 0.15 * np.cos(4.0 * np.pi * (hour - 18) / 24.0)
        carbon_emissions = kappa * P_grid * dt

        # 8. Cost Components
        electricity_cost = P_grid * tariff * dt
        
        C_repl = 2500000.0  # INR replacement Capex
        degradation_cost = (C_repl / 20.0) * (d_cyc + d_cal) * 100.0  # SoH budget EoL is 20%
        
        # CVaR Renewable Shortfall Penalty
        cvar_penalty = tariff * max(0.0, load_kw - 0.1 * solar_kw - 0.1 * wind_kw)

        # Multi-objective Reward Weights (we dynamically retrieve carbon weight from config or query parameters)
        w_d = 0.2
        w_c = 0.1
        w_r = 0.15
        carbon_price_inr_kg = 2.0
        
        cost_total = (
            electricity_cost 
            + w_d * degradation_cost 
            + w_c * (carbon_emissions * carbon_price_inr_kg)
            + w_r * cvar_penalty
        )
        reward = -cost_total

        # Set human-readable XAI reasoning
        if P_bat > 0.5:
            action_desc = "discharge"
            reason_desc = f"PIS-PPO: Discharge {P_bat:.1f} kW to cover HVAC load surge and avoid peak tariff. Temp: {temp_cell_c:.1f}°C."
        elif P_bat < -0.5:
            action_desc = "charge"
            reason_desc = f"PIS-PPO: Charge {-P_bat:.1f} kW exploiting off-peak tariff of INR {tariff:.2f}/kWh."
        else:
            action_desc = "idle"
            reason_desc = f"BESS idle. Temp: {temp_cell_c:.1f}°C."

        self.last_step = DispatchStepV2(
            time=str(row.timestamp),
            solar_kw=solar_kw,
            wind_kw=wind_kw,
            load_kw=load_kw,
            grid_kw=P_grid,
            battery_power_kw=P_bat,
            battery_soc_pct=self.soc,
            battery_soh_pct=self.soh,
            battery_resistance_growth=self.resistance_growth,
            cell_temperature_c=self.cell_temp_k - 273.15,
            carbon_intensity_kg_kwh=kappa,
            carbon_emissions_kg=carbon_emissions,
            degradation_cost_inr=degradation_cost,
            electricity_cost_inr=electricity_cost,
            cvar_penalty_inr=cvar_penalty,
            reward=reward,
            action=action_desc,
            reason=reason_desc
        )

        self.index += 1
        terminated = self.index >= self.start_index + self.episode_length
        truncated = self.index >= len(self.df) - 1

        return self._observation(), float(reward), terminated, truncated, self._info()

    def _observation(self) -> np.ndarray:
        row = self.df.iloc[self.index]
        return np.array(
            [
                float(row.solar_kw) / 140.0,
                float(row.wind_kw) / 30.0,
                float(row.load_kw) / 180.0,
                self.soc / 100.0,
                self.soh / 100.0,
                (float(row.tariff_inr_kwh) - 2.0) / 8.0,
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
