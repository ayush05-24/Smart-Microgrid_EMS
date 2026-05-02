from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .gpu import gpu_summary
from .ml.inference import forecast_payload
from .services.alerts import detect_alerts
from .services.dispatch import build_dispatch_table, latest_operator_recommendation
from .services.exports import export_for_matlab
from .services.live_simulator import live_simulator
from .services.metrics import compute_performance_metrics
from .services.repository import recent_window
from .services.scenarios import run_scenario
from .utils import rounded_records


class ScenarioRequest(BaseModel):
    scenario: str = Field(default="normal", examples=["peak_load", "low_solar", "tariff_spike"])
    horizon_hours: int = Field(default=48, ge=1, le=168)


class LiveStartRequest(BaseModel):
    interval_seconds: float = Field(default=1.5, ge=0.5, le=30.0)
    reset: bool = False


class OverrideRequest(BaseModel):
    mode: str = Field(default="auto", examples=["auto", "force_charge", "force_discharge", "island"])


app = FastAPI(title="Smart Microgrid EMS API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, object]:
    return {
        "service": "Smart Microgrid EMS",
        "status": "online",
        "gpu": gpu_summary(),
        "endpoints": ["/forecast", "/optimize", "/decisions", "/metrics", "/alerts", "/simulate"],
    }


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "online", "service": "Smart Microgrid EMS API", "gpu": gpu_summary()}


@app.get("/live/status")
def live_status() -> dict[str, object]:
    return live_simulator.status()


@app.post("/live/start")
def live_start(request: LiveStartRequest) -> dict[str, object]:
    return live_simulator.start(interval_seconds=request.interval_seconds, reset=request.reset)


@app.post("/live/stop")
def live_stop() -> dict[str, object]:
    return live_simulator.stop()


@app.post("/live/override")
def live_override(request: OverrideRequest) -> dict[str, object]:
    return live_simulator.set_override(request.mode)


@app.get("/live/snapshot")
def live_snapshot(records: int = Query(120, ge=1, le=720)) -> dict[str, object]:
    return live_simulator.snapshot(records)


@app.get("/forecast")
def forecast(horizon_hours: int = Query(24, ge=1, le=168)) -> dict[str, object]:
    return forecast_payload(horizon_hours)


@app.get("/optimize")
def optimize(horizon_hours: int = Query(24, ge=1, le=168)) -> dict[str, object]:
    df = recent_window(horizon_hours)
    decision_df = build_dispatch_table(df, horizon_hours=horizon_hours)
    return {
        "recommendation": latest_operator_recommendation(df),
        "dispatch": rounded_records(decision_df, 3),
    }


@app.get("/decisions")
def decisions(horizon_hours: int = Query(24, ge=1, le=168)) -> dict[str, object]:
    df = recent_window(horizon_hours)
    decision_df = build_dispatch_table(df, horizon_hours=horizon_hours)
    return {
        "decision_table": rounded_records(decision_df, 3),
        "columns": ["time", "solar_kw", "load_kw", "battery_soc_pct", "grid_kw", "action", "reason"],
    }


@app.get("/metrics")
def metrics(horizon_hours: int = Query(168, ge=1, le=720)) -> dict[str, object]:
    df = recent_window(horizon_hours)
    return compute_performance_metrics(df, horizon_hours=horizon_hours, prefix="api")


@app.get("/alerts")
def alerts(horizon_hours: int = Query(48, ge=1, le=168)) -> dict[str, object]:
    df = recent_window(horizon_hours)
    dispatch_df = build_dispatch_table(df, horizon_hours=horizon_hours)
    return {"alerts": detect_alerts(df, dispatch_df)}


@app.post("/simulate")
def simulate(request: ScenarioRequest) -> dict[str, object]:
    df = recent_window(request.horizon_hours)
    return run_scenario(df, request.scenario, horizon_hours=request.horizon_hours)


@app.get("/matlab/export")
def matlab_export(horizon_hours: int = Query(168, ge=1, le=720)) -> dict[str, object]:
    df = recent_window(horizon_hours)
    return export_for_matlab(df, horizon_hours=horizon_hours)
