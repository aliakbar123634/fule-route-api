# Fuel Route API

Django REST API that calculates a driving route between two locations and
finds optimal fuel stops along the route, minimizing total fuel cost.

## How it works

1. **Routing** — Start/destination are geocoded, then a driving route is
   fetched from the public [OSRM](https://router.project-osrm.org) API.
2. **Station discovery** — Fuel stations near the route corridor are
   discovered via the [Overpass API](https://overpass-api.de) (OpenStreetMap).
3. **Price matching** — Discovered stations are matched against the provided
   `fuel-prices-for-be-assessment.csv` price list; only stations with a
   verified CSV price are eligible for optimization.
4. **Optimization** — A dynamic-programming optimizer selects fuel stops that
   minimize total fuel cost, respecting the vehicle's maximum range.

## Assumptions

- The vehicle **starts with a full tank**; the cost estimate reflects fuel
  purchased en route only (initial tank cost is not included).
- Vehicle range: **500 miles**; fuel economy: **10 MPG**. Both are
  configurable in `routing/views.py` (`VEHICLE_MAX_RANGE_MILES`,
  `FUEL_ECONOMY_MPG`).
- Station prices come from the bundled CSV; unmatched stations are returned
  as candidates but excluded from cost optimization.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py load_stations --csv data/fuel-prices-for-be-assessment.csv
# Required for fuel-stop optimization: geocodes ~900 station cities
# (one-time, ~15 min; results are cached in the database)
python manage.py populate_station_coordinates
```

## Run

```bash
python manage.py runserver
```

## API

### POST /api/route/

Request:

```json
{
  "start": "Chicago, IL",
  "destination": "Dallas, TX"
}
```

Response (200):

```json
{
  "start": "Chicago, IL",
  "destination": "Dallas, TX",
  "total_distance_miles": 966.92,
  "estimated_duration_hours": 17.1,
  "fuel_requirements": {
    "vehicle_max_range_miles": 500,
    "fuel_economy_mpg": 10,
    "estimated_trip_gallons": 96.69,
    "status": "optimized_with_verified_prices",
    "estimated_fuel_cost": 134.97,
    "cost_currency": "USD",
    "cost_scope": "Intermediate refueling only; initial tank cost is not included."
  },
  "fuel_stops": [
    {"name": "...", "retail_price": 3.12, "route_position_miles": 210.4}
  ],
  "fuel_station_candidates": [],
  "fuel_station_count": 12,
  "verified_priced_station_count": 6
}
```

The `fuel_requirements.status` field is honest about what happened:

| status | meaning |
|---|---|
| `optimized_with_verified_prices` | stops + cost computed from verified CSV prices |
| `prices_not_verified` | route OK, but no verified prices — no cost claimed |
| `station_discovery_failed_or_empty` | route OK, Overpass lookup failed — no stops |
| `no_feasible_verified_station_route` | verified stations exist but no feasible stop sequence |

Validation errors return `400`; routing/geocoding failures return `502`.

## Tests

```bash
python manage.py test routing
```

## Project structure

```
config/                 Django project settings / URLs
routing/
  models.py             Station, GeocodeCache
  views.py              POST /api/route/ endpoint
  serializers.py        Request validation
  services/
    route_service.py        OSRM routing
    geocoding_service.py    Nominatim geocoding + cache
    station_location_service.py  Overpass station discovery
    station_matching_service.py  OSM <-> CSV price matching
    fuel_stop_service.py    Haversine, corridor filter, DP optimizer
    route_station_service.py    Orchestrates discovery along route
  management/commands/
    load_stations.py               Import CSV prices
    populate_station_coordinates.py Geocode station cities
```

## Environment variables (optional)

| variable | default | purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | insecure dev key | override for non-local runs |
| `DJANGO_DEBUG` | `True` | set `False` in production |
| `DJANGO_ALLOWED_HOSTS` | empty | comma-separated hosts |

## External services

- OSRM demo server (routing) — free, no key required
- Overpass API (station discovery) — free, rate-limited; large-radius
  queries can time out, in which case the API returns the route with a
  `station_discovery_failed_or_empty` status instead of failing
- Nominatim (geocoding) — free, cached in the database
