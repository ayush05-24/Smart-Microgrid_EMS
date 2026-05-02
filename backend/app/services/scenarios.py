from __future__ import annotations

import pandas as pd

from ..config import MICROGRID
from .alerts import detect_alerts
from .dispatch import build_dispatch_table, latest_operator_recommendation
from .metrics import compute_performance_metrics
from ..utils import rounded_records


SUPPORTED_SCENARIOS = {"normal", "peak_load", "high_load", "low_solar", "tariff_spike"}


def run_scenario(df: pd.DataFrame, scenario: str, horizon_hours: int = 48) -> dict[str, object]:
    scenario = scenario.lower().strip()
    if scenario == "high_load":
        scenario = "peak_load"
    if scenario not in SUPPORTED_SCENARIOS:
        raise ValueError(f"Unsupported scenario '{scenario}'. Use one of {sorted(SUPPORTED_SCENARIOS)}")

    work = df.head(horizon_hours).copy().reset_index(drop=True)
    description = "Normal operating conditions"
    if scenario == "peak_load":
        work["load_kw"] = (work["load_kw"] * 1.24).clip(upper=MICROGRID.load_max_kw)
        description = "Peak load event: demand increased by 24 percent within feeder limits."
    elif scenario == "low_solar":
        daylight = work["solar_kw"] > 2.0
        work.loc[daylight, "solar_kw"] = (work.loc[daylight, "solar_kw"] * 0.38).clip(lower=0)
        description = "Low solar event: cloud cover reduces daylight PV output to 38 percent."
    elif scenario == "tariff_spike":
        work["tariff_inr_kwh"] = work["tariff_inr_kwh"].where(work["tariff_inr_kwh"] < 8.0, 11.5)
        description = "Tariff spike event: evening peak import price rises to 11.5 INR/kWh."

    dispatch_df = build_dispatch_table(work, horizon_hours=len(work))
    metrics = compute_performance_metrics(work, horizon_hours=len(work), prefix=f"scenario_{scenario}")
    alerts = detect_alerts(work, dispatch_df)
    return {
        "scenario": scenario,
        "description": description,
        "recommendation": latest_operator_recommendation(work),
        "metrics": metrics,
        "alerts": alerts,
        "decisions": rounded_records(dispatch_df.head(24), 3),
    }
