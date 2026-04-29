# Simulation Pipeline

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

## Community JSON

The community JSON is the main input. It describes the simulation window and all PV systems in the community.

```json
{
  "name": "My Community",
  "desc": "Optional description",
  "start_date": "2026-04-01",
  "end_date": "2026-04-28",
  "systems": [
    {
      "name": "System #0",
      "props": {
        "latitude": 47.02,
        "longitude": 8.31,
        "altitude_m": 470,
        "tilt_deg": 20,
        "azimuth_deg": 180,
        "modules_per_string": 4,
        "strings": 2,
        "module_cec": "Canadian_Solar_Inc__CS6X_305P",
        "inverter_cec": "Fronius_USA__Fronius_Primo_3_8_1_208_240__208V_"
      },
      "events": {
        "permanent": {
          "soiling":     { "enabled": true,  "params": { ... } },
          "mask_shading":{ "enabled": false, "params": { ... } },
          "degradation": { "enabled": false, "params": { ... } },
          "pid":         { "enabled": true,  "params": { ... } }
        },
        "temporary": {
          "inverter_fault_abc": { "start": "2026-04-06", "end": "2026-04-20", "params": { ... } }
        }
      }
    }
  ]
}
```

The GUI (`data_generator_gui.py`) is the intended way to create and edit these files.

---

## WeatherModel

Weather is fetched from Open-Meteo via `WeatherModel.request_historical()`.

Column mapping from Open-Meteo:
- `shortwave_radiation`      → `ghi`
- `diffuse_radiation`        → `dhi`
- `direct_normal_irradiance` → `dni`
- `wind_speed_10m`           → `wind_speed`
- `precipitation`            → `precip`
- `temperature_2m`           → `temp_air`
- `snowfall`                 → `snow`

---

## Simulation

`Simulation` takes the community dict and a `WeatherModel` instance. For each system it:

1. Fetches weather for the simulation window
2. Applies point A faults to the weather DataFrame
3. Splits the time series into segments via `get_b_segments()` and applies point B faults per segment
4. Runs `PvSystem.run_model()` on each segment and concatenates the results
5. Applies point C faults to the combined AC output
6. Saves a CSV per system to `output/<sim_id>/`

The output CSV has columns for AC power, original weather, anomaly weather, fault flags, and shading loss.