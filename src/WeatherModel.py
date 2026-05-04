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

    def request_historical(self, ids,latitudes, longitudes, start, end,tz) -> dict[tuple, pd.DataFrame]:
        url = "https://historical-forecast-api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitudes,   # Pass a list, e.g. [47.3, 46.8, 47.0]
            "longitude": longitudes, # Pass a list, e.g. [8.5, 9.1, 7.4]
            "start_date": start,
            "end_date": end,
            "hourly": [
                "cloud_cover", "shortwave_radiation", "diffuse_radiation",
                "direct_normal_irradiance", "direct_radiation", "temperature_2m",
                "wind_speed_10m", "precipitation", "snowfall", "is_day"
            ],
            "models": "dwd_icon_d2"
        }

        responses = self.openmeteo.weather_api(url, params=params)

        results = {}
        for idx,response in enumerate(responses):
            hourly = response.Hourly()

            hourly_data = {
                "date": pd.date_range(
                    start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                    end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                    freq=pd.Timedelta(seconds=hourly.Interval()),
                    inclusive="left"
                ),
                "cloud_cover":        hourly.Variables(0).ValuesAsNumpy(),
                "ghi":                hourly.Variables(1).ValuesAsNumpy(),
                "dhi":                hourly.Variables(2).ValuesAsNumpy(),
                "dni":                hourly.Variables(3).ValuesAsNumpy(),
                "direct_irradiance":  hourly.Variables(4).ValuesAsNumpy(),
                "temp_air":           hourly.Variables(5).ValuesAsNumpy(),
                "wind_speed":         hourly.Variables(6).ValuesAsNumpy(),
                "precip":             hourly.Variables(7).ValuesAsNumpy(),
                "snow":               hourly.Variables(8).ValuesAsNumpy(),
                "isday":              hourly.Variables(9).ValuesAsNumpy(),
            }

            df = pd.DataFrame(data=hourly_data).set_index("date")

            lat = response.Latitude()
            lon = response.Longitude()
            results[ids[idx]] = df.tz_convert(tz[idx])

        return results