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
                    
            ## can add more point c fault types       
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

            



