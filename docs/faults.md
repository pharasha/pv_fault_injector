# Fault Modeling

## Pipeline reference

```
fetch_weather()                →  weather_df
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
from faults import soiling_kimber

weather_faulty = soiling_kimber(
    weather_df,
    soiling_loss_rate=0.002,    # 0.2% loss per day
    cleaning_threshold=5.0,     # mm of daily rain needed to clean
    max_soiling=0.3,            # cap at 30% loss
)
ac = run_simulation(cfg, weather_faulty)
```

Internally this calls `pvlib.soiling.kimber()` on the daily rainfall totals (computed from the `precipitation` column that Open-Meteo already returns). The function returns a time series of soiling loss fractions, which is then reindexed to hourly and applied to GHI/DHI/DNI.

The `precipitation` column is already in `weather_df` from `fetch_weather()`, so no extra data is needed.

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

TODO: check if treating two strings as two seperate arrays models the mismatch correctly. Strings would operate on theire own MPP and there wouldnt be a compromise that causes a mismatch loss.

**In pvlib:** `PVSystem` accepts multiple `Array` objects, and `ModelChain.run_model()` accepts a list of weather DataFrames (one per array).

**Injection point:** B - replaces `run_simulation`.

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

**In pvlib:** No. Modify `cfg` before passing to `run_simulation`.

**Injection point:** B - modify `cfg` before `run_simulation`.

```python
from faults import open_string

cfg_faulty = open_string(cfg, strings_lost=2)
ac = run_simulation(cfg_faulty, weather_df)
```

This reduces `strings_per_inverter` by `strings_lost` and scales `real_module_count` proportionally. The ModelChain then models a smaller system from the start.

---

## Module degradation

Panels age and lose output capacity over time. 
TODO: Check all relevent effects.

WIP: The dominant effect is a reduction in photocurrent (`I_L_ref`) - the amount of current a cell produces per unit of irradiance decreases.

**In pvlib:** No dedicated degradation function. Modify the module parameters before building the system.

**Injection point:** B - modify module parameters, then build system manually (cannot go through `run_simulation` directly).

```python
from pvlib.pvsystem import retrieve_sam
from faults import degradation

# modules are read from CECMod database
modules = retrieve_sam("CECMod") # we can change later to modules.cfg
module_params = modules[cfg["module_cec"]]

degraded = degradation(module_params, years=10, annual_rate=0.005)
# degraded is a modified copy with I_L_ref reduced by 5% over 10 years
```

Use degradation function to modify module parameters before building the  `PVSystem` (instead of using the original `module_params`). This requires building the system manually, replacing `module_parameters=module` with `module_parameters=degraded`.

TODO: check the 0.5%/year rate.

---

## PID (Potential Induced Degradation)

High voltage stress between the cell and the grounded module frame drives leakage currents through the encapsulant. This degrades the cell's shunt resistance and reduces photocurrent. PID can cause 50–80% power loss in severe cases, develops much faster than normal aging, and is partially reversible overnight when the string voltage reverses relative to ground.

The power curve signature is distinct from normal degradation: `R_sh_ref` (shunt resistance) collapses hard, which shows up as a drooping IV curve before Vmp and a fill factor loss that gets more pronounced at high irradiance. Normal degradation barely touches shunt resistance.

**In pvlib:** Modify module parameters before building the system.

**Injection point:** B - modify module parameters, then build system manually.

```python
from pvlib.pvsystem import retrieve_sam
from faults import pid

modules = retrieve_sam("CECMod")
module_params = modules[cfg["module_cec"]]

pid_params = pid(module_params, severity=0.5)  # moderate PID
# Inside pid: I_L_ref reduced by eg. 50%, R_sh_ref reduced by eg. 40%
```

Pass `pid_params` as `module_parameters` when constructing the `Array` or `PVSystem`.

`severity` ranges from 0 (no effect) to 1 (complete failure).

TODO: verify that reducing I_L_ref and R_sh_ref is sufficient to model PID accurately, and find realistic severity ranges from literature.

---

## Inverter fault
The inverter operates at reduced efficiency, MPPT is not tracking correctly, the unit is overheating, or it has partially shut down.

**In pvlib:** No support, scale AC output after simulation.

**Injection point:** C - scale `ac` after `run_simulation`.

```python
from faults import inverter_fault

ac = run_simulation(cfg, weather_df)
ac_faulty = inverter_fault(ac, efficiency=0.7)  # inverter delivers 70% of normal output
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

---

## Implemented functions

| Function | Source | What it touches | Links |
|---|---|---|---|
| `soiling_kimber()` | Kimber 2006 | scales GHI/DHI/DNI in `weather_df` | [PVPMC](https://pvpmc.sandia.gov/modeling-guide/1-weather-design-inputs/shading-soiling-and-reflection-losses/soiling-losses/kimber-soiling-model/) |
| `degradation()` | Jordan & Kurtz 2013 (NREL/TP-5200-51664) | reduces `I_L_ref` by 0.5%/year | [NREL PDF](https://docs.nrel.gov/docs/fy12osti/51664.pdf) / [PVsyst degradation model](https://www.pvsyst.com/help-pvsyst7/pvmodule_degradation.htm) |
| `pid()` | EPJ PV 2026 / PMC 2022 | collapses `R_sh_ref`, minor `I_L_ref` hit | [EPJ PV 2026](https://www.epj-pv.org/articles/epjpv/full_html/2026/01/pv20250051/pv20250051.html) / [PMC 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9699168/) |
| `open_string()` | Sabbaghpur Arani 2016 / NREL 2024 | reduces `strings_per_inverter` | [Wiley 2016](https://onlinelibrary.wiley.com/doi/10.1155/2016/8712960) / [NREL 2024](https://www.osti.gov/pages/servlets/purl/2580300) |

