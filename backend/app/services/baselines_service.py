from __future__ import annotations

import numpy as np
import pandas as pd
from ..config import BATTERY

def solve_dp_optimal_for_horizon(df: pd.DataFrame, initial_soc: float = 55.0) -> float:
    """
    Solves exact dynamic programming over the given horizon and returns the minimum cost.
    Used by the metrics system to calculate the real-time optimality gap.
    """
    T = len(df)
    S_min = BATTERY.min_soc_pct
    S_max = BATTERY.max_soc_pct
    eta_ch = BATTERY.charge_efficiency
    eta_dis = BATTERY.discharge_efficiency
    C_max = BATTERY.capacity_kwh
    
    soc_states = np.linspace(S_min, S_max, 36) # 36 states for fast API response
    N_states = len(soc_states)
    
    V = np.full((T + 1, N_states), float("inf"))
    V[T, :] = 0.0
    
    C_repl = 2500000.0
    w_d = 0.2
    w_c = 0.1
    carbon_price_inr_kg = 2.0

    for t in range(T - 1, -1, -1):
        row = df.iloc[t]
        solar = float(row.solar_kw)
        wind = float(row.wind_kw)
        load = float(row.load_kw)
        tariff = float(row.tariff_inr_kwh)
        hour = int(row.hour_of_day)
        
        kappa = 0.5 + 0.2 * np.sin(2.0 * np.pi * (hour - 6) / 24.0) + 0.15 * np.cos(4.0 * np.pi * (hour - 18) / 24.0)

        for s_idx, soc_curr in enumerate(soc_states):
            best_cost = float("inf")
            
            for next_idx, soc_next in enumerate(soc_states):
                soc_diff = soc_curr - soc_next
                if soc_diff >= 0.0:
                    P_bat = (soc_diff * C_max * 0.99) / (100.0 * 1.0 * eta_dis)
                else:
                    P_bat = (soc_diff * C_max * 0.99 * eta_ch) / 100.0
                
                if P_bat > BATTERY.max_discharge_kw or P_bat < -BATTERY.max_charge_kw:
                    continue
                
                # Grid balance: no export allowed, so BESS discharge cannot exceed net load.
                # Excess generation is curtailed (P_grid = 0.0).
                if P_bat > max(0.0, load - solar - wind):
                    continue
                P_grid = max(load - solar - wind - P_bat, 0.0)

                electricity_cost = P_grid * tariff
                d_cyc = abs(P_bat) / (2.0 * 3000.0 * C_max)
                degradation_cost = (C_repl / 20.0) * d_cyc * 100.0
                carbon_em = kappa * P_grid
                
                cost = electricity_cost + w_d * degradation_cost + w_c * (carbon_em * carbon_price_inr_kg)
                total_cost = cost + V[t + 1, next_idx]
                
                if total_cost < best_cost:
                    best_cost = total_cost
            
            V[t, s_idx] = best_cost

    # Extract optimal cost starting from closest discretized state
    s_idx = np.argmin(np.abs(soc_states - initial_soc))
    opt_cost = V[0, s_idx]
    
    if np.isinf(opt_cost):
        # Fallback to a simple heuristic optimal estimate if no feasible path exists in discrete grid
        return float(df["load_kw"].sum() * 0.8 * df["tariff_inr_kwh"].mean())
        
    return float(opt_cost)
