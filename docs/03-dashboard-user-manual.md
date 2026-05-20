# Dashboard User Manual & SCADA Operator Guide

This document is the official user manual and operator guide for the Smart Microgrid EMS SCADA interface. It details the frontend architecture, live streaming protocols, manual overrides, and risk threshold alarms.

---

## 1. Frontend Architecture & Technology Stack

The operator dashboard is a high-speed, modern Single Page Application (SPA) designed for real-time industrial monitoring:

- **Framework**: React.js (built with Vite for fast compiling and sub-300ms hot reloading).
- **Styling**: Vanilla CSS utilizing a premium **glassmorphism** aesthetic (semi-transparent panel backdrops, soft drop shadows, and high contrast typography).
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
  - The `records_window` array populates the **Power Flow Chart** (live load, solar, wind, and battery power) and **SoC Trajectory Chart**.
  - The dispatch log list displays the **Dispatch Decision History Table** in reverse-chronological order.

---

## 3. Manual Operator Overrides

In default operation, the microgrid runs in **Auto Mode**, allowing the trained PPO agent to make economic dispatch decisions. Operators can override the AI agent using the control toolbar:

### 3.1. Auto Mode
- **Description**: The AI agent controls the battery. It optimizes charging during solar surplus or low-tariff night periods and discharges during peak hours.

### 3.2. Force Charge BESS
- **Description**: Bypasses the AI and forces BESS to charge at maximum capacity ($55\text{ kW}$) until it reaches the upper safety limit ($90\%$).
- **Use Case**: Preparing for expected grid blackouts or utilizing dynamic off-peak grid pricing.

### 3.3. Force Discharge BESS
- **Description**: Forces the battery to discharge at maximum capacity ($58\text{ kW}$) until it drains to the lower safety limit ($20\%$).
- **Use Case**: Shaving peak demand costs or supporting critical emergency loads.

### 3.4. Island Mode
- **Description**: Simulates complete grid failure. The microgrid disconnects from the utility grid. BESS, solar, and wind must support the facility load.
- **Use Case**: Maintaining continuous power to hospital rooms, data centers, or cleanrooms.

---

## 4. SCADA Risk Alerts & Alarms

The dashboard includes a real-time Risk Alerts banner fed by `GET /alerts`. Alarms are triggered under the following physical conditions:

| Alarm Name | Trigger Condition | Operational Action |
| :--- | :--- | :--- |
| **Grid Overload Risk** | $P_{\text{grid}} \ge 135 \text{ kW}$ | Warns operator of high peak demand fees. |
| **Critical Peak Tariff** | $\text{Tariff} \ge 9.20 \text{ INR/kWh}$ | Prompts BESS discharge to avoid high import rates. |
| **BESS Battery Violation** | $SoC < 20\% \text{ or } SoC > 90\%$ | Bypasses commands to force the BESS back to safe limits. |
| **Island Mode Active** | Island mode enabled by operator | Warns that the local grid is isolated. |
| **BESS Health Warning** | BESS cycles exceed aging limit | Recommends battery cell inspection. |
