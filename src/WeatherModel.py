import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry

class WeatherModel():
    def __init__(self):
        # Setup the Open-Meteo DatabaseAPI client with cache and retry on error
        self.cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
        self.retry_session = retry(self.cache_session, retries=5, backoff_factor=0.2)
        self.openmeteo = openmeteo_requests.Client(session=self.retry_session)

    def request_historical(self, latitude, longitude, start, end) -> pd.DataFrame:
        # Make sure all required weather variables are listed here
        # The order of variables in hourly or daily is important to assign them correctly below
        url = "https://historical-forecast-api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start,
            "end_date": end,
            "hourly": [
                "cloud_cover", "shortwave_radiation","diffuse_radiation", "direct_normal_irradiance", "direct_radiation","temperature_2m","wind_speed_10m","precipitation","snowfall","is_day"
            ],
            "models":"meteoswiss_icon_ch1"
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
        hourly_data["wind_speed"] = hourly_wind_speed
        hourly_data["precip"] = hourly_precip
        hourly_data["snow"] = hourly_snow
        hourly_data["isday"] = hourly_isday

        hourly_dataframe = pd.DataFrame(data=hourly_data)
        hourly_dataframe.index = hourly_dataframe['date']

        hourly_dataframe = hourly_dataframe.drop('date', axis=1)

        return hourly_dataframe