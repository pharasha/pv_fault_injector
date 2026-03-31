import pandas as pd
from retry_requests import retry
from pvlib.pvsystem import PVSystem, Array, FixedMount, retrieve_sam
from pvlib.location import Location
from pvlib.modelchain import ModelChain

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

        


class PvSystem:
    def __init__(self, config):
        self.id                   = config["id"]
        self.latitude             = config["latitude"]
        self.longitude            = config["longitude"]
        self.altitude             = config["altitude_m"]
        self.timezone             = config["timezone"]
        self.tilt                 = config["tilt_deg"]
        self.azimuth              = config["azimuth_deg"]
        self.loss                 = config["system_loss_fraction"]
        self.modules_per_string   = config["modules_per_string"]
        self.strings_per_inverter = config["strings_per_inverter"]
        self.module_cec           = config["module_cec"]
        self.inverter_cec         = config["inverter_cec"]

    def build_system(self, module_params=None):
        # module_params: override parameters used by fault injection (degradation, PID, etc.)
        pass

    def location(self):
        pass

    def simulate(self, weather_df, module_params=None):
        pass

    def simulate_chunked(self, chunks):
        # chunks: list of (weather_df, module_params) from degradation_timeseries()
        pass




