import pandas as pd
import WeatherModel,PvSystem
import pvlib as pvl

class Simulation:
    def __init__(self, systems, weather_model: WeatherModel, story):
        self.systems=[]
        for sys in systems:
            self.systems.append(PvSystem(sys))
        self.story=story
        self.weather_model=weather_model
        self.weather={}

    def fetchWeather(self,sys):
        weather=self.weather_model.request_historical(sys.latitude,sys.longitude,self.story.start,self.story.end)
        return weather
    
    def applyAnomalies(self,weather):
        # ENTRY POINT A
        
        #SOILING LOSSES
        soiling_loss=pvl.soiling.kimber(weather, cleaning_threshold=6, soiling_loss_rate=0.0015, grace_period=14, max_soiling=0.3, manual_wash_dates=None, initial_soiling=0, rain_accum_period=24)
        
        #SNOW COVERAGE LOSSES

        


        return None

    def run(self,applyFaults=True,save=False):
        while sim_id!="":
            sim_id=input("Enter a simulation ID:")

        for sys in self.systems:
            self.weather[sys.id]=

        # ENTRY POINT A
        weather_loss=[self.applyAnomalies(weather) for weather in self.weather]

        # Save Simulation Data
        if save:
            for idx,data in self.weather:
                data.to_csv("./data/output/"+sim_id+"/"+idx+"/weather.csv")
                #.to_csv("./data/output/"+sim_id+"/"+idx+"/weather.csv") LEFT FOR POWER OUTPUT DATA
        




