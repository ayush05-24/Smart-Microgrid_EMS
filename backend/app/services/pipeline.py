from __future__ import annotations

from ..config import ensure_project_dirs
from ..data.cleaning import clean_nasa_power_dataset
from ..data.synthetic import generate_operational_dataset
from .dispatch import build_dispatch_table, latest_operator_recommendation
from .exports import export_for_matlab
from .metrics import compute_performance_metrics


def run_data_and_control_pipeline() -> dict[str, object]:
    ensure_project_dirs()
    cleaned = clean_nasa_power_dataset()
    ems = generate_operational_dataset(cleaned)
    recent = ems.tail(24 * 7).reset_index(drop=True)
    dispatch = build_dispatch_table(recent, horizon_hours=24)
    metrics = compute_performance_metrics(recent, horizon_hours=len(recent), prefix="baseline")
    exports = export_for_matlab(recent, horizon_hours=len(recent))
    return {
        "cleaned_rows": len(cleaned),
        "ems_rows": len(ems),
        "recommendation": latest_operator_recommendation(recent),
        "decision_sample": dispatch.head(5).to_dict(orient="records"),
        "metrics": metrics,
        "exports": exports,
    }

