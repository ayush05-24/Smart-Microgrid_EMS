# Project Planning & Objectives

This document outlines the project planning, core requirements, objectives, and execution milestones established for the Smart Microgrid Energy Management System (EMS).

---

## 1. Project Objectives

The project is structured around five key engineering objectives to deliver an end-to-end intelligent energy management controller:

### Objective 1: Meteorological Data Acquisition & Preprocessing
*   Extract 6 years ($52,608 \text{ hours}$) of historical meteorological measurements from the NASA POWER API for local coordinates ($12.9163^\circ\text{ N}, 79.1325^\circ\text{ E}$).
*   Establish an automated cleaning, linear time-interpolation, and range-bounding pipeline to eliminate telemetry sensors' spikes.

### Objective 2: High-Accuracy Short-Term Forecasting Layer
*   Develop sequence-to-sequence LSTM forecasting models to predict solar PV generation and building electrical load over a rolling 24-hour horizon.
*   Anticipate mechanical load profiles, specifically the **2.5-hour HVAC thermal lag**, using 12-hour historical sequences.

### Objective 3: Real-Time Dispatch Optimization Layer
*   Formulate battery charging and discharging control as a Markov Decision Process (MDP).
*   Train a Proximal Policy Optimization (PPO) Deep Reinforcement Learning agent in a custom OpenAI Gym environment to minimize cost under Time-of-Use grid tariffs.

### Objective 4: Safety & BESS Degradation Enforcements
*   Implement hard physical constraints preventing charging/discharging rates from exceeding safety bounds.
*   Enforce a safe operational State-of-Charge (SoC) envelope ($20\%$ to $90\%$) and apply battery cycle degradation penalties in the PPO reward function.

### Objective 5: Industry-Grade SCADA Dashboard
*   Deploy a FastAPI backend to expose prediction, control, and metrics endpoints at low latencies.
*   Design a React SCADA dashboard with a 1.5-second refresh cycle, displaying real-time power flows, interactive override controls, and active risk alerts.

---

## 2. Project Requirements

### Compute & Hardware Requirements
*   **Edge Gateway / Server**: Minimum 4-core CPU, 8 GB RAM for real-time telemetry processing and hosting API endpoints.
*   **Training Accel**: NVIDIA CUDA-compatible GPU (e.g., RTX 3060 or higher) with PyTorch support for LSTM and PPO training.
*   **Microgrid Assets**:
    *   140 kW Solar PV Array.
    *   15 kW Low-Wind Speed Turbine (1.5 m/s cut-in speed).
    *   180 kWh Lithium-ion BESS with 93% round-trip efficiency.

### Software Stack Requirements
*   **Backend Runtime**: Python 3.13
*   **Web Framework**: FastAPI & Uvicorn (HTTP / Server-Sent Events)
*   **Scientific Stack**: PyTorch, Stable-Baselines3, Gym, Pandas, NumPy, Scikit-learn, Joblib
*   **Frontend**: React 19, Vite, Recharts, Lucide React, CSS3

---

## 3. Work Package Breakdown & Milestones

```text
  Phase 1: Ingestion & EDA (Weeks 1-4)
    ├── NASA POWER API Ingestion
    ├── Weather Cleaning & Interpolation
    └── HVAC Lag & Load Profiling Analysis
  
  Phase 2: Forecasting Layer (Weeks 5-8)
    ├── LSTM Solar Predictor Training
    ├── LSTM Load Predictor Training
    └── Model Optimization & Scaler Validation
  
  Phase 3: DRL Optimization (Weeks 9-12)
    ├── Custom Gym Environment Setup
    ├── PPO Reward Function Formulation
    └── Safety Constraint Verification
  
  Phase 4: Interface & SCADA (Weeks 13-16)
    ├── FastAPI Endpoint Development
    ├── React Dashboard & Charts Layout
    └── Dynamic Telemetry Polling Loops
  
  Phase 5: MATLAB & Defense (Weeks 17-20)
    ├── MATLAB/Simulink Exporters
    ├── Scenario & Stress Testing Validation
    └── Capstone Report & Defense Presentation
```
