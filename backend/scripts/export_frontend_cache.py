from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.ml.inference import forecast_payload
from backend.app.services.alerts import detect_alerts
from backend.app.services.dispatch import build_dispatch_table, latest_operator_recommendation
from backend.app.services.metrics import compute_performance_metrics
from backend.app.services.repository import recent_window
from backend.app.utils import rounded_records


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    cache_dir = PROJECT_ROOT / "frontend" / "public" / "api-cache"
    forecast = forecast_payload(24)
    window_24h = recent_window(24)
    window_48h = recent_window(48)
    window_168h = recent_window(168)

    dispatch = build_dispatch_table(window_24h, horizon_hours=24)
    alerts_dispatch = build_dispatch_table(window_48h, horizon_hours=48)

    write_json(cache_dir / "forecast.json", forecast)
    write_json(
        cache_dir / "optimize.json",
        {
            "recommendation": latest_operator_recommendation(window_24h),
            "dispatch": rounded_records(dispatch, 3),
            "source": "cached_snapshot",
        },
    )
    write_json(cache_dir / "metrics.json", compute_performance_metrics(window_168h, 168, "frontend_cache"))
    write_json(
        cache_dir / "alerts.json",
        {"alerts": detect_alerts(window_48h, alerts_dispatch), "source": "cached_snapshot"},
    )
    print(f"Frontend API cache written to {cache_dir}")

