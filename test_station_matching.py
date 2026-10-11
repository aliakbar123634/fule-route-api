
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from routing.services.station_matching_service import (
    find_unique_name_candidate,
)
from routing.services.station_location_service import (
    get_fuel_stations_nearby,
)

# Dallas, Texas
stations = get_fuel_stations_nearby(
    latitude=32.7767,
    longitude=-96.7970,
    radius_meters=10000,
)

counts = {
    "candidate_for_review": 0,
    "ambiguous": 0,
    "unmatched": 0,
}

for station in stations:
    result = find_unique_name_candidate(
        osm_station=station,
        state="TX",
    )
    counts[result["status"]] += 1

print("OSM stations:", len(stations))
print("Matching report:", counts)
print("Note: Candidates are not verified price matches.")
