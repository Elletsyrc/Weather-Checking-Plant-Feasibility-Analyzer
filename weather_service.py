"""
weather_service.py
-------------------
Fetches real-time + 7-day forecast weather data.

Default provider: Open-Meteo (https://open-meteo.com) - free, no API key required.
Optional provider: OpenWeatherMap, if the user sets an OPENWEATHERMAP_API_KEY
environment variable (see README.md for instructions).
"""

import os
import requests

OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OWM_GEOCODE_URL = "https://api.openweathermap.org/geo/1.0/direct"
OWM_ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"

OWM_API_KEY = os.environ.get("OPENWEATHERMAP_API_KEY", "").strip()


class WeatherError(Exception):
    pass


def geocode_location(location_name: str):
    """Resolve a free-text location name into (lat, lon, display_name)."""
    if OWM_API_KEY:
        resp = requests.get(OWM_GEOCODE_URL, params={
            "q": location_name, "limit": 1, "appid": OWM_API_KEY
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            raise WeatherError(f"Location '{location_name}' not found.")
        item = data[0]
        display = f"{item.get('name')}, {item.get('country', '')}".strip(", ")
        return item["lat"], item["lon"], display

    resp = requests.get(OPEN_METEO_GEOCODE_URL, params={
        "name": location_name, "count": 1, "language": "en", "format": "json"
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results")
    if not results:
        raise WeatherError(f"Location '{location_name}' not found.")
    item = results[0]
    display = f"{item.get('name')}, {item.get('country', '')}".strip(", ")
    return item["latitude"], item["longitude"], display


def fetch_weather(location_name: str):
    """
    Returns a dict:
      {
        "location": "City, Country",
        "current": {temp, humidity, rainfall, sunlight, wind},
        "daily": [ {date, temp, humidity, rainfall, sunlight, wind}, ... 7 entries ]
      }
    """
    lat, lon, display_name = geocode_location(location_name)

    if OWM_API_KEY:
        return _fetch_owm(lat, lon, display_name)
    return _fetch_open_meteo(lat, lon, display_name)


def _fetch_open_meteo(lat, lon, display_name):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "daily": ("temperature_2m_max,temperature_2m_min,precipitation_sum,"
                  "wind_speed_10m_max,sunshine_duration,relative_humidity_2m_mean"),
        "timezone": "auto",
        "forecast_days": 7,
        "wind_speed_unit": "kmh",
    }
    resp = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    cur = data.get("current", {})
    current = {
        "temp": cur.get("temperature_2m"),
        "humidity": cur.get("relative_humidity_2m"),
        "rainfall": cur.get("precipitation", 0.0),
        "sunlight": None,  # not available for "current"; daily sunshine used instead
        "wind": cur.get("wind_speed_10m"),
    }

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])
    wind = daily.get("wind_speed_10m_max", [])
    sunshine_sec = daily.get("sunshine_duration", [])
    humidity_mean = daily.get("relative_humidity_2m_mean", [])

    days = []
    for i, date in enumerate(dates):
        avg_temp = (tmax[i] + tmin[i]) / 2.0 if i < len(tmax) and i < len(tmin) else None
        sunlight_hours = (sunshine_sec[i] / 3600.0) if i < len(sunshine_sec) and sunshine_sec[i] is not None else None
        days.append({
            "date": date,
            "temp": avg_temp,
            "humidity": humidity_mean[i] if i < len(humidity_mean) else None,
            "rainfall": precip[i] if i < len(precip) else 0.0,
            "sunlight": sunlight_hours,
            "wind": wind[i] if i < len(wind) else None,
        })

    # backfill current sunlight from day 0's forecast if missing
    if current["sunlight"] is None and days:
        current["sunlight"] = days[0]["sunlight"]

    return {"location": display_name, "current": current, "daily": days}


def _fetch_owm(lat, lon, display_name):
    resp = requests.get(OWM_ONECALL_URL, params={
        "lat": lat, "lon": lon, "appid": OWM_API_KEY, "units": "metric",
        "exclude": "minutely,alerts"
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    cur = data.get("current", {})
    current = {
        "temp": cur.get("temp"),
        "humidity": cur.get("humidity"),
        "rainfall": cur.get("rain", {}).get("1h", 0.0) if isinstance(cur.get("rain"), dict) else 0.0,
        "sunlight": None,
        "wind": (cur.get("wind_speed", 0) * 3.6),  # m/s -> km/h
    }

    days = []
    for d in data.get("daily", [])[:7]:
        import datetime
        date_str = datetime.datetime.utcfromtimestamp(d["dt"]).strftime("%Y-%m-%d")
        sunrise, sunset = d.get("sunrise"), d.get("sunset")
        daylight_hours = (sunset - sunrise) / 3600.0 if sunrise and sunset else 10.0
        cloud_factor = 1.0 - (d.get("clouds", 50) / 100.0) * 0.7
        sunlight_hours = max(0.5, daylight_hours * cloud_factor)
        days.append({
            "date": date_str,
            "temp": d.get("temp", {}).get("day"),
            "humidity": d.get("humidity"),
            "rainfall": d.get("rain", 0.0) if isinstance(d.get("rain"), (int, float)) else 0.0,
            "sunlight": sunlight_hours,
            "wind": d.get("wind_speed", 0) * 3.6,
        })

    if current["sunlight"] is None and days:
        current["sunlight"] = days[0]["sunlight"]

    return {"location": display_name, "current": current, "daily": days}
