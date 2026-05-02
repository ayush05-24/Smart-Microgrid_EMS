# Smart Microgrid EMS Control System

Production-style Intelligent Smart Microgrid Energy Management System with NASA POWER cleaning, realistic synthetic operational signals, CUDA LSTM forecasting, PPO optimization, FastAPI control endpoints, MATLAB/Simulink exports, and a React operator dashboard.

## Structure

```text
backend/
  app/
    data/          NASA cleaning, normalization, synthetic load/tariff/BESS generation
    ml/            CUDA LSTM forecasters
    rl/            PPO microgrid dispatch environment and training
    services/      dispatch, alerts, metrics, scenarios, MATLAB export
    main.py        FastAPI API
  scripts/         run, train, export, Windows start scripts
  tests/
frontend/
  src/             React operator dashboard
data/
  raw/             NASA POWER CSV
  processed/       cleaned and EMS datasets
  outputs/         forecast, reward traces, plots
  reports/         dispatch and metrics reports
  exports/         CSV/MAT Simulink exports
models/
  forecast/        trained LSTM .pt files
  ppo/             trained PPO policy
  scalers/         fitted feature scalers
notebooks/
venv/
```

## Setup

```powershell
cd "C:\Users\ayush\Desktop\Final Year Project"
python -m venv venv
venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd frontend
npm.cmd install --cache ..\.npm-cache
```

The backend requirements pin CUDA PyTorch:

```text
torch==2.6.0+cu124
torchvision==0.21.0+cu124
torchaudio==2.6.0+cu124
```

Verify GPU from the venv:

```powershell
venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

Expected on this machine:

```text
2.6.0+cu124
True
NVIDIA GeForce RTX 3060 Laptop GPU
```

## Run Pipeline

```powershell
venv\Scripts\python.exe backend\scripts\run_pipeline.py
```

Key outputs:

```text
data\processed\cleaned_nasa_power.csv
data\processed\ems_dataset.csv
data\processed\cleaning_report.json
data\synthetic\synthetic_validation_report.json
data\outputs\plots\solar_trends.png
data\outputs\plots\temperature_trends.png
data\outputs\plots\wind_trends.png
data\outputs\plots\load_curve.png
data\outputs\plots\tariff_curve.png
data\outputs\plots\battery_soc_validation.png
data\reports\baseline_metrics_report.json
```

Latest validation from this run:

```text
Rows cleaned: 52608
Cost savings: 12.23%
Battery safe: true
Renewable utilization: 93.37%
Grid dependency: 68.58%
```

## Train Forecasting Models

```powershell
venv\Scripts\python.exe backend\scripts\train_forecasts.py --epochs 8 --batch-size 256 --sequence-length 48
```

Outputs:

```text
models\forecast\solar_kw_lstm.pt
models\forecast\load_kw_lstm.pt
models\scalers\solar_kw_x_scaler.joblib
models\scalers\load_kw_x_scaler.joblib
data\outputs\solar_kw_forecast.csv
data\outputs\load_kw_forecast.csv
data\outputs\plots\solar_kw_prediction_vs_actual.png
data\outputs\plots\load_kw_prediction_vs_actual.png
data\outputs\plots\solar_kw_loss_curve.png
data\outputs\plots\load_kw_loss_curve.png
```

Latest CUDA training results:

```text
Solar RMSE: 3.6688 kW
Load RMSE: 4.8532 kW
Device: cuda
```

## Train PPO

```powershell
venv\Scripts\python.exe backend\scripts\train_ppo.py --timesteps 20000
```

Outputs:

```text
models\ppo\microgrid_ppo.zip
data\outputs\ppo_reward_trace.csv
data\outputs\ppo_action_samples.csv
data\outputs\plots\ppo_reward_curve.png
data\outputs\plots\ppo_action_patterns.png
```

## API

```powershell
venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Endpoints:

```text
GET  /forecast
GET  /optimize
GET  /decisions
GET  /metrics
GET  /alerts
POST /simulate
GET  /matlab/export
GET  /live/status
POST /live/start
POST /live/stop
POST /live/override
```

Example:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/metrics?horizon_hours=168
```

## Frontend

Development:

```powershell
cd frontend
npm.cmd run dev
```

Production build:

```powershell
cd frontend
npm.cmd run build
```

Preview built dashboard:

```powershell
cd "C:\Users\ayush\Desktop\Final Year Project"
venv\Scripts\python.exe -m http.server 4173 -d frontend\dist --bind 127.0.0.1
```

Open:

```text
http://127.0.0.1:5173
http://127.0.0.1:4173
```

One-command Windows launcher:

```powershell
.\start_system.bat
```

The dashboard includes a **Start live stream** control. It starts the backend synthetic telemetry generator and switches the dashboard to a 1.5-second live refresh cadence. Runtime telemetry is stored in:

```text
data\runtime\live_telemetry.jsonl
```

Detailed live-data behavior:

```text
docs\frontend-live-data.md
```

## Deep Dive Documentation

Presentation-ready explanation files are available in:

```text
docs\deep-dive\
```

Start here:

```text
docs\deep-dive\00-documentation-map.md
```

These files explain project purpose, report alignment, formulas, runbook, dashboard charts, live simulation behavior, outputs, forecasting, future upgrades, and full EDA interpretation.

## Audit And EDA

Generate the report audit and EDA package:

```powershell
venv\Scripts\python.exe backend\scripts\audit_report_and_generate_eda.py
```

Outputs:

```text
docs\project-report-audit.md
docs\data-eda-report.md
data\outputs\eda\
```

## MATLAB/Simulink

Export:

```powershell
venv\Scripts\python.exe backend\scripts\export_simulink.py
```

Outputs:

```text
data\exports\microgrid_predictions_dispatch.csv
data\exports\microgrid_predictions_dispatch.mat
data\exports\run_simulink_microgrid_validation.m
data\exports\ml_vs_simulink_reference.csv
```

Simulink wiring:

```text
PV subsystem input: solar_ts
Load subsystem input: load_ts
BESS subsystem input: battery_power_ts and soc_ts
Grid subsystem output/log: Grid_kW
```

## Tests

```powershell
venv\Scripts\python.exe -m pytest backend\tests -q -p no:cacheprovider
```

Latest result:

```text
3 passed
```
