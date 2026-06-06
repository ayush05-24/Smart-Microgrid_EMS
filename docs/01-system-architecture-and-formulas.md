# System Architecture & Mathematical Formulations

This document provides a comprehensive technical overview of the Smart Microgrid Energy Management System (EMS), detailing the system architecture, component layout, and mathematical formulations.

---

## 1. Central Configuration & Parameters

The microgrid parameters are centrally managed in [config.py](file:///c:/Users/ayush/Desktop/Project/Projects/Final%20Year%20Project/backend/app/config.py) and represent a commercial-scale microgrid installation:

| Parameter | Value | Description |
| :--- | :--- | :--- |
| **Solar Capacity ($P_{\text{pv\_max}}$)** | $140.0 \text{ kW}$ | Peak photovoltaic generating capacity |
| **Solar Performance Ratio ($\eta_{\text{pv}}$)** | $0.82$ | System derating/inverter losses |
| **Wind Capacity ($P_{\text{wind\_max}}$)** | $15.0 \text{ kW}$ | Peak wind turbine generation capacity |
| **Minimum Facility Load ($P_{\text{load\_min}}$)** | $24.0 \text{ kW}$ | Night-time base load threshold |
| **Maximum Facility Load ($P_{\text{load\_max}}$)** | $175.0 \text{ kW}$ | Peak design facility load limit |
| **BESS Energy Capacity ($C_{\text{max}}$)** | $180.0 \text{ kWh}$ | Total battery capacity |
| **Safe SoC Bounds ($[\underline{S}, \bar{S}]$)** | $20.0\% \text{ to } 90.0\%$ | State-of-Charge operational boundaries |
| **Nominal BESS Charge Rate ($\bar{P}_{\text{ch}}$)** | $55.0 \text{ kW}$ | Nominal charging power limit |
| **Nominal BESS Discharge Rate ($\bar{P}_{\text{dis}}$)** | $58.0 \text{ kW}$ | Nominal discharging power limit |
| **BESS Round-Trip Efficiency ($\eta_{\text{rt}}$)** | $0.93$ | Total storage conversion efficiency |
| **BESS Capex Cost ($C_{\text{repl}}$)** | ₹$2,500,000.0$ | Battery replacement cost (INR) |
| **BESS End-of-Life (EoL) SoH** | $80.0\%$ | Capacity fade threshold for battery retirement |
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

### 2.3. BESS State-of-Health (SoH) & Dynamic Aging
The State-of-Health ($SoH_t$) decreases dynamically due to coupled cycle and calendar aging:

$$SoH_{t+1} = SoH_t - (d^{\text{cyc}}_t + d^{\text{cal}}_t) \cdot 100\%$$

#### 2.3.1. Cycle Aging ($d^{\text{cyc}}_t$)
Using a Depth-of-Discharge (DoD) power law $N_f(\delta) = a \cdot \delta^{-b}$ modeling cycles-to-failure for DoD $\delta$, the incremental capacity fade at operating DoD $\delta_t = 1 - SoC_t/100$ is:

$$d^{\text{cyc}}_t = \frac{|P^b_t| \cdot \Delta t}{2 \cdot N_f(\delta_t) \cdot C_{\text{max}} \cdot \delta_t} \cdot \xi(T^b_t)$$

For standard Lithium-ion NMC cells, parameters are set to $a = 3251.0$ and $b = 1.05$.

#### 2.3.2. Calendar Aging ($d^{\text{cal}}_t$)
Calendar capacity fade grows with time, temperature, and stored energy:

$$d^{\text{cal}}_t = k_{\text{cal}} \cdot \xi(T^b_t) \cdot \left(\frac{SoC_t}{100}\right)^\mu \cdot \Delta t$$

Where $k_{\text{cal}} = 1.48 \times 10^{-6}$ per hour and $\mu = 0.8$.

#### 2.3.3. Arrhenius Temperature Acceleration ($\xi(T^b_t)$)
The cell temperature $T^b_t$ (in Kelvin) accelerates aging:

$$\xi(T^b_t) = \exp\left[ \frac{E_a}{R} \left( \frac{1}{T_{\text{ref}}} - \frac{1}{T^b_t} \right) \right]$$

Where:
- $E_a = 50,000 \text{ J/mol}$ (activation energy)
- $R = 8.314 \text{ J/(mol K)}$ (ideal gas constant)
- $T_{\text{ref}} = 298.15 \text{ K}$ ($25^\circ\text{C}$ reference temperature)
- Cell temperature is modeled dynamically from ambient temperature $T^a_t$ and internal heat loss:
  $$T^b_t = T^a_t + R_{\text{th}} \cdot P_{\text{loss}}$$
  $$P_{\text{loss}} = (1 - \eta_{\text{ch}, t}) \cdot [P^b_t]^- + \left(\frac{1}{\eta_{\text{dis}, t}} - 1\right) \cdot [P^b_t]^+$$
  With cell thermal resistance $R_{\text{th}} = 0.05 \text{ K/kW}$.

#### 2.3.4. Internal Resistance & Efficiency Degradation
The battery internal resistance grows by 1.2x of the capacity fade rate:

$$R_{\text{i}, t+1} = R_{\text{i}, t} + 1.2 \cdot (d^{\text{cyc}}_t + d^{\text{cal}}_t) \cdot 100\%$$

As resistance grows, the charging and discharging efficiencies degrade:

$$\eta_{\text{ch}, t} = \frac{\eta_{\text{ch}, 0}}{(R_{\text{i}, t})^{0.1}}, \quad \eta_{\text{dis}, t} = \frac{\eta_{\text{dis}, 0}}{(R_{\text{i}, t})^{0.1}}$$

### 2.4. BESS Dynamic State-of-Charge (SoC) Dynamics
The battery energy state $E_{t+1}$ updates based on charge/discharge power $P^b_t$ (where $P^b_t < 0$ represents charging, and $P^b_t > 0$ represents discharging):

- **Charging State Update ($P^b_t < 0$)**:
  $$E_{t+1} = E_t - P^b_t \cdot \eta_{\text{ch}, t} \cdot \Delta t$$
- **Discharging State Update ($P^b_t \ge 0$)**:
  $$E_{t+1} = E_t - \left(\frac{P^b_t}{\eta_{\text{dis}, t}}\right) \cdot \Delta t$$
- **State-of-Charge (SoC) Conversion**:
  $$SoC_{t} = \left(\frac{E_t}{C_{\text{max}} \cdot SoH_t/100}\right) \cdot 100\%$$

### 2.5. Microgrid Power Balance & Net Load
Grid import $P_{\text{grid}, t}$ balances any local energy surplus or deficit:

$$P_{\text{grid}, t} = \max\left(P_{\text{load}, t} - P_{\text{pv}, t} - P_{\text{wind}, t} - P^b_t, 0.0\right)$$

Renewable Energy Used ($P_{\text{renew\_used}, t}$) and curtailment ($P_{\text{curtailed}, t}$) are:

$$P_{\text{renew\_used}, t} = \min\left(P_{\text{pv}, t} + P_{\text{wind}, t}, P_{\text{load}, t} - \min(P^b_t, 0.0)\right)$$

$$P_{\text{curtailed}, t} = \max\left(P_{\text{pv}, t} + P_{\text{wind}, t} - P_{\text{renew\_used}, t}, 0\right)$$

### 2.6. Tariff Structure (Time-of-Use)
Energy purchase rates are governed by a dynamic tariff profile reflecting utility grid pricing structures (India commercial standard):

$$\text{Tariff}(t) = \begin{cases}
  2.60 \text{ INR/kWh} & \text{if } t \in [22:00, 06:00) \text{ (Night Off-Peak)} \\
  9.20 \text{ INR/kWh} & \text{if } t \in [18:00, 22:00) \text{ (Evening Peak)} \\
  5.60 \text{ INR/kWh} & \text{otherwise (Normal Hours)}
\end{cases}$$

### 2.7. Diurnal Grid Carbon Intensity
To simulate Indian grid variations (coal baseline, afternoon solar injection), carbon intensity $\kappa_t$ (kg-CO₂/kWh) follows a diurnal profile:

$$\kappa_t = 0.5 + 0.2 \cdot \sin\left(\frac{2\pi (h_t - 6)}{24}\right) + 0.15 \cdot \cos\left(\frac{4\pi (h_t - 18)}{24}\right)$$

---

## 3. Physics-Informed Safe Reinforcement Learning

The Energy Management System (EMS) battery dispatch problem is cast as a **Constrained Markov Decision Process (CMDP)**.

### 3.1. Differentiable Feasibility Projection Layer
To guarantee physical safety and prevent cell degradation without relying on soft reward penalties, the raw action request $\tilde{a}_t \in [-1, 1]$ output by the policy is projected onto the instantaneous feasible action set $\mathcal{F}_t$:

$$P^b_t = \Pi_{\mathcal{F}_t}(\hat{P}^b_t) = \text{clip}(\hat{P}^b_t, P^{\text{min}}_t, P^{\text{max}}_t)$$

Where the boundaries $[P^{\text{min}}_t, P^{\text{max}}_t]$ enforce constraints on State-of-Charge (SoC), charging/discharging power (including cell temperature thermal derating derate factor $d_{\text{rate}} = \max(0, \min(1, \frac{T_{\text{crit}} - T^b_t}{T_{\text{crit}} - T_{\text{warn}}}))$), and grid connection limits by construction:

- **Thermal Derating Limits**:
  $$P^{\text{thermal}}_{\text{ch}} = \bar{P}_{\text{ch}} \cdot d_{\text{rate}}, \quad P^{\text{thermal}}_{\text{dis}} = \bar{P}_{\text{dis}} \cdot d_{\text{rate}}$$
- **SoC Limits**:
  $$P^b_{\text{SoC, min}} = -\frac{(\bar{S} - SoC_t) \cdot C_{\text{max}} \cdot SoH_t/100}{100 \cdot \Delta t \cdot \eta_{\text{ch}, t}}$$
  $$P^b_{\text{SoC, max}} = \frac{(SoC_t - \underline{S}) \cdot C_{\text{max}} \cdot SoH_t/100 \cdot \eta_{\text{dis}, t}}{100 \cdot \Delta t}$$
- **Combined Projection Boundaries**:
  $$P^{\text{min}}_t = \max\left( -P^{\text{thermal}}_{\text{ch}},\; P^b_{\text{SoC, min}} \right)$$
  $$P^{\text{max}}_t = \min\left( P^{\text{thermal}}_{\text{dis}},\; P^b_{\text{SoC, max}},\; \max(0.0, P_{\text{load}, t} - P_{\text{pv}, t} - P_{\text{wind}, t}) \right)$$

Since this clipping operator is sub-differentiable, policy gradients flow directly to network weights $\theta$ during training.

### 3.2. Observation Space (State vector $s_t$)
A 9-dimensional continuous feature vector:
$$s_t = \left[ P_{\text{pv}, t}, P_{\text{wind}, t}, P_{\text{load}, t}, SoC_t, SoH_t, \text{Tariff}_t, \phi^s_t, \phi^c_t, \text{IsWeekend}_t \right]$$

Where $\phi^s_t = \sin(2\pi \cdot \text{hour}_t/24)$ and $\phi^c_t = \cos(2\pi \cdot \text{hour}_t/24)$ are cyclic hour encodings.

### 3.3. Reward Function Formulation
The agent optimizes a multi-objective reward formulation designed to minimize cost, battery aging, and carbon footprint:

$$R_t = -(E_{\text{cost}, t} + w_d \cdot C_{\text{deg}, t} + w_c \cdot (E^{\text{CO}_2}_t \cdot P_{\text{carbon}}) + w_r \cdot \text{CVaR}_t)$$

Where:
- **Electricity Purchase Cost ($E_{\text{cost}, t}$)**:
  $$E_{\text{cost}, t} = P_{\text{grid}, t} \cdot \text{Tariff}_t \cdot \Delta t$$
- **Battery Aging Cost ($C_{\text{deg}, t}$)**:
  $$C_{\text{deg}, t} = \frac{C_{\text{repl}}}{0.2} \cdot (d^{\text{cyc}}_t + d^{\text{cal}}_t) \cdot 100$$
- **Grid Carbon Emissions Cost ($E^{\text{CO}_2}_t$)**:
  $$E^{\text{CO}_2}_t = \kappa_t \cdot P_{\text{grid}, t} \cdot \Delta t, \quad P_{\text{carbon}} = 2.0 \text{ INR/kg}$$
- **CVaR Renewable Shortfall Penalty**: Approximates financial risk under extreme renewable shortfalls using LSTM forecast quantiles:
  $$\text{CVaR}_t = \text{Tariff}_t \cdot \max\left( 0.0,\; P_{\text{load}, t} - P^{(0.1)}_{\text{pv}, t} - P^{(0.1)}_{\text{wind}, t} \right)$$
- **Weights**: $w_d = 0.2$, $w_c = 0.1$, $w_r = 0.15$. The carbon weight is dynamically adjusted on the SCADA UI (adjusting $w_c$).

---

## 4. Explainable AI (XAI) Metrics

*   **Decision Entropy**: Measures policy decisiveness from Gaussian standard deviation:
    $$\mathcal{H}_t = \frac{1}{2} \log(2\pi e \sigma^2(s_t))$$
*   **Integrated Gradients (IG)**: Feature attributions computed by path integration from an idle baseline state $s'$ (zero loads, zero solar/wind, 50% SoC):
    $$IG_i(s_t) = (s_{t,i} - s'_{i}) \times \frac{1}{K} \sum_{k=1}^K \frac{\partial \pi_\theta(s' + \frac{k}{K}(s_t - s'))}{\partial s_i}$$
    Using $K=30$ approximation steps.
*   **Explanation Fidelity**: Percentage of steps where the continuous DRL action matches the logical heuristic rule direction:
    $$\mathcal{F}^{\text{exp}} = \frac{1}{T} \sum_t \mathbb{I}\left[ \text{sign}(P^b_{\text{opt}, t}) = \text{rule}(s_t) \right]$$
*   **Attribution Stability**: Sensitivity of integrated gradients to input perturbations $\delta \sim \mathcal{N}(0, 0.01^2)$:
    $$\mathcal{S}^{\text{exp}} = 1 - \frac{\mathbb{E}_{\|\delta\| \le \rho} \|IG(s_t + \delta) - IG(s_t)\|_1}{\|IG(s_t)\|_1 + \epsilon}$$
