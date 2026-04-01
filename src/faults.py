# fault injection functions
# sources: Kimber 2006, Jordan & Kurtz 2013 (NREL/TP-5200-51664), EPJ PV 2026, Sabbaghpur Arani 2016

import pvlib

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


