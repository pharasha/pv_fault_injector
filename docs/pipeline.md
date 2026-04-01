# Simulation Pipeline

## File Overview
```
pv_fault_injector/
|
├── data/
|   ├── modules.json            # Module characteristics
|   ├── settings.json           # Simulation settings
|   └── ...
|
├── docs/
|   ├── pipeline.md             # pipeline documentation
|   └──  faults.md              # faults documentation
|
├── simulation.py               # Main Simulation and Classes
├── faults.py                   # Fault injection functions
├── weather.py                  # Weather fetcher and 
└── README.md
```
---

## Data Flow

```
config.json ──► weather.py ──► weather_df (ghi, dhi, dni, temp_air, wind_speed, precipitation, ...)
                                    │
                    ┌───────────────┴───────────────┐
                    │ Injection point A             │ Injection point B
                    ▼                               ▼
             soiling, shading         degradation, pid, open_string
                                          
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
config.json ──► simulate.py ◄── weather_df (modified or original)
                    │           module_params (modified or original)
                    ▼
            ac_simulated (hourly W)
                    │
                    ▼
              inverter, wiring          (Injection point C)

                    │
                    ▼
            ac_faulty (hourly W)
            
                    │
                    ▼       
            metrics + plots
```
---

## weather.py

fetched using OpenMeteo.

Column mapping:
- `shortwave_radiation`      → `ghi`
- `diffuse_radiation`        → `dhi`
- `direct_normal_irradiance` → `dni`
- `wind_speed_10m`           → `wind_speed`
...


## simulate.py



## config.json Fields

| Field | Description |
|---|---|
| `system_id` | smart-me device ID for filtering the parquet |
| `module_cec` | CEC database key for the module |
| `inverter_cec` | CEC database key for the inverter |
| `modules_per_string` | used only for the CEC model topology |
| `strings` | used only for the CEC model topology |
| `real_module_count` | actual number of modules on the roof |
| `system_loss_fraction` | flat derate for healthy-system losses (0–1) |
| `comparison_window` | default date range for compare.py |
