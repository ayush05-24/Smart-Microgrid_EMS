import numpy as np
import torch
from ..config import BATTERY

def project_action_numpy(
    P_hat: float | np.ndarray,
    soc: float,
    soh: float,
    solar_kw: float,
    wind_kw: float,
    load_kw: float,
    cell_temp_c: float | np.ndarray = 25.0,
    dt: float = 1.0
) -> float | np.ndarray:
    """
    Project raw BESS power request P_hat onto the feasible action set using NumPy.
    Ensures SoC limits, dynamic thermal derating based on cell temperature, and grid import constraints are satisfied.
    """
    eta_ch = BATTERY.charge_efficiency
    eta_dis = BATTERY.discharge_efficiency
    C_max = BATTERY.capacity_kwh
    S_min = BATTERY.min_soc_pct
    S_max = BATTERY.max_soc_pct

    # 1. Dynamic Thermal Derating
    T_warn, T_crit = 45.0, 55.0
    if isinstance(cell_temp_c, np.ndarray):
        derate = np.clip((T_crit - cell_temp_c) / (T_crit - T_warn), 0.0, 1.0)
    else:
        derate = max(0.0, min(1.0, (T_crit - cell_temp_c) / (T_crit - T_warn)))

    max_charge = BATTERY.max_charge_kw * derate
    max_discharge = BATTERY.max_discharge_kw * derate

    # 2. SoC charging lower bound (P_bat >= P_soc_min, charging is negative)
    P_soc_min = - ((S_max - soc) * C_max * (soh / 100.0)) / (100.0 * dt * eta_ch)
    # SoC discharging upper bound (P_bat <= P_soc_max, discharging is positive)
    P_soc_max = ((soc - S_min) * C_max * (soh / 100.0) * eta_dis) / (100.0 * dt)

    # 3. Combine hardware limits and SoC bounds
    P_min = np.maximum(-max_charge, P_soc_min)
    # Grid limit: P_grid = Load - PV - Wind - P_bat >= 0 => P_bat <= Load - PV - Wind
    # When load - PV - Wind < 0 (surplus), BESS discharge is capped at 0.0, not a negative value, to allow BESS to idle.
    P_max = np.minimum(
        np.minimum(max_discharge, P_soc_max),
        np.maximum(0.0, load_kw - solar_kw - wind_kw)
    )

    # Safety bounds crossover
    crossover = P_min > P_max
    if np.any(crossover):
        if isinstance(P_min, np.ndarray):
            P_min[crossover] = P_max[crossover]
        else:
            P_min = P_max

    return np.clip(P_hat, P_min, P_max)


def project_action_torch(
    P_hat: torch.Tensor,
    soc: torch.Tensor,
    soh: torch.Tensor,
    solar_kw: torch.Tensor,
    wind_kw: torch.Tensor,
    load_kw: torch.Tensor,
    cell_temp_c: torch.Tensor,
    dt: float = 1.0
) -> torch.Tensor:
    """
    Project raw BESS power request P_hat onto the feasible action set using PyTorch.
    Enforces dynamic thermal derating in a differentiable manner.
    """
    eta_ch = BATTERY.charge_efficiency
    eta_dis = BATTERY.discharge_efficiency
    C_max = BATTERY.capacity_kwh
    S_min = BATTERY.min_soc_pct
    S_max = BATTERY.max_soc_pct

    # 1. Thermal Derating
    T_warn, T_crit = 45.0, 55.0
    derate = torch.clamp((T_crit - cell_temp_c) / (T_crit - T_warn), min=0.0, max=1.0)
    
    max_charge = BATTERY.max_charge_kw * derate
    max_discharge = BATTERY.max_discharge_kw * derate

    # 2. SoC limits
    P_soc_min = - ((S_max - soc) * C_max * (soh / 100.0)) / (100.0 * dt * eta_ch)
    P_soc_max = ((soc - S_min) * C_max * (soh / 100.0) * eta_dis) / (100.0 * dt)

    # 3. Combine bounds
    P_min = torch.clamp(-max_charge, min=P_soc_min)
    
    grid_bound = torch.clamp(load_kw - solar_kw - wind_kw, min=0.0)
    P_max_candidate = torch.clamp(max_discharge, max=P_soc_max)
    P_max = torch.minimum(P_max_candidate, grid_bound)

    # Resolve crossover in a differentiable manner
    P_min = torch.minimum(P_min, P_max)

    return torch.clamp(P_hat, min=P_min, max=P_max)
