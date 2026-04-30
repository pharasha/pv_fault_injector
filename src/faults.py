# fault injection functions

import pandas as pd
import pvlib
import numpy as np

FAULT_LIST=["soiling","degradation","inverter_fault","pid","open_string","mask_shading", "snowfall_dc_loss"]
# ==========================================================
# Injection point A: modify weather_df before simulation
# ==========================================================



def soiling_kimber(weather_df, soiling_loss_rate=0.15, cleaning_threshold=6.0,
                   max_soiling=0.30, grace_period=14):
    soiling_loss_rate = float(soiling_loss_rate) / 100   # GUI stores %/day (e.g. 0.1 = 0.1%/day), pvlib expects fraction/day
    cleaning_threshold = float(cleaning_threshold) * 100  # GUI stores fraction 0-1 (e.g. 0.05 → 5mm), pvlib expects mm
    max_soiling = float(max_soiling)
    grace_period = int(grace_period)
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


def mask_shading(weather_df, location, az_range, el_range,
                  affected_fraction, opacity, ramp):
    az_range = [float(v) for v in az_range]
    el_range = [float(v) for v in el_range]
    affected_fraction = float(affected_fraction)
    opacity = float(opacity)
    ramp = float(ramp)
    # Array-level partial shading applies a shading factor to the entire array based on sun position.
    # az_range and el_range define the sun positions where shading occurs, with ramp controlling the speed at which shading increases.
    df = weather_df.copy()
    idx = df.index

    sun_position = pvlib.solarposition.get_solarposition(idx, location.latitude, location.longitude)
    
    sun_az = sun_position["azimuth"]
    sun_el = sun_position["apparent_elevation"]

    score_az = trapezoid_score(sun_az, *az_range, ramp)
    score_el = trapezoid_score(sun_el, *el_range, ramp)
    # shading_scores = np.minimum(score_az, score_el)
    shading_scores = score_az * score_el

    loss = shading_scores * affected_fraction * opacity

    df["dni"] = df["dni"] * (1 - loss)
    df["dhi"] = df["dhi"] * (1 - loss)
    df["ghi"] = df["dhi"] + np.clip(np.cos(np.deg2rad(sun_position["apparent_zenith"])), 0, 1) * df["dni"]

    return df, pd.Series(loss, index=idx)

# helper function for shading faults
def trapezoid_score(x, x_lo, x_hi, ramp = 10):
    # ramp: transition width in degrees on each edge — score rises 0→1 from x_lo to x_lo+ramp
    x = np.asarray(x)
    if ramp <= 0:
        return ((x >= x_lo) & (x <= x_hi)).astype(float)
    left = (x - x_lo) / ramp 
    right = (x_hi - x) / ramp
    return np.clip(np.minimum(left, right), 0.0, 1.0)



# ==========================================================
# Injection point B: modify module params or system config
# ==========================================================

def degradation(module_params, years, annual_rate=0.5):
    years = float(years)
    annual_rate = float(annual_rate) / 100  # GUI stores %/year (e.g. 0.5 = 0.5%/year)
    # Jordan & Kurtz (2013): median 0.5%/year Pmax loss
    # PVsyst internally assumes ca. 80% of that loss maps to I_L_ref reduction,
    # we will use this assumption for now
    # setting initial degradation that is already present before simulation starts
    params = module_params.copy()
    params["I_L_ref"] = params["I_L_ref"] * (1 - annual_rate * years)
    return params


def pid(module_params, severity):
    severity = float(severity)
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



# ==========================================================
# Injection point C: modify AC output (post-simulation)
# ==========================================================

def inverter_fault(ac_power, efficiency_loss=0.3):
    efficiency_loss = float(efficiency_loss)
    # efficiency_loss: 0.0 -> healthy, 0.3 -> 30% AC power loss
    return ac_power * (1 - efficiency_loss)

def snowfall_dc_loss(ac_power, weather_df, sys):
    # Returns DC level loss caused by snowfall on modules.
    # Uses a function which calculates the portion of the panel covered by snow (since it can slide).
    # Then uses this portion to calculate DC loss portion. 
    snow_cover_ratio = pvlib.snow.coverage_nrel(weather_df["snow"], 
                                              weather_df["ghi"], 
                                              weather_df["temp_air"], 
                                              sys.tilt)
    
    snow_loss_ratio = pvlib.snow.dc_loss_nrel(snow_cover_ratio,
                                            sys.strings)

    return ac_power * (1 - snow_loss_ratio)