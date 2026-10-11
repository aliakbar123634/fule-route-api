from math import isfinite

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from routing.models import Station
from routing.serializers import RouteRequestSerializer
from routing.services.fuel_stop_service import (
    filter_stations_near_route,
)
from routing.services.route_service import (
    get_route_by_location,
    RouteServiceError,
)
from routing.services.geocoding_service import GeocodingError
from routing.services.route_station_service import (
    find_stations_along_route,
)
from routing.services.station_location_service import (
    StationLocationError,
)


VEHICLE_MAX_RANGE_MILES = 500
FUEL_ECONOMY_MPG = 10
STATION_CORRIDOR_MILES = 10


def get_db_priced_stations(route_coordinates, corridor_miles=STATION_CORRIDOR_MILES):
    """
    Build the verified-price station set from the assessment CSV data
    stored in the database.

    The CSV is the assessment's own price list, so these prices are
    treated as verified (price_verified=True). Only stations with
    geocoded coordinates take part — run
    `python manage.py populate_station_coordinates` after loading the CSV.

    A bounding-box prefilter keeps the corridor projection cheap before
    the precise nearest-segment filter runs.
    """
    if not route_coordinates or len(route_coordinates) < 2:
        return []

    longitudes = [c[0] for c in route_coordinates]
    latitudes = [c[1] for c in route_coordinates]

    # ~69 miles per degree of latitude; pad the box by the corridor.
    pad = corridor_miles / 69.0 + 0.5
    lat_min, lat_max = min(latitudes) - pad, max(latitudes) + pad
    lon_min, lon_max = min(longitudes) - pad, max(longitudes) + pad

    candidates = []
    queryset = Station.objects.exclude(
        latitude__isnull=True
    ).exclude(
        longitude__isnull=True
    )

    for db_station in queryset.iterator():
        if not (
            lat_min <= db_station.latitude <= lat_max
            and lon_min <= db_station.longitude <= lon_max
        ):
            continue

        try:
            price = float(db_station.retail_price)
        except (TypeError, ValueError):
            continue

        if not isfinite(price) or price <= 0:
            continue

        candidates.append({
            "truckstop_id": db_station.truckstop_id,
            "name": db_station.name,
            "city": db_station.city,
            "state": db_station.state,
            "retail_price": price,
            "latitude": db_station.latitude,
            "longitude": db_station.longitude,
            # CSV prices are the assessment's verified price list.
            "price_verified": True,
        })

    if not candidates:
        return []

    # Adds route_position_miles and keeps the corridor filter.
    return filter_stations_near_route(
        candidates,
        route_coordinates,
        corridor_miles=corridor_miles,
    )


def get_verified_priced_stations(stations):
    """
    Only accept stations with explicitly verified, positive prices
    and a valid route position.
    """
    verified_stations = []

    for station in stations:
        if station.get("price_verified") is not True:
            continue

        try:
            price = float(station.get("retail_price"))
        except (TypeError, ValueError):
            continue

        if not isfinite(price) or price <= 0:
            continue

        try:
            route_position = float(station.get("route_position_miles"))
        except (TypeError, ValueError):
            continue

        if not isfinite(route_position) or route_position < 0:
            continue

        verified_stations.append({
            **station,
            "retail_price": price,
            "route_position_miles": route_position,
        })

    return verified_stations


@api_view(["POST"])
def route_api(request):
    serializer = RouteRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    start = serializer.validated_data["start"]
    destination = serializer.validated_data["destination"]

    # 1. Calculate the driving route.
    try:
        result = get_route_by_location(start, destination)
    except (RouteServiceError, GeocodingError) as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    distance_miles = float(result["distance_miles"])
    duration_hours = float(result["duration_seconds"]) / 3600
    estimated_gallons = distance_miles / FUEL_ECONOMY_MPG
    route_coordinates = result["geometry"]["coordinates"]

    # 2. Verified prices come from the assessment CSV in the database.
    db_stations = get_db_priced_stations(
        route_coordinates,
        corridor_miles=STATION_CORRIDOR_MILES,
    )
    priced_stations = get_verified_priced_stations(db_stations)

    # 3. OSM discovery adds extra (unverified) candidates only.
    stations = []

    try:
        stations = find_stations_along_route(
            route_coordinates=route_coordinates,
            corridor_miles=STATION_CORRIDOR_MILES,
            sample_spacing_miles=50,
            search_radius_miles=5,
        )

        if stations is None:
            stations = []

    except (StationLocationError, TimeoutError, OSError):
        stations = []

    fuel_stops = []
    estimated_fuel_cost = None

    fuel_status = "prices_not_verified"
    fuel_message = (
        "Route calculated successfully. "
        "No verified-price stations were found in the route corridor. "
        "Run `python manage.py populate_station_coordinates` after "
        "loading the CSV so the optimizer has priced stations."
    )

    # 4. Optimize only with verified prices.
    if priced_stations:
        from routing.services.fuel_stop_service import (
            select_fuel_stops,
        )

        try:
            optimization = select_fuel_stops(
                route_distance_miles=distance_miles,
                candidate_stations=priced_stations,
                max_range_miles=VEHICLE_MAX_RANGE_MILES,
                fuel_economy_mpg=FUEL_ECONOMY_MPG,
            )

            fuel_stops = optimization.get("stops", [])
            estimated_fuel_cost = optimization.get(
                "estimated_fuel_cost"
            )

            fuel_status = "optimized_with_verified_prices"
            fuel_message = (
                "Fuel-stop optimization used verified CSV station prices."
            )

        except ValueError:
            fuel_status = "no_feasible_verified_station_route"
            fuel_message = (
                "No feasible fuel-stop route was found using the "
                "currently verified stations."
            )

    elif not stations and not db_stations:
        fuel_status = "station_discovery_failed_or_empty"
        fuel_message = (
            "The route was calculated, but no stations were found. "
            "OSM discovery failed and no geocoded CSV stations exist."
        )

    # 5. Return route and diagnostic information.
    return Response(
        {
            "start": result["start"],
            "destination": result["destination"],
            "total_distance_miles": round(distance_miles, 2),
            "estimated_duration_hours": round(duration_hours, 2),
            "fuel_requirements": {
                "vehicle_max_range_miles": VEHICLE_MAX_RANGE_MILES,
                "fuel_economy_mpg": FUEL_ECONOMY_MPG,
                "estimated_trip_gallons": round(
                    estimated_gallons, 2
                ),
                "intermediate_stops_required_by_range": (
                    distance_miles > VEHICLE_MAX_RANGE_MILES
                ),
                "status": fuel_status,
                "message": fuel_message,
                "estimated_fuel_cost": estimated_fuel_cost,
                "cost_currency": "USD",
                "cost_scope": (
                    "Assumes the vehicle starts with a full tank; "
                    "total reflects fuel purchased en route only."
                ),
            },
            "fuel_stops": fuel_stops,
            "fuel_station_candidates": stations,
            "fuel_station_count": len(stations),
            "verified_priced_station_count": len(priced_stations),
            "route_geometry": result["geometry"],
        },
        status=status.HTTP_200_OK,
    )
