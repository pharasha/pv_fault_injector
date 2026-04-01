# Fault Modeling

## Pipeline reference

```
fetch_weather()  -------------- →  weather_df
                                       │
                               run_simulation(cfg, weather_df)
                                   ├─ build_system(cfg)
                                   └─ ModelChain.run_model()
                                       │
                                       ▼
                                     ac (W)
```

Faults are injected at one of three points:
- **A** - modify `weather_df` before passing to `run_simulation`
- **B** - modify `cfg` or module parameters before `run_simulation` builds the system
- **C** - scale `ac` after `run_simulation` returns

---

## Faults we cannot include

Cell-level effects like bypass diode activation and individual cell hotspots require computing full IV curves per cell, which is incompatible with the ModelChain pipeline.

---

## Soiling

Kimber model: rain-based cleaning

Soiling loss builds up over time and resets when it rains enough. More realistic than a constant factor.

**In pvlib:** Supported, `pvlib.soiling.kimber()`.

**Injection point:** A - modify `weather_df` before `run_simulation`.

```python
from src import faults

weather_faulty = faults.soiling_kimber(
    weather_df,
    soiling_loss_rate=0.0015,    # 0.15% loss per day
    cleaning_threshold=6.0,     # mm of daily rain needed to clean
    max_soiling=0.3,            # cap at 30% loss
)
ac = run_simulation(cfg, weather_faulty)
```

Internally this calls `pvlib.soiling.kimber()` on the daily rainfall totals (computed from the `precipitation` column that Open-Meteo already returns). The function returns a time series of soiling loss fractions, which is then reindexed to hourly and applied to GHI/DHI/DNI.

---

## Partial Shading (module-level shading)
A specific module receives reduced irradiance due to a physical object (chimney, vent, etc). Seperatly simulate shaded and unshaded modules/strings.

Accurate approach:
Because modules in a string share the same current, a shaded module activates its bypass diode and drops out of the string, causing a disproportionate power loss.

Pvlib cant handle this natively the array must be split into the affected string and the rest.
Each is simulated independently using the single-diode model to produce full I-V curves.
The curves are combined in series (modules) and parallel (strings).
The healty strings are simulated normally.

Key assumptions: shading fraction is constant (no moving shading).

---

## Partial Shading (string-level shading)

Entire strings are shaded. The shading fault applies to the whole string and not individual modules. Split the shaded and unshaded part into two diffrent Array objects.

Note: pvlib multi-array treats each array as independent (multi-MPPT equivalent). This skips the mismatch loss that occurs in a single-MPPT system where shaded and unshaded strings share one bus voltage. For accurate single-MPPT modeling, compute IV curves per string via `singlediode()`, combine in parallel, and find MPP with `bishop88_mpp()`. The mismatch loss is small compared to the loss caused by irradiance reduction, so the multi-array approximation is good enough for a synthetic dataset.

**In pvlib:** `PVSystem` accepts multiple `Array` objects, and `ModelChain.run_model()` accepts a list of weather DataFrames (one per array).

**Injection point:** B - replaces `run_simulation` or just run simulation with two array objects.

```python
# split strings into two Array objects (shaded / unshaded)
# reduce DNI on the shaded array weather input
# build PVSystem with both arrays
# run ModelChain with two weather DataFrames
# mc.results.ac is the combined output
```
---

## Open string

One or more strings are completely disconnected (broken connector, damaged wire). Those strings produce zero power.

**Injection point:** B - modify `cfg` before `run_simulation`.

```python
from src import faults

cfg_faulty = faults.open_string(cfg, strings_lost=2)
ac = run_simulation(cfg_faulty, weather_df)
```

This reduces `strings` by `strings_lost`. The ModelChain then models a smaller system from the start.

---

## Module degradation

Panels age and lose output capacity over time. The dominant effect is a reduction in photocurrent (`I_L_ref`). Jordan & Kurtz (2013) report a median Pmax loss of 0.5%/year.

**Injection point:** B - `degradation_timeseries()` splits `weather_df` into monthly chunks and returns `[(chunk, params), ...]`. `Simulation.simulate()` iterates over these, setting `module_parameters` per chunk before each `ModelChain.run_model()` call.

```python
chunks = faults.degradation_timeseries(weather_df, module_params, initial_years=5)
for chunk_weather, chunk_params in chunks:
    sys.array.module_parameters = chunk_params
    results = sys.run_model(chunk_weather)
```

`degradation()` is the underlying helper and can also be used standalone to set a fixed degradation state.

---

## PID (Potential Induced Degradation)

High voltage stress between the cell and the grounded module frame drives leakage currents through the encapsulant. This degrades the cell's shunt resistance and reduces photocurrent. PID can cause 50–80% power loss in severe cases, develops much faster than normal aging, and is partially reversible overnight when the string voltage reverses relative to ground.

The power curve signature is distinct from normal degradation: `R_sh_ref` (shunt resistance) collapses hard, which shows up as a drooping IV curve before Vmp and a fill factor loss that gets more pronounced at high irradiance. Normal degradation barely touches shunt resistance.

**Injection point:** B - apply before simulation, same pattern as degradation. `pid()` returns modified params; set `sys.array.module_parameters` before calling `run_model()`.

```python
pid_params = faults.pid(sys.array.module_parameters, severity=0.5)
sys.array.module_parameters = pid_params
results = sys.run_model(weather_df)
```

`severity` ranges from 0 (healthy) to 1 (fully degraded). Values at severity=1: 93% R_sh_ref collapse, 5% I_L_ref drop. See sources in the implemented functions table.

TODO: not yet wired into Simulation.py.

---

## Inverter fault
The inverter operates at reduced efficiency, MPPT is not tracking correctly, the unit is overheating, or it has partially shut down.

**In pvlib:** No support, scale AC output after simulation.

**Injection point:** C - scale `ac` after `run_simulation`.

```python
from faults import inverter_fault

ac = run_simulation(cfg, weather_df)
ac_faulty = inverter_fault(ac, efficiency_loss=0.3)  # inverter delivers 70% of normal output
```

---

## Wiring / connection loss

Added resistance due to loose or corroded connectors, that was not accounted for in the baseline `system_loss_fraction`. This shows up as an additional flat power loss.

**In pvlib:** No support, scale AC output after simulation.

**Injection point:** C - scale `ac` after `run_simulation`.

```python
from faults import wiring_loss

ac = run_simulation(cfg, weather_df)
ac_faulty = wiring_loss(ac, resistance_factor=0.05)  # 5% extra loss
```

TODO: not yet implemented.

---

## Implemented functions

| Function | Source | What it touches | Scientific Basis & Key Numbers | Links |
| :--- | :--- | :--- | :--- | :--- |
| `soiling_kimber()` | Kimber 2006 | scales GHI/DHI/DNI in `weather_df` | 0.15% daily loss; 6mm rain threshold for cleaning; 14-day grace period. | [PVPMC](https://pvpmc.sandia.gov/modeling-guide/1-weather-design-inputs/shading-soiling-and-reflection-losses/soiling-losses/kimber-soiling-model/) |
| `degradation()` | Jordan & Kurtz 2013 | reduces `I_L_ref` by 0.5%/year | 0.5%/year median Pmax loss, 80% can be mapped to Photocurrent. We map 100% for simplicity. | [Jordan & Kurtz (2013)](https://docs.nrel.gov/docs/fy12osti/51664.pdf) / [PVsyst](https://www.pvsyst.com/help-pvsyst7/pvmodule_degradation.htm) |
| `pid()` | Mahmood 2026 / Hasan 2022 | collapses `R_sh_ref` by 94.3%, minor `I_L_ref` hit by 5% | Experimental 94.3% collapse in Shunt Resistance (25.41 $\Omega$ to 1.435 $\Omega$). Photocurrent drop by 5%. | [Mahmood et al. (2026)](https://doi.org/10.1051/epjpv/2025028) |
| `open_string()` | Sabbaghpur Arani 2016 | reduces `strings`: `strings` - `strings_lost` | Linear reduction in total array current capacity when strings are disconnected. | [Sabbaghpur Arani (2016)](https://onlinelibrary.wiley.com/doi/10.1155/2016/8712960) |
| `shading_string()` | - | scale irradiance for a specific array | 50% (for example) reduction in GHI/DHI/DNI to simulate a shaded parallel branch. | - |
| `degradation_timeseries()` | Jordan & Kurtz 2013 | splits `weather_df` into chunks, applies time-varying degradation to each | Builds on `degradation()`: computes elapsed years per chunk and applies annual rate incrementally. | [Jordan & Kurtz (2013)](https://docs.nrel.gov/docs/fy12osti/51664.pdf) |
| `inverter_fault()` | - | scales AC output by `(1 - efficiency_loss)` | - | - |
