from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from stable_baselines3 import DQN, SAC, TD3, PPO
from stable_baselines3.common.env_util import make_vec_env

from ..config import BATTERY
from .microgrid_env_v2 import MicrogridCMDPEnv
from .projection import project_action_numpy


# 1. Dynamic Programming (DP) - Exact global optimum with perfect foresight
class DPDispatcher:
    def __init__(self, capacity_kwh: float = 180.0, min_soc: float = 20.0, max_soc: float = 90.0) -> None:
        self.C_max = capacity_kwh
        self.S_min = min_soc
        self.S_max = max_soc
        self.eta_ch = BATTERY.charge_efficiency
        self.eta_dis = BATTERY.discharge_efficiency
        
        # Discretize state space (SoC from 20% to 90% in 1% steps)
        self.soc_states = np.linspace(self.S_min, self.S_max, 71)

    def solve_horizon(self, df_horizon: pd.DataFrame, initial_soc: float) -> tuple[list[float], list[str]]:
        """
        Solves the optimal dispatch schedule over the horizon using backward Dynamic Programming.
        """
        T = len(df_horizon)
        N_states = len(self.soc_states)
        
        # DP tables
        # V[t, s] is the minimum cost from step t with state s to end
        V = np.full((T + 1, N_states), float("inf"))
        policy = np.zeros((T, N_states), dtype=int)  # stores index of next state
        
        # Terminal cost
        V[T, :] = 0.0
        
        # Constants
        C_repl = 2500000.0
        w_d = 0.2
        w_c = 0.1
        carbon_price_inr_kg = 2.0

        # Backward recursion
        for t in range(T - 1, -1, -1):
            row = df_horizon.iloc[t]
            solar = float(row.solar_kw)
            wind = float(row.wind_kw)
            load = float(row.load_kw)
            tariff = float(row.tariff_inr_kwh)
            hour = int(row.hour_of_day)
            
            # Carbon intensity
            kappa = 0.5 + 0.2 * np.sin(2.0 * np.pi * (hour - 6) / 24.0) + 0.15 * np.cos(4.0 * np.pi * (hour - 18) / 24.0)

            for s_idx, soc_curr in enumerate(self.soc_states):
                best_cost = float("inf")
                best_next_idx = s_idx  # default to idle
                
                for next_idx, soc_next in enumerate(self.soc_states):
                    # Calculate required battery power to transition from soc_curr to soc_next
                    soc_diff = soc_curr - soc_next
                    if soc_diff >= 0.0:  # discharging (positive power)
                        P_bat = (soc_diff * self.C_max * 0.99) / (100.0 * 1.0 * self.eta_dis) # assume SoH = 99%
                    else:  # charging (negative power)
                        P_bat = (soc_diff * self.C_max * 0.99 * self.eta_ch) / 100.0
                    
                    # Enforce physical power limits
                    if P_bat > BATTERY.max_discharge_kw or P_bat < -BATTERY.max_charge_kw:
                        continue
                    
                    # Grid balance: no export allowed, so BESS discharge cannot exceed net load.
                    # Excess generation is curtailed (P_grid = 0.0).
                    if P_bat > max(0.0, load - solar - wind):
                        continue
                    P_grid = max(load - solar - wind - P_bat, 0.0)

                    # Compute costs
                    electricity_cost = P_grid * tariff
                    
                    # Simple cycle aging cost approximation for DP transition
                    d_cyc = abs(P_bat) / (2.0 * 3000.0 * self.C_max)
                    degradation_cost = (C_repl / 20.0) * d_cyc * 100.0
                    
                    # Carbon emissions
                    carbon_em = kappa * P_grid
                    
                    cost = electricity_cost + w_d * degradation_cost + w_c * (carbon_em * carbon_price_inr_kg)
                    total_cost = cost + V[t + 1, next_idx]
                    
                    if total_cost < best_cost:
                        best_cost = total_cost
                        best_next_idx = next_idx
                
                V[t, s_idx] = best_cost
                policy[t, s_idx] = best_next_idx

        # Forward path reconstruction
        optimal_power = []
        optimal_actions = []
        
        curr_soc = initial_soc
        for t in range(T):
            # Find closest discretized state
            s_idx = np.argmin(np.abs(self.soc_states - curr_soc))
            next_idx = policy[t, s_idx]
            next_soc = self.soc_states[next_idx]
            
            soc_diff = curr_soc - next_soc
            if soc_diff >= 0.0:
                P_bat = (soc_diff * self.C_max * 0.99) / (100.0 * 1.0 * self.eta_dis)
                action = "discharge" if P_bat > 0.5 else "idle"
            else:
                P_bat = (soc_diff * self.C_max * 0.99 * self.eta_ch) / 100.0
                action = "charge"
                
            optimal_power.append(P_bat)
            optimal_actions.append(action)
            curr_soc = next_soc

        return optimal_power, optimal_actions


# 2. Model Predictive Control (MPC) - rolling horizon using forecasting
class MPCDispatcher:
    def __init__(self, dp_solver: DPDispatcher) -> None:
        self.dp = dp_solver

    def solve_step(self, df_forecast: pd.DataFrame, current_soc: float) -> tuple[float, str]:
        """
        Solves a 24-hour horizon using forecast data and returns the first step action.
        """
        # If forecast window is too short, pad it
        if len(df_forecast) < 2:
            return 0.0, "idle"
        
        powers, actions = self.dp.solve_horizon(df_forecast, current_soc)
        return powers[0], actions[0]


# 3. Stable Baselines3 Training Baselines (SAC, TD3, DQN, Point-PPO)
def train_sb3_baseline(model_type: str, env: MicrogridCMDPEnv, steps: int = 15000) -> object:
    """
    Trains a stable-baselines3 agent on the new CMDP environment.
    """
    if model_type == "sac":
        model = SAC("MlpPolicy", env, learning_rate=3e-4, batch_size=64, verbose=0, seed=42)
    elif model_type == "td3":
        model = TD3("MlpPolicy", env, learning_rate=3e-4, batch_size=64, verbose=0, seed=42)
    elif model_type == "dqn":
        # Discretize env for DQN
        # In a real environment, we'd wrap it to convert discrete actions to continuous, 
        # but since we already have MicrogridPPOEnv as a discrete env, we can train DQN on that!
        from .microgrid_env import MicrogridPPOEnv
        discrete_env = MicrogridPPOEnv(episode_length=env.episode_length)
        model = DQN("MlpPolicy", discrete_env, learning_rate=5e-4, verbose=0, seed=42)
    elif model_type == "ppo_point":
        model = PPO("MlpPolicy", env, learning_rate=3e-4, n_steps=512, batch_size=64, verbose=0, seed=42)
    else:
        raise ValueError(f"Unknown baseline: {model_type}")
        
    model.learn(total_timesteps=steps)
    return model
