import pandas as pd
from src import WeatherModel, PvSystem
from src import faults
import matplotlib.pyplot as plt
from prompt_toolkit import prompt
from datetime import datetime
import os

KNOWN_FAULT_TYPES = sorted(
    ["soiling", "mask_shading", "degradation", "pid", "open_string", "inverter_fault", "snow"],
    key=len, reverse=True,
)

class Simulation():
    def __init__(self, community, weather_model: WeatherModel.WeatherModel):
        self.community                  = community
        self.weather_model              = weather_model
        self.systems                    = {}
        self.system_data                = {}
        for i, sys_data in enumerate(community["systems"]):
            sid = sys_data["name"]
            self.systems[sid]           = PvSystem.PvSystem(sys_data["props"])
            self.system_data[sid]       = sys_data
        self.weather                    = {}
        self.weather_with_anomalies     = {}
        self.mask_shading_loss          = {}
        self.output                     = {}
        self.output_healthy             = {}
        self.timezone                   = { id: sys.timezone for id, sys in self.systems.items() }

    def fetchWeather(self, sys, id):
        start = self.community["start_date"]
        end   = self.community["end_date"]
        weather = self.weather_model.request_historical(sys.latitude, sys.longitude, start, end)
        return weather.tz_convert(sys.timezone)

    def set_timezone(self, timestamp, timezone):
        ts = pd.Timestamp(timestamp)
        return ts.tz_localize(timezone) if ts.tzinfo is None else ts.tz_convert(timezone)
    
    def build_fault_list(self, events):
        fault_list = []
        for fault_type, cfg in events["permanent"].items():
            if cfg["enabled"]:
                fault_list.append({"type": fault_type, "params": cfg.get("params", {})})
        temporary = events.get("temporary") or {}
        for key, event in temporary.items():
            fault_type = next((ft for ft in KNOWN_FAULT_TYPES if key.startswith(ft)), key)
            fault_list.append({
                "type": fault_type,
                "start": event["start"],
                "end": event["end"],
                "params": event.get("params", {})
            })
        return fault_list

    def apply_point_a(self, id, weather_df, fault_list, location):
        df = weather_df.copy()
        for f in fault_list:
            if f["type"] == "soiling":
                df = faults.soiling_kimber(df, **f.get("params", {}))
            if f["type"] == "mask_shading":
                df, self.mask_shading_loss[id] = faults.mask_shading(df, location, **f.get("params", {}))
        return df

    # ------------------------------------------------------
    # pvlib only accepts static params, so the timeseries is split into chunks where each 
    # chunk has constant params. boundaries come from fault window (start & end times) and 
    # from degradation's monthly resampling.
    # ------------------------------------------------------

    def get_b_segments(self, weather_df, b_faults, original_params, original_strings):
        # splits weather_df into segments with constant params, ready for run_model.
        # boundaries come from fault windows (start/end) and degradation's resampling freq.
        # returns [(chunk, module_params, strings), ...] with all params pre-computed.
        if not b_faults:
            return [(weather_df, original_params.copy(), original_strings)]

        tz = weather_df.index.tz
        sim_start = weather_df.index[0]
        sim_end = weather_df.index[-1] + pd.Timedelta(hours=1)

        chunk_borders = {sim_start, sim_end}
        for f in b_faults:
            for k in ("start", "end"):
                if k in f:
                    chunk_borders.add(self.set_timezone(f[k], tz))

        deg_fault = next((f for f in b_faults if f["type"] == "degradation"), None)
        if deg_fault:
            freq = deg_fault.get("params", {}).get("freq", "ME")
            for _, period in weather_df.resample(freq):
                if not period.empty:
                    chunk_borders.add(period.index[0])

        chunk_borders = sorted(chunk_borders)

        segments = []
        for i in range(len(chunk_borders) - 1):
            chunk_start, chunk_end = chunk_borders[i], chunk_borders[i + 1]
            chunk = weather_df[(weather_df.index >= chunk_start) & (weather_df.index < chunk_end)]
            if chunk.empty:
                continue

            active = {}
            for f in b_faults:
                f_window_start = self.set_timezone(f["start"], tz) if "start" in f else sim_start
                f_window_end   = self.set_timezone(f["end"],   tz) if "end"   in f else sim_end
                if chunk_start >= f_window_start and chunk_end <= f_window_end:
                    active[f["type"]] = f.get("params", {})

            strings = original_strings - int(active.get("open_string", {}).get("strings_lost", 0))
            params = original_params.copy()

            if "degradation" in active:
                t_offset = (chunk.index[0] - sim_start).total_seconds() / (365.25 * 24 * 3600)
                params = faults.degradation(
                    params,
                    years=float(active["degradation"].get("initial_years", 0)) + t_offset,
                    annual_rate=active["degradation"].get("annual_rate", 0.005),
                )

            if "pid" in active:
                params = faults.pid(params, **active["pid"])

            segments.append((chunk, params, strings))

        return segments

    def apply_point_b(self, sys, weather_df, fault_list):
        b_types = {"degradation", "pid", "open_string"}
        b_faults = [f for f in fault_list if f["type"] in b_types]

        original_params = sys.array.module_parameters.copy()
        original_strings = sys.array.strings
        segments = self.get_b_segments(weather_df, b_faults, original_params, original_strings)
        out_arr = []

        for chunk, params, strings in segments:
            sys.array.module_parameters = params
            sys.array.strings = strings
            out_arr.append(sys.run_model(chunk).ac)

        sys.array.module_parameters = original_params
        sys.array.strings = original_strings

        return pd.concat(out_arr)
    
    def apply_point_c(self, ac, fault_list,weather_df,sys):

        if any(f["type"] == "snow" for f in fault_list):
            ac = faults.snowfall_dc_loss(ac,weather_df,sys)

        tz = ac.index.tz
        for f in fault_list:
            if f["type"] == "inverter_fault":
                params = f.get("params", {})
                # if start or end is specified, create mask and only apply inverter_fault to that window
                # otherwise apply to whole series
                if "start" in f or "end" in f:
                    window_start = self.set_timezone(f["start"], tz) if "start" in f else ac.index[0]
                    window_end = self.set_timezone(f["end"],   tz) if "end"   in f else ac.index[-1]
                    mask = (ac.index >= window_start) & (ac.index <= window_end)
                    ac = ac.copy()
                    ac[mask] = faults.inverter_fault(ac[mask], **params)
                else:
                    ac = faults.inverter_fault(ac, **params)
            #? can add more point c fault types
        return ac

    #  new pipeline when apply functions are done:
    def run(self, save=True):
        for id, sys in self.systems.items():
            fault_list = self.build_fault_list(self.system_data[id]["events"])

            # featch weather system
            self.weather[id] = self.fetchWeather(sys, id)

            # Injection Point A: weather modifications
            self.weather_with_anomalies[id] = self.apply_point_a(id, self.weather[id], fault_list, sys.location)

            # Injection Point B: module param modifications + simulation
            ac = self.apply_point_b(sys, self.weather_with_anomalies[id], fault_list)

            # Injection Point C: AC output modifications
            self.output[id] = self.apply_point_c(ac, fault_list,self.weather[id],sys)

            self.output_healthy[id] =  sys.run_model(self.weather[id]).ac

        # Save the outputs
        if save:
            self.save()

    def plot_id(self, id):
        plt.figure()
        plt.title("Output power of System "+id)
        plt.xlabel("Time")
        plt.ylabel("Output Power (kW)")
        plt.plot(self.output[id])
        plt.show()

    
    def save(self):

        sim_id=self.community["name"]+"_"+datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

        meta_rows = []

        for id, sys in self.systems.items():

            # Make Flags Frame
            fault_list = self.build_fault_list(self.system_data[id]["events"])
            flag_frame = pd.DataFrame(0, index=self.weather[id].index, columns=faults.FAULT_LIST)

            for fault in fault_list:
                flag_frame.loc[fault.get("start"):fault.get("end"), fault["type"]] = 1

            fault_ratio = 1 - (self.output[id] / self.output_healthy[id])
            fault_ratio_col = fault_ratio.rename("fault_ratio")
            fault_flag = (fault_ratio >= 0.2).astype(int).rename("fault_flag")

            p_peak = sys.module['STC'] * sys.modules_per_string * sys.strings

            # Combine columns: ac power | original weather | anomaly weather | fault flags | shading loss
            all_frame = pd.concat([
                self.output[id].rename("ac_power"),
                self.output_healthy[id].rename("ac_power_healthy"),
                pd.Series(p_peak, index=self.weather[id].index, name="p_peak_w"),
                self.weather[id],
                self.weather_with_anomalies[id].add_suffix("_anomaly"),
                fault_ratio_col,
                fault_flag,
                flag_frame,
            ], axis=1)

            if id in self.mask_shading_loss:
                all_frame["mask_shading_loss"] = self.mask_shading_loss[id]

            # Create directory if it doesn't exist
            file_path = './output/'+sim_id+'/'+id+'.csv'
            directory = os.path.dirname(file_path)
            if not os.path.exists(directory):
                os.makedirs(directory)

            # Save All
            all_frame.to_csv('./output/'+sim_id+'/'+id+'.csv')

            meta_rows.append({
                "system_id":         id,
                "latitude":          sys.latitude,
                "longitude":         sys.longitude,
                "altitude_m":        sys.altitude,
                "tilt_deg":          sys.tilt,
                "azimuth_deg":       sys.azimuth,
                "modules_per_string":sys.modules_per_string,
                "strings":           sys.strings,
                "p_peak_w":          p_peak,
                "module_cec":        sys.module_cec,
                "inverter_cec":      sys.inverter_cec,
                "timezone":          sys.timezone,
                "start_date":        self.community["start_date"],
                "end_date":          self.community["end_date"],
            })

        pd.DataFrame(meta_rows).to_csv('./output/'+sim_id+'/metadata.csv', index=False)






            



