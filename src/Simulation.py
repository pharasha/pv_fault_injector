import pandas as pd
import WeatherModel,PvSystem
from Faults import *

class Simulation:
    def __init__(self, systems, weather_model: WeatherModel, story):
        self.systems=[]
        for sys in systems:
            self.systems.append(PvSystem(sys))
        self.story=story
        self.weather_model=weather_model
        self.weather={}
        self.weather_with_anomalies={}

    def fetchWeather(self,sys):
        weather=self.weather_model.request_historical(sys.latitude,sys.longitude,self.story.start,self.story.end)
        return weather
    
    def applyAnomalies(self,weather_df):
        
        #SOILING LOSSES
        df=soiling_kimber(weather_df)

        #SNOW COVERAGE LOSSES
        # df=snow(.)

        return df


    def simulate_chunked(self,sys, chunk):
        
        sys.array.module_parameters=chunk[1]

        results=sys.run_model(chunk[0])

        return results.ac

    def simulate(self, sys,weather):

        out=pd.DataFrame()
        #ENTRY POINT B
        chunks=degradation_timeseries(weather,sys.array.module_parameters)
        for chunk in chunks:
                pd.concat(out,self.simulate_chunked(self,sys, chunk))
        return out


        


    def run(self):
        for sys in self.systems:
            # FETCH WEATHER DATA FOR EACH SYSTEM
            self.weather[sys.id]=self.fetchWeather(sys)
            # ENTRY POINT A FOR FAULTS AFFECTING WEATHER DATA
            self.weather_with_anomalies[sys.id]=self.applyAnomalies(self.weather[sys.id])
            
            out=sys.simulate(sys,self.weather_with_anomalies[sys.id])
            



