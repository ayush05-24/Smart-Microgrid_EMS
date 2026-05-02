# Report Vs Implementation Audit

This file compares the report `C:/Users/ayush/Desktop/VIT_BTech_Report_Ayush.pdf` with the current project implementation.

The short answer:

> Most major report claims are implemented. The main mismatch is that the report describes continuous-action PPO, while the current code uses a discrete action space: idle, charge, discharge. The project also uses wind speed as a feature but does not dispatch a wind turbine model.

## High-Level Coverage Matrix

| Report item | Project status | Evidence |
|---|---|---|
| NASA POWER dataset with 52,608 hourly rows | Present | `data/processed/cleaned_nasa_power.csv`, cleaning report shows 52,608 rows. |
| Data cleaning and feature standardization | Present | `backend/app/data/cleaning.py`. |
| Missing-value handling | Present | Time interpolation plus forward/backward fill. |
| Timestamp conversion | Present | UTC timestamps converted to Asia/Kolkata local timestamps. |
| Normalized features | Present | MinMax scalers saved in `models/scalers/`. |
| Realistic synthetic load | Present | Morning peak, evening peak, weekend factor, seasonal factor, temperature/humidity load, noise, spikes. |
| India time-of-use tariff | Present | INR 2.6 off-peak, INR 5.6 mid, INR 9.2 peak. |
| 180 kWh BESS | Present | `backend/app/config.py`. |
| SoC safety limits | Present | 20 percent to 90 percent in code. |
| LSTM solar forecast | Present | `models/forecast/solar_kw_lstm.pt`, forecast CSV, loss and prediction plots. |
| LSTM load forecast | Present | `models/forecast/load_kw_lstm.pt`, forecast CSV, loss and prediction plots. |
| GPU training | Present | Training reports show device `cuda`. API health shows NVIDIA RTX 3060 Laptop GPU. |
| PPO training | Present | `models/ppo/microgrid_ppo.zip`, reward trace, action samples, reward plot. |
| FastAPI backend | Present | `backend/app/main.py`. |
| Operator dashboard | Present and improved | React dashboard in `frontend/src/App.jsx`. |
| Alerts | Present | `backend/app/services/alerts.py`. |
| Metrics | Present | `backend/app/services/metrics.py`. |
| Scenario simulation | Present | `backend/app/services/scenarios.py`. |
| MATLAB export | Present | `backend/app/services/exports.py`, files under `data/exports/`. |
| Live dashboard fallback/simulation | Present | Backend live simulator and frontend live stream button. |

## Items Fully Up To The Mark

### 1. NASA Dataset Handling

The report states that NASA POWER data is used as the meteorological base. This is implemented properly.

Evidence:

- Rows after cleaning: 52,608.
- Date range: 2020-01-01 05:30:00 to 2026-01-01 04:30:00.
- Missing values after cleaning: 0.
- Duplicate timestamps after cleaning: 0.

Implementation:

- `backend/app/data/cleaning.py`
- `data/processed/cleaning_report.json`

### 2. Synthetic Operational Data

The report requires synthetic operational data because NASA POWER provides weather but not facility load, tariff, or battery telemetry. The implementation creates these fields under realistic constraints.

Evidence:

- Load min: 26.383 kW.
- Load max: 151.913 kW.
- Configured load limits: 24 kW to 175 kW.
- Battery violations: 0.
- Tariff values: 2.6, 5.6, 9.2 INR/kWh.

Implementation:

- `backend/app/data/synthetic.py`
- `data/synthetic/synthetic_validation_report.json`

### 3. Forecasting

The report says two LSTM models are trained: solar and load. This is implemented using PyTorch and CUDA.

Current results:

| Model | MAE | RMSE | Device |
|---|---:|---:|---|
| Solar LSTM | 2.0748 kW | 3.5749 kW | cuda |
| Load LSTM | 3.5385 kW | 4.7597 kW | cuda |

Implementation:

- `backend/app/ml/lstm.py`
- `backend/scripts/train_forecasts.py`

### 4. Cost Optimization Result

The report mentions a 12.23 percent cost reduction over a seven-day evaluation. The implementation produces the same metric.

Current metrics:

| Metric | Value |
|---|---:|
| Baseline cost | INR 41,165.47 |
| Optimized cost | INR 36,130.22 |
| Savings | INR 5,035.25 |
| Savings percent | 12.23 percent |

Implementation:

- `backend/app/services/metrics.py`
- `data/reports/baseline_metrics_report.json`

### 5. Dashboard And Operator Explainability

The report emphasizes a SCADA-style dashboard and explainable dispatch strings. The project now implements a control-room dashboard with:

- Live KPIs.
- Power flow chart.
- Forecast chart.
- Dispatch recommendation.
- Action table with reasons.
- Alerts panel.
- Cost analytics.
- Sustainability metrics.
- Scenario simulator.
- Live stream controls.
- Override buttons: auto, force charge, force discharge, island mode.

Implementation:

- `frontend/src/App.jsx`
- `frontend/src/styles/app.css`
- `backend/app/services/dispatch.py`

## Mismatches Or Overclaims

These are not failures, but they should be explained honestly during presentation.

### 1. Continuous PPO Action Vs Discrete PPO Action

Report wording:

- The report describes a continuous action scalar for PPO battery dispatch.

Current code:

- `MicrogridPPOEnv` uses `spaces.Discrete(3)`.
- Actions are:
  - `0`: idle
  - `1`: charge
  - `2`: discharge

Defense:

- The original functional requirement asked for charge, discharge, and idle actions.
- Discrete action space is easier to validate and safer for operator-facing control.
- It reduces impossible intermediate behavior during a student project demo.
- The project can be upgraded to a continuous Box action space in future work.

What to say:

> The report describes the research direction as continuous-control PPO. The current implemented system uses a safer discrete dispatch action space because the operator interface and dashboard requirements are expressed as charge, discharge, and idle. This gives better explainability and avoids unsafe fractional control during demonstration.

### 2. Wind Generation

Report wording:

- It mentions wind generation in the state.

Current code:

- Wind speed is included as a weather/forecast feature.
- No wind turbine power curve is implemented.

Defense:

- NASA wind speed is used as an environmental feature.
- The implemented microgrid asset model is PV + BESS + grid.
- Wind turbine dispatch can be added with a power curve in future work.

### 3. Battery SoC Upper Limit

Report wording:

- Some sections mention 95 percent upper SoC limit.

Current code:

- Uses 90 percent maximum SoC.

Defense:

- 90 percent is more conservative for lithium-ion battery life.
- Lower upper bound reduces degradation and gives a stronger safety argument.

### 4. JavaScript Fallback Simulator

Report wording:

- Mentions a frontend JavaScript fallback simulator.

Current project:

- Uses backend live simulator plus frontend static cache fallback.

Defense:

- Backend simulation is more realistic because it uses the same battery/tariff/dispatch logic as the API.
- Frontend cache still prevents blank dashboard when backend is offline.

### 5. MATLAB/Simulink

Report wording:

- Talks about MATLAB/Simulink integration.

Current project:

- Exports CSV, MAT, validation reference CSV, and MATLAB runner script.
- Does not include a completed `.slx` Simulink model.

Defense:

- The data interface is implemented.
- The physical Simulink block diagram is a future integration deliverable.

## What Is Better Than The Report

Some implementation details are stronger than the report wording:

| Area | Improvement |
|---|---|
| Live simulation | Backend simulator is connected to API and dashboard. |
| Operator controls | Override modes are implemented. |
| Fallback behavior | Dashboard falls back to local cached API JSON. |
| Documentation | Dedicated live-data, EDA, and audit docs exist. |
| Test coverage | Backend tests validate data constraints, metrics, and live simulator safety. |
| Dashboard usability | Layout is denser and easier for grid operators than a purely visual demo page. |

## Final Audit Conclusion

The project is substantially aligned with the report. The system contains the major pieces required for an intelligent microgrid EMS:

- Data pipeline.
- Synthetic realistic operational dataset.
- GPU LSTM forecasting.
- PPO training.
- Dispatch decision engine.
- Battery health tracking.
- Alerts.
- Metrics.
- Scenario simulation.
- FastAPI.
- React dashboard.
- MATLAB export.
- EDA and validation artifacts.

The only technical claim that should be corrected or carefully defended is continuous-action PPO. Current implementation is discrete-action PPO. This is acceptable for a safety-focused operator dashboard, but the report should not claim exact continuous-action implementation unless the environment is later upgraded.

