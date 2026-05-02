from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import BATTERY, MICROGRID


def build_dispatch_table(df: pd.DataFrame, horizon_hours: int = 24) -> pd.DataFrame:
    work = df.head(horizon_hours).copy().reset_index(drop=True)
    min_energy = BATTERY.capacity_kwh * BATTERY.min_soc_pct / 100.0
    max_energy = BATTERY.capacity_kwh * BATTERY.max_soc_pct / 100.0
    energy = BATTERY.capacity_kwh * float(work.get("battery_soc_pct", pd.Series([BATTERY.initial_soc_pct])).iloc[0]) / 100.0
    energy = float(np.clip(energy, min_energy, max_energy))

    records: list[dict[str, object]] = []
    for idx, row in enumerate(work.itertuples(index=False)):
        solar_kw = float(row.solar_kw)
        load_kw = float(row.load_kw)
        tariff = float(row.tariff_inr_kwh)
        surplus_kw = solar_kw - load_kw
        action = "idle"
        reason = "Hold battery inside safe band; no economic dispatch needed."
        battery_power_kw = 0.0

        if surplus_kw > 5.0 and energy < max_energy - 1e-6:
            charge_kw = min(surplus_kw, BATTERY.max_charge_kw, (max_energy - energy) / BATTERY.charge_efficiency)
            energy += charge_kw * BATTERY.charge_efficiency
            battery_power_kw = -charge_kw
            action = "charge"
            reason = "Solar surplus available; charging BESS without grid import."
        elif (tariff >= 8.0 or load_kw >= MICROGRID.peak_load_risk_kw) and surplus_kw < -3.0 and energy > min_energy + 1e-6:
            discharge_kw = min(-surplus_kw, BATTERY.max_discharge_kw, (energy - min_energy) * BATTERY.discharge_efficiency)
            energy -= discharge_kw / BATTERY.discharge_efficiency
            battery_power_kw = discharge_kw
            action = "discharge"
            reason = "Peak tariff or high demand; discharging BESS to reduce grid purchase."
        else:
            lookahead = work.iloc[idx + 1 : idx + 19]
            future_peak_need = bool(
                not lookahead.empty
                and ((lookahead["tariff_inr_kwh"] >= 8.0) & (lookahead["load_kw"] > lookahead["solar_kw"] + 5.0)).any()
            )

        if action == "idle" and tariff <= 3.0 and future_peak_need and energy < (BATTERY.capacity_kwh * 0.75):
            charge_kw = min(18.0, BATTERY.max_charge_kw, (max_energy - energy) / BATTERY.charge_efficiency)
            energy += charge_kw * BATTERY.charge_efficiency
            battery_power_kw = -charge_kw
            action = "charge"
            reason = "Off-peak tariff; pre-charging BESS for peak-period cost reduction."

        soc_pct = energy / BATTERY.capacity_kwh * 100.0
        grid_kw = max(load_kw - solar_kw - max(battery_power_kw, 0.0) + max(-battery_power_kw, 0.0), 0.0)
        renewable_used_kw = min(solar_kw, load_kw + max(-battery_power_kw, 0.0))
        curtailed_kw = max(solar_kw - renewable_used_kw, 0.0)

        records.append(
            {
                "timestamp": row.timestamp,
                "time": str(row.timestamp),
                "solar_kw": round(solar_kw, 3),
                "load_kw": round(load_kw, 3),
                "battery_soc_pct": round(soc_pct, 3),
                "battery_power_kw": round(battery_power_kw, 3),
                "grid_kw": round(grid_kw, 3),
                "tariff_inr_kwh": round(tariff, 2),
                "cost_inr": round(grid_kw * tariff, 3),
                "renewable_used_kw": round(renewable_used_kw, 3),
                "curtailed_kw": round(curtailed_kw, 3),
                "action": action,
                "reason": reason,
            }
        )

    return pd.DataFrame(records)


def latest_operator_recommendation(df: pd.DataFrame) -> dict[str, object]:
    table = build_dispatch_table(df, horizon_hours=1)
    if table.empty:
        return {"recommendation": "No dispatch data available", "reason": "EMS dataset is empty."}
    row = table.iloc[0]
    label = {
        "charge": "System recommends: Charge battery now",
        "discharge": "System recommends: Discharge battery now",
        "idle": "System recommends: Hold battery now",
    }[row["action"]]
    return {
        "recommendation": label,
        "action": row["action"],
        "reason": row["reason"],
        "battery_soc_pct": row["battery_soc_pct"],
        "grid_kw": row["grid_kw"],
        "tariff_inr_kwh": row["tariff_inr_kwh"],
    }
