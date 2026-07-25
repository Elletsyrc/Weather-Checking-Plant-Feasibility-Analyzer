// ============================================================
// Weather–Plant Success Simulator — frontend logic
// ============================================================

const state = {
  plants: {},
  currentPlantId: null,
  weather: null,
  growthChart: null,
  factorChart: null,
  soilChart: null,
};

const el = (id) => document.getElementById(id);

// ---------------------------------------------------------------- init
async function init() {
  await loadPlants();
  bindEvents();
}

async function loadPlants() {
  const res = await fetch('/api/plants');
  state.plants = await res.json();
  const select = el('plantSelect');
  select.innerHTML = '';
  Object.values(state.plants).forEach((p) => {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = `${p.icon || '🌱'} ${p.name}`;
    select.appendChild(opt);
  });
  if (!state.currentPlantId && Object.keys(state.plants).length) {
    state.currentPlantId = Object.keys(state.plants)[0];
  }
  select.value = state.currentPlantId;
  updatePlantDesc();
}

function updatePlantDesc() {
  const p = state.plants[state.currentPlantId];
  el('plantDesc').textContent = p ? p.description || '' : '';
}

// ---------------------------------------------------------------- events
function bindEvents() {
  el('fetchWeatherBtn').addEventListener('click', fetchWeather);
  el('locationInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') fetchWeather(); });
  el('plantSelect').addEventListener('change', (e) => {
    state.currentPlantId = e.target.value;
    updatePlantDesc();
  });
  el('simulateBtn').addEventListener('click', runSimulation);

  el('newPlantBtn').addEventListener('click', () => openPlantModal(null));
  el('editPlantBtn').addEventListener('click', () => openPlantModal(state.currentPlantId));
  el('cancelModalBtn').addEventListener('click', closePlantModal);
  el('plantModal').addEventListener('click', (e) => { if (e.target.id === 'plantModal') closePlantModal(); });
  el('plantForm').addEventListener('submit', savePlantForm);
  el('deletePlantBtn').addEventListener('click', deleteCurrentPlant);
}

// ---------------------------------------------------------------- weather
async function fetchWeather() {
  const location = el('locationInput').value.trim();
  const statusMsg = el('weatherStatus');
  if (!location) { statusMsg.textContent = 'Enter a location first.'; statusMsg.className = 'status-msg error'; return; }

  statusMsg.textContent = 'Fetching weather…';
  statusMsg.className = 'status-msg';

  try {
    const res = await fetch(`/api/weather?location=${encodeURIComponent(location)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to fetch weather.');

    state.weather = data;
    statusMsg.textContent = `✓ ${data.location}`;
    statusMsg.className = 'status-msg ok';
    renderCurrentConditions(data.current);
  } catch (err) {
    statusMsg.textContent = `⚠ ${err.message}`;
    statusMsg.className = 'status-msg error';
  }
}

function renderCurrentConditions(current) {
  const card = el('currentConditionsCard');
  const grid = el('currentConditions');
  const items = [
    ['Temperature', current.temp != null ? `${current.temp.toFixed(1)}°C` : '—'],
    ['Humidity', current.humidity != null ? `${current.humidity.toFixed(0)}%` : '—'],
    ['Rainfall', current.rainfall != null ? `${current.rainfall.toFixed(1)} mm` : '—'],
    ['Sunlight', current.sunlight != null ? `${current.sunlight.toFixed(1)} h` : '—'],
    ['Wind', current.wind != null ? `${current.wind.toFixed(1)} km/h` : '—'],
  ];
  grid.innerHTML = items.map(([label, value]) => `
    <div class="cond-item">
      <div class="label">${label}</div>
      <div class="value">${value}</div>
    </div>`).join('');
  card.style.display = 'block';
}

// ---------------------------------------------------------------- simulate
async function runSimulation() {
  if (!state.weather) {
    await fetchWeather();
    if (!state.weather) return;
  }
  const statusMsg = el('weatherStatus');
  const btn = el('simulateBtn');
  btn.disabled = true;
  btn.textContent = 'Simulating…';

  try {
    const res = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plant_id: state.currentPlantId, weather: state.weather }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Simulation failed.');
    renderResults(data);
  } catch (err) {
    statusMsg.textContent = `⚠ ${err.message}`;
    statusMsg.className = 'status-msg error';
  } finally {
    btn.disabled = false;
    btn.textContent = '▶ Run Simulation';
  }
}

// ---------------------------------------------------------------- render results
function renderResults(result) {
  el('emptyState').style.display = 'none';
  el('resultCard').style.display = 'block';
  el('chartCard').style.display = 'block';
  el('factorChartCard').style.display = 'block';
  el('soilChartCard').style.display = 'block';

  const today = result.days[0];
  el('resultPlantName').textContent = `${result.icon} ${result.plant} — ${result.location || ''}`;
  el('resultScore').textContent = `${today.success_score}%`;

  const statusEl = el('resultStatus');
  statusEl.textContent = today.status;
  statusEl.className = 'status-pill ' + statusClass(today.success_score);

  el('limitingFactor').innerHTML =
    `Most limiting factor today: <strong>${labelFactor(today.scores)}</strong>`;

  renderPlantVisual(today.success_score);
  renderIdealComparison(result, today);
  renderGrowthChart(result.days);
  renderFactorChart(today.scores);
  renderSoilChart(result.days);
}

function statusClass(score) {
  if (score >= 60) return '';
  if (score >= 30) return 'stressed';
  return 'critical';
}

function labelFactor(scores) {
  const names = { temperature: 'Temperature', humidity: 'Humidity', sunlight: 'Sunlight', water: 'Soil Moisture', wind: 'Wind' };
  let minKey = Object.keys(scores)[0];
  Object.keys(scores).forEach((k) => { if (scores[k] < scores[minKey]) minKey = k; });
  return names[minKey];
}

function renderIdealComparison(result, today) {
  const plant = state.plants[state.currentPlantId];
  const rows = [
    { label: 'Leaf Temperature', unit: '°C', value: today.leaf_temp, min: plant.temp_min, low: plant.temp_low, high: plant.temp_high, max: plant.temp_max },
    { label: 'Humidity', unit: '%', value: today.humidity, min: plant.humidity_min, low: plant.humidity_low, high: plant.humidity_high, max: plant.humidity_max },
    { label: 'Sunlight', unit: 'h', value: today.sunlight, min: plant.sunlight_min, low: plant.sunlight_low, high: plant.sunlight_high, max: plant.sunlight_max },
    { label: 'Soil Moisture', unit: '%', value: today.soil_moisture_pct, min: 0, low: 25, high: 85, max: 100 },
    { label: 'Wind', unit: 'km/h', value: today.wind, min: plant.wind_min, low: plant.wind_low, high: plant.wind_high, max: plant.wind_max },
  ];

  el('idealComparison').innerHTML = rows.map((r) => {
    const span = r.max - r.min || 1;
    const pct = (v) => Math.max(0, Math.min(100, ((v - r.min) / span) * 100));
    return `
    <div class="factor-row">
      <div class="factor-label">
        <span>${r.label} — ideal ${r.low}–${r.high}${r.unit}</span>
        <span class="fv">${r.value}${r.unit}</span>
      </div>
      <div class="bar-track">
        <div class="bar-ideal-zone" style="left:${pct(r.low)}%; width:${pct(r.high) - pct(r.low)}%;"></div>
        <div class="bar-fill" style="left:calc(${pct(r.value)}% - 1.5px);"></div>
      </div>
    </div>`;
  }).join('');
}

// ---------------------------------------------------------------- charts
function renderGrowthChart(days) {
  const ctx = el('growthChart').getContext('2d');
  const labels = days.map((d) => formatDate(d.date));
  const scores = days.map((d) => d.success_score);

  if (state.growthChart) state.growthChart.destroy();
  state.growthChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Growth potential (%)',
        data: scores,
        borderColor: '#7fb069',
        backgroundColor: 'rgba(127,176,105,0.18)',
        fill: true,
        tension: 0.35,
        pointBackgroundColor: scores.map((s) => scoreColor(s)),
        pointRadius: 5,
        borderWidth: 2,
      }],
    },
    options: chartBaseOptions('%', 0, 100),
  });
}

function renderFactorChart(scores) {
  const ctx = el('factorChart').getContext('2d');
  const labels = ['Temperature', 'Humidity', 'Sunlight', 'Soil Moisture', 'Wind'];
  const values = [scores.temperature, scores.humidity, scores.sunlight, scores.water, scores.wind];

  if (state.factorChart) state.factorChart.destroy();
  state.factorChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Suitability (%)',
        data: values,
        backgroundColor: values.map((v) => scoreColor(v)),
        borderRadius: 6,
      }],
    },
    options: { ...chartBaseOptions('%', 0, 100), indexAxis: 'y' },
  });
}

function renderSoilChart(days) {
  const ctx = el('soilChart').getContext('2d');
  const labels = days.map((d) => formatDate(d.date));
  const moisture = days.map((d) => d.soil_moisture_pct);
  const rainfall = days.map((d) => d.rainfall);

  if (state.soilChart) state.soilChart.destroy();
  state.soilChart = new Chart(ctx, {
    data: {
      labels,
      datasets: [
        {
          type: 'line', label: 'Soil moisture (%)', data: moisture,
          borderColor: '#6fa8c9', backgroundColor: 'rgba(111,168,201,0.15)',
          fill: true, tension: 0.3, yAxisID: 'y', pointRadius: 3, borderWidth: 2,
        },
        {
          type: 'bar', label: 'Rainfall (mm)', data: rainfall,
          backgroundColor: 'rgba(184,164,120,0.55)', yAxisID: 'y1', borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { labels: { color: '#a9b5a8' } } },
      scales: {
        x: { ticks: { color: '#a9b5a8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        y: { position: 'left', min: 0, max: 100, ticks: { color: '#a9b5a8' }, grid: { color: 'rgba(255,255,255,0.05)' }, title: { display: true, text: 'Soil moisture %', color: '#a9b5a8' } },
        y1: { position: 'right', min: 0, ticks: { color: '#a9b5a8' }, grid: { display: false }, title: { display: true, text: 'Rainfall mm', color: '#a9b5a8' } },
      },
    },
  });
}

function chartBaseOptions(unit, min, max) {
  return {
    responsive: true,
    plugins: { legend: { labels: { color: '#a9b5a8' } } },
    scales: {
      x: { ticks: { color: '#a9b5a8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
      y: { min, max, ticks: { color: '#a9b5a8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
    },
  };
}

function scoreColor(score) {
  if (score >= 80) return '#7fb069';
  if (score >= 60) return '#a6d17f';
  if (score >= 40) return '#e0a458';
  if (score >= 20) return '#d97b3f';
  return '#c1443c';
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

// ---------------------------------------------------------------- plant SVG visual
function renderPlantVisual(score) {
  const container = el('plantVisual');
  const t = Math.max(0, Math.min(100, score)) / 100; // 0 = dead, 1 = perfect

  // Interpolate color: stress-red -> amber -> leaf-bright
  const color = scoreColor(score);
  const droop = (1 - t) * 35; // degrees of droop when unhealthy
  const leafScale = 0.75 + t * 0.35;

  container.innerHTML = `
  <svg viewBox="0 0 150 170" width="150" height="170" xmlns="http://www.w3.org/2000/svg">
    <ellipse cx="75" cy="158" rx="55" ry="10" fill="#000" opacity="0.25"/>
    <rect x="35" y="132" width="80" height="30" rx="6" fill="#5a4632"/>
    <rect x="35" y="132" width="80" height="8" rx="4" fill="#6b5640"/>

    <!-- stem -->
    <path d="M75 132 C 75 100, 75 90, 75 60"
          stroke="#5c7a4a" stroke-width="6" fill="none" stroke-linecap="round"/>

    <!-- leaves: left, right, top — droop and desaturate with stress -->
    <g transform="translate(75,95) rotate(${-25 - droop})">
      <ellipse cx="-28" cy="0" rx="30" ry="14" fill="${color}" transform="scale(${leafScale})"/>
    </g>
    <g transform="translate(75,75) rotate(${25 + droop})">
      <ellipse cx="28" cy="0" rx="30" ry="14" fill="${color}" transform="scale(${leafScale})"/>
    </g>
    <g transform="translate(75,58) rotate(${droop * 0.6})">
      <ellipse cx="0" cy="-18" rx="16" ry="26" fill="${color}" transform="scale(${leafScale})"/>
    </g>

    <!-- face: healthy = simple smile, stressed = flat/frown -->
    <g transform="translate(75,58)">
      <circle cx="-6" cy="-2" r="2.2" fill="#1a2018"/>
      <circle cx="6" cy="-2" r="2.2" fill="#1a2018"/>
      <path d="M -7 ${4 + (1 - t) * 6} Q 0 ${4 + (t - 0.5) * 14} 7 ${4 + (1 - t) * 6}"
            stroke="#1a2018" stroke-width="1.6" fill="none" stroke-linecap="round"/>
    </g>
  </svg>`;
}

// ---------------------------------------------------------------- plant editor modal
const PLANT_FIELDS = [
  'name', 'icon', 'description',
  'temp_min', 'temp_low', 'temp_high', 'temp_max',
  'humidity_min', 'humidity_low', 'humidity_high', 'humidity_max',
  'sunlight_min', 'sunlight_low', 'sunlight_high', 'sunlight_max',
  'rainfall_min', 'rainfall_low', 'rainfall_high', 'rainfall_max',
  'wind_min', 'wind_low', 'wind_high', 'wind_max',
  'leaf_absorptivity', 'soil_water_capacity',
];

function openPlantModal(plantId) {
  const isNew = !plantId;
  const plant = isNew ? blankPlant() : state.plants[plantId];

  el('modalTitle').textContent = isNew ? 'New Plant Profile' : `Edit ${plant.name}`;
  el('f_original_id').value = isNew ? '' : plantId;
  PLANT_FIELDS.forEach((f) => {
    const input = el('f_' + f);
    if (input) input.value = plant[f] ?? '';
  });
  el('deletePlantBtn').style.display = isNew ? 'none' : 'inline-block';
  el('plantModal').classList.remove('hidden');
}

function blankPlant() {
  return {
    name: '', icon: '🌱', description: '',
    temp_min: 5, temp_low: 15, temp_high: 25, temp_max: 35,
    humidity_min: 30, humidity_low: 50, humidity_high: 70, humidity_max: 90,
    sunlight_min: 3, sunlight_low: 5, sunlight_high: 7, sunlight_max: 10,
    rainfall_min: 0, rainfall_low: 10, rainfall_high: 30, rainfall_max: 60,
    wind_min: 0, wind_low: 0, wind_high: 20, wind_max: 40,
    leaf_absorptivity: 0.6, soil_water_capacity: 50,
  };
}

function closePlantModal() {
  el('plantModal').classList.add('hidden');
}

async function savePlantForm(e) {
  e.preventDefault();
  const originalId = el('f_original_id').value;
  const payload = {};
  PLANT_FIELDS.forEach((f) => {
    const input = el('f_' + f);
    if (!input) return;
    payload[f] = input.type === 'number' ? parseFloat(input.value) : input.value;
  });

  try {
    let res;
    if (originalId) {
      res = await fetch(`/api/plants/${originalId}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
    } else {
      res = await fetch('/api/plants', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to save plant.');

    await loadPlants();
    state.currentPlantId = data.id;
    el('plantSelect').value = data.id;
    updatePlantDesc();
    closePlantModal();
  } catch (err) {
    alert(err.message);
  }
}

async function deleteCurrentPlant() {
  const id = el('f_original_id').value;
  if (!id) return;
  if (!confirm(`Delete plant profile "${state.plants[id].name}"? This cannot be undone.`)) return;

  const res = await fetch(`/api/plants/${id}`, { method: 'DELETE' });
  if (!res.ok) { alert('Failed to delete plant.'); return; }

  await loadPlants();
  closePlantModal();
}

// ---------------------------------------------------------------- go
init();
