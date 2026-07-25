# Weather-Checking-Plant-Feasibility-Analyzer

A full-stack simulator that pulls **real weather data**, models **leaf heat transfer**
and **soil water balance** with simple physics equations, and scores how well a
plant will grow under current/upcoming conditions — with editable plant profiles,
charts, and an animated health icon.

## Stack
- **Backend:** Python (Flask) — weather fetching, physics/biology simulation, plant CRUD
- **Frontend:** HTML / CSS / vanilla JS — Chart.js for graphs, custom SVG for the plant icon
- **Weather source:** [Open-Meteo](https://open-meteo.com) (free, no API key needed) by
  default. OpenWeatherMap is supported as an optional swap-in.

## 1. Setup

```bash
cd weather_plant_sim
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. (Optional) Use OpenWeatherMap instead of Open-Meteo

By default no API key is needed — Open-Meteo is free and unlimited for this use case.
If you'd rather use OpenWeatherMap (e.g. for its One Call API), get a key from
https://openweathermap.org/api and set it before running:

```bash
export OPENWEATHERMAP_API_KEY="your_key_here"    # Windows: set OPENWEATHERMAP_API_KEY=your_key_here
```

## 3. Run

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

## How it works

### 1. Weather Input
`weather_service.py` geocodes a free-text location, then fetches current conditions
plus a 7-day forecast (temperature, humidity, precipitation, wind, sunshine duration).

### 2. Plant Profiles (editable)
Stored in `plants.json`, editable live from the UI (`+ New` / `✎ Edit`). Each plant
defines a **trapezoidal ideal range** — `min → low → high → max` — for:
- Temperature (°C)
- Humidity (%)
- Sunlight (hours/day)
- Rainfall / water need (mm-equivalent)
- Wind tolerance (km/h)

plus two physical properties: **leaf absorptivity** (0–1, how much solar heating the
leaf surface picks up) and **soil water capacity** (mm the root zone can hold).

### 3. Physics & Biology Modeling (`simulation.py`)

**Leaf heat transfer:**
```
T_leaf = T_air + solar_gain − wind_cooling
solar_gain   = absorptivity × (sunlight_hours / 12) × 7°C
wind_cooling = min(wind_kmh × 0.15, 6°C)
```
Sunlight heats the leaf above air temperature; wind increases convective cooling.

**Water balance (daily soil-moisture bucket):**
```
evaporation = 4mm × (T_air/25) × (1 − humidity/100) × (1 + wind/25)
soil_moisture[day] = clamp(soil_moisture[day-1] + rainfall − evaporation, 0, capacity)
```

**Growth/success scoring:**
Each factor (temperature via leaf temp, humidity, sunlight, soil moisture, wind) is
scored 0–100 with a trapezoidal membership function: 100 inside the plant's ideal
`low–high` band, ramping to 0 at `min`/`max`. The daily score is a weighted blend:

| Factor | Weight |
|---|---|
| Temperature | 30% |
| Water/soil moisture | 25% |
| Sunlight | 20% |
| Humidity | 15% |
| Wind | 10% |

### 4. Output
- A **0–100% success score** + status label (Thriving / Healthy / Stressed / Struggling / Critical)
- The **most limiting factor** for the day
- A **7-day growth potential line chart**
- A **soil moisture vs rainfall chart**
- A **per-factor suitability bar chart**
- An **animated SVG plant icon** — leaves droop and shift from green → amber → red as
  the score drops

## API Reference

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/plants` | List all plant profiles |
| POST | `/api/plants` | Create a plant profile |
| PUT | `/api/plants/<id>` | Update a plant profile |
| DELETE | `/api/plants/<id>` | Delete a plant profile |
| GET | `/api/weather?location=City` | Fetch current + 7-day forecast |
| POST | `/api/simulate` | Run the simulation (`{plant_id, location}` or `{plant_id, weather}`) |

## Notes / possible extensions
- Add historical weather logging to a small SQLite DB to track a plant over time.
- Add multiple micro-climate zones (greenhouse vs open field) as a modifier on the model.
- Swap the trapezoidal scoring for a Gaussian curve if you want smoother falloff.

## Interface 1
![image1](images/Screenshot%20(1142).png)

## Interface 2
![image2](images/Screenshot%20(1143).png)
