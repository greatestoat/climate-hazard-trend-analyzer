# Climate Hazard Trend Analyzer

Analyses historical daily weather from Open-Meteo's ERA5 reanalysis to detect **heatwaves, cold waves, and heavy rainfall** for a city or custom
bounding box and shows how their frequency and duration have changed. Built for the Dygnify Ventures
Full-Stack Developer assessment.

| Layer | Stack |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, Recharts, Leaflet, Vitest |
| Backend | Python 3.11+, FastAPI, Pandas, NumPy, SciPy, slowapi |
| Database | MongoDB (PyMongo async driver) |
| Data | Open-Meteo Historical Weather API (ERA5 model) + Geocoding API (no API key) |

```
climate-hazard-analyzer/
├── backend/
│   ├── app/
│   │   ├── main.py            app factory, CORS, rate limiting, error handlers
│   │   ├── api.py             REST routes
│   │   ├── config.py          env-driven settings
│   │   ├── schemas.py         request validation
│   │   ├── errors.py          typed errors -> HTTP codes
│   │   ├── repository.py      MongoDB access + indexes + TTL caching
│   │   └── services/
│   │       ├── openmeteo.py   HTTP client: timeouts, retries, backoff
│   │       ├── regions.py     city / bounding-box representation
│   │       ├── analysis.py    cleaning, thresholds, events, trends (pure functions)
│   │       └── pipeline.py    cache -> fetch -> clean -> analyse -> store
│   ├── tests/                 pytest (in-memory fakes, no network or DB needed)
│   └── requirements.txt, requirements-dev.txt, pytest.ini, .env.example
└── frontend/
    ├── src/{components,pages,hooks,services,lib,types,test}
    └── package.json, vite.config.ts, tsconfig.json, index.html, .env.example
```

## 1. Prerequisites (Windows 10/11)

* **Python 3.11+** (`py --version`), **Node.js 22 LTS** (`node --version`), **Git**
* **MongoDB 7+** (step 2) and an internet connection (Open-Meteo)

## 2. MongoDB

Pick **one** option. Run in PowerShell.

**Option A, Docker Desktop (simplest):**
```powershell
docker run -d --name climate-mongo -p 27017:27017 -v climate-mongo-data:/data/db mongo:7
docker ps          # climate-mongo should be "Up"
# Later: docker stop climate-mongo / docker start climate-mongo
```

**Option B, native Windows service:**
```powershell
winget install MongoDB.Server
Get-Service MongoDB                    # Status should be Running
Start-Service MongoDB                  # run as Administrator if it is Stopped
```

**Option C, MongoDB Atlas (free tier):** create a cluster, allow your IP, and put the `mongodb+srv://...` string in `MONGODB_URI`.

Check the port: `Test-NetConnection localhost -Port 27017` (TcpTestSucceeded should be True).
Collections and indexes are created automatically when the backend starts.

## 3. Backend

```powershell
cd climate-hazard-analyzer\backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env           # edit MONGODB_URI / CORS_ORIGINS if needed
uvicorn app.main:app --reload --port 8000
```
Open http://localhost:8000/docs for interactive API docs. Verify:
```powershell
Invoke-RestMethod http://localhost:8000/api/health        # status: ok, database: up
```

## 4. Frontend (second terminal)

```powershell
cd climate-hazard-analyzer\frontend
npm install
Copy-Item .env.example .env           # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```
Open http://localhost:5173. Search a city (e.g. Hyderabad), keep the default period, and select **Run analysis**.
The first run for a region downloads about 35 years of data and can take 10-60 s; repeat runs are cached. The region map's
OpenStreetMap tiles also require an internet connection.

## 5. Tests

```powershell
# Backend (no network or MongoDB needed)
cd backend ; .\.venv\Scripts\Activate.ps1 ; pytest -v

# Frontend
cd ..\frontend ; npm test ; npm run typecheck ; npm run build
```

Optional API smoke test (needs MongoDB and internet):
```powershell
$body = @{ region=@{type="city";name="Hyderabad";country="India";latitude=17.385;longitude=78.4867}
           start_date="1991-01-01"; end_date="2025-12-31" } | ConvertTo-Json -Depth 5
$r = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/analyses -ContentType "application/json" -Body $body
$r.result.summary
Invoke-RestMethod "http://localhost:8000/api/analyses/$($r.id)/events?sort=duration&order=desc&page_size=5"
```

## 6. REST API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Service and database status |
| GET | `/api/cities?q=` | City search (Open-Meteo geocoding), `q` 2-80 chars |
| POST | `/api/analyses` | Create (or return cached) analysis; 201 |
| GET | `/api/analyses/{id}` | Retrieve a stored analysis |
| GET | `/api/analyses/{id}/events` | Detected events: `year`, `sort` (start/duration/peak/intensity), `order`, `page`, `page_size` |
| GET | `/api/analyses/{id}/events.csv` | Download detected events as hazard-specific CSV; optional `year` filter |

Request body for `POST /api/analyses`:
```json
{
  "region": {"type": "city", "name": "Hyderabad", "latitude": 17.385, "longitude": 78.487},
  "start_date": "1991-01-01", "end_date": "2025-12-31",
  "hazard": "heatwave", "percentile": 95, "min_duration": 3, "threshold_method": "period"
}
```
`region` may instead be `{"type": "bbox", "south": 16, "west": 78, "north": 18, "east": 80}`.
Errors share one shape: `{"error": {"code", "message", "details"}}` with 404 not found, 422 validation / insufficient data,
429 rate limited, 502 / 504 upstream failure, 503 database unavailable.

## 7. Method

**Data sources.** Daily maximum temperature, minimum temperature, and precipitation totals come from the [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api), with the ERA5 model explicitly selected. City search uses the [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api). The application caches downloaded daily values and analysis results in MongoDB; MongoDB is storage, not an independent weather source. The region selector's map background uses OpenStreetMap tiles. ERA5 is gridded reanalysis, not a direct station observation.

**Region representation.**
*City* = one point at the geocoded coordinates. *Custom box* = a 3×3 grid of cell-centre points (configurable via
`BBOX_GRID_SIZE`); Open-Meteo is queried for all points in one request and each daily weather variable is averaged (missing points ignored) into a
single regional series. Boxes must satisfy south < north, west < east (no antimeridian crossing) and span <= 10 degrees per side.

**Hazard definitions.** Heatwave is at least 3 consecutive days with daily maximum temperature strictly above the selected upper-tail percentile (default 95). Cold wave is at least 3 consecutive days with daily minimum temperature strictly below the selected lower-tail percentile (default 5; allowed 1-10). Heavy rainfall is a daily precipitation total strictly above the selected percentile (default 95) among days with at least 1 mm precipitation; consecutive qualifying days form an event, with a one-day minimum by default. Rainfall percentiles are restricted to 90-99.9. For all hazards, `threshold_method=period` uses one threshold over the selected period; `seasonal` computes thresholds in a plus/minus 7-day day-of-year window across years. For seasonal rainfall thresholds, windows with fewer than 10 wet-day samples fall back to the period-wide wet-day threshold. A remaining missing day after short-gap interpolation breaks a temperature run. Rainfall is not interpolated across missing days.

**Data handling.**
* Invalid dates are dropped and counted. Non-numeric measurements become missing observations and affect coverage; they are not included in the invalid-row count. Duplicate dates are averaged.
* Temperatures outside -90 to 60 degrees Celsius and negative precipitation totals are removed. For temperature series only, when at least 1,500 readings are available, spikes beyond 8 robust sigmas of the day-of-year anomaly are removed. This deliberately loose outlier limit aims to retain genuine extremes.
* Missing runs of up to 2 days are linearly interpolated before event detection; longer missing runs remain gaps and break events. Interpolated values count toward annual coverage, and their number is shown in the data-quality panel.
* A year is **complete** only if the requested date range covers the whole calendar year and at least 90% of its days are valid, including interpolated days. Incomplete years are shown but excluded from trend estimates, rolling means, annual averages, and early-versus-late percentage changes.
* End dates are clamped to today minus 5 days (archive lag), with a warning in the response.
* Open-Meteo calls use timeouts and retry with exponential backoff on 429/5xx/timeouts. If the API is unavailable, previously stored data is used with a warning when at least 90% of the requested daily range is stored.

**Statistics.** Annual event counts assign each event to its start year; hazard days are counted by calendar year. The charts show five-observation rolling means over complete years, with at least 3 observations to display a value. Gaps in complete-year coverage can therefore span more than five calendar years. OLS slopes and Mann-Kendall tests are calculated for annual hazard days and event counts using complete years, requiring at least 5 non-constant observations. Mann-Kendall reports Kendall's tau and a two-sided nominal p-value: exact permutations are used for up to 8 complete years, and a tie-corrected normal approximation for longer series. Neither method adjusts for serial correlation or multiple comparisons; p-values are exploratory and are not presented as proof of statistical significance, causation, or absence of a trend. Early-versus-late percentage change compares the first and last halves of complete years, requiring at least 6 complete years; for an odd count, the middle year is omitted. If the early baseline is zero, percentage change is undefined. These summaries describe the selected region, period, and hazard definition; they are not a formal attribution study.

**CSV export.** The events panel downloads all detected events, or only the currently selected year, as UTF-8 CSV. The year filter uses each event start year. The file contains event dates, duration, hazard-specific extreme and mean values, cumulative excess above/below threshold, and threshold. Units are Celsius for temperature hazards and millimetres for rainfall. Annual summaries and raw daily weather values are not included. The download requires the analysis record to remain available in the database.

**Map selection.** In Custom box mode, select two opposite corners on the Leaflet map to fill the coordinate fields. Coordinates remain editable, and the existing 10-degree-per-side validation still applies. Map tiles come from OpenStreetMap and require an internet connection; city selection remains available without opening the map.

**PDF report.** Choose Save report as PDF after an analysis, then select Save as PDF in the browser print dialog. The print layout includes the analysis summary, charts, insights, and data-quality notes; the paginated event table is omitted so the report does not imply it contains the full event list. Printed output depends on the browser chart rendering and print settings.

**Scope and assumptions.** The app supports heatwave, cold wave, and heavy rainfall. Regions are a geocoded city point or a user-defined box; states can be approximated with a box but are not a separate region type. Boxes cannot cross the antimeridian and are limited to 10 degrees per side. Heat and rainfall percentiles are 90-99.9; cold-wave percentiles are 1-10. Heat and cold events require at least 3 days; rainfall events allow 1-14 days. The default period-wide percentile uses the selected analysis period as its own threshold baseline, so changing that period can change detected events and the trend. Use the seasonal threshold option when a calendar-day comparison is more appropriate. The rainfall rule is a transparent event heuristic and does not account for local impacts, soil saturation, or rainfall return periods.

The application explicitly requests Open-Meteo ERA5 rather than the API's changing Best Match default, supporting a consistent multi-decade input. ERA5 is gridded reanalysis, not a direct station observation; city results represent one grid point and box results average a 3x3 sample of grid points. Grid resolution and regional averaging cannot capture all local variation. The model identifier is part of the weather cache key, so values cached by an older build using Best Match are not reused. See the [Open-Meteo Historical Weather API documentation](https://open-meteo.com/en/docs/historical-weather-api).

**MongoDB.** `weather_daily` (unique index `region_key,date`), `weather_fetches` (cache records, TTL index),
`analyses` (index on `params_hash`, TTL), `heatwave_events` (legacy collection name; stores all hazard event types, indexes on `analysis_id,start` and `analysis_id,year`, TTL).
Identical requests reuse the stored analysis; a different percentile or method on the same region and dates reuses cached weather.

## 8. Configuration

All settings are environment variables (see `backend/.env.example`): `MONGODB_URI`, `MONGODB_DB`, `CORS_ORIGINS` (comma-separated),
`RATE_LIMIT_DEFAULT`, `RATE_LIMIT_ANALYSIS`, `RATE_LIMIT_ENABLED`, cache TTLs, HTTP timeout and retries. `.env` is git-ignored.

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| Dashboard says it can't reach the server | Backend not running, or `VITE_API_BASE_URL` is wrong. Restart `npm run dev` after editing `.env`. |
| Browser CORS error | Add your frontend origin to `CORS_ORIGINS` and restart the backend. |
| 503 `database_unavailable` | MongoDB isn't running (`docker start climate-mongo` or `Start-Service MongoDB`). |
| 429 `rate_limited` | Wait a minute, or raise `RATE_LIMIT_ANALYSIS`. |
| 502 / 504 from Open-Meteo | Retry; large boxes and long ranges take longer. |
| `Activate.ps1` is blocked | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |

## 10. Deployment and next steps

No public deployment URL is configured in this repository yet. The case-study submission asks for a deployed URL; add it here after deployment. A hosted setup needs a MongoDB instance, a FastAPI host running `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, and a static frontend build (`npm run build`, then serve `frontend/dist`). Set `MONGODB_URI`, `MONGODB_DB`, and `CORS_ORIGINS` on the backend host; set `VITE_API_BASE_URL` to the deployed backend URL when building the frontend. Do not use the local `.env` examples in production, and allow the frontend origin in backend CORS settings.

With more time, I would add automated deployment and end-to-end checks, a statistically robust trend option such as Mann-Kendall with serial-correlation handling and clear assumptions, and additional hazard types only after defining and validating their data requirements and event rules.

## 11. AI tools disclosure

OpenAI Codex was used during development to assist with implementation and review of the CSV export, Leaflet region selector, print-to-PDF report, additional hazard logic, trend estimates, UI refinements, and README updates. AI-generated suggestions were reviewed against the application code and case-study requirements; I remain responsible for understanding and explaining the submitted implementation.
