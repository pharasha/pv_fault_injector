import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from pvlib.pvsystem import retrieve_sam
from src import Simulation, WeatherModel
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)


# shared setup

module_params = retrieve_sam('CECMod')['Canadian_Solar_Inc__CS6K_285M']
base_I_L  = module_params['I_L_ref']
base_R_sh = module_params['R_sh_ref']
original_strings = 2

systems = {
    'sys1': {
        'module_cec':           'Canadian_Solar_Inc__CS6K_285M',
        'inverter_cec':         'Fronius_USA__Fronius_Primo_3_8_1_208_240__208V_',
        'latitude':             47.4062,
        'longitude':            9.3046,
        'altitude_m':           670,
        'timezone':             'Europe/Zurich',
        'tilt_deg':             20,
        'azimuth_deg':          180,
        'system_loss_fraction': 0.14,
        'modules_per_string':   4,
        'strings':              original_strings,
        'real_module_count':    8,
    }
}
story = {'timeframe': {'start': '2023-01-01', 'end': '2023-03-31'}, 'faults': {}}
wm  = WeatherModel.WeatherModel()
sim = Simulation.Simulation(systems, wm, story)

# synthetic 3-month hourly weather — no API needed for get_b_segments tests
idx = pd.date_range('2023-01-01', '2023-03-31 23:00', freq='h', tz='Europe/Zurich')
weather_df = pd.DataFrame({'ghi': 0, 'dhi': 0, 'dni': 0, 'temp_air': 10, 'wind_speed': 1}, index=idx)

print(f"base I_L_ref  = {base_I_L:.6f}")
print(f"base R_sh_ref = {base_R_sh:.4f}")
print()


def params_at(segments, date):
    ts = pd.Timestamp(date, tz='Europe/Zurich')
    for chunk, params, strings in segments:
        if chunk.index[0] <= ts <= chunk.index[-1]:
            return params, strings
    raise KeyError(f"no segment covers {date}")


# test 1: degradation only
print("TEST 1: degradation only (full window, 5%/yr)")

fault_list = [{'type': 'degradation', 'params': {'annual_rate': 0.05}}]
segs = sim.get_b_segments(weather_df, fault_list, module_params, original_strings)

assert len(segs) == 3, f"FAIL: expected 3 monthly segments, got {len(segs)}"

jan_I_L = params_at(segs, '2023-01-15')[0]['I_L_ref']
feb_I_L = params_at(segs, '2023-02-15')[0]['I_L_ref']
mar_I_L = params_at(segs, '2023-03-15')[0]['I_L_ref']

print(f"  Jan I_L_ref: {jan_I_L:.6f}  (t=0, expected ~{base_I_L:.6f})")
print(f"  Feb I_L_ref: {feb_I_L:.6f}  (t~1/12)")
print(f"  Mar I_L_ref: {mar_I_L:.6f}  (t~2/12)")

assert jan_I_L == base_I_L,         "FAIL: Jan should have no degradation (t=0)"
assert jan_I_L > feb_I_L > mar_I_L, "FAIL: I_L_ref not decreasing month over month"
assert mar_I_L < base_I_L,          "FAIL: degradation not applied"
print("  -> OK\n")


# test 2: pid only (windowed)
print("TEST 2: pid only, February window, severity=0.8")

fault_list = [{'type': 'pid', 'start': '2023-02-01', 'end': '2023-02-28', 'params': {'severity': 0.8}}]
segs = sim.get_b_segments(weather_df, fault_list, module_params, original_strings)

jan_params = params_at(segs, '2023-01-15')[0]
feb_params = params_at(segs, '2023-02-15')[0]
mar_params = params_at(segs, '2023-03-15')[0]

expected_feb_R_sh = base_R_sh * (1 - 0.93 * 0.8)
expected_feb_I_L  = base_I_L  * (1 - 0.05 * 0.8)

print(f"  Jan R_sh_ref: {jan_params['R_sh_ref']:.4f}  (expected ~{base_R_sh:.4f})")
print(f"  Feb R_sh_ref: {feb_params['R_sh_ref']:.4f}  (expected ~{expected_feb_R_sh:.4f})")
print(f"  Mar R_sh_ref: {mar_params['R_sh_ref']:.4f}  (expected ~{base_R_sh:.4f})")

assert abs(jan_params['R_sh_ref'] - base_R_sh) < 1e-6,         "FAIL: Jan R_sh_ref modified outside window"
assert abs(mar_params['R_sh_ref'] - base_R_sh) < 1e-6,         "FAIL: Mar R_sh_ref modified outside window"
assert abs(feb_params['R_sh_ref'] - expected_feb_R_sh) < 1e-4, "FAIL: Feb R_sh_ref wrong"
assert abs(feb_params['I_L_ref']  - expected_feb_I_L)  < 1e-6, "FAIL: Feb I_L_ref wrong"
print("  -> OK\n")


# test 3: degradation + pid stacked
print("TEST 3: degradation (full) + pid (Feb only) stacked")

fault_list = [
    {'type': 'degradation', 'params': {'annual_rate': 0.05}},
    {'type': 'pid', 'start': '2023-02-01', 'end': '2023-02-28', 'params': {'severity': 0.8}},
]
segs = sim.get_b_segments(weather_df, fault_list, module_params, original_strings)

jan_params = params_at(segs, '2023-01-15')[0]
feb_params = params_at(segs, '2023-02-15')[0]
mar_params = params_at(segs, '2023-03-15')[0]

# R_sh_ref reduced from jan to feb by pid (0.8 * 0.93 > 0.5)
assert feb_params['R_sh_ref'] < jan_params['R_sh_ref'] * 0.5, "FAIL: R_sh_ref not collapsed in Feb"
assert jan_params['R_sh_ref'] > base_R_sh * 0.99,             "FAIL: R_sh_ref wrongly modified in Jan"
assert mar_params['R_sh_ref'] > base_R_sh * 0.99,             "FAIL: R_sh_ref wrongly modified in Mar"
assert jan_params['I_L_ref'] > feb_params['I_L_ref'],          "FAIL: Feb I_L_ref not lower than Jan"
assert feb_params['I_L_ref'] < mar_params['I_L_ref'],          "FAIL: Feb I_L_ref (pid+deg) should be below Mar (deg only)"

print(f"  Jan I_L_ref: {jan_params['I_L_ref']:.6f}")
print(f"  Feb I_L_ref: {feb_params['I_L_ref']:.6f}  <- pid+degradation")
print(f"  Mar I_L_ref: {mar_params['I_L_ref']:.6f}")
print("  -> OK\n")


# test 4: open_string
print("TEST 4: open_string (1 string lost, Feb only)")

fault_list = [{'type': 'open_string', 'start': '2023-02-01', 'end': '2023-02-28', 'params': {'strings_lost': 1}}]
segs = sim.get_b_segments(weather_df, fault_list, module_params, original_strings)

jan_strings = params_at(segs, '2023-01-15')[1]
feb_strings = params_at(segs, '2023-02-15')[1]
mar_strings = params_at(segs, '2023-03-15')[1]

print(f"  Jan strings: {jan_strings}  (expected {original_strings})")
print(f"  Feb strings: {feb_strings}  (expected {original_strings - 1})")
print(f"  Mar strings: {mar_strings}  (expected {original_strings})")

assert jan_strings == original_strings,     "FAIL: strings modified outside window in Jan"
assert feb_strings == original_strings - 1, "FAIL: strings not reduced in Feb"
assert mar_strings == original_strings,     "FAIL: strings modified outside window in Mar"
print("  -> OK\n")


# test 5: apply_point_b smoke test (requires weather API)
print("TEST 5: apply_point_b end-to-end smoke test (real weather + run_model)")

sys1    = sim.systems['sys1']
weather = sim.fetchWeather(sys1)
fault_list = [
    {'type': 'degradation', 'params': {'annual_rate': 0.05}},
    {'type': 'pid', 'start': '2023-02-01', 'end': '2023-02-28', 'params': {'severity': 0.8}},
]
ac_faulty  = sim.apply_point_b(sys1, weather, fault_list)
ac_healthy = sim.apply_point_b(sys1, weather, [])

assert isinstance(ac_faulty, pd.Series),     "FAIL: output is not a Series"
assert len(ac_faulty) == len(weather),        "FAIL: output length doesn't match weather"
assert ac_faulty.index.equals(weather.index), "FAIL: output index doesn't match weather"

feb_faulty  = ac_faulty['2023-02'].sum()
feb_healthy = ac_healthy['2023-02'].sum()
jan_faulty  = ac_faulty['2023-01'].sum()
jan_healthy = ac_healthy['2023-01'].sum()

print(f"  Jan healthy: {jan_healthy/1000:.1f} kWh  faulty: {jan_faulty/1000:.1f} kWh  (no fault active)")
print(f"  Feb healthy: {feb_healthy/1000:.1f} kWh  faulty: {feb_faulty/1000:.1f} kWh  (pid active, severity=0.8)")

assert feb_faulty < feb_healthy, "FAIL: Feb AC not lower with pid active"
assert abs(jan_faulty - jan_healthy) / max(jan_healthy, 1) < 0.01, "FAIL: Jan AC changed despite no fault"
print("  -> OK\n")

print("ALL TESTS PASSED")
