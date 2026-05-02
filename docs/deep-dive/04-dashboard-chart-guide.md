# Dashboard Chart Guide For Real-Time Operation

This file explains each dashboard chart/panel, what it means in real time, and how a real grid operator would use it.

Dashboard file:

- `frontend/src/App.jsx`

API client:

- `frontend/src/api/client.js`

## Refresh Behavior

| Mode | Refresh frequency | Data source |
|---|---:|---|
| Normal API mode | 30 seconds | Backend historical/processed EMS data. |
| Live simulation mode | 1.5 seconds | Backend live telemetry simulator. |
| Offline cache mode | Static snapshot | `frontend/public/api-cache/*.json`. |

When the operator clicks **Start live stream**, the frontend calls:

```text
POST /live/start
```

Then it polls the backend every 1.5 seconds.

## Top Command Bar

The top bar shows:

- Connection state: online, refreshing, degraded, or offline cached snapshot.
- Current refresh cadence: 1.5s live tick or 30s polling.
- Last updated time.
- Active API base URL.
- Start/stop live stream button.
- Manual refresh button.

Operator use:

- Confirms whether data is live or cached.
- Prevents accidental interpretation of stale data as live data.
- Gives immediate visibility into backend connectivity.

## KPI Strip

The dashboard shows six key values at the top.

### 1. Solar

Meaning:

- Current PV generation in kW.

How operator uses it:

- Checks whether renewable supply is available.
- Low solar during daytime can indicate cloud cover or renewable drop.
- Zero solar at night is expected.

### 2. Load

Meaning:

- Current facility demand in kW.

How operator uses it:

- Detects morning/evening peaks.
- Watches for demand spikes.
- Compares load against solar and battery output.

### 3. BESS SoC

Meaning:

- Battery state of charge in percent.

How operator uses it:

- Confirms battery is inside 20 to 90 percent safe operating band.
- Low SoC near evening peak means limited peak support.
- High SoC before evening peak is useful because stored energy can offset expensive grid import.

### 4. Grid

Meaning:

- Current grid import power in kW.

How operator uses it:

- High grid import during peak tariff means cost risk.
- If grid import drops during battery discharge, dispatch is working.
- In island mode, grid import should go to zero and load shedding may appear if supply is insufficient.

### 5. Tariff

Meaning:

- Current grid import cost in INR/kWh.

How operator uses it:

- Off-peak: charging may be acceptable.
- Mid tariff: usually hold unless solar surplus exists.
- Peak tariff: discharge battery if SoC allows.

### 6. Savings

Meaning:

- Estimated percentage savings against baseline grid import cost.

How operator uses it:

- Measures whether EMS dispatch is economically useful.
- Can be used as a management KPI in reports.

## Power Flow Chart

Signals shown:

- Load kW.
- Solar kW.
- Grid kW.
- Battery SoC percent.

What it tells:

- Whether load is being served by solar, grid, or battery.
- Whether battery SoC is rising or falling.
- Whether grid import increases during solar drop or load rise.

Operator interpretation:

| Pattern | Meaning |
|---|---|
| Solar above load and SoC rising | Battery is storing renewable surplus. |
| Load above solar and grid high | Facility depends on grid. |
| Peak tariff and grid falling | Battery discharge is reducing cost. |
| SoC stuck near 20 percent | Battery reserve is low. |
| SoC near 90 percent with solar surplus | Battery is close to full, curtailment may occur. |

## Dispatch Panel

Shows:

- Current recommended action.
- Explanation/reason.
- Override buttons.

Actions:

| Action | Meaning |
|---|---|
| Charge | Put energy into BESS. |
| Discharge | Use BESS to serve load or reduce grid import. |
| Idle | Keep battery unchanged. |

Override modes:

| Mode | What it does |
|---|---|
| Auto dispatch | Backend dispatch logic decides. |
| Force charge | Pushes the battery toward charging within safe limits. |
| Force discharge | Pushes the battery toward discharging within safe limits. |
| Island mode | Sets grid import to zero and uses solar/battery only; may create load shedding if supply is not enough. |

Operator use:

- Understands not only what the EMS recommends, but why.
- Tests emergency behavior.
- Demonstrates operator authority over AI recommendations.

## Forecast Chart

Signals shown:

- Forecast solar kW.
- Forecast load kW.

What it tells:

- Expected renewable availability.
- Expected demand.
- Whether future deficit or surplus is likely.

Operator use:

- Prepare for evening peak.
- Pre-charge battery before high tariff.
- Identify low solar periods.
- Avoid using battery too early if future high tariff/load is expected.

## Alerts Panel

Alert types:

| Alert | Meaning |
|---|---|
| `peak_demand_risk` | Load is near or above high-load threshold. |
| `renewable_drop` | Solar is expected to fall sharply. |
| `battery_low_soc` | Battery is near minimum safe SoC. |
| `battery_high_soc` | Battery is near maximum safe SoC. |
| `peak_tariff_import` | Grid import is happening during expensive tariff. |

Operator use:

- Prioritizes attention.
- Supports fast response.
- Gives concrete messages rather than raw data only.

## Cost Chart

Shows:

- Baseline cost.
- Optimized cost.

Baseline means:

```text
grid supplies load after solar, with no intelligent battery dispatch
```

Optimized means:

```text
dispatch engine uses battery according to tariff, solar surplus, and SoC constraints
```

Operator use:

- Demonstrates economic benefit.
- Supports energy management reporting.
- Useful for monthly/weekly savings communication.

## Sustainability Chart

Shows:

- Renewable share.
- Grid dependency.
- Self-sufficiency.

Operator use:

- Tracks carbon and sustainability goals.
- Shows whether the microgrid is using local renewable energy effectively.
- Helps justify battery and PV investments beyond cost savings.

## Scenario Panel

Available scenarios:

| Scenario | What changes |
|---|---|
| Normal | Uses current dataset/window. |
| Peak load | Increases load by 24 percent within feeder limits. |
| Low solar | Reduces daylight PV output to 38 percent. |
| Tariff spike | Raises peak tariff to 11.5 INR/kWh. |

Operator use:

- Tests system robustness before an event.
- Shows how cost, grid dependency, alerts, and dispatch decisions change.
- Good for viva/demo because it proves the dashboard is interactive.

## Dispatch Schedule Table

Columns:

| Column | Meaning |
|---|---|
| Time | Timestamp of decision row. |
| Solar | PV output in kW. |
| Load | Facility demand in kW. |
| SoC | Battery charge level. |
| Grid | Required grid import. |
| Action | Charge, discharge, or idle. |
| Reason | Human-readable dispatch explanation. |

Operator use:

- Provides auditability.
- Shows not only the current action but near-term planned behavior.
- Helps explain decisions to supervisors or reviewers.

## How To Tell If Dashboard Is Live

The dashboard is live if:

- Top bar says `online`.
- It shows `1.5s live tick`.
- Live records count increases.
- The latest update time changes every few seconds.
- `GET /live/status` returns `running: true`.

If it says `offline: cached snapshot`, then the backend is not reachable and the data is static.

