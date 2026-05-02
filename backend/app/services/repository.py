from __future__ import annotations

import pandas as pd

from ..config import EMS_DATASET
from .live_simulator import live_simulator


def load_ems_dataset() -> pd.DataFrame:
    if not EMS_DATASET.exists():
        from ..data.synthetic import generate_operational_dataset

        generate_operational_dataset()
    return pd.read_csv(EMS_DATASET, parse_dates=["timestamp", "timestamp_utc"]).sort_values("timestamp").reset_index(drop=True)


def recent_window(hours: int = 24 * 7) -> pd.DataFrame:
    if live_simulator.has_live_data():
        live_df = live_simulator.window(hours)
        if not live_df.empty:
            return live_df
    df = load_ems_dataset()
    return df.tail(max(int(hours), 1)).reset_index(drop=True)
