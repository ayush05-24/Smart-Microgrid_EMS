from __future__ import annotations

from backend.app.config import BATTERY, MICROGRID
from backend.app.data.cleaning import clean_nasa_power_dataset
from backend.app.data.synthetic import generate_operational_dataset
from backend.app.services.metrics import compute_performance_metrics
from backend.app.services.live_simulator import live_simulator


def test_cleaning_and_synthetic_constraints() -> None:
    cleaned = clean_nasa_power_dataset()
    ems = generate_operational_dataset(cleaned)

    assert not cleaned.empty
    assert cleaned["timestamp"].is_monotonic_increasing
    assert cleaned[["ghi", "dni", "diffuse_irradiance", "temperature_c", "wind_speed_mps"]].isna().sum().sum() == 0
    assert ems["load_kw"].between(MICROGRID.load_min_kw, MICROGRID.load_max_kw).all()
    assert ems["wind_kw"].between(0, MICROGRID.wind_capacity_kw).all()
    assert ems["battery_soc_pct"].between(BATTERY.min_soc_pct, BATTERY.max_soc_pct).all()
    assert set(ems["tariff_inr_kwh"].unique()).issubset({2.6, 5.6, 9.2})


def test_metrics_are_operator_safe() -> None:
    cleaned = clean_nasa_power_dataset()
    ems = generate_operational_dataset(cleaned).tail(24 * 7).reset_index(drop=True)
    metrics = compute_performance_metrics(ems, horizon_hours=24 * 7, prefix="test")

    assert metrics["optimized_cost_inr"] >= 0
    assert 0 <= metrics["renewable_utilization_pct"] <= 100
    assert 0 <= metrics["grid_dependency_pct"] <= 100
    assert metrics["battery"]["safe_soc"] is True


def test_live_simulator_generates_safe_operator_data() -> None:
    status = live_simulator.start(interval_seconds=0.5, reset=True)
    assert status["running"] is True
    import time

    time.sleep(0.8)
    snapshot = live_simulator.snapshot(3)
    live_simulator.stop()

    assert snapshot["records"] >= 1
    latest = snapshot["latest"]
    assert MICROGRID.load_min_kw <= latest["load_kw"] <= MICROGRID.load_max_kw
    assert 0 <= latest["solar_kw"] <= MICROGRID.pv_capacity_kw
    assert 0 <= latest["wind_kw"] <= MICROGRID.wind_capacity_kw
    assert BATTERY.min_soc_pct <= latest["battery_soc_pct"] <= BATTERY.max_soc_pct
    assert latest["tariff_inr_kwh"] in {2.6, 5.6, 9.2}
