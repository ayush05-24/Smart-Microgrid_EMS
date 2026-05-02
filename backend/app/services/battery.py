from __future__ import annotations

import pandas as pd

from ..config import BATTERY


def battery_health_report(dispatch_df: pd.DataFrame) -> dict[str, float | int | bool | str]:
    throughput_kwh = float(dispatch_df["battery_power_kw"].abs().sum())
    equivalent_cycles = throughput_kwh / (2.0 * BATTERY.capacity_kwh)
    soc_min = float(dispatch_df["battery_soc_pct"].min())
    soc_max = float(dispatch_df["battery_soc_pct"].max())
    safe = bool(dispatch_df["battery_soc_pct"].between(BATTERY.min_soc_pct, BATTERY.max_soc_pct).all())
    stress_penalty = max(0.0, equivalent_cycles - 0.8) * 1.6
    edge_penalty = 0.0
    if soc_min < BATTERY.min_soc_pct + 3.0:
        edge_penalty += 1.2
    if soc_max > BATTERY.max_soc_pct - 3.0:
        edge_penalty += 1.0
    health_score = max(70.0, 100.0 - stress_penalty - edge_penalty)
    return {
        "capacity_kwh": BATTERY.capacity_kwh,
        "soc_min_pct": round(soc_min, 3),
        "soc_max_pct": round(soc_max, 3),
        "safe_soc": safe,
        "equivalent_cycles": round(equivalent_cycles, 4),
        "estimated_health_score": round(health_score, 2),
        "status": "healthy" if safe and health_score >= 90 else "watch",
    }

