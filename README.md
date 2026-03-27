# PV Fault Injector
A Python tool for simulating PV systems based on PVLib with custome support for fault injection.

## File Overview
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