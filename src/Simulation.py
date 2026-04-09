import pandas as pd
from src import WeatherModel, PvSystem
from src import faults
import matplotlib.pyplot as plt

class Simulation():
    def __init__(self, systems, weather_model: WeatherModel.WeatherModel, story):
        self.systems = {}
        for id, sys in systems.items():
            self.systems[id] = PvSystem.PvSystem(sys)
        self.story                      = story
        self.weather_model              = weather_model
        self.weather                    = {}
        self.weather_with_anomalies     = {}
        self.output                     = {}

    def fetchWeather(self, sys):
        weather = self.weather_model.request_historical(sys.latitude, sys.longitude, self.story["timeframe"]["start"], self.story["timeframe"]["end"])
        return weather.tz_convert(sys.timezone)
    
    def applyAnomalies(self,weather_df):
        
        #SOILING LOSSES
        df=faults.soiling_kimber(weather_df)

        #SNOW COVERAGE LOSSES
        # df=snow(.)

        return df


    def set_timezone(self, timestamp, timezone):
        ts = pd.Timestamp(timestamp)
        return ts.tz_localize(timezone) if ts.tzinfo is None else ts.tz_convert(timezone)
    
    def apply_point_a(self, weather_df, fault_list):
        df = weather_df.copy()
        for f in fault_list:
            if f["type"] == "soiling":
                df = faults.soiling_kimber(df, **f.get("params", {}))
            # SNOW COVERAGE LOSSES
            # if f["type"] == "snow"
            # df = faults.snow(df, ...)
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

            strings = original_strings - active.get("open_string", {}).get("strings_lost", 0)
            params = original_params.copy()

            if "degradation" in active:
                t_offset = (chunk.index[0] - sim_start).total_seconds() / (365.25 * 24 * 3600)
                params = faults.degradation(
                    params,
                    years=active["degradation"].get("initial_years", 0) + t_offset,
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
    
    def apply_point_c(self, ac, fault_list):
        print(f"[C] fault_list: {[f['type'] for f in fault_list]}")
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
                    print(f"[C] inverter_fault applied to window {window_start} - {window_end} ({mask.sum()} timesteps)")
                    ac = ac.copy()
                    ac[mask] = faults.inverter_fault(ac[mask], **params)
                else:
                    print(f"[C] inverter_fault applied to whole series ({len(ac)} timesteps)")
                    ac = faults.inverter_fault(ac, **params)

            #? can add more point c fault types
        return ac

    def simulate_chunked(self, sys, chunk):
        # chunk[0]: weather data
        # chunk[1]: module parameters
        
        sys.array.module_parameters=chunk[1]

        results=sys.run_model(chunk[0])

        return results.ac

    def simulate(self, sys, weather):

        out_arr=[]
        #ENTRY POINT B
        chunks=faults.degradation_timeseries(weather, sys.array.module_parameters)
        for chunk in chunks:
                out_arr.append(self.simulate_chunked(sys, chunk))
        out=pd.concat(out_arr)
        return out


    def run(self):
        for id, sys in self.systems.items():
            # FETCH WEATHER DATA FOR EACH SYSTEM
            self.weather[id]=self.fetchWeather(sys)
            # ENTRY POINT A FOR faults AFFECTING WEATHER DATA
            self.weather_with_anomalies[id]=self.applyAnomalies(self.weather[id])
            out=self.simulate(sys,self.weather_with_anomalies[id])
            self.output[id]=out
        

    #  new pipeline when apply functions are done:
    def run_new(self):
        for id, sys in self.systems.items():
            fault_list = self.story.get("faults", {}).get(id, [])
    
            # featch weather system
            self.weather[id] = self.fetchWeather(sys)
    
            # Injection Point A: weather modifications
            self.weather_with_anomalies[id] = self.apply_point_a(self.weather[id], fault_list)
    
            # Injection Point B: module param modifications + simulation
            ac = self.apply_point_b(sys, self.weather_with_anomalies[id], fault_list)
    
            # Injection Point C: AC output modifications
            self.output[id] = self.apply_point_c(ac, fault_list)

    def plot_id(self, id):
        plt.figure()
        plt.title("Output power of System "+id)
        plt.xlabel("Time")
        plt.ylabel("Output Power (kW)")
        plt.plot(self.output[id])
        plt.show()

            



