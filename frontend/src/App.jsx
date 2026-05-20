import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BatteryCharging,
  Bolt,
  CloudSun,
  Gauge,
  IndianRupee,
  Leaf,
  PauseCircle,
  PlayCircle,
  PlugZap,
  Radio,
  RefreshCcw,
  ShieldCheck,
  Wind,
  Zap
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import {
  getAlerts,
  getApiBase,
  getApiMode,
  getForecast,
  getLiveStatus,
  getLiveSnapshot,
  getMetrics,
  getOptimization,
  runScenario,
  setLiveOverride,
  startLiveSimulation,
  stopLiveSimulation
} from "./api/client.js";

const number = (value, digits = 1) => Number(value || 0).toFixed(digits);
const statusText = {
  auto: "Auto dispatch",
  force_charge: "Force charge",
  force_discharge: "Force discharge",
  island: "Island mode"
};

function App() {
  const [forecast, setForecast] = useState([]);
  const [recommendation, setRecommendation] = useState(null);
  const [dispatch, setDispatch] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [scenario, setScenario] = useState("normal");
  const [scenarioResult, setScenarioResult] = useState(null);
  const [status, setStatus] = useState("connecting");
  const [apiBase, setApiBase] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [liveStatus, setLiveStatus] = useState({ running: false, override_mode: "auto", records: 0 });

  const pollMs = liveStatus.running ? 1500 : 30000;

  async function refresh() {
    setStatus("refreshing");
    const isLive = liveStatus.running;
    const results = await Promise.allSettled([
      getForecast(24),
      getOptimization(24),
      getMetrics(isLive ? 120 : 168),
      getAlerts(48),
      isLive ? getLiveSnapshot(120) : getLiveStatus()
    ]);
    const [forecastResult, optimizationResult, metricsResult, alertsResult, liveResult] = results;
    const failed = results.filter((result) => result.status === "rejected");

    if (forecastResult.status === "fulfilled") setForecast(forecastResult.value.records || []);
    if (optimizationResult.status === "fulfilled") {
      setRecommendation(optimizationResult.value.recommendation || null);
      setDispatch(optimizationResult.value.dispatch || []);
    }
    if (metricsResult.status === "fulfilled") setMetrics(metricsResult.value);
    if (alertsResult.status === "fulfilled") setAlerts(alertsResult.value.alerts || []);
    if (liveResult.status === "fulfilled") setLiveStatus(liveResult.value);

    setApiBase(getApiBase());
    setLastUpdated(new Date());

    if (getApiMode() === "cache") setStatus("offline: cached snapshot");
    else if (failed.length === 0) setStatus("online");
    else if (failed.length < results.length) setStatus(`degraded: ${failed.length} request failed`);
    else setStatus(`offline: ${failed[0].reason?.message || "API unreachable"}`);
  }

  async function startLive() {
    try {
      setLiveStatus(await startLiveSimulation(1.5, true));
      await refresh();
    } catch (error) {
      setStatus(`live start failed: ${error.message}`);
    }
  }

  async function stopLive() {
    try {
      setLiveStatus(await stopLiveSimulation());
      await refresh();
    } catch (error) {
      setStatus(`live stop failed: ${error.message}`);
    }
  }

  async function changeOverride(mode) {
    try {
      setLiveStatus(await setLiveOverride(mode));
      await refresh();
    } catch (error) {
      setStatus(`override failed: ${error.message}`);
    }
  }

  async function simulate() {
    try {
      const result = await runScenario(scenario, 48);
      setScenarioResult(result);
    } catch (error) {
      setStatus(`scenario failed: ${error.message}`);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(refresh, pollMs);
    return () => window.clearInterval(timer);
  }, [pollMs]);

  const current = liveStatus.running ? (liveStatus.latest || {}) : (dispatch[0] || {});
  const powerSeries = useMemo(() => {
    if (liveStatus.running && liveStatus.records_window && liveStatus.records_window.length > 0) {
      return liveStatus.records_window.slice(-24);
    }
    return dispatch.slice(0, 24);
  }, [liveStatus.running, liveStatus.records_window, dispatch]);
  const savings = Number(metrics?.cost_savings_pct || 0);
  const batterySafe = metrics?.battery?.safe_soc !== false;

  const energyMix = useMemo(() => {
    if (!metrics) return [];
    return [
      { name: "Renewable", value: Number(metrics.renewable_share_pct || 0), color: "#2f9e44" },
      { name: "Grid", value: Number(metrics.grid_dependency_pct || 0), color: "#1971c2" }
    ];
  }, [metrics]);

  const costBars = useMemo(() => {
    if (!metrics) return [];
    return [
      { name: "Baseline", cost: Number(metrics.baseline_cost_inr || 0) },
      { name: "Optimized", cost: Number(metrics.optimized_cost_inr || 0) }
    ];
  }, [metrics]);

  return (
    <main className="console">
      <header className="command-bar">
        <div className="identity">
          <span className={`beacon ${liveStatus.running ? "running" : ""}`} />
          <div>
            <p className="eyebrow">Microgrid EMS Control Room</p>
            <h1>Operator Dashboard</h1>
          </div>
        </div>
        <div className="command-meta">
          <span>{status}</span>
          <span>{liveStatus.running ? "1.5s live tick" : "30s polling"}</span>
          <span>{lastUpdated ? lastUpdated.toLocaleTimeString() : "waiting"}</span>
          <span>{apiBase || "API pending"}</span>
        </div>
        <div className="command-actions">
          <button className="icon-button" onClick={refresh} title="Refresh">
            <RefreshCcw size={18} />
          </button>
          {liveStatus.running ? (
            <button className="command secondary" onClick={stopLive}>
              <PauseCircle size={18} /> Stop stream
            </button>
          ) : (
            <button className="command" onClick={startLive}>
              <PlayCircle size={18} /> Start live stream
            </button>
          )}
        </div>
      </header>

      <section className="status-strip">
        <Kpi icon={<CloudSun />} label="Solar" value={`${number(current.solar_kw)} kW`} hint="PV generation" tone="solar" />
        <Kpi icon={<Wind />} label="Wind" value={`${number(current.wind_kw)} kW`} hint="Turbine generation" tone="wind" />
        <Kpi icon={<Bolt />} label="Load" value={`${number(current.load_kw)} kW`} hint="Facility demand" tone="load" />
        <Kpi icon={<BatteryCharging />} label="BESS SoC" value={`${number(current.battery_soc_pct)}%`} hint={batterySafe ? "Inside safe band" : "Limit risk"} tone="battery" />
        <Kpi icon={<PlugZap />} label="Grid" value={`${number(current.grid_kw)} kW`} hint="Import power" tone="grid" />
        <Kpi icon={<IndianRupee />} label="Tariff" value={`${number(current.tariff_inr_kwh, 2)}`} hint="INR/kWh" tone="tariff" />
        <Kpi icon={<Leaf />} label="Savings" value={`${number(savings, 2)}%`} hint="vs baseline" tone="savings" />
      </section>

      <section className="control-grid">
        <article className="panel span-2">
          <PanelTitle title="Power Flow" subtitle="Solar, load, grid and SoC" />
          <div className="chart large">
            <ResponsiveContainer>
              <AreaChart data={powerSeries}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tickFormatter={shortTime} minTickGap={24} />
                <YAxis yAxisId="left" />
                <YAxis yAxisId="right" orientation="right" domain={[0, 100]} />
                <Tooltip labelFormatter={formatTime} />
                <Area yAxisId="left" type="monotone" dataKey="load_kw" name="Load kW" stroke="#1971c2" fill="#d0ebff" strokeWidth={2} />
                <Area yAxisId="left" type="monotone" dataKey="solar_kw" name="Solar kW" stroke="#f59f00" fill="#fff3bf" strokeWidth={2} />
                <Area yAxisId="left" type="monotone" dataKey="wind_kw" name="Wind kW" stroke="#0f766e" fill="#ccfbf1" strokeWidth={2} />
                <Line yAxisId="left" type="monotone" dataKey="grid_kw" name="Grid kW" stroke="#c92a2a" strokeWidth={2} dot={false} />
                <Line yAxisId="right" type="monotone" dataKey="battery_soc_pct" name="SoC %" stroke="#2f9e44" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel decision-panel">
          <PanelTitle title="Dispatch" subtitle={statusText[liveStatus.override_mode] || "Auto dispatch"} />
          <div className="recommendation">
            <Zap size={22} />
            <strong>{recommendation?.recommendation || "Waiting for dispatch"}</strong>
            <p>{recommendation?.reason || "Start the backend API or live stream."}</p>
          </div>
          <div className="override-grid">
            {["auto", "force_charge", "force_discharge", "island"].map((mode) => (
              <button
                key={mode}
                className={liveStatus.override_mode === mode ? "override active" : "override"}
                onClick={() => changeOverride(mode)}
              >
                {statusText[mode]}
              </button>
            ))}
          </div>
        </article>

        <article className="panel">
          <PanelTitle title="Forecast" subtitle="Next operating horizon" />
          <div className="chart">
            <ResponsiveContainer>
              <LineChart data={forecast}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" minTickGap={28} tickFormatter={shortTime} />
                <YAxis />
                <Tooltip labelFormatter={formatTime} />
                <Line type="monotone" dataKey="solar_kw" name="Solar kW" stroke="#f59f00" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="wind_kw" name="Wind kW" stroke="#0f766e" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="load_kw" name="Load kW" stroke="#1971c2" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel">
          <PanelTitle title="Alerts" subtitle={`${alerts.length} active`} />
          <div className="alert-list">
            {alerts.length === 0 ? (
              <div className="empty-state"><ShieldCheck size={20} /> No active warnings</div>
            ) : (
              alerts.slice(0, 6).map((alert, index) => (
                <div className={`alert ${alert.severity}`} key={`${alert.type}-${index}`}>
                  <AlertTriangle size={18} />
                  <div>
                    <strong>{alert.type.replaceAll("_", " ")}</strong>
                    <p>{alert.message}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="panel">
          <PanelTitle title="Cost" subtitle="Baseline vs optimized" />
          <div className="chart">
            <ResponsiveContainer>
              <BarChart data={costBars}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="cost" name="INR" fill="#2f9e44" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="metric-row">
            <span>Saved INR {number(metrics?.cost_savings_inr, 0)}</span>
            <strong>{number(savings, 2)}%</strong>
          </div>
        </article>

        <article className="panel">
          <PanelTitle title="Sustainability" subtitle="Energy mix" />
          <div className="chart compact">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={energyMix} dataKey="value" nameKey="name" innerRadius={52} outerRadius={82}>
                  {energyMix.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="metric-row">
            <span>Self-sufficiency</span>
            <strong>{number(metrics?.self_sufficiency_pct)}%</strong>
          </div>
        </article>

        <article className="panel">
          <PanelTitle title="Scenario" subtitle="Stress test" />
          <div className="scenario-controls">
            <select value={scenario} onChange={(event) => setScenario(event.target.value)}>
              <option value="normal">Normal</option>
              <option value="peak_load">Peak load</option>
              <option value="low_solar">Low solar</option>
              <option value="tariff_spike">Tariff spike</option>
            </select>
            <button onClick={simulate}>Run</button>
          </div>
          {scenarioResult ? (
            <div className="scenario-result">
              <strong>{scenarioResult.description}</strong>
              <p>Cost savings {number(scenarioResult.metrics?.cost_savings_pct, 2)}%</p>
              <p>Grid dependency {number(scenarioResult.metrics?.grid_dependency_pct, 2)}%</p>
            </div>
          ) : (
            <div className="empty-state"><Gauge size={19} /> Select and run a scenario</div>
          )}
        </article>

        <article className="panel span-3">
          <PanelTitle title="Dispatch Schedule" subtitle="Operator-readable action table" />
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Solar</th>
                  <th>Wind</th>
                  <th>Load</th>
                  <th>SoC</th>
                  <th>Grid</th>
                  <th>Action</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {(liveStatus.running && liveStatus.records_window && liveStatus.records_window.length > 0
                  ? [...liveStatus.records_window].reverse().slice(0, 14)
                  : dispatch.slice(0, 14)
                ).map((row, idx) => {
                  const action = row.action || row.operator_action || "idle";
                  const reason = row.reason || `Telemetry signal: BESS is ${action}.`;
                  return (
                    <tr key={row.time || row.timestamp || idx}>
                      <td>{shortTime(row.time || row.timestamp)}</td>
                      <td>{number(row.solar_kw)} kW</td>
                      <td>{number(row.wind_kw)} kW</td>
                      <td>{number(row.load_kw)} kW</td>
                      <td>{number(row.battery_soc_pct)}%</td>
                      <td>{number(row.grid_kw)} kW</td>
                      <td><span className={`pill ${action}`}>{action}</span></td>
                      <td>{reason}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </article>
      </section>

      <footer className="footer-line">
        <Radio size={16} /> Live records {liveStatus.records || 0} | Override {statusText[liveStatus.override_mode] || "Auto dispatch"}
      </footer>
    </main>
  );
}

function Kpi({ icon, label, value, hint, tone }) {
  return (
    <article className={`kpi ${tone}`}>
      <div className="kpi-icon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </article>
  );
}

function PanelTitle({ title, subtitle }) {
  return (
    <div className="panel-title">
      <h2>{title}</h2>
      <p>{subtitle}</p>
    </div>
  );
}

function shortTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 16);
  return date.toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default App;
