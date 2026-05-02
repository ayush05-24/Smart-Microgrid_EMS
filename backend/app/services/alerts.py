from __future__ import annotations

import pandas as pd

from ..config import BATTERY, MICROGRID


def detect_alerts(df: pd.DataFrame, dispatch_df: pd.DataFrame | None = None) -> list[dict[str, object]]:
    alerts: list[dict[str, object]] = []
    work = df.copy().reset_index(drop=True)
    if work.empty:
        return [{"severity": "critical", "type": "data", "message": "No EMS data available."}]

    latest = work.iloc[0]
    load_threshold = max(MICROGRID.peak_load_risk_kw, float(work["load_kw"].quantile(0.95)))
    risky = work[work["load_kw"] >= load_threshold].head(3)
    for row in risky.itertuples(index=False):
        alerts.append(
            {
                "severity": "high",
                "type": "peak_demand_risk",
                "timestamp": str(row.timestamp),
                "message": f"Peak demand risk: load forecast {row.load_kw:.1f} kW.",
            }
        )

    solar_drop = work["solar_kw"].diff().fillna(0)
    drops = work[solar_drop <= -MICROGRID.renewable_drop_kw].head(3)
    for row in drops.itertuples(index=False):
        alerts.append(
            {
                "severity": "medium",
                "type": "renewable_drop",
                "timestamp": str(row.timestamp),
                "message": f"Renewable drop expected: solar falls sharply near {row.timestamp}.",
            }
        )

    if dispatch_df is not None and not dispatch_df.empty:
        low_soc = dispatch_df[dispatch_df["battery_soc_pct"] <= BATTERY.min_soc_pct + 2.0].head(2)
        high_soc = dispatch_df[dispatch_df["battery_soc_pct"] >= BATTERY.max_soc_pct - 2.0].head(2)
        for row in low_soc.itertuples(index=False):
            alerts.append(
                {
                    "severity": "critical",
                    "type": "battery_low_soc",
                    "timestamp": str(row.timestamp),
                    "message": f"Battery near minimum safe SoC: {row.battery_soc_pct:.1f}%.",
                }
            )
        for row in high_soc.itertuples(index=False):
            alerts.append(
                {
                    "severity": "medium",
                    "type": "battery_high_soc",
                    "timestamp": str(row.timestamp),
                    "message": f"Battery near maximum safe SoC: {row.battery_soc_pct:.1f}%.",
                }
            )

    if float(latest["tariff_inr_kwh"]) >= 8.0 and float(latest["load_kw"]) > float(latest["solar_kw"]):
        alerts.append(
            {
                "severity": "high",
                "type": "peak_tariff_import",
                "timestamp": str(latest["timestamp"]),
                "message": "Grid import is exposed to peak tariff; dispatch battery if SoC allows.",
            }
        )

    return alerts[:12]

