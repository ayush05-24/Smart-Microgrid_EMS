# Exploratory Data Analysis & Feature Engineering

This document outlines the raw data source, the data engineering pipeline, and the physical insights uncovered during the Exploratory Data Analysis (EDA).

---

## 1. Meteorological Data Source

The meteorological measurements were extracted from the **NASA Prediction of Worldwide Energy Resources (POWER) API** for the coordinates corresponding to Vellore, Tamil Nadu, India ($12.9163^\circ\text{ N}, 79.1325^\circ\text{ E}$):

- **Temporal Coverage**: 6 years of continuous hourly readings.
- **Total Record Count**: $52,608 \text{ rows}$.
- **Features Extracted**:
  - Global Horizontal Irradiance ($GHI$)
  - Direct Normal Irradiance ($DNI$)
  - Diffuse Horizontal Irradiance ($DIFF$)
  - Ambient Dry Bulb Temperature ($T$)
  - Relative Humidity ($RH$)
  - Wind Speed at $10\text{ meters}$ ($WS10M$)
  - Corrected Precipitation ($PRECTOTCORR$)

---

## 2. Data Cleaning & Normalization Pipeline

The cleaning pipeline is defined in [cleaning.py](file:///c:/Users/ayush/Desktop/Project/Projects/Final%20Year%20Project/backend/app/data/cleaning.py) and processes raw NASA coordinates:

1. **Null Replacement**: Replaces NASA missing value codes (`-999`) with standard Python `NaN`.
2. **Timestamp Alignment**: Builds a UTC timestamp from year, month, day, and hour coordinates, then localizes it to `Asia/Kolkata` timezone.
3. **De-duplication**: Drops duplicate timestamps and sorts the index sequentially.
4. **Interpolation**: Interpolates numeric columns using a time-weighted linear interpolation, followed by forward and backward filling for edge values.
5. **Physical Range Clipping**: Enforces physical boundaries to eliminate telemetry sensor spikes:
   - $GHI$ & $DNI$: $[0, 1100] \text{ W/m}^2$
   - $DIFF$: $[0, 900] \text{ W/m}^2$
   - Temperature: $[-5, 55]^\circ\text{C}$
   - Wind Speed: $[0, 35] \text{ m/s}$
   - Humidity: $[0, 100]\%$
   - Precipitation: $[0, 300] \text{ mm}$
6. **Feature Scale Normalization**: Saves a fitted Min-Max feature scaler to `models/scalers/` for LSTM neural network training.

---

## 3. HVAC Thermal Lag Discovery

A key insight from the Exploratory Data Analysis was the discovery of **HVAC Thermal Lag** in commercial building demand profiles:

- **The Phenomenon**: In commercial facilities, maximum ambient temperature occurs around $13:00\text{ to } 14:00$. However, due to the thermal mass of the building (concrete, insulation, glass heat absorption), the internal temperature peaks later.
- **The HVAC Response**: Air conditioning systems work hardest to dissipate this absorbed heat in the late afternoon and early evening.
- **The Lag**: The resulting electrical load surge peaks between **$15:30\text{ to } 16:30$**—creating a **$2.5\text{-hour}$ thermal lag**.
- **Control Implications**: Simple rule-based battery controllers fail to anticipate this delayed load surge, whereas our sequence-to-sequence LSTM load forecasters learn this temporal dependency, enabling the PPO agent to hold BESS capacity for this high-tariff peak.

---

## 4. Diurnal & Seasonal Environmental Profiles

### 4.1. Solar Profile
- **Peak Irradiance**: Typically peaks at $12:00\text{ to } 13:00$ local time, reaching up to $950 \text{ W/m}^2$ on clear summer days.
- **Night Constraints**: Irradiance is zero between $18:30$ and $05:30$.

### 4.2. Wind Profile
- **Wind Speed Distribution**: Average wind speed ranges between $2.0\text{ m/s}$ and $4.5\text{ m/s}$.
- **Tuning**: Standard commercial wind turbines (cut-in speed $\ge 3.0\text{ m/s}$) generate little to no power in these conditions. Therefore, we modeled a low-wind turbine (cut-in speed $1.5\text{ m/s}$, rated speed $8.0\text{ m/s}$) to ensure realistic power generation.

### 4.3. Seasonal Modulations
We applied seasonal factors to simulate realistic grid operations:
- **Summer Multiplier** (March to June): $+16\%$ HVAC load increase.
- **Winter Multiplier** (November to February): $-9\%$ load decrease.
- **Weekend Factor**: $-12\%$ load drop due to reduced business operations.
