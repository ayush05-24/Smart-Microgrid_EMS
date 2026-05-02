from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..config import PLOTS_DIR, REPORT_DIR, ensure_project_dirs
from ..utils import write_json
from .battery import battery_health_report
from .dispatch import build_dispatch_table


def compute_performance_metrics(df: pd.DataFrame, horizon_hours: int = 24 * 7, prefix: str = "system") -> dict[str, object]:
    ensure_project_dirs()
    work = df.head(horizon_hours).copy().reset_index(drop=True)
    dispatch_df = build_dispatch_table(work, horizon_hours=len(work))

    baseline_grid_kw = (work["load_kw"] - work["solar_kw"]).clip(lower=0)
    baseline_cost = float((baseline_grid_kw * work["tariff_inr_kwh"]).sum())
    optimized_cost = float(dispatch_df["cost_inr"].sum())
    savings = baseline_cost - optimized_cost
    savings_pct = (savings / baseline_cost * 100.0) if baseline_cost > 0 else 0.0

    total_load = float(work["load_kw"].sum())
    total_solar = float(work["solar_kw"].sum())
    total_grid = float(dispatch_df["grid_kw"].sum())
    renewable_used = float(dispatch_df["renewable_used_kw"].sum())
    renewable_utilization_pct = (renewable_used / total_solar * 100.0) if total_solar > 0 else 0.0
    grid_dependency_pct = (total_grid / total_load * 100.0) if total_load > 0 else 0.0
    renewable_share_pct = (renewable_used / total_load * 100.0) if total_load > 0 else 0.0
    self_sufficiency_pct = max(0.0, 100.0 - grid_dependency_pct)

    report = {
        "horizon_hours": int(len(work)),
        "baseline_cost_inr": round(baseline_cost, 2),
        "optimized_cost_inr": round(optimized_cost, 2),
        "cost_savings_inr": round(savings, 2),
        "cost_savings_pct": round(savings_pct, 2),
        "renewable_utilization_pct": round(renewable_utilization_pct, 2),
        "renewable_share_pct": round(renewable_share_pct, 2),
        "grid_dependency_pct": round(grid_dependency_pct, 2),
        "self_sufficiency_pct": round(self_sufficiency_pct, 2),
        "total_load_kwh": round(total_load, 2),
        "total_solar_kwh": round(total_solar, 2),
        "total_grid_kwh": round(total_grid, 2),
        "battery": battery_health_report(dispatch_df),
    }
    dispatch_df.to_csv(REPORT_DIR / f"{prefix}_dispatch_report.csv", index=False)
    write_json(REPORT_DIR / f"{prefix}_metrics_report.json", report)
    _plot_cost_comparison(work, dispatch_df, baseline_grid_kw, prefix)
    _plot_energy_mix(report, prefix)
    return report


def _plot_cost_comparison(work: pd.DataFrame, dispatch_df: pd.DataFrame, baseline_grid_kw: pd.Series, prefix: str) -> None:
    cost_df = pd.DataFrame(
        {
            "timestamp": work["timestamp"],
            "baseline_cost": baseline_grid_kw.to_numpy() * work["tariff_inr_kwh"].to_numpy(),
            "optimized_cost": dispatch_df["cost_inr"].to_numpy(),
        }
    )
    daily = cost_df.set_index("timestamp").resample("D").sum()
    fig, ax = plt.subplots(figsize=(12, 5))
    daily[["baseline_cost", "optimized_cost"]].plot(kind="bar", ax=ax, color=["#868e96", "#2f9e44"])
    ax.set_title("Cost Optimization Comparison")
    ax.set_ylabel("INR/day")
    ax.set_xlabel("Date")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / f"{prefix}_cost_optimization.png", dpi=150)
    plt.close(fig)


def _plot_energy_mix(report: dict[str, object], prefix: str) -> None:
    labels = ["Renewable share", "Grid dependency", "Self sufficiency"]
    values = [
        float(report["renewable_share_pct"]),
        float(report["grid_dependency_pct"]),
        float(report["self_sufficiency_pct"]),
    ]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, values, color=["#2f9e44", "#1971c2", "#0f766e"])
    ax.set_ylim(0, 100)
    ax.set_ylabel("%")
    ax.set_title("Sustainability and Grid Dependency Metrics")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / f"{prefix}_sustainability_metrics.png", dpi=150)
    plt.close(fig)

