% Smart Microgrid EMS MATLAB/Simulink validation runner
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
        fprintf('ML EMS vs Simulink Grid RMSE: %.4f kW\n', rmse);
    end
else
    fprintf('smart_microgrid_model.slx not found. Timeseries were exported to base workspace.\n');
end
