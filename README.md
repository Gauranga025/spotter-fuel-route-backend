# Fuel Route Optimization API

A Django REST API that calculates optimal fuel stops along driving routes in the USA, minimizing total fuel cost while respecting vehicle range constraints.

## Overview

This API accepts start and finish locations within the USA, calculates a driving route using OSRM, finds fuel stations along the route corridor, and optimizes fuel purchases to minimize total cost given a 500-mile maximum vehicle range and 10 MPG fuel efficiency.

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP POST
       ▼
┌─────────────────────────────────┐
│   Django REST API View          │
│   (routes/views.py)             │
└──────┬──────────────────────────┘
       │
       ├──────────────────┬──────────────────┬──────────────────┐
       ▼                  ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Geocoding    │  │ OSRM Routing │  │ Route        │  │ Fuel         │
│ Service      │  │ Service      │  │ Matching     │  │ Optimizer    │
│ (Nominatim)  │  │ (OSRM API)   │  │ Service      │  │ (Dynamic     │
│              │  │              │  │ (PostGIS)    │  │ Programming) │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Geocode      │  │ Route        │  │ Candidate    │  │ Optimal      │
│ Cache        │  │ Geometry     │  │ Stations     │  │ Fuel Plan    │
│ (DB)         │  │ (GeoJSON)    │  │ (PostGIS)    │  │              │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

## Algorithm

### 1. Geocoding
- Start and finish locations are geocoded using Nominatim (OpenStreetMap)
- Results are cached in the database to avoid repeated API calls
- Only locations within USA bounds are accepted

### 2. Route Calculation
- A single OSRM API call calculates the driving route between start and finish
- Returns route distance, duration, and GeoJSON LineString geometry
- **Important**: Only ONE routing API call is made per request

### 3. Route Corridor
- A configurable corridor (default 10 miles) is created around the route
- PostGIS spatial queries find fuel stations within this corridor
- This dramatically reduces the candidate set from ~8,000 to typically <100 stations

### 4. Spatial Station Filtering
- Stations are filtered using PostGIS `ST_Within` on the buffered corridor
- Stations with 'success' (address-level) or 'fallback' (city-level) geocode
  status are considered
- Spatial indexing ensures fast queries

### 5. Station Projection
- Each candidate station is projected onto the route line
- Distance from start along route is calculated
- Lateral distance from route is calculated
- Stations are sorted by distance along route

### 6. Fuel Optimization
- Dynamic programming finds the minimum-cost fuel purchase sequence
- Respects:
  - 500-mile maximum vehicle range
  - 10 MPG fuel efficiency
  - 50-gallon tank capacity
  - Initial fuel = 0 gallons
- Transitions between stations are only allowed if distance ≤ 500 miles
- Fuel purchase amounts are optimized (not always full tank)

## Why Only One Routing API Call?

The routing API is called exactly once between start and finish. Station optimization occurs locally using:

1. **PostGIS spatial queries** to filter stations near the route
2. **Geometric projections** to calculate distances along the route
3. **Dynamic programming** to find optimal fuel stops

This approach:
- Minimizes external API dependencies
- Reduces latency (no per-station routing calls)
- Makes the system more reliable
- Respects rate limits of free routing services

## Dataset

The provided CSV (`fuel-prices-for-be-assessment.csv`) contains approximately 8,151 fuel station records with:

- OPIS Truckstop ID
- Truckstop Name
- Address
- City
- State
- Rack ID
- Retail Price

## Data Preprocessing

Fuel stations are preprocessed using a Django management command:

```bash
python manage.py import_fuel_stations fuel-prices-for-be-assessment.csv
```

The import process:

1. Reads and validates the CSV
2. Normalizes strings and state codes
3. Validates fuel prices
4. Geocodes station addresses using Nominatim
5. Caches geocoding results to avoid duplicate API calls
6. Falls back to city-level geocoding if address-level fails
7. Stores coordinates as PostGIS PointField
8. Marks geocode status and precision
9. Is idempotent (safe to re-run)

**Important**: Geocoding 8,000+ stations can take time due to rate limits. The process is resumable and caches results.

## Assumptions

- **Maximum Range**: 500 miles
- **Fuel Efficiency**: 10 MPG
- **Tank Capacity**: 50 gallons (derived from 500 miles / 10 MPG)
- **Initial Fuel**: 50 gallons (full tank)
- **Route Corridor**: 10 miles (configurable)
- **Station Precision**: Stations with 'success' or 'fallback' geocode status
  are used. Fallback stations use city-level coordinates which may be
  several miles from the actual location.
- **Route Distance**: Approximated using PostGIS geometric projections
- **Fuel Price**: Retail price from CSV (assumed current)

## Setup

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)

### Quick Start with Docker

1. Clone the repository:
```bash
git clone <repository-url>
cd Backend
```

2. Build and start with Docker Compose:
```bash
docker compose up --build
```

This will:
- Start PostgreSQL with PostGIS
- Run Django migrations
- Start the API server on port 8000

### Local Development Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your settings
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Import fuel station data:

**Option A: Import and geocode (full process)**
```bash
python manage.py import_fuel_stations fuel-prices-for-be-assessment.csv
```

Note: The import command will geocode all stations. Due to Nominatim rate limits (1 request/second by default), this may take several hours. The process is resumable.

**Option B: Load pre-geocoded fixture (for testing/review)**
```bash
python manage.py load_fixture
```

This loads a fixture with pre-geocoded stations, avoiding the need to wait for geocoding. To create the fixture from imported data:
```bash
python manage.py dumpdata stations.FuelStation --indent 2 > stations/fixtures/fuel_stations_fixture.json
```

6. Start the development server:
```bash
python manage.py runserver
```

## Database Setup

The application uses PostgreSQL with PostGIS extension.

### Docker Setup

PostgreSQL with PostGIS is automatically configured in `docker-compose.yml`.

### Manual Setup

1. Install PostgreSQL and PostGIS
2. Create database:
```sql
CREATE DATABASE fuelroute;
```

3. Enable PostGIS:
```sql
CREATE EXTENSION postgis;
```

4. Configure `DATABASE_URL` in `.env`

## Import Data

```bash
python manage.py import_fuel_stations fuel-prices-for-be-assessment.csv
```

Options:
- `--batch-size`: Number of records per batch (default: 100)
- `--skip-geocoding`: Skip geocoding (useful for testing)
- `--retry-failed`: Retry geocoding for stations with failed status

Example:
```bash
python manage.py import_fuel_stations fuel-prices-for-be-assessment.csv --batch-size 50
python manage.py import_fuel_stations fuel-prices-for-be-assessment.csv --retry-failed
```

## API Usage

### Endpoint

```
POST /api/v1/routes/fuel-plan/
```

### Request Body

```json
{
  "start": "Dallas, TX",
  "finish": "Denver, CO"
}
```

### Example with cURL

```bash
curl -X POST http://localhost:8000/api/v1/routes/fuel-plan/ \
  -H "Content-Type: application/json" \
  -d '{"start": "Dallas, TX", "finish": "Denver, CO"}'
```

### Example with Postman

1. Create a new POST request to `http://localhost:8000/api/v1/routes/fuel-plan/`
2. Set header `Content-Type: application/json`
3. Set body:
```json
{
  "start": "Dallas, TX",
  "finish": "Denver, CO"
}
```

### Example Response (Success)

```json
{
  "status": "success",
  "request": {
    "start": "Dallas, TX",
    "finish": "Denver, CO"
  },
  "route": {
    "distance_miles": 794.32,
    "duration_minutes": 721.4,
    "geometry": {
      "type": "LineString",
      "coordinates": [
        [-96.8, 32.8],
        [-96.7, 32.9],
        ...
      ]
    }
  },
  "vehicle": {
    "max_range_miles": 500,
    "mpg": 10,
    "tank_capacity_gallons": 50,
    "initial_fuel_gallons": 50
  },
  "fuel_stops": [
    {
      "station_id": 123,
      "name": "Example Truckstop",
      "address": "123 Example Road",
      "city": "Amarillo",
      "state": "TX",
      "latitude": 35.22,
      "longitude": -101.83,
      "price_per_gallon": 3.12,
      "distance_from_start_miles": 365.4,
      "gallons_purchased": 36.54,
      "fuel_cost": 113.99
    }
  ],
  "fuel_summary": {
    "total_gallons": 79.43,
    "total_cost": 246.83
  }
}
```

### Example Response (No Feasible Route)

```json
{
  "status": "no_feasible_route",
  "reason": "No feasible sequence of fuel stations can cover the route within the vehicle's 500-mile maximum range."
}
```

### Error Responses

- **400 Bad Request**: Invalid input (missing fields, same start/finish)
- **503 Service Unavailable**: External service error (geocoding/routing)
- **500 Internal Server Error**: Unexpected error

## API Documentation

Interactive API documentation is available via drf-spectacular:

- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/
- **OpenAPI Schema**: http://localhost:8000/api/schema/

## Testing

Run the test suite:

```bash
pytest
```

Tests cover:
- Serializer validation
- Geocoding service (with mocked external APIs)
- Routing service (with mocked OSRM)
- Fuel optimizer algorithm
- Various edge cases and constraints

All tests mock external APIs and can run offline.

## Performance

### External API Calls

Per request:
 **1 OSRM routing call**
- **2 Nominatim geocoding calls** (start and finish, cached on subsequent requests)

### Spatial Filtering

- PostGIS spatial index on station locations
- Corridor filtering reduces candidate set from ~8,000 to typically <100
- Projection calculations done in-memory on filtered set

### Typical Request Time

- Geocoding (cached): ~50ms
- OSRM routing: ~200-500ms
- Spatial filtering: ~50-100ms
- Optimization: ~10-50ms
- **Total**: ~300-700ms

## Limitations

### External Service Rate Limits

- **Nominatim**: 1 request/second (configurable User-Agent required)
- **OSRM**: No strict limit but free server may be busy

### Geocoding Accuracy

- Address-level geocoding depends on Nominatim data quality
- Falls back to city-level if address fails
- City-level coordinates may be several miles from actual location

### Route Corridor Approximation

- 10-mile corridor may miss stations slightly off-route
- Stations far from highway may not be included even if useful

### Dataset Freshness

- Fuel prices are from provided CSV (not real-time)
- Station data may not reflect recent closures/openings

### Geographic Scope

- Only supports locations within the USA
- Uses approximate USA bounds for validation

## Configuration

Environment variables (see `.env.example`):

```env
DEBUG=False
SECRET_KEY=change-me
DATABASE_URL=postgresql://postgres:postgres@db:5432/fuelroute
OSRM_BASE_URL=https://router.project-osrm.org
NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org
ROUTE_CORRIDOR_MILES=10
MAX_RANGE_MILES=500
MPG=10
TANK_CAPACITY_GALLONS=50
INITIAL_FUEL_GALLONS=50
```

## Project Structure

```
Backend/
├── config/
│   ├── settings.py          # Django settings
│   ├── urls.py              # URL configuration
│   └── wsgi.py
├── stations/
│   ├── models.py            # FuelStation and GeocodeCache models
│   ├── admin.py             # Django admin configuration
│   ├── services/
│   │   └── geocoding.py     # Geocoding service
│   └── management/
│       └── commands/
│           └── import_fuel_stations.py
├── routes/
│   ├── views.py             # API view
│   ├── serializers.py       # Request/response serializers
│   ├── urls.py              # Route URLs
│   └── services/
│       ├── routing.py       # OSRM routing service
│       ├── route_matching.py # PostGIS corridor matching
│       └── fuel_optimizer.py # Dynamic programming optimizer
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_serializers.py
│   ├── test_geocoding.py
│   ├── test_routing.py
│   └── test_fuel_optimizer.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
└── README.md
```

## License

This project is for assessment purposes.
