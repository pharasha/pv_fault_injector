# fault injection functions

import pvlib

FAULT_LIST=["soiling","degradation","inverter_fault","pid","open_string"]
# ==========================================================
# Injection point A: modify weather_df before simulation
# ==========================================================



def soiling_kimber(weather_df, soiling_loss_rate=0.0015, cleaning_threshold=6.0,
                   max_soiling=0.30, grace_period=14):
    # Kimber (2006): rain-based soiling model where loss builds up daily and resets on rain
    # soiling_loss_rate: fraction lost per day (Kimber default: 0.15%/day)
    # cleaning_threshold: daily rain in mm needed to clean (Kimber default: 6 mm)
    # max_soiling: cap on total loss fraction
    # grace_period: days after rain where dust won't re-deposit (Kimber default: 14)
    daily_precip  = weather_df["precip"].resample("D").sum() # hourly -> daily
    soiling_ratio = pvlib.soiling.kimber(
        daily_precip,
        soiling_loss_rate=soiling_loss_rate,
        cleaning_threshold=cleaning_threshold,
        max_soiling=max_soiling,
        grace_period=grace_period,
    )
    soiling_ratio = soiling_ratio.reindex(weather_df.index, method="ffill")# daily -> hourly

    df = weather_df.copy()
    for col in ["ghi", "dhi", "dni"]:
        df[col] = df[col] * (1-soiling_ratio)
    return df


def shading_string(weather_df, shading_factor=0.5):
    # String-level partial shading uniformly reduces irradiance for an entire string.
    # To use this correctly, build a PVSystem with two array objects. 
    # Apply this modified weather_df only to the shaded array, and
    # pass the unmodified weather_df to the healthy array.
    df = weather_df.copy()
    for col in ["ghi", "dhi", "dni"]:
        df[col] = df[col] * (1 - shading_factor)
    return df



# ==========================================================
# Injection point B: modify module params or system config
# ==========================================================

def degradation(module_params, years, annual_rate=0.005):
    # Jordan & Kurtz (2013): median 0.5%/year Pmax loss
    # PVsyst internally assumes ca. 80% of that loss maps to I_L_ref reduction,
    # we will use this assumption for now
    # setting initial degradation that is already present before simulation starts
    params = module_params.copy()
    params["I_L_ref"] = params["I_L_ref"] * (1 - annual_rate * years)
    return params


def degradation_timeseries(weather_df, module_params, initial_years=0, annual_rate=0.005, freq="ME"):
    # time-varying degradation, splits weather_df into chunks, returns [(chunk, params), ...]
    # initial_years: degradation already present before simulation starts
    # freq: chunk size, "YE" yearly, "ME" monthly
    chunks = []
    for _, chunk in weather_df.resample(freq):
        if chunk.empty:
            continue
        t = (chunk.index[0] - weather_df.index[0]).days / 365.25  # years since sim start
        params = degradation(module_params, years=initial_years + t, annual_rate=annual_rate)
        chunks.append((chunk, params))
    return chunks


def pid(module_params, severity):
    # PID-s (shunting type, dominant in p-type c-Si, most common and destructive), EPJ PV 2026
    # collapses R_sh_ref and mild drop in I_L_ref
    # severity 0 → healthy, severity 1 → fully degraded
    # R_sh_ref: linear reduction, ca. 93% collapse at severity=1 Hasan et al. (2022)
    # I_L_ref: mild reduction, ca. 5% at severity=1 Mahmood et al. (2026)
    params = module_params.copy()
    params["R_sh_ref"] = params["R_sh_ref"] * (1 - 0.93 * severity)
    params["I_L_ref"]  = params["I_L_ref"]  * (1 - 0.05 * severity)
    return params


def open_string(system_config, strings_lost):
    # Sabbaghpur Arani (2016): open string removes 1/N of array current
    # modeled by reducing strings
    cfg = system_config.copy()
    cfg["strings"] = cfg["strings"] - strings_lost
    return cfg


def wiring_loss_physics(system_config, added_loss_percent=3.0):
    # TODO: should this be added?
    pass


def bridging_fault(module_params, modules_shorted=2):
    # Sabbaghpur Arani (2016) Section 6.2: Bridging/Short-circuit
    # This fault shorts out a number of modules in a string.
    # TODO: should this be added?
    pass


# ==========================================================
# Injection point C: modify AC output (post-simulation)
# ==========================================================

def inverter_fault(ac_power, efficiency_loss=0.3): 
    # efficiency_loss: 0.0 -> healthy, 0.3 -> 30% AC power loss
    return ac_power * (1 - efficiency_loss)
