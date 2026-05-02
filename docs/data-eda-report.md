# Data EDA Report

Generated from the actual project data files.

## Source Data

| Item | Value |
|---|---:|
| Cleaned NASA rows | 52,608 |
| EMS rows | 52,608 |
| Start timestamp | 2020-01-01 05:30:00 |
| End timestamp | 2026-01-01 04:30:00 |
| Duplicate timestamps after cleaning | 0 |
| Missing cells after cleaning | 0 |

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
| Peak load | 151.91 kW |
| 95th percentile load | 108.57 kW |
| Solar zero or near-zero hours | 48.10% |
| Total simulated load | 3,844,827.29 kWh-equivalent |
| Total PV generation potential | 1,275,872.00 kWh-equivalent |
| Strongest temperature-load lag | 0 hours |
| Correlation at strongest lag | 0.6072 |

## Statistical Summary

| stat | ghi | dni | diffuse_irradiance | temperature_c | wind_speed_mps | humidity_pct | precipitation_mm | solar_kw | load_kw | tariff_inr_kwh | battery_soc_pct | battery_power_kw |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| count | 52608.000 | 52608.000 | 52608.000 | 52608.000 | 52608.000 | 52608.000 | 52608.000 | 52608.000 | 52608.000 | 52608.000 | 52608.000 | 52608.000 |
| mean | 216.967 | 128.985 | 104.025 | 26.836 | 3.238 | 73.753 | 3.572 | 24.252 | 73.084 | 5.200 | 24.576 | -0.085 |
| std | 294.485 | 206.295 | 131.098 | 4.976 | 1.633 | 21.557 | 11.199 | 32.760 | 20.702 | 2.236 | 12.426 | 8.963 |
| min | 0.000 | 0.000 | 0.000 | 13.430 | 0.030 | 11.170 | 0.000 | 0.000 | 26.383 | 2.600 | 20.000 | -55.000 |
| 1% | 0.000 | 0.000 | 0.000 | 17.050 | 0.540 | 20.920 | 0.000 | 0.000 | 36.756 | 2.600 | 20.000 | -28.370 |
| 5% | 0.000 | 0.000 | 0.000 | 19.180 | 1.100 | 30.600 | 0.000 | 0.000 | 42.101 | 2.600 | 20.000 | -10.462 |
| 25% | 0.000 | 0.000 | 0.000 | 23.590 | 2.060 | 59.830 | 0.000 | 0.000 | 56.550 | 2.600 | 20.000 | 0.000 |
| 50% | 7.190 | 0.000 | 9.400 | 26.180 | 2.910 | 79.440 | 0.030 | 0.818 | 72.019 | 5.600 | 20.000 | 0.000 |
| 75% | 428.428 | 210.432 | 211.492 | 29.820 | 4.200 | 91.930 | 2.070 | 48.191 | 88.382 | 5.600 | 20.000 | 0.000 |
| 95% | 826.312 | 595.809 | 354.860 | 36.340 | 6.260 | 98.670 | 18.686 | 91.615 | 108.575 | 9.200 | 54.294 | 0.000 |
| 99% | 941.670 | 754.370 | 430.438 | 39.640 | 8.140 | 100.000 | 48.567 | 103.633 | 118.667 | 9.200 | 83.452 | 57.261 |
| max | 1043.150 | 1100.000 | 540.250 | 44.520 | 14.630 | 100.000 | 300.000 | 114.615 | 151.913 | 9.200 | 90.000 | 58.000 |

## Tariff Distribution

| tariff_inr_kwh | hours |
| --- | --- |
| 2.600 | 17536.000 |
| 5.600 | 26304.000 |
| 9.200 | 8768.000 |

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
