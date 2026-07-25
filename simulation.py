"""
simulation.py
--------------
Core physics & biology model for the Weather-Plant Success Simulator.

Models implemented:
1. Leaf heat-transfer model  -> estimates leaf temperature from air temperature,
   solar heating (via sunlight hours) and convective wind cooling.
2. Water balance model       -> simulates soil moisture over multiple days using
   a simplified evaporation vs rainfall bucket model.
3. Growth/success scoring    -> trapezoidal "ideal range" fuzzy scoring per
   variable (temperature, humidity, sunlight, soil moisture, wind), combined
   into a single weighted 0-100 success score per day.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


# ----------------------------------------------------------------------
# 1. Trapezoidal "ideal range" scoring function
# ----------------------------------------------------------------------
def trapezoid_score(value: float, vmin: float, low: float, high: float, vmax: float) -> float:
    """
    Returns a 0-100 suitability score for `value` given a plant's tolerance
    envelope described by four points:

        vmin   low            high   vmax
         |------|===== 100% ====|------|
      0% ramp-up            0% ramp-down

    - Below vmin or above vmax  -> 0  (lethal / far outside tolerance)
    - Between low and high      -> 100 (ideal zone)
    - Between vmin-low or high-vmax -> linear ramp
    """
    if vmax <= vmin:
        return 0.0
    if value <= vmin or value >= vmax:
        return 0.0
    if low <= value <= high:
        return 100.0
    if value < low:
        # ramp up from vmin -> low
        if low == vmin:
            return 100.0
        return max(0.0, min(100.0, (value - vmin) / (low - vmin) * 100.0))
    # value > high, ramp down from high -> vmax
    if vmax == high:
        return 100.0
    return max(0.0, min(100.0, (vmax - value) / (vmax - high) * 100.0))


# ----------------------------------------------------------------------
# 2. Leaf heat-transfer model
# ----------------------------------------------------------------------
def leaf_temperature(air_temp_c: float, sunlight_hours: float, wind_kmh: float,
                      absorptivity: float) -> float:
    """
    Estimates leaf surface temperature from air temperature.

    Physical intuition (simplified energy balance):
      - Solar gain heats the leaf above air temperature; magnitude depends on
        how much of the day is sunlit and how absorptive the leaf surface is.
      - Wind increases convective heat loss, cooling the leaf back toward
        (or below) air temperature.

    T_leaf = T_air + solar_gain - wind_cooling

      solar_gain   = absorptivity * (sunlight_hours / 12) * SOLAR_GAIN_MAX
      wind_cooling = min(wind_kmh * WIND_COOLING_COEFF, WIND_COOLING_CAP)
    """
    SOLAR_GAIN_MAX = 7.0      # max °C a fully-absorptive leaf gains in full 12h sun
    WIND_COOLING_COEFF = 0.15  # °C cooling per km/h of wind
    WIND_COOLING_CAP = 6.0     # convective cooling saturates (boundary layer effect)

    solar_gain = absorptivity * (max(0.0, sunlight_hours) / 12.0) * SOLAR_GAIN_MAX
    wind_cooling = min(max(0.0, wind_kmh) * WIND_COOLING_COEFF, WIND_COOLING_CAP)

    return air_temp_c + solar_gain - wind_cooling


# ----------------------------------------------------------------------
# 3. Water balance model (soil moisture bucket simulation)
# ----------------------------------------------------------------------
def daily_evaporation(air_temp_c: float, humidity_pct: float, wind_kmh: float) -> float:
    """
    Simplified Penman-style evapotranspiration proxy (mm/day).
    Higher temperature & wind increase evaporation; higher humidity suppresses it.
    """
    BASE_EVAP = 4.0  # mm/day baseline at 25C, 50% humidity, no wind
    temp_factor = max(0.1, air_temp_c / 25.0)
    humidity_factor = max(0.1, 1.0 - (humidity_pct / 100.0))
    wind_factor = 1.0 + (max(0.0, wind_kmh) / 25.0)
    return BASE_EVAP * temp_factor * humidity_factor * wind_factor


def simulate_soil_moisture(daily_weather: List[Dict[str, Any]], soil_capacity: float,
                            start_fraction: float = 0.5) -> List[float]:
    """
    Runs a day-by-day bucket water-balance simulation.
    Returns list of soil moisture values (mm) held in the root zone, one per day,
    clamped between 0 and soil_capacity.
    """
    moisture = soil_capacity * start_fraction
    results = []
    for day in daily_weather:
        evap = daily_evaporation(day["temp"], day["humidity"], day["wind"])
        rainfall = day.get("rainfall", 0.0)
        moisture = moisture + rainfall - evap
        moisture = max(0.0, min(soil_capacity, moisture))
        results.append(round(moisture, 2))
    return results


# ----------------------------------------------------------------------
# 4. Full daily simulation combining all models
# ----------------------------------------------------------------------
WEIGHTS = {
    "temperature": 0.30,
    "water": 0.25,
    "sunlight": 0.20,
    "humidity": 0.15,
    "wind": 0.10,
}


def simulate_plant(plant: Dict[str, Any], daily_weather: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    plant: plant profile dict (see plants.json)
    daily_weather: list of dicts, each with keys:
        date, temp (C, avg/representative), humidity (%), rainfall (mm),
        sunlight (hours), wind (km/h)

    Returns a dict with per-day breakdown and overall summary.
    """
    soil_capacity = plant.get("soil_water_capacity", 50)
    soil_moisture_series = simulate_soil_moisture(daily_weather, soil_capacity)

    days_out = []
    for day, soil_moisture in zip(daily_weather, soil_moisture_series):
        leaf_t = leaf_temperature(
            day["temp"], day["sunlight"], day["wind"], plant.get("leaf_absorptivity", 0.6)
        )

        score_temp = trapezoid_score(
            leaf_t, plant["temp_min"], plant["temp_low"], plant["temp_high"], plant["temp_max"]
        )
        score_humidity = trapezoid_score(
            day["humidity"], plant["humidity_min"], plant["humidity_low"],
            plant["humidity_high"], plant["humidity_max"]
        )
        score_sun = trapezoid_score(
            day["sunlight"], plant["sunlight_min"], plant["sunlight_low"],
            plant["sunlight_high"], plant["sunlight_max"]
        )
        # map soil moisture (mm held) back onto the plant's rainfall/water preference scale
        # by expressing it as a percentage of soil capacity, then comparing to the plant's
        # rainfall_* thresholds expressed the same way.
        water_pct = (soil_moisture / soil_capacity * 100.0) if soil_capacity > 0 else 0
        rain_max_ref = max(plant["rainfall_max"], 1)
        score_water = trapezoid_score(
            (water_pct / 100.0) * rain_max_ref,
            plant["rainfall_min"], plant["rainfall_low"], plant["rainfall_high"], plant["rainfall_max"]
        )
        score_wind = trapezoid_score(
            day["wind"], plant["wind_min"], plant["wind_low"], plant["wind_high"], plant["wind_max"]
        )

        overall = (
            score_temp * WEIGHTS["temperature"] +
            score_water * WEIGHTS["water"] +
            score_sun * WEIGHTS["sunlight"] +
            score_humidity * WEIGHTS["humidity"] +
            score_wind * WEIGHTS["wind"]
        )

        days_out.append({
            "date": day.get("date"),
            "air_temp": round(day["temp"], 1),
            "leaf_temp": round(leaf_t, 1),
            "humidity": round(day["humidity"], 1),
            "sunlight": round(day["sunlight"], 1),
            "wind": round(day["wind"], 1),
            "rainfall": round(day.get("rainfall", 0.0), 1),
            "soil_moisture": soil_moisture,
            "soil_moisture_pct": round(water_pct, 1),
            "scores": {
                "temperature": round(score_temp, 1),
                "humidity": round(score_humidity, 1),
                "sunlight": round(score_sun, 1),
                "water": round(score_water, 1),
                "wind": round(score_wind, 1),
            },
            "success_score": round(overall, 1),
            "status": status_label(overall),
        })

    avg_score = sum(d["success_score"] for d in days_out) / len(days_out) if days_out else 0
    return {
        "plant": plant["name"],
        "icon": plant.get("icon", "🌱"),
        "days": days_out,
        "average_score": round(avg_score, 1),
        "overall_status": status_label(avg_score),
        "limiting_factor": find_limiting_factor(days_out),
    }


def status_label(score: float) -> str:
    if score >= 80:
        return "Thriving"
    if score >= 60:
        return "Healthy"
    if score >= 40:
        return "Stressed"
    if score >= 20:
        return "Struggling"
    return "Critical"


def find_limiting_factor(days_out: List[Dict[str, Any]]) -> str:
    """Identifies which environmental factor most consistently limits growth (lowest avg score)."""
    if not days_out:
        return "unknown"
    totals = {"temperature": 0.0, "humidity": 0.0, "sunlight": 0.0, "water": 0.0, "wind": 0.0}
    for d in days_out:
        for k, v in d["scores"].items():
            totals[k] += v
    n = len(days_out)
    avgs = {k: v / n for k, v in totals.items()}
    return min(avgs, key=avgs.get)
