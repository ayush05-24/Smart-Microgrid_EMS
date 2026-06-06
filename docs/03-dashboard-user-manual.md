# Dashboard User Manual & SCADA Operator Guide

This document is the official user manual and operator guide for the Smart Microgrid EMS SCADA interface. It details the frontend architecture, live streaming protocols, manual overrides, explainable AI components, and risk threshold alarms.

---

## 1. Frontend Architecture & Technology Stack

The operator dashboard is a high-speed, modern Single Page Application (SPA) designed for real-time industrial monitoring:

- **Framework**: React.js 19 (built with Vite for fast compiling and sub-300ms hot reloading).
- **Styling**: Vanilla CSS utilizing a premium **glassmorphism** aesthetic (semi-transparent panel backdrops, soft drop shadows, and high-contrast typography).
- **Visualization**: Recharts charting library for responsive time-series vector graphing.
- **Icons**: Lucide React for consistent vector symbols.
- **Client Wrapper**: [client.js](file:///c:/Users/ayush/Desktop/Project/Projects/Final%20Year%20Project/frontend/src/api/client.js) providing automated polling loops, network error handling, and offline mock-data fallbacks.

---

## 2. Live Telemetry & Streaming Protocol

When the operator starts the live streaming simulation, the dashboard transitions from a historical analysis tool to a real-time SCADA interface:

- **Endpoint**: `POST /live/start` and `POST /live/stop` coordinate the background simulation thread.
- **Refresh Cycle**: The frontend performs a polling request to `GET /live/snapshot?records=120` every **$1.5\text{ seconds}$** ($1500\text{ ms}$).
- **Time-Lapse Speed**: Each telemetry tick advances the simulation timeline by **$1\text{ hour}$**. A full diurnal cycle (24 hours) is simulated in **$36\text{ seconds}$**.
- **Data Integration**:
  - The latest telemetry values update the **KPI Cards** (Solar, Wind, Load, BESS SoC, Grid Import, and Tariffs).
  - The `records_window` array populates the **Power Flow & Forecast Chart** (live load, solar, wind, and battery power) and **SoC Trajectory Chart**.
  - The dispatch log list displays the **Dispatch Decision History Table** in reverse-chronological order.

---

## 3. SCADA Panels & UI Layout

The dashboard is structured into high-performance visual blocks:

### 3.1. Primary KPI Header
Displays real-time telemetry metrics:
- **PV Generation**: Active Solar PV output in kW.
- **Wind Generation**: Active Wind turbine output in kW.
- **Facility Load**: Current building power consumption in kW.
- **BESS SoC**: State of Charge percentage.
- **Net Grid Flow**: Current power drawn from (or sent to) the utility grid.
- **TOU Price**: Active pricing tier in INR/kWh.

### 3.2. Power Flow & Quantile Forecast Chart (Recharts)
Plots real-time generation and loads alongside **Quantile LSTM forecast bands**. The 10% and 90% confidence percentiles are rendered as a shaded envelope around the median (50% percentile) forecast line using transparent `<Area>` curves, enabling operators to visually inspect renewable uncertainty in real time.

### 3.3. BESS Dynamic Aging Logs Panel
Provides deep diagnostics into battery degradation and cell temperature:
- **State of Health (SoH)**: Capacity retention percentage (retires at 80.0%).
- **Cell Temperature**: Real-time internal cell temperature in °C, indicating if thermal derating is active.
- **Resistance Growth**: Displays internal resistance growth ratio ($R_{\text{i}}/R_0$), indicating efficiency fade.
- **Incremental Aging Cost**: The physical cost in INR of the current capacity fade step.
- **Safety Layer Violations**: Confirms that the differentiable projection layer has maintained **0 violations** (100% projected safety).

### 3.4. DRL Explainability & Integrated Gradients Panel
Exposes the inner decision-making parameters of the PIS-PPO agent:
- **Decision Entropy**: Gauges the policy's decisiveness (lower means more confident).
- **Explanation Fidelity**: Tracks the alignment percentage between the DRL agent and logical engineering rules.
- **IG Feature Attributions**: Rendered as a dynamic horizontal bar chart, showing which features (Solar, Wind, Load, SoC, Tariff, etc.) contributed positively or negatively to the active dispatch action.

### 3.5. OPEX & Optimality Gap Panel
Renders a real-time bar chart comparing operational expenditures (OPEX) between the Rule-based baseline, PIS-PPO agent, and the exact Dynamic Programming (DP) perfect foresight global optimum, visually mapping the optimality gap.

---

## 4. Manual Operator Overrides & Controls

In default operation, the microgrid runs in **Auto Mode**, allowing the trained PIS-PPO agent to make safe, optimal dispatch decisions. Operators can override the AI agent using the control toolbar:

### 4.1. Auto Mode
- **Description**: The PIS-PPO agent controls the battery. It optimizes charging during solar surplus or low-tariff night periods and discharges during peak hours.

### 4.2. Force Charge BESS
- **Description**: Bypasses the AI and forces BESS to charge at maximum capacity ($55\text{ kW}$) until it reaches the upper safety limit ($90\%$).

### 4.3. Force Discharge BESS
- **Description**: Forces the battery to discharge at maximum capacity ($58\text{ kW}$) until it drains to the lower safety limit ($20\%$).

### 4.4. Island Mode
- **Description**: Simulates complete grid failure. The microgrid disconnects from the utility grid. BESS, solar, and wind must support the facility load.

### 4.5. Carbon-Arbitrage Weight Slider
- **Description**: Allows operators to dynamically adjust the carbon optimization weight ($w_c \in [0.0, 1.0]$) in the backend utility function, shifting the agent's behavior between cost-minimization and carbon footprint reduction.

---

## 5. SCADA Risk Alerts & Alarms

The dashboard includes a real-time Risk Alerts banner fed by `GET /alerts`. Alarms are triggered under the following physical conditions:

| Alarm Name | Trigger Condition | Operational Action |
| :--- | :--- | :--- |
| **Grid Overload Risk** | $P_{\text{grid}} \ge 135 \text{ kW}$ | Warns operator of high peak demand fees. |
| **Critical Peak Tariff** | $\text{Tariff} \ge 9.20 \text{ INR/kWh}$ | Prompts BESS discharge to avoid high import rates. |
| **BESS Battery Violation** | $SoC < 20\% \text{ or } SoC > 90\%$ | Bypasses commands to force the BESS back to safe limits. |
| **Island Mode Active** | Island mode enabled by operator | Warns that the local grid is isolated. |
| **BESS Health Warning** | BESS cycles exceed aging limit | Recommends battery cell inspection. |
