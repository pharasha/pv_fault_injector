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

    def fetchWeather(self,sys):
        weather=self.weather_model.request_historical(sys.latitude,sys.longitude,self.story["timeframe"]["start"],self.story["timeframe"]["end"])
        return weather
    
    def applyAnomalies(self,weather_df):
        
        #SOILING LOSSES
        df=faults.soiling_kimber(weather_df)

        #SNOW COVERAGE LOSSES
        # df=snow(.)

        return df

    def apply_point_a(self, weather_df, fault_list):
        df = weather_df.copy()
        for f in fault_list:
            if f["type"] == "soiling":
                df = faults.soiling_kimber(df, **f.get("params", {}))
        return df
    
    def apply_point_b(self, module_params, fault_list):
        # Point B needs correct chunk creation. chunks can have fixed sizes in general, and dynamic
        # sizing for fault windows. E.g. if a fault window starts at t1 and ends at t2, and these timestamps
        # dont align with the fixed chunk boarders, we need to create additional chunks for the fault window.
        # 7day chunk --- 7day chunk --- 3day chunk --- fault starts on 4th day (t1) --- 4day chunk (with fault) --- ...
        # 7day chunk (with fault) --- 2day chunk (with fault) --- fault ends after 2nd day (t2) --- 5day chunk  --- 7day chunk ---
        # Or maybe even better, at the start create chunks based on all the fault start and end times, then we have no unnecessary
        # splitting at the healty times.

        # TODO NEED INDEXED DATAFRAME. MODULE_PARAMS ARE NOT INDEXED CURRENTLY.

        chunk_boarders = []
        chunk_boarders.append(module_params.index[0])
        chunk_boarders.append(module_params.index[-1])

        for f in fault_list:
            # for each fault, get start and end time. store these in a list.
            fault_start = pd.Timestamp(f["start"]) if "start" in f else None
            fault_end   = pd.Timestamp(f["end"])   if "end"   in f else None
            assert fault_start < fault_end, f"Invalid fault window for fault {f['type']}: start time {fault_start} is not before end time {fault_end}"
            chunk_boarders.append(fault_start)
            chunk_boarders.append(fault_end)
        
        # create chunks based on fault windows. if no faults, just one chunk with the whole time series
        chunks = []
        chunk_boarders = sorted(set([cb for cb in chunk_boarders if cb is not None])) # remove duplicates and sort
        for i in range(len(chunk_boarders)-1):
            chunk_start = chunk_boarders[i]
            chunk_end   = chunk_boarders[i+1]
            chunks.append(module_params[chunk_start:chunk_end])

        for chunk in chunks:
            for f in fault_list:
                if f["start"] <= chunk.index[0] and f["end"] >= chunk.index[-1]: # if fault window fully covers the chunk, apply the fault
                    if f["type"] == "degradation":
                        #! need a way to increase severity similar to what degradation_timeseries does. 
                        params = f.get("params", {}) # key value pairs
                        module_params = faults.degradation_timeseries(module_params, **params)

                    #? can add more point b fault types       
        return module_params
    
    def apply_point_c(self, ac, fault_list):
        for f in fault_list:
            if f["type"] == "inverter_fault":
                params = f.get("params", {}) # key value pairs
                # if start or end is specified, create mask and only apply inverter_fault to that window
                # otherwise apply to whole series
                if "start" in f or "end" in f:
                    window_start = pd.Timestamp(f["start"]) if "start" in f else ac.index[0]
                    window_end   = pd.Timestamp(f["end"])   if "end"   in f else ac.index[-1]
                    mask = (ac.index >= window_start) & (ac.index <= window_end) # boolean mask for the window
                    ac = ac.copy()
                    ac[mask] = faults.inverter_fault(ac[mask], **params)
                else:
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
        

    def plot_id(self, id):
        plt.figure()
        plt.title("Output power of System "+id)
        plt.xlabel("Time")
        plt.ylabel("Output Power (kW)")
        plt.plot(self.output[id])
        plt.show()

            



