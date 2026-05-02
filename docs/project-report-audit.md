# Project Report Audit

Audited against `C:/Users/ayush/Desktop/VIT_BTech_Report_Ayush.pdf`.

## Coverage Matrix

| Report claim / requirement | Status | Evidence |
|---|---|---|
| 5-year NASA POWER dataset with 52,608 hourly rows | Present | cleaned_nasa_power.csv has 52,608 rows from 2020-01-01 05:30:00 to 2026-01-01 04:30:00 |
| LSTM solar and load forecasting | Present | solar model: True, load model: True, solar RMSE 3.5749, load RMSE 4.7597 |
| PPO reinforcement learning dispatch agent | Present | model exists: True, timesteps: 20000 |
| 180 kWh BESS with physics constraints | Present | capacity 180.0 kWh, SoC limits 20.0-90.0%, charge 55.0 kW, discharge 58.0 kW |
| Time-of-use tariff arbitrage | Present | tariff values in EMS dataset: [2.6, 5.6, 9.2] |
| FastAPI backend endpoints | Present | /forecast, /optimize, /decisions, /metrics, /alerts, /simulate, /matlab/export, and live simulator endpoints are implemented |
| SCADA-style operator dashboard | Improved | React dashboard now has command bar, dense KPIs, live stream controls, override controls, charts, alerts, cost, sustainability, scenario and dispatch table |
| Explainable dispatch reasoning | Present | Dispatch table and recommendation panel expose action and reason strings from backend dispatch logic |
| Local fallback / dynamic simulator | Present | Frontend cache exists and backend live telemetry generator can be started from dashboard button |
| MATLAB/Simulink export | Present | CSV, MAT, validation reference CSV, and MATLAB runner script exist in data/exports |
| Detailed EDA | Present | Generated docs/data-eda-report.md and plots under data/outputs/eda |

## Gaps To Be Aware Of

- The report describes a continuous action scalar PPO formulation, while the current environment uses a discrete action space: idle, charge, discharge. This is acceptable for the original dashboard requirement but does not exactly match the continuous-control claim.
- The report mentions wind generation in the MDP state. The implementation uses wind speed as a data feature, but no wind turbine power model is dispatched.
- The current regenerated EDA finds strongest temperature-load correlation at 0 hours, while the report text claims an approximately 2.5-hour lag. The report should be updated or the load generator should be changed to include a clearer lagged HVAC response.
- The report text mentions 20%-95% SoC limits in some places. The implemented BESS uses 20%-90%, which is more conservative but should be made consistent in the report or code.
- A MATLAB/Simulink export workflow exists, but a complete .slx physical model is not present in the project folder.
- The dashboard can simulate live telemetry, but it is not connected to real SCADA, smart meters, inverter telemetry, or BMS hardware.

## Novelty Assessment

- The strongest project novelty is not simply using LSTM or PPO, because both are known in energy management research.
- The useful differentiator is the operator-trust layer: dispatch reasoning, hard battery safety boundaries, override modes, fallback telemetry, scenario stress testing, and MATLAB export in one teaching-grade EMS stack.
- The new live simulator is valuable for review and demos because it creates a control-room experience without needing real SCADA access while still enforcing realistic battery and tariff behavior.
- A stronger publishable novelty would be: hybrid XAI + safety-shielded DRL EMS with operator override and digital-twin fallback telemetry for low-infrastructure microgrid validation.

## Report Text Signals Used

The report emphasizes LSTM forecasting, PPO-based BESS dispatch, 52,608 NASA POWER rows, 180 kWh BESS, ToU arbitrage, SCADA-style explainability, operator override, fallback simulation, MATLAB/Simulink export, and 12.23% cost savings. The current project covers most of that system surface, with the main technical mismatch being discrete PPO action control versus the report's continuous-action wording.
