"""
app.py
------
Flask backend for the Weather-Plant Success Simulator.

Routes:
  GET  /                       -> main UI
  GET  /api/plants             -> list all plant profiles
  POST /api/plants             -> create a new plant profile
  PUT  /api/plants/<id>        -> update an existing plant profile
  DELETE /api/plants/<id>      -> delete a plant profile
  GET  /api/weather?location=  -> fetch real-time + 7-day forecast weather
  POST /api/simulate           -> run the physics/biology simulation
                                   body: { "plant_id": "...", "location": "..." }
                                   OR    { "plant_id": "...", "weather": {...} }
"""

import json
import os
from flask import Flask, jsonify, request, render_template

from weather_service import fetch_weather, WeatherError
from simulation import simulate_plant

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLANTS_FILE = os.path.join(BASE_DIR, "plants.json")

app = Flask(__name__)


# ---------------------------------------------------------------- helpers
def load_plants():
    with open(PLANTS_FILE, "r") as f:
        return json.load(f)


def save_plants(plants):
    with open(PLANTS_FILE, "w") as f:
        json.dump(plants, f, indent=2)


REQUIRED_PLANT_FIELDS = [
    "name", "temp_min", "temp_low", "temp_high", "temp_max",
    "humidity_min", "humidity_low", "humidity_high", "humidity_max",
    "sunlight_min", "sunlight_low", "sunlight_high", "sunlight_max",
    "rainfall_min", "rainfall_low", "rainfall_high", "rainfall_max",
    "wind_min", "wind_low", "wind_high", "wind_max",
    "leaf_absorptivity", "soil_water_capacity",
]


def validate_plant(payload):
    missing = [f for f in REQUIRED_PLANT_FIELDS if f not in payload]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"
    return None


# ---------------------------------------------------------------- pages
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------- plant CRUD
@app.route("/api/plants", methods=["GET"])
def get_plants():
    return jsonify(load_plants())


@app.route("/api/plants", methods=["POST"])
def create_plant():
    payload = request.get_json(force=True)
    error = validate_plant(payload)
    if error:
        return jsonify({"error": error}), 400

    plants = load_plants()
    plant_id = payload.get("id") or payload["name"].strip().lower().replace(" ", "_")
    payload["id"] = plant_id
    payload.setdefault("icon", "🌱")
    payload.setdefault("description", "")
    plants[plant_id] = payload
    save_plants(plants)
    return jsonify(payload), 201


@app.route("/api/plants/<plant_id>", methods=["PUT"])
def update_plant(plant_id):
    plants = load_plants()
    if plant_id not in plants:
        return jsonify({"error": "Plant not found"}), 404
    payload = request.get_json(force=True)
    error = validate_plant(payload)
    if error:
        return jsonify({"error": error}), 400
    payload["id"] = plant_id
    payload.setdefault("icon", plants[plant_id].get("icon", "🌱"))
    payload.setdefault("description", plants[plant_id].get("description", ""))
    plants[plant_id] = payload
    save_plants(plants)
    return jsonify(payload)


@app.route("/api/plants/<plant_id>", methods=["DELETE"])
def delete_plant(plant_id):
    plants = load_plants()
    if plant_id not in plants:
        return jsonify({"error": "Plant not found"}), 404
    del plants[plant_id]
    save_plants(plants)
    return jsonify({"deleted": plant_id})


# ---------------------------------------------------------------- weather
@app.route("/api/weather", methods=["GET"])
def get_weather():
    location = request.args.get("location", "").strip()
    if not location:
        return jsonify({"error": "Query parameter 'location' is required."}), 400
    try:
        data = fetch_weather(location)
        return jsonify(data)
    except WeatherError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Weather service failed: {e}"}), 502


# ---------------------------------------------------------------- simulate
@app.route("/api/simulate", methods=["POST"])
def simulate():
    payload = request.get_json(force=True)
    plant_id = payload.get("plant_id")
    if not plant_id:
        return jsonify({"error": "plant_id is required"}), 400

    plants = load_plants()
    plant = plants.get(plant_id)
    if not plant:
        return jsonify({"error": f"Unknown plant_id '{plant_id}'"}), 404

    weather = payload.get("weather")
    if not weather:
        location = payload.get("location", "").strip()
        if not location:
            return jsonify({"error": "Provide either 'weather' data or a 'location'."}), 400
        try:
            weather = fetch_weather(location)
        except WeatherError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            return jsonify({"error": f"Weather service failed: {e}"}), 502

    daily = weather.get("daily", [])
    if not daily:
        return jsonify({"error": "No forecast data available to simulate."}), 400

    # Fill any missing values with sane defaults so simulation never crashes
    for d in daily:
        d["temp"] = d.get("temp") if d.get("temp") is not None else 20.0
        d["humidity"] = d.get("humidity") if d.get("humidity") is not None else 50.0
        d["rainfall"] = d.get("rainfall") if d.get("rainfall") is not None else 0.0
        d["sunlight"] = d.get("sunlight") if d.get("sunlight") is not None else 6.0
        d["wind"] = d.get("wind") if d.get("wind") is not None else 10.0

    result = simulate_plant(plant, daily)
    result["location"] = weather.get("location", payload.get("location", ""))
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
