from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import savemat

from ..config import EXPORT_DIR
from .dispatch import build_dispatch_table


def export_for_matlab(df: pd.DataFrame, horizon_hours: int = 24 * 7) -> dict[str, str]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    work = df.head(horizon_hours).copy().reset_index(drop=True)
    dispatch = build_dispatch_table(work, horizon_hours=len(work))
    export_df = pd.DataFrame(
        {
            "timestamp": work["timestamp"],
            "solar_kw": work["solar_kw"],
            "load_kw": work["load_kw"],
            "tariff_inr_kwh": work["tariff_inr_kwh"],
            "battery_soc_pct": dispatch["battery_soc_pct"],
            "battery_power_kw": dispatch["battery_power_kw"],
            "grid_kw": dispatch["grid_kw"],
        }
    )
    csv_path = EXPORT_DIR / "microgrid_predictions_dispatch.csv"
    mat_path = EXPORT_DIR / "microgrid_predictions_dispatch.mat"
    script_path = EXPORT_DIR / "run_simulink_microgrid_validation.m"
    comparison_path = EXPORT_DIR / "ml_vs_simulink_reference.csv"

    export_df.to_csv(csv_path, index=False)
    matlab_time_hours = np.arange(len(export_df), dtype=float)
    savemat(
        mat_path,
        {
            "time_hours": matlab_time_hours,
            "solar_kw": export_df["solar_kw"].to_numpy(dtype=float),
            "load_kw": export_df["load_kw"].to_numpy(dtype=float),
            "tariff_inr_kwh": export_df["tariff_inr_kwh"].to_numpy(dtype=float),
            "battery_soc_pct": export_df["battery_soc_pct"].to_numpy(dtype=float),
            "battery_power_kw": export_df["battery_power_kw"].to_numpy(dtype=float),
            "grid_kw": export_df["grid_kw"].to_numpy(dtype=float),
        },
    )
    _write_matlab_script(script_path)
    _write_reference_comparison(export_df, comparison_path)
    return {
        "csv": str(csv_path),
        "mat": str(mat_path),
        "matlab_script": str(script_path),
        "comparison_csv": str(comparison_path),
    }


def _write_reference_comparison(export_df: pd.DataFrame, path: Path) -> None:
    reference = export_df.copy()
    reference["simulink_reference_grid_kw"] = (
        reference["load_kw"] - reference["solar_kw"] - reference["battery_power_kw"].clip(lower=0)
        + (-reference["battery_power_kw"].clip(upper=0))
    ).clip(lower=0)
    reference["grid_kw_error"] = reference["grid_kw"] - reference["simulink_reference_grid_kw"]
    reference.to_csv(path, index=False)


def _write_matlab_script(path: Path) -> None:
    path.write_text(
        """% Smart Microgrid EMS MATLAB/Simulink validation runner
% Run from the data/exports folder after backend export.
clear; clc;
data = load('microgrid_predictions_dispatch.mat');

time = data.time_hours(:);
solar_ts = timeseries(data.solar_kw(:), time, 'Name', 'PV_kW');
load_ts = timeseries(data.load_kw(:), time, 'Name', 'Load_kW');
soc_ts = timeseries(data.battery_soc_pct(:), time, 'Name', 'Battery_SoC_pct');
battery_power_ts = timeseries(data.battery_power_kw(:), time, 'Name', 'BESS_Power_kW');
grid_ts = timeseries(data.grid_kw(:), time, 'Name', 'EMS_Grid_kW');

assignin('base', 'solar_ts', solar_ts);
assignin('base', 'load_ts', load_ts);
assignin('base', 'soc_ts', soc_ts);
assignin('base', 'battery_power_ts', battery_power_ts);
assignin('base', 'grid_ts', grid_ts);

% Simulink model wiring expectation:
% 1. PV subsystem consumes solar_ts.
% 2. Load subsystem consumes load_ts.
% 3. BESS subsystem consumes battery_power_ts and initial SoC.
% 4. Grid subsystem computes import/export and logs Grid_kW.
%
% If a model named smart_microgrid_model.slx is present, this script runs it
% and compares logged Grid_kW with EMS_Grid_kW.
model = 'smart_microgrid_model';
if isfile([model '.slx'])
    simOut = sim(model, 'StopTime', num2str(time(end)));
    if isprop(simOut, 'logsout')
        gridSignal = simOut.logsout.get('Grid_kW');
        sim_grid = gridSignal.Values.Data(:);
        ems_grid = data.grid_kw(:);
        n = min(numel(sim_grid), numel(ems_grid));
        rmse = sqrt(mean((sim_grid(1:n) - ems_grid(1:n)).^2));
        fprintf('ML EMS vs Simulink Grid RMSE: %.4f kW\\n', rmse);
    end
else
    fprintf('smart_microgrid_model.slx not found. Timeseries were exported to base workspace.\\n');
end
""",
        encoding="utf-8",
    )

