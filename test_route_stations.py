
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from routing.services.route_service import get_route_by_location
from routing.services.route_station_service import (
    find_stations_along_route,
)

route = get_route_by_location(
    start="Dallas, TX",
    destination="Fort Worth, TX",
)

print("Route distance:", round(route["distance_miles"], 2), "miles")

stations = find_stations_along_route(
    route_coordinates=route["geometry"]["coordinates"],
    corridor_miles=5,
    sample_spacing_miles=100,
    search_radius_miles=5,
)

print("OSM candidates near route:", len(stations))

for station in stations[:10]:
    print({
        "name": station.get("name"),
        "osm_id": station.get("osm_id"),
        "distance_from_route_miles": station.get(
            "distance_from_route_miles"
        ),
        "route_position_miles": station.get("route_position_miles"),
    })
