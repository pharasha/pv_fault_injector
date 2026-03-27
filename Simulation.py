import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry


# story is a dict obtained from a json file containing the simulation window and events
# systems is an array containing all the pv systems configs

story={
    "start_date":"01/01/2024",
    "end_date":"01/01/2026",
    "anomalies": None
}

systems={
    ""
}

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
    
    def applyAnomalies(self,sys):
        return None

    def run(self):
        for sys in self.systems:
            self.weather[sys.id]=self.fetchWeather(sys)
        

# config is a dict obtained from a json file containing the pv system's for the simulation

class PvSystem:
    def __init__(self, config):
        self.id=config["id"]
        self.latitude=config["latitude"]
        self.longitude=config["longitude"]
        self.peakPower=config["peakPower"]



class WeatherModel:
    def __init__(self):
        # Setup the Open-Meteo DatabaseAPI client with cache and retry on error
        self.cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
        self.retry_session = retry(self.cache_session, retries=5, backoff_factor=0.2)
        self.openmeteo = openmeteo_requests.Client(session=self.retry_session)

    def request_historical(self, latitude, longitude, start, end) -> pd.DataFrame:
        # Make sure all required weather variables are listed here
        # The order of variables in hourly or daily is important to assign them correctly below
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start,
            "end_date": end,
            "hourly": [
                "cloud_cover", "shortwave_radiation","diffuse_radiation", "direct_normal_irradiance", "direct_radiation","temperature_2m","wind_speed_10m","precipitation","snowfall","is_day"
            ]
        }
        responses = self.openmeteo.weather_api(url, params=params)

        # Process first location. Add a for-loop for multiple locations or weather models
        response = responses[0]
        # Process hourly data. The order of variables needs to be the same as requested.
        hourly = response.Hourly()
        hourly_cloud_cover = hourly.Variables(0).ValuesAsNumpy()
        hourly_shortwave_radiation = hourly.Variables(1).ValuesAsNumpy()
        hourly_diffuse_radiation = hourly.Variables(2).ValuesAsNumpy()
        hourly_direct_normal_irradiance = hourly.Variables(3).ValuesAsNumpy()
        hourly_direct_irradiance = hourly.Variables(4).ValuesAsNumpy()
        hourly_temperature = hourly.Variables(5).ValuesAsNumpy()
        hourly_wind_speed = hourly.Variables(6).ValuesAsNumpy()
        hourly_precip = hourly.Variables(7).ValuesAsNumpy()
        hourly_snow = hourly.Variables(8).ValuesAsNumpy()
        hourly_isday = hourly.Variables(9).ValuesAsNumpy()

        hourly_data = {"date": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        )}

        hourly_data["cloud_cover"] = hourly_cloud_cover
        hourly_data["ghi"] = hourly_shortwave_radiation
        hourly_data["dhi"] = hourly_diffuse_radiation
        hourly_data["dni"] = hourly_direct_normal_irradiance
        hourly_data["direct_irradiance"] = hourly_direct_irradiance
        hourly_data["temp_air"] = hourly_temperature
        hourly_data["wind"] = hourly_wind_speed
        hourly_data["precip"] = hourly_precip
        hourly_data["snow"] = hourly_snow
        hourly_data["isday"] = hourly_isday

        hourly_dataframe = pd.DataFrame(data=hourly_data)
        hourly_dataframe.index = hourly_dataframe['date']

        hourly_dataframe = hourly_dataframe.drop('date', axis=1)

        return hourly_dataframe

