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

            



