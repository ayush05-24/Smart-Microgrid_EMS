# System Architecture & Mathematical Formulations

This document provides a comprehensive technical overview of the Smart Microgrid Energy Management System (EMS), detailing the system architecture, component layout, and mathematical formulations.

---

## 1. Central Configuration & Parameters

The microgrid parameters are centrally managed in [config.py](file:///c:/Users/ayush/Desktop/Project/Projects/Final%20Year%20Project/backend/app/config.py) and represent a commercial-scale commercial microgrid installation:

| Parameter | Value | Description |
| :--- | :--- | :--- |
| **Solar Capacity ($P_{\text{pv\_max}}$)** | $140.0 \text{ kW}$ | Peak photovoltaic generating capacity |
| **Solar Performance Ratio ($\eta_{\text{pv}}$)** | $0.82$ | System derating/inverter losses |
| **Wind Capacity ($P_{\text{wind\_max}}$)** | $15.0 \text{ kW}$ | Peak wind turbine generation capacity |
| **Minimum Facility Load ($P_{\text{load\_min}}$)** | $24.0 \text{ kW}$ | Night-time base load threshold |
| **Maximum Facility Load ($P_{\text{load\_max}}$)** | $175.0 \text{ kW}$ | Peak design facility load limit |
| **BESS Energy Capacity ($E_{\text{bess}}$)** | $180.0 \text{ kWh}$ | Total battery capacity |
| **Safe SoC Bounds** | $20.0\% \text{ to } 90.0\%$ | State-of-Charge operational boundaries |
| **Max BESS Charge Rate** | $55.0 \text{ kW}$ | Charging power limit |
| **Max BESS Discharge Rate** | $58.0 \text{ kW}$ | Discharging power limit |
| **Round-Trip Efficiency ($\eta_{\text{rt}}$)** | $0.93$ | Total storage conversion efficiency |
| **Timezone** | `Asia/Kolkata` | Local time coordination standard |

---

## 2. Mathematical Formulations

### 2.1. Solar Power Generation Model
The actual photovoltaic power output $P_{\text{pv}, t}$ at time $t$ is calculated from Global Horizontal Irradiance ($GHI_t$), ambient temperature ($T_t$), and relative humidity ($RH_t$):

$$P_{\text{pv}, t} = \left(\frac{GHI_t}{1000}\right) \cdot P_{\text{pv\_max}} \cdot \eta_{\text{pv}} \cdot f_{\text{temp}}(T_t) \cdot f_{\text{hum}}(RH_t)$$

Where:
- **Temperature Derating Factor ($f_{\text{temp}}$)**: Represents panel efficiency degradation at high temperatures:
  $$f_{\text{temp}}(T_t) = 1 - \max(T_t - 25, 0) \cdot 0.004$$
- **Humidity Derating Factor ($f_{\text{hum}}$)**: Accounts for atmospheric scattering and moisture accumulation:
  $$f_{\text{hum}}(RH_t) = 1 - \max(RH_t - 85, 0) \cdot 0.001$$
- The output is bounded by physical limits:
  $$0 \le P_{\text{pv}, t} \le P_{\text{pv\_max}}$$

### 2.2. Wind Power Generation Model
The wind turbine output $P_{\text{wind}, t}$ utilizes a realistic physical power curve with cut-in, rated, and cut-out speeds:

$$P_{\text{wind}}(v_t) = \begin{cases} 
  0 & \text{if } v_t < v_{\text{cut-in}} \\ 
  P_{\text{wind\_max}} \cdot \left(\frac{v_t - v_{\text{cut-in}}}{v_{\text{rated}} - v_{\text{cut-in}}}\right)^3 & \text{if } v_{\text{cut-in}} \le v_t < v_{\text{rated}} \\ 
  P_{\text{wind\_max}} & \text{if } v_{\text{rated}} \le v_t \le v_{\text{cut-out}} \\
  0 & \text{if } v_t > v_{\text{cut-out}}
\end{cases}$$

Where the parameters are tuned for realistic low-wind speed locations:
- **Cut-in speed ($v_{\text{cut-in}}$)** = $1.5 \text{ m/s}$
- **Rated speed ($v_{\text{rated}}$)** = $8.0 \text{ m/s}$
- **Cut-out speed ($v_{\text{cut-out}}$)** = $20.0 \text{ m/s}$

### 2.3. BESS State-of-Charge (SoC) Dynamics
The battery state updates based on charging $P_{\text{ch}, t}$ or discharging $P_{\text{dis}, t}$ command vectors:

$$\eta_{\text{ch}} = \eta_{\text{dis}} = \sqrt{\eta_{\text{rt}}} = \sqrt{0.93} \approx 0.9644$$

- **Charging State Update**:
  $$E_{t+1} = E_t + P_{\text{ch}, t} \cdot \eta_{\text{ch}} \cdot \Delta t$$
- **Discharging State Update**:
  $$E_{t+1} = E_t - \left(\frac{P_{\text{dis}, t}}{\eta_{\text{dis}}}\right) \cdot \Delta t$$
- **State-of-Charge (SoC) Conversion**:
  $$SoC_{t} = \left(\frac{E_t}{E_{\text{bess}}}\right) \cdot 100\%$$
- The system enforces a strict physical bounding envelope to prevent accelerated degradation:
  $$20.0\% \le SoC_t \le 90.0\%$$

### 2.4. Microgrid Power Balance
Grid import $P_{\text{grid}, t}$ balances any local energy surplus or deficit dynamically:

$$P_{\text{grid}, t} = \max\left(P_{\text{load}, t} - P_{\text{pv}, t} - P_{\text{wind}, t} + P_{\text{ch}, t} - P_{\text{dis}, t}, 0\right)$$

Renewable Energy Used ($P_{\text{renew\_used}, t}$) and curtailment ($P_{\text{curtailed}, t}$) are:

$$P_{\text{renew\_used}, t} = \min\left(P_{\text{pv}, t} + P_{\text{wind}, t}, P_{\text{load}, t} + P_{\text{ch}, t}\right)$$

$$P_{\text{curtailed}, t} = \max\left(P_{\text{pv}, t} + P_{\text{wind}, t} - P_{\text{renew\_used}, t}, 0\right)$$

### 2.5. Tariff Structure (Time-of-Use)
Energy purchase rates are governed by a dynamic tariff profile reflecting utility grid pricing structures (India commercial standard):

$$\text{Tariff}(t) = \begin{cases}
  2.60 \text{ INR/kWh} & \text{if } t \in [22:00, 06:00) \text{ (Night Off-Peak)} \\
  9.20 \text{ INR/kWh} & \text{if } t \in [18:00, 22:00) \text{ (Evening Peak)} \\
  5.60 \text{ INR/kWh} & \text{otherwise (Normal Hours)}
\end{cases}$$

---

## 3. Deep Reinforcement Learning (DRL) Formulation

The optimization is solved via a custom OpenAI Gym Environment using **Proximal Policy Optimization (PPO)**.

### 3.1. Observation Space (State vector $s_t$)
A 9-dimensional continuous feature vector:
$$s_t = \left[ P_{\text{solar}, t}, P_{\text{wind}, t}, P_{\text{load}, t}, SoC_t, \text{Tariff}_t, \sin\left(\frac{2\pi \cdot \text{hour}_t}{24}\right), \cos\left(\frac{2\pi \cdot \text{hour}_t}{24}\right), \text{IsWeekend}_t \right]$$

### 3.2. Action Space ($a_t$)
Discrete action vectors mapping operating modes:
- **0**: Idle BESS ($P_{\text{bess}} = 0$)
- **1**: Charge BESS ($P_{\text{ch}} = \min(P_{\text{ch\_max}}, \text{remaining capacity})$)
- **2**: Discharge BESS ($P_{\text{dis}} = \min(P_{\text{dis\_max}}, \text{available energy})$)

### 3.3. Reward Function Formulation
The agent optimizes a multi-objective reward formulation designed to minimize cost, BESS degradation, peak grid imports, and safety violations:

$$R_t = R_{\text{economic}} + R_{\text{degradation}} + R_{\text{peak}} + R_{\text{safety}} + R_{\text{renewable}}$$

- **Economic Cost Penalty**:
  $$R_{\text{economic}} = -\frac{P_{\text{grid}, t} \cdot \text{Tariff}_t}{24}$$
- **Battery Degradation Penalty**: Penalizes cell cycling to extend physical lifetime:
  $$R_{\text{degradation}} = -|P_{\text{bess}, t}| \cdot \text{Cost}_{\text{deg}} \quad (\text{where } \text{Cost}_{\text{deg}} = 0.05 \text{ INR/kWh})$$
- **Peak Import Penalty**: Penalizes excessive grid dependency during peak tariff hours:
  $$R_{\text{peak}} = \begin{cases} -0.06 \cdot P_{\text{grid}, t} & \text{if } \text{Tariff}_t \ge 9.20 \\ 0 & \text{otherwise} \end{cases}$$
- **Safety Violation Penalty**: Heavily penalizes transitions that breach battery SoC boundaries:
  $$R_{\text{safety}} = \begin{cases} -45.0 & \text{if SoC bounds violated} \\ 0 & \text{otherwise} \end{cases}$$
- **Renewable Utilization Reward**: Rewards local consumption of clean energy:
  $$R_{\text{renewable}} = 0.018 \cdot P_{\text{renew\_used}, t}$$

---

## 4. LSTM Forecasting Layer

The system uses separate sequence-to-sequence LSTM forecasters to predict solar generation and building load 24 hours into the future.

### Model Architecture:
- **Input Sequence Length**: $48 \text{ timesteps } (12 \text{ hours})$
- **Hidden Network Size**: $96 \text{ units}$
- **LSTM Layers**: $2 \text{ stacked layers}$
- **Dropout Ratio**: $0.15$
- **Optimizer**: `AdamW` with dynamic weight decay.
- **Loss Criterion**: Mean Squared Error (MSE).
- **Execution Target**: CUDA GPU with PyTorch optimization.
