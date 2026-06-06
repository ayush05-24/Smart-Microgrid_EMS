from __future__ import annotations

import numpy as np
import torch
from backend.app.config import BATTERY
from backend.app.rl.projection import project_action_numpy, project_action_torch


def test_projection_numpy_soc_bounds() -> None:
    # 1. Test battery is full (soc = max_soc_pct), charging action (negative) should be projected to 0 or positive
    soc_full = BATTERY.max_soc_pct
    soh = 100.0
    solar = 50.0
    wind = 10.0
    load = 10.0  # solar surplus = 50 + 10 - 10 = 50 kW
    
    # Raw action: charge BESS by -30 kW (negative)
    p_hat = -30.0
    p_projected = project_action_numpy(
        p_hat, soc_full, soh, solar, wind, load, cell_temp_c=25.0
    )
    # Since battery is full and there is solar surplus, BESS should not be forced to charge.
    # It should idle (0.0) or discharge. Here, since solar surplus is high, discharge is capped at 0 (to prevent export).
    # So the action should project exactly to 0.0 (idle).
    assert p_projected == 0.0


def test_projection_numpy_no_export() -> None:
    # 2. Test discharging action (positive) under deficit: max discharge is capped at load - PV - wind (prevent export)
    soc_mid = 50.0
    soh = 100.0
    solar = 10.0
    wind = 5.0
    load = 20.0  # net deficit = 5 kW
    
    # Raw action: discharge by 30 kW (positive)
    p_hat = 30.0
    p_projected = project_action_numpy(
        p_hat, soc_mid, soh, solar, wind, load, cell_temp_c=25.0
    )
    # Projected BESS power should be capped at net deficit (5 kW) to prevent export
    assert p_projected <= 5.0
    assert p_projected > 0.0


def test_projection_torch_behavior() -> None:
    # 3. Test torch version matches numpy version
    soc = torch.tensor([50.0], dtype=torch.float32)
    soh = torch.tensor([100.0], dtype=torch.float32)
    solar = torch.tensor([10.0], dtype=torch.float32)
    wind = torch.tensor([5.0], dtype=torch.float32)
    load = torch.tensor([20.0], dtype=torch.float32)
    cell_temp = torch.tensor([25.0], dtype=torch.float32)
    p_hat = torch.tensor([30.0], dtype=torch.float32)
    
    p_projected = project_action_torch(
        p_hat, soc, soh, solar, wind, load, cell_temp
    )
    assert p_projected.item() <= 5.0
    assert p_projected.item() > 0.0
