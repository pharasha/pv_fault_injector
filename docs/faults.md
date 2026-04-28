# Fault Modeling

## Pipeline reference

```
fetch_weather()  ──────────────────►  weather_df
                                           │
                                   ┌───────┴───────┐
                                   │ Point A       │ Point B
                                   ▼               ▼
                                soiling       degradation
                              mask_shading        pid
                                              open_string
                                   │               │
                                   └───────┬───────┘
                                           ▼
                                      run_model()
                                           │
                                           ▼
                                         ac (W)
                                           │
                            Point C: inverter_fault, snow
                                           │
                                           ▼
                                         ac (W)
```

Faults are injected at one of three points:
- **A** - modify `weather_df` before passing to `run_model`
- **B** - modify module parameters or system config before `run_model`. The simulation splits the time series into segments at fault boundaries so each segment gets the right parameters.
- **C** - scale `ac` after `run_model` returns

---

## Faults we cannot include

Cell-level effects like bypass diode activation and individual cell hotspots require computing full IV curves per cell, which is incompatible with the ModelChain pipeline.

---

## Soiling

Kimber model: rain-based cleaning.

Soiling loss builds up over time and resets when it rains enough. More realistic than a constant factor.

**In pvlib:** Supported via `pvlib.soiling.kimber()`.

**Injection point:** A - modifies GHI, DHI, DNI in `weather_df`.

Parameters:
- `soiling_loss_rate` - fraction of irradiance lost per day (default 0.15%/day)
- `cleaning_threshold` - daily rain in mm needed to trigger cleaning (default 6 mm)
- `max_soiling` - cap on total soiling loss fraction (default 0.30)
- `grace_period` - days after rain where dust won't re-deposit (default 14)

Internally aggregates the hourly `precip` column to daily totals, runs Kimber, then reindexes back to hourly before applying to irradiance.

---

## Mask Shading

Array-level partial shading driven by sun position. Models a physical obstruction (building, chimney, hill) that blocks the array when the sun moves through a specific azimuth and elevation window.

**Injection point:** A - modifies DNI, DHI, GHI in `weather_df`. Also returns a shading loss series that gets saved in the output CSV.

Parameters:
- `az_range` - `[lo, hi]` azimuth bounds in degrees where the obstruction is visible (e.g. `[150, 210]` for a south-facing obstruction)
- `el_range` - `[lo, hi]` sun elevation bounds in degrees (e.g. `[5, 30]` for a low obstruction)
- `affected_fraction` - fraction of the array affected (0–1)
- `opacity` - how much light is blocked when the sun is fully inside the window (0–1)
- `ramp` - transition width in degrees at the edges of the window. Set to 0 for a hard cutoff.

The shading score is computed as a trapezoid function over both azimuth and elevation, then multiplied together. This gives a smooth gradient at the edges of the obstruction rather than an abrupt step.

---

## Open String

One or more strings are completely disconnected (broken connector, damaged wire). Those strings produce zero power.

**Injection point:** B - reduces `strings` by `strings_lost` before `run_model`.

Parameters:
- `strings_lost` - number of strings to disconnect

Can be applied as a temporary fault with a start and end date, in which case `get_b_segments()` handles splitting the time series so the reduced string count only applies during the fault window.

---

## Module Degradation

Panels age and lose output capacity over time. The dominant effect is a reduction in photocurrent (`I_L_ref`). Jordan & Kurtz (2013) report a median Pmax loss of 0.5%/year.

**Injection point:** B - reduces `I_L_ref` in the module parameters.

Parameters:
- `annual_rate` - fractional Pmax loss per year (default 0.005)
- `initial_years` - age of the system at the start of the simulation (default 0)

The simulation handles the time-varying part automatically. `get_b_segments()` splits the weather series into monthly chunks and computes the elapsed years from the simulation start for each chunk, so degradation increases gradually over time.

---

## PID (Potential Induced Degradation)

High voltage stress between the cell and the grounded module frame drives leakage currents through the encapsulant. This degrades the shunt resistance and reduces photocurrent. PID can cause 50–80% power loss in severe cases and develops much faster than normal aging.

The signature is distinct from normal degradation: `R_sh_ref` collapses hard, which shows up as a drooping IV curve before Vmp and a fill factor loss that gets worse at high irradiance. Normal degradation barely touches shunt resistance.

**Injection point:** B - collapses `R_sh_ref` and reduces `I_L_ref`.

Parameters:
- `severity` - 0 (healthy) to 1 (fully degraded). At severity=1: 93% R_sh_ref collapse, 5% I_L_ref drop.

---

## Inverter Fault

The inverter operates at reduced efficiency due to overheating, partial shutdown, or poor MPPT tracking.

**Injection point:** C - scales AC output by `(1 - efficiency_loss)`.

Parameters:
- `efficiency_loss` - fractional AC power loss (e.g. 0.3 means the inverter delivers 70% of normal output)

Can be applied as a temporary fault with a start and end date.

---

## Snowfall DC Loss

Snow accumulates on the modules and reduces the effective irradiance reaching the cells. Panels at steeper tilts shed snow faster.

**In pvlib:** Supported via `pvlib.snow.coverage_nrel()` and `pvlib.snow.dc_loss_nrel()`.

**Injection point:** C - scales AC output by the computed snow loss ratio.

Requires a `snow` column in `weather_df` (available from Open-Meteo). The coverage model accounts for panel tilt, and the DC loss model accounts for the number of strings.

---

## Implemented functions

| Function | Source | What it touches | Scientific Basis & Key Numbers |
| :--- | :--- | :--- | :--- |
| `soiling_kimber()` | Kimber 2006 | scales GHI/DHI/DNI | 0.15%/day loss; 6 mm rain threshold; 14-day grace period |
| `mask_shading()` | - | scales DNI/DHI/GHI based on sun position | trapezoid score over azimuth × elevation window |
| `degradation()` | Jordan & Kurtz 2013 | reduces `I_L_ref` | 0.5%/year median Pmax loss |
| `pid()` | Mahmood 2026 / Hasan 2022 | collapses `R_sh_ref` by 93%, reduces `I_L_ref` by 5% | Experimental shunt resistance collapse in p-type c-Si |
| `open_string()` | Sabbaghpur Arani 2016 | reduces `strings` | Linear reduction in array current capacity |
| `inverter_fault()` | - | scales AC output by `(1 - efficiency_loss)` | - |
| `snowfall_dc_loss()` | - | scales AC output by snow loss ratio | - |