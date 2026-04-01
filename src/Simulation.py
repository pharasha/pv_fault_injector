import pandas as pd
import WeatherModel,PvSystem

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


    def simulate_chunked(self, chunks):
        # chunks: list of (weather_df, module_params) from degradation_timeseries()
        pass

    def simulate(self, weather_df):
        pass

    def run(self):
        for sys in self.systems:
            self.weather[sys.id]=self.fetchWeather(sys)



