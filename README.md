# PV Fault Injector
A Python tool for simulating PV systems based on PVLib with custom support for fault injection.

## File Overview
```
pv_fault_injector/
|
├── data/
|   └── horw.json               # Example community config
|
├── docs/
|   ├── pipeline.md             # Pipeline documentation
|   └── faults.md               # Faults documentation
|
├── src/
|   ├── Simulation.py           # Simulation class
|   ├── PvSystem.py             # PvSystem class
|   ├── WeatherModel.py         # Weather fetching
|   ├── faults.py               # Fault injection functions
|   └── plot.py                 # Plotting functions
|
├── output/                     # Simulation output (CSV per system)
├── data_generator_gui.py       # GUI for creating and editing community JSON files
└── README.md
```
---

## Data Flow

```
community.json ──► WeatherModel ──► weather_df (ghi, dhi, dni, temp_air, wind_speed, precipitation, ...)
                                        │
                        ┌───────────────┴───────────────┐
                        │ Injection point A             │ Injection point B
                        ▼                               ▼
                soiling, mask_shading    degradation, pid, open_string
                                            
                        │                               │
                        └───────────────┬───────────────┘
                                        ▼
                                 PvSystem.run_model()
                                        │
                                        ▼
                                ac_simulated (hourly W)
                                        │
                                        ▼
                          inverter_fault, snowfall        (Injection point C)
                                        │
                                        ▼
                                ac_faulty (hourly W)
                                        │
                                        ▼
                                output CSV + plots
```
---