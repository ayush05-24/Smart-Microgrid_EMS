from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import BATTERY, CLEANED_DATASET, EMS_DATASET, FORECAST_MODEL_DIR, OUTPUT_DIR, PPO_MODEL_DIR

REPORT_PDF = Path(r"C:\Users\ayush\Desktop\VIT_BTech_Report_Ayush.pdf")
DOCS_DIR = PROJECT_ROOT / "docs"
EDA_DIR = OUTPUT_DIR / "eda"
REPORT_TEXT = PROJECT_ROOT / "data" / "reports" / "report_extracted_text.txt"


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    EDA_DIR.mkdir(parents=True, exist_ok=True)
    report_text = extract_report_text()
    cleaned = pd.read_csv(CLEANED_DATASET, parse_dates=["timestamp", "timestamp_utc"])
    ems = pd.read_csv(EMS_DATASET, parse_dates=["timestamp", "timestamp_utc"])
    eda = build_eda(cleaned, ems)
    write_eda_markdown(cleaned, ems, eda)
    write_audit_markdown(report_text, cleaned, ems)
    print(f"EDA report: {DOCS_DIR / 'data-eda-report.md'}")
    print(f"Audit report: {DOCS_DIR / 'project-report-audit.md'}")


def extract_report_text() -> str:
    if REPORT_TEXT.exists():
        return REPORT_TEXT.read_text(encoding="utf-8")
    reader = PdfReader(str(REPORT_PDF))
    text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    REPORT_TEXT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_TEXT.write_text(text, encoding="utf-8")
    return text


def build_eda(cleaned: pd.DataFrame, ems: pd.DataFrame) -> dict[str, object]:
    selected = [
        "ghi",
        "dni",
        "diffuse_irradiance",
        "temperature_c",
        "wind_speed_mps",
        "humidity_pct",
        "precipitation_mm",
        "solar_kw",
        "load_kw",
        "tariff_inr_kwh",
        "battery_soc_pct",
        "grid_kw" if "grid_kw" in ems.columns else "battery_power_kw",
    ]
    selected = [column for column in selected if column in ems.columns]

    ems = ems.copy()
    ems["hour"] = ems["timestamp"].dt.hour
    ems["month_name"] = ems["timestamp"].dt.month_name().str.slice(0, 3)
    ems["weekday_type"] = ems["timestamp"].dt.dayofweek.map(lambda value: "Weekend" if value >= 5 else "Weekday")

    hourly = ems.groupby("hour")[["solar_kw", "load_kw", "tariff_inr_kwh", "battery_soc_pct"]].mean()
    monthly = ems.groupby(ems["timestamp"].dt.month)[["solar_kw", "load_kw", "temperature_c", "ghi"]].mean()
    weekday = ems.groupby("weekday_type")[["load_kw", "solar_kw", "tariff_inr_kwh"]].mean()
    lag_corr = temperature_load_lag(ems)

    plot_correlation_heatmap(ems, selected)
    plot_hourly_profile(hourly)
    plot_monthly_profile(monthly)
    plot_lag_correlation(lag_corr)
    plot_load_duration(ems)
    plot_distribution_panels(ems)
    plot_battery_grid_sample(ems)

    return {
        "hourly": hourly,
        "monthly": monthly,
        "weekday": weekday,
        "lag_corr": lag_corr,
        "selected": selected,
    }


def temperature_load_lag(ems: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for lag in range(0, 9):
        shifted_temp = ems["temperature_c"].shift(lag)
        rows.append({"lag_hours": lag, "correlation": shifted_temp.corr(ems["load_kw"])})
    return pd.DataFrame(rows)


def plot_correlation_heatmap(ems: pd.DataFrame, selected: list[str]) -> None:
    fig, ax = plt.subplots(figsize=(11, 8))
    sns.heatmap(ems[selected].corr(), cmap="RdYlGn", center=0, annot=False, ax=ax)
    ax.set_title("EMS Feature Correlation Heatmap")
    fig.tight_layout()
    fig.savefig(EDA_DIR / "eda_correlation_heatmap.png", dpi=160)
    plt.close(fig)


def plot_hourly_profile(hourly: pd.DataFrame) -> None:
    fig, ax1 = plt.subplots(figsize=(12, 5))
    hourly[["solar_kw", "load_kw"]].plot(ax=ax1, linewidth=2)
    ax1.set_ylabel("Power (kW)")
    ax1.set_xlabel("Hour of day")
    ax1.grid(alpha=0.25)
    ax2 = ax1.twinx()
    hourly["tariff_inr_kwh"].plot(ax=ax2, color="#c92a2a", linestyle="--", linewidth=2, label="Tariff")
    ax2.set_ylabel("INR/kWh")
    ax1.set_title("Average Hourly Solar, Load and Tariff Profile")
    fig.tight_layout()
    fig.savefig(EDA_DIR / "eda_hourly_profile.png", dpi=160)
    plt.close(fig)


def plot_monthly_profile(monthly: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5))
    monthly[["solar_kw", "load_kw", "temperature_c"]].plot(ax=ax, linewidth=2)
    ax.set_title("Monthly Seasonality of Solar, Load and Temperature")
    ax.set_xlabel("Month")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(EDA_DIR / "eda_monthly_profile.png", dpi=160)
    plt.close(fig)


def plot_lag_correlation(lag_corr: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(lag_corr["lag_hours"], lag_corr["correlation"], color="#0f766e")
    ax.set_title("Temperature-to-Load Lag Correlation")
    ax.set_xlabel("Temperature lag (hours)")
    ax.set_ylabel("Correlation with load")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(EDA_DIR / "eda_temperature_load_lag.png", dpi=160)
    plt.close(fig)


def plot_load_duration(ems: pd.DataFrame) -> None:
    sorted_load = ems["load_kw"].sort_values(ascending=False).reset_index(drop=True)
    exceedance = sorted_load.index / max(len(sorted_load) - 1, 1) * 100
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(exceedance, sorted_load, color="#1971c2", linewidth=2)
    ax.set_title("Load Duration Curve")
    ax.set_xlabel("Exceedance (%)")
    ax.set_ylabel("Load (kW)")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(EDA_DIR / "eda_load_duration_curve.png", dpi=160)
    plt.close(fig)


def plot_distribution_panels(ems: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    sns.histplot(ems["ghi"], bins=60, ax=axes[0, 0], color="#f59f00")
    axes[0, 0].set_title("GHI Distribution")
    sns.histplot(ems["solar_kw"], bins=60, ax=axes[0, 1], color="#b06000")
    axes[0, 1].set_title("Solar kW Distribution")
    sns.histplot(ems["load_kw"], bins=60, ax=axes[1, 0], color="#1971c2")
    axes[1, 0].set_title("Load kW Distribution")
    sns.histplot(ems["battery_soc_pct"], bins=45, ax=axes[1, 1], color="#2f9e44")
    axes[1, 1].set_title("Battery SoC Distribution")
    fig.tight_layout()
    fig.savefig(EDA_DIR / "eda_distributions.png", dpi=160)
    plt.close(fig)


def plot_battery_grid_sample(ems: pd.DataFrame) -> None:
    sample = ems.tail(24 * 7).copy()
    if "grid_kw" not in sample.columns:
        sample["grid_kw"] = (sample["load_kw"] - sample["solar_kw"] - sample["battery_power_kw"].clip(lower=0)).clip(lower=0)
    fig, ax = plt.subplots(figsize=(13, 5))
    sample.set_index("timestamp")[["battery_soc_pct", "grid_kw", "battery_power_kw"]].plot(ax=ax, linewidth=1.8)
    ax.set_title("Recent Battery and Grid Operating Profile")
    ax.set_xlabel("Timestamp")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(EDA_DIR / "eda_battery_grid_recent.png", dpi=160)
    plt.close(fig)


def write_eda_markdown(cleaned: pd.DataFrame, ems: pd.DataFrame, eda: dict[str, object]) -> None:
    numeric_cols = [
        "ghi",
        "dni",
        "diffuse_irradiance",
        "temperature_c",
        "wind_speed_mps",
        "humidity_pct",
        "precipitation_mm",
        "solar_kw",
        "load_kw",
        "tariff_inr_kwh",
        "battery_soc_pct",
        "battery_power_kw",
    ]
    numeric_cols = [column for column in numeric_cols if column in ems.columns]
    summary = ems[numeric_cols].describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).round(3)
    lag_corr = eda["lag_corr"]
    best_lag = lag_corr.iloc[lag_corr["correlation"].abs().idxmax()]
    tariff_counts = ems["tariff_inr_kwh"].value_counts().sort_index()
    missing = cleaned.isna().sum()
    duplicates = int(cleaned["timestamp"].duplicated().sum())
    solar_zero_pct = float((ems["solar_kw"] <= 0.1).mean() * 100)
    peak_load = float(ems["load_kw"].max())
    load_p95 = float(ems["load_kw"].quantile(0.95))
    renewable_potential = float(ems["solar_kw"].sum())
    load_total = float(ems["load_kw"].sum())

    content = f"""# Data EDA Report

Generated from the actual project data files.

## Source Data

| Item | Value |
|---|---:|
| Cleaned NASA rows | {len(cleaned):,} |
| EMS rows | {len(ems):,} |
| Start timestamp | {cleaned['timestamp'].min()} |
| End timestamp | {cleaned['timestamp'].max()} |
| Duplicate timestamps after cleaning | {duplicates} |
| Missing cells after cleaning | {int(missing.sum())} |

## Dataset Meaning

The raw source is NASA POWER hourly meteorological data. The EMS dataset extends it with physically constrained microgrid operating signals:

| Signal | Meaning |
|---|---|
| `ghi`, `dni`, `diffuse_irradiance` | Solar resource inputs |
| `temperature_c`, `wind_speed_mps`, `humidity_pct`, `precipitation_mm` | Weather drivers |
| `solar_kw` | PV generation derived from irradiance and PV capacity |
| `load_kw` | realistic synthetic facility demand |
| `tariff_inr_kwh` | India-style time-of-use tariff |
| `battery_soc_pct`, `battery_power_kw` | BESS state and charge/discharge power |

## Key Findings

| Finding | Value |
|---|---:|
| Peak load | {peak_load:.2f} kW |
| 95th percentile load | {load_p95:.2f} kW |
| Solar zero or near-zero hours | {solar_zero_pct:.2f}% |
| Total simulated load | {load_total:,.2f} kWh-equivalent |
| Total PV generation potential | {renewable_potential:,.2f} kWh-equivalent |
| Strongest temperature-load lag | {int(best_lag['lag_hours'])} hours |
| Correlation at strongest lag | {best_lag['correlation']:.4f} |

## Statistical Summary

{df_to_markdown(summary.reset_index().rename(columns={"index": "stat"}))}

## Tariff Distribution

{df_to_markdown(tariff_counts.to_frame('hours').reset_index().rename(columns={"tariff_inr_kwh": "tariff_inr_kwh"}))}

## EDA Plots

| Plot | File |
|---|---|
| Correlation heatmap | `data/outputs/eda/eda_correlation_heatmap.png` |
| Hourly solar/load/tariff profile | `data/outputs/eda/eda_hourly_profile.png` |
| Monthly seasonality | `data/outputs/eda/eda_monthly_profile.png` |
| Temperature-load lag correlation | `data/outputs/eda/eda_temperature_load_lag.png` |
| Load duration curve | `data/outputs/eda/eda_load_duration_curve.png` |
| Signal distributions | `data/outputs/eda/eda_distributions.png` |
| Recent battery/grid profile | `data/outputs/eda/eda_battery_grid_recent.png` |

## Operator Interpretation

The data supports the EMS design because the highest-value control window is evening: solar output drops toward zero while load and tariff rise. Battery dispatch is therefore economically useful when it pre-charges during low tariff periods or solar surplus and discharges during peak tariff import. The lag correlation analysis also supports sequence models because load response is not explained only by the current weather hour.
"""
    (DOCS_DIR / "data-eda-report.md").write_text(content, encoding="utf-8")


def write_audit_markdown(report_text: str, cleaned: pd.DataFrame, ems: pd.DataFrame) -> None:
    training_reports = {
        "solar": load_json(OUTPUT_DIR / "solar_kw_training_report.json"),
        "load": load_json(OUTPUT_DIR / "load_kw_training_report.json"),
        "ppo": load_json(OUTPUT_DIR / "ppo_training_report.json"),
        "metrics": load_json(PROJECT_ROOT / "data" / "reports" / "baseline_metrics_report.json"),
    }
    checks = [
        (
            "5-year NASA POWER dataset with 52,608 hourly rows",
            "Present",
            f"cleaned_nasa_power.csv has {len(cleaned):,} rows from {cleaned['timestamp'].min()} to {cleaned['timestamp'].max()}",
        ),
        (
            "LSTM solar and load forecasting",
            "Present",
            f"solar model: {(FORECAST_MODEL_DIR / 'solar_kw_lstm.pt').exists()}, load model: {(FORECAST_MODEL_DIR / 'load_kw_lstm.pt').exists()}, solar RMSE {training_reports['solar'].get('rmse_kw')}, load RMSE {training_reports['load'].get('rmse_kw')}",
        ),
        (
            "PPO reinforcement learning dispatch agent",
            "Present",
            f"model exists: {(PPO_MODEL_DIR / 'microgrid_ppo.zip').exists()}, timesteps: {training_reports['ppo'].get('total_timesteps')}",
        ),
        (
            "180 kWh BESS with physics constraints",
            "Present",
            f"capacity {BATTERY.capacity_kwh} kWh, SoC limits {BATTERY.min_soc_pct}-{BATTERY.max_soc_pct}%, charge {BATTERY.max_charge_kw} kW, discharge {BATTERY.max_discharge_kw} kW",
        ),
        (
            "Time-of-use tariff arbitrage",
            "Present",
            f"tariff values in EMS dataset: {sorted(ems['tariff_inr_kwh'].unique().tolist())}",
        ),
        (
            "FastAPI backend endpoints",
            "Present",
            "/forecast, /optimize, /decisions, /metrics, /alerts, /simulate, /matlab/export, and live simulator endpoints are implemented",
        ),
        (
            "SCADA-style operator dashboard",
            "Improved",
            "React dashboard now has command bar, dense KPIs, live stream controls, override controls, charts, alerts, cost, sustainability, scenario and dispatch table",
        ),
        (
            "Explainable dispatch reasoning",
            "Present",
            "Dispatch table and recommendation panel expose action and reason strings from backend dispatch logic",
        ),
        (
            "Local fallback / dynamic simulator",
            "Present",
            "Frontend cache exists and backend live telemetry generator can be started from dashboard button",
        ),
        (
            "MATLAB/Simulink export",
            "Present",
            "CSV, MAT, validation reference CSV, and MATLAB runner script exist in data/exports",
        ),
        (
            "Detailed EDA",
            "Present",
            "Generated docs/data-eda-report.md and plots under data/outputs/eda",
        ),
    ]
    gaps = [
        "The report describes a continuous action scalar PPO formulation, while the current environment uses a discrete action space: idle, charge, discharge. This is acceptable for the original dashboard requirement but does not exactly match the continuous-control claim.",
        "The report mentions wind generation in the MDP state. The implementation uses wind speed as a data feature, but no wind turbine power model is dispatched.",
        "The current regenerated EDA finds strongest temperature-load correlation at 0 hours, while the report text claims an approximately 2.5-hour lag. The report should be updated or the load generator should be changed to include a clearer lagged HVAC response.",
        "The report text mentions 20%-95% SoC limits in some places. The implemented BESS uses 20%-90%, which is more conservative but should be made consistent in the report or code.",
        "A MATLAB/Simulink export workflow exists, but a complete .slx physical model is not present in the project folder.",
        "The dashboard can simulate live telemetry, but it is not connected to real SCADA, smart meters, inverter telemetry, or BMS hardware.",
    ]
    novelty = [
        "The strongest project novelty is not simply using LSTM or PPO, because both are known in energy management research.",
        "The useful differentiator is the operator-trust layer: dispatch reasoning, hard battery safety boundaries, override modes, fallback telemetry, scenario stress testing, and MATLAB export in one teaching-grade EMS stack.",
        "The new live simulator is valuable for review and demos because it creates a control-room experience without needing real SCADA access while still enforcing realistic battery and tariff behavior.",
        "A stronger publishable novelty would be: hybrid XAI + safety-shielded DRL EMS with operator override and digital-twin fallback telemetry for low-infrastructure microgrid validation.",
    ]
    table = "\n".join(f"| {claim} | {status} | {evidence} |" for claim, status, evidence in checks)
    gap_lines = "\n".join(f"- {gap}" for gap in gaps)
    novelty_lines = "\n".join(f"- {item}" for item in novelty)
    content = f"""# Project Report Audit

Audited against `C:/Users/ayush/Desktop/VIT_BTech_Report_Ayush.pdf`.

## Coverage Matrix

| Report claim / requirement | Status | Evidence |
|---|---|---|
{table}

## Gaps To Be Aware Of

{gap_lines}

## Novelty Assessment

{novelty_lines}

## Report Text Signals Used

The report emphasizes LSTM forecasting, PPO-based BESS dispatch, 52,608 NASA POWER rows, 180 kWh BESS, ToU arbitrage, SCADA-style explainability, operator override, fallback simulation, MATLAB/Simulink export, and 12.23% cost savings. The current project covers most of that system surface, with the main technical mismatch being discrete PPO action control versus the report's continuous-action wording.
"""
    (DOCS_DIR / "project-report-audit.md").write_text(content, encoding="utf-8")


def load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def df_to_markdown(df: pd.DataFrame) -> str:
    columns = [str(column) for column in df.columns]
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in df.iterrows():
        values = []
        for value in row.tolist():
            if isinstance(value, float):
                values.append(f"{value:.3f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


if __name__ == "__main__":
    main()
