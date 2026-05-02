# Data Used, Synthetic Data, And EDA

This file explains the data used in the project, what is real, what is synthetic, and what the EDA shows.

## Data Sources

### Real Source Data

The real source dataset is the NASA POWER meteorological CSV:

```text
data/raw/Dataset_5yrs.csv
```

After cleaning:

```text
data/processed/cleaned_nasa_power.csv
```

The dataset contains hourly weather/solar resource values:

| Field | Meaning |
|---|---|
| GHI | Global horizontal irradiance. |
| DNI | Direct normal irradiance. |
| Diffuse irradiance | Diffuse solar component. |
| Temperature | Ambient temperature. |
| Wind speed | Wind speed at 10 m. |
| Humidity | Relative humidity. |
| Precipitation | Corrected precipitation. |

Current cleaned dataset:

| Metric | Value |
|---|---:|
| Rows | 52,608 |
| Start timestamp | 2020-01-01 05:30:00 |
| End timestamp | 2026-01-01 04:30:00 |
| Duplicate timestamps | 0 |
| Missing cells after cleaning | 0 |

## Synthetic Data

NASA POWER does not provide:

- Facility load demand.
- Grid tariff.
- Battery SoC.
- Battery power.
- Grid import.
- Dispatch action.

So the project generates these under realistic constraints.

Synthetic dataset:

```text
data/processed/ems_dataset.csv
```

## What Is Synthetic And Why

| Synthetic field | Why it is needed | How realism is enforced |
|---|---|---|
| `solar_kw` | Converts irradiance into PV power. | Uses PV capacity, performance ratio, temperature/humidity derating, clipping. |
| `load_kw` | NASA does not provide site demand. | Morning/evening peaks, weekday/weekend effect, seasonality, cooling load, humidity, noise, events, hard limits. |
| `tariff_inr_kwh` | Needed for cost optimization. | Deterministic India-style time-of-use tariff. |
| `battery_soc_pct` | Needed for BESS dispatch. | 20 to 90 percent SoC safety band. |
| `battery_power_kw` | Shows charge/discharge. | Max charge/discharge power and efficiency constraints. |
| `battery_energy_kwh` | Converts SoC to stored energy. | Based on 180 kWh capacity. |
| `battery_violation` | Safety validation. | Should remain 0. |
| `derived features` | Needed for ML. | Hour/day cyclic encodings, lags, rolling averages. |

## Current Synthetic Validation

| Signal | Result |
|---|---:|
| Load min | 26.383 kW |
| Load max | 151.913 kW |
| Load mean | 73.084 kW |
| Load constraint | 24 to 175 kW |
| Tariff values | 2.6, 5.6, 9.2 INR/kWh |
| Battery capacity | 180 kWh |
| Battery min SoC | 20 percent |
| Battery max SoC | 90 percent |
| Observed min SoC | 20 percent |
| Observed max SoC | 90 percent |
| Battery violations | 0 |

## EDA Summary

Detailed generated EDA report:

```text
docs/data-eda-report.md
```

EDA plot folder:

```text
data/outputs/eda/
```

Key findings:

| Finding | Value |
|---|---:|
| Peak load | 151.91 kW |
| 95th percentile load | 108.57 kW |
| Solar zero or near-zero hours | 48.10 percent |
| Total simulated load | 3,844,827.29 kWh-equivalent |
| Total PV generation potential | 1,275,872.00 kWh-equivalent |
| Strongest temperature-load lag | 0 hours |
| Correlation at strongest lag | 0.6072 |

## Weather Feature Ranges After Cleaning

| Feature | Min | Max | Mean |
|---|---:|---:|---:|
| GHI | 0.0 | 1043.15 | 216.9669 |
| DNI | 0.0 | 1100.0 | 128.9846 |
| Diffuse irradiance | 0.0 | 540.25 | 104.0249 |
| Temperature | 13.43 | 44.52 | 26.8362 |
| Wind speed | 0.03 | 14.63 | 3.2380 |
| Humidity | 11.17 | 100.0 | 73.7525 |
| Precipitation | 0.0 | 300.0 | 3.5717 |

## EDA Plot Interpretation

### 1. Correlation Heatmap

Path:

```text
data/outputs/eda/eda_correlation_heatmap.png
```

What it shows:

- Relationships between weather, solar, load, tariff, and battery features.
- Whether solar is strongly tied to irradiance.
- Whether temperature and load are related.

How to use it:

- Justifies feature selection for forecasting.
- Shows that the model has meaningful explanatory variables.

### 2. Hourly Profile

Path:

```text
data/outputs/eda/eda_hourly_profile.png
```

What it shows:

- Average solar/load/tariff behavior by hour.

Expected pattern:

- Solar rises after morning, peaks in daytime, falls at evening.
- Load has morning and evening peaks.
- Tariff is highest in evening.

Why it matters:

- This is the central EMS problem: evening tariff is high when solar is low.
- Battery dispatch is valuable because it can move energy across time.

### 3. Monthly Profile

Path:

```text
data/outputs/eda/eda_monthly_profile.png
```

What it shows:

- Seasonal changes in weather, solar, and load.

Why it matters:

- Summer load increases due to cooling.
- Solar resource varies across months.
- Forecasting and dispatch must handle seasonality.

### 4. Temperature-Load Lag

Path:

```text
data/outputs/eda/eda_temperature_load_lag.png
```

What it shows:

- Correlation between temperature and load at different time lags.

Current finding:

- Strongest correlation is at 0 hours with correlation 0.6072.

Important report note:

- The report text claims an approximately 2.5-hour temperature-load lag.
- Current generated EDA does not support that exact claim.

Defense:

> The current synthetic load generator includes immediate cooling load response. Therefore the strongest lag appears at 0 hours. A future version can add thermal inertia to shift peak load response by 2 to 3 hours if exact report alignment is required.

### 5. Load Duration Curve

Path:

```text
data/outputs/eda/eda_load_duration_curve.png
```

What it shows:

- Loads sorted from highest to lowest.
- How often extreme load appears.

Why it matters:

- Helps size battery and grid connection.
- Shows whether high peaks are rare or frequent.
- Supports peak demand risk threshold selection.

### 6. Signal Distributions

Path:

```text
data/outputs/eda/eda_distributions.png
```

What it shows:

- Distribution of key weather and EMS signals.

Why it matters:

- Confirms values are not unrealistic.
- Shows solar has many zero values because night hours exist.
- Shows load distribution stays inside practical range.

### 7. Recent Battery/Grid Profile

Path:

```text
data/outputs/eda/eda_battery_grid_recent.png
```

What it shows:

- Recent battery SoC and grid import behavior.

Why it matters:

- Shows how BESS dispatch affects grid import.
- Helps validate safety and operational behavior.

## Data Flow

```text
NASA POWER raw CSV
    -> cleaning.py
    -> cleaned_nasa_power.csv
    -> synthetic.py
    -> ems_dataset.csv
    -> LSTM training / PPO training / metrics / API
    -> React dashboard
```

Live mode data flow:

```text
Start live stream button
    -> POST /live/start
    -> live_simulator.py background thread
    -> data/runtime/live_telemetry.jsonl
    -> recent_window()
    -> forecast / optimize / metrics / alerts endpoints
    -> dashboard refresh every 1.5 seconds
```

## Why Synthetic Data Is Defensible

Synthetic data is defensible because:

- NASA POWER provides weather but not private facility demand or BESS telemetry.
- Facility load profiles are often unavailable due to privacy and hardware access.
- Synthetic load follows real constraints: morning/evening peaks, weekday/weekend variation, seasonal cooling, weather effects, noise, and bounded spikes.
- Battery simulation respects capacity, SoC limits, charge/discharge limits, and efficiency.
- Tariff is deterministic and within India TOU ranges.

Important:

> Synthetic data should be presented as a realistic operating layer built on top of real NASA weather data, not as measured building load data.

## Best Way To Explain The Dataset In Presentation

Use this statement:

> The meteorological base is real NASA POWER hourly data. Since the project does not have access to a private site's smart meter, tariff bill, inverter, and BMS telemetry, the operational layer is generated synthetically but constrained by real microgrid behavior: bounded load, time-of-use tariff, PV physics, battery capacity, efficiency, and SoC safety limits.

## Data Limitations

| Limitation | Effect | Defense |
|---|---|---|
| No real smart meter load | Load is synthetic. | Synthetic load is constrained and realistic. |
| No real BMS telemetry | Battery behavior is simulated. | Physics constraints are implemented and validated. |
| No real inverter telemetry | PV output is derived from irradiance. | PV formula uses capacity, PR, and derating. |
| No real tariff API | Tariff schedule is fixed. | Deterministic TOU tariff matches project requirement. |
| NASA data is hourly | Limited high-frequency weather detail. | Live simulator provides high-frequency dashboard behavior, while training uses hourly data. |

## EDA Conclusion

The EDA supports the EMS design:

- Solar is variable and often unavailable at night.
- Load has peaks and weather dependency.
- Evening tariff creates an economic problem.
- Battery dispatch can reduce peak grid import.
- Forecasting is useful because the best battery action depends on future load, solar, and tariff.
- The generated synthetic layer remains within realistic ranges and battery safety constraints.

