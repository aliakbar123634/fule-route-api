



from math import isfinite

from routing.services.station_location_service import (
    get_fuel_stations_nearby,
    StationLocationError,
)
from routing.services.fuel_stop_service import (
    filter_stations_near_route,
    build_route_distances,
)


MAX_ROUTE_LOOKUPS = 2
METERS_PER_MILE = 1609.344


def find_stations_along_route(
    route_coordinates,
    corridor_miles=5,
    sample_spacing_miles=100,
    search_radius_miles=5,
):
    """
    Find mapped fuel stations near sampled route coordinates.

    Limits external lookups to reduce pressure on the public Overpass API.
    This is an initial discovery strategy, not a guarantee of complete
    station coverage along the entire route.
    """
    for name, value in (
        ("corridor_miles", corridor_miles),
        ("sample_spacing_miles", sample_spacing_miles),
        ("search_radius_miles", search_radius_miles),
    ):
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{name} must be a positive finite number.")

    if search_radius_miles * METERS_PER_MILE > 50000:
        raise ValueError("Search radius cannot exceed 50,000 meters.")

    if not route_coordinates:
        return []

    cumulative_miles = build_route_distances(route_coordinates)

    if not cumulative_miles:
        return []

    total_distance = cumulative_miles[-1]

    # Limit external lookups. On long routes this means the route is
    # sampled more widely, so some stations may not be discovered.
    desired_intervals = max(
        1,
        int(total_distance / sample_spacing_miles),
    )
    interval_count = min(desired_intervals, MAX_ROUTE_LOOKUPS - 1)

    sample_positions = [
        total_distance * index / interval_count
        for index in range(interval_count + 1)
    ]

    stations_by_id = {}

    for sample_position in sample_positions:
        nearest_index = min(
            range(len(cumulative_miles)),
            key=lambda index: abs(
                cumulative_miles[index] - sample_position
            ),
        )

        longitude, latitude = route_coordinates[nearest_index]

        try:
            nearby_stations = get_fuel_stations_nearby(
                latitude=latitude,
                longitude=longitude,
                radius_meters=int(
                    search_radius_miles * METERS_PER_MILE
                ),
            )
        except StationLocationError:
            # Do not silently return partial results if a lookup fails.
            raise

        for station in nearby_stations:
            osm_type = station.get("osm_type")
            osm_id = station.get("osm_id")

            if osm_type is None or osm_id is None:
                continue

            stations_by_id[(osm_type, osm_id)] = station

    return filter_stations_near_route(
        list(stations_by_id.values()),
        route_coordinates,
        corridor_miles=corridor_miles,
    )
