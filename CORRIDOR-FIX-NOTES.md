# v3 corridor geocoding fix (2026-10-11)

## Problem
`populate_station_coordinates` hit Nominatim rate limits: 302 cities OK,
6016 failed. With so few geocoded cities on the Chicago -> Dallas corridor,
the optimizer returns `no_feasible_verified_station_route` even though
27 priced stations exist near the route (gaps > 500 miles between them).

## What changed
- `routing/services/geocoding_service.py`
  - New `get_coordinates_with_retry()`: retries transient failures
    (HTTP errors, timeouts, rate-limit blocks) with exponential backoff
    (2s, 4s, 8s, 16s, 32s); permanent "No US location found" answers
    are not retried.
- `routing/management/commands/populate_station_coordinates.py`
  - Now uses the retry helper, so a full re-run is viable again.
- `routing/management/commands/populate_corridor_coordinates.py` (NEW)
  - Geocodes only stations in the given states (default: IL MO AR TN TX,
    the Chicago -> Dallas corridor). Resume-safe: skips already-geocoded
    cities, so your 302 done rows are kept.

## Ali's steps (on his PC, inside the project folder)
1. Unzip this pack INTO the existing project folder (do NOT delete the
   folder first — `db.sqlite3` with your 302 geocoded cities must stay).
2. Run:
   `python manage.py populate_corridor_coordinates`
   Takes ~10-20 minutes. If many SKIP lines appear, wait ~1 hour and
   re-run the same command (it resumes automatically).
3. Restart runserver and retry Postman:
   POST http://127.0.0.1:8000/route/
   {"start": "Chicago, IL", "destination": "Dallas, TX"}
   Expect: `fuel_stops` non-empty, `estimated_fuel_cost` a number,
   status `optimized_with_verified_prices`.
4. Only then record the Loom demo.

Optional: `--states IL MO AR TN TX MS OK` to widen, `--limit 50` to test.
