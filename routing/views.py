

# from math import isfinite

# from rest_framework.decorators import api_view
# from rest_framework.response import Response
# from rest_framework import status

# from routing.serializers import RouteRequestSerializer
# from routing.services.route_service import (
#     get_route_by_location,
#     RouteServiceError,
# )
# from routing.services.geocoding_service import GeocodingError
# from routing.services.route_station_service import (
#     find_stations_along_route,
# )
# from routing.services.station_location_service import (
#     StationLocationError,
# )


# VEHICLE_MAX_RANGE_MILES = 500
# FUEL_ECONOMY_MPG = 10


# def get_verified_priced_stations(stations):
#     """
#     Only accept stations with explicitly verified, positive prices
#     and a valid route position.
#     """
#     verified_stations = []

#     for station in stations:
#         if station.get("price_verified") is not True:
#             continue

#         try:
#             price = float(station.get("retail_price"))
#         except (TypeError, ValueError):
#             continue

#         if not isfinite(price) or price <= 0:
#             continue

#         try:
#             route_position = float(station.get("route_position_miles"))
#         except (TypeError, ValueError):
#             continue

#         if not isfinite(route_position) or route_position < 0:
#             continue

#         verified_stations.append({
#             **station,
#             "retail_price": price,
#             "route_position_miles": route_position,
#         })

#     return verified_stations


# @api_view(["POST"])
# def route_api(request):
#     serializer = RouteRequestSerializer(data=request.data)
#     serializer.is_valid(raise_exception=True)

#     start = serializer.validated_data["start"]
#     destination = serializer.validated_data["destination"]

#     # 1. Calculate the driving route.
#     try:
#         result = get_route_by_location(start, destination)
#     except (RouteServiceError, GeocodingError) as exc:
#         return Response(
#             {"error": str(exc)},
#             status=status.HTTP_502_BAD_GATEWAY,
#         )

#     distance_miles = float(result["distance_miles"])
#     duration_hours = float(result["duration_seconds"]) / 3600
#     estimated_gallons = distance_miles / FUEL_ECONOMY_MPG

#     # 2. Discover stations along the route.
#     stations = []

#     try:
#         stations = find_stations_along_route(
#             route_coordinates=result["geometry"]["coordinates"],
#             corridor_miles=10,
#             sample_spacing_miles=50,
#             search_radius_miles=10,
#         )

#         if stations is None:
#             stations = []

#         print(
#             f"[Station Discovery] Found {len(stations)} stations "
#             f"for route: {start} -> {destination}"
#         )

#     except (StationLocationError, TimeoutError, OSError) as exc:
#         print(
#             f"[Station Discovery Error] "
#             f"{type(exc).__name__}: {exc}"
#         )
#         stations = []

#     # 3. Do not trust unverified CSV prices.
#     priced_stations = get_verified_priced_stations(stations)

#     fuel_stops = []
#     estimated_fuel_cost = None

#     fuel_status = "prices_not_verified"
#     fuel_message = (
#         "Route calculated successfully. Station candidates are returned "
#         "when discovery succeeds, but CSV prices must be verified before "
#         "fuel-cost optimization."
#     )

#     # 4. Optimize only with verified prices.
#     if priced_stations:
#         from routing.services.fuel_stop_service import (
#             select_fuel_stops,
#         )

#         try:
#             optimization = select_fuel_stops(
#                 route_distance_miles=distance_miles,
#                 candidate_stations=priced_stations,
#                 max_range_miles=VEHICLE_MAX_RANGE_MILES,
#                 fuel_economy_mpg=FUEL_ECONOMY_MPG,
#             )

#             fuel_stops = optimization.get("stops", [])
#             estimated_fuel_cost = optimization.get(
#                 "estimated_fuel_cost"
#             )

#             fuel_status = "optimized_with_verified_prices"
#             fuel_message = (
#                 "Fuel-stop optimization used explicitly verified "
#                 "station prices."
#             )

#         except ValueError as exc:
#             print(f"[Fuel Optimization Error] {exc}")

#             fuel_status = "no_feasible_verified_station_route"
#             fuel_message = (
#                 "No feasible fuel-stop route was found using the "
#                 "currently verified stations."
#             )

#     elif not stations:
#         fuel_status = "station_discovery_failed_or_empty"
#         fuel_message = (
#             "The route was calculated, but station discovery returned "
#             "no stations. Check the Django server terminal for "
#             "the Station Discovery log."
#         )

#     # 5. Return route and diagnostic information.
#     return Response(
#         {
#             "start": result["start"],
#             "destination": result["destination"],
#             "total_distance_miles": round(distance_miles, 2),
#             "estimated_duration_hours": round(duration_hours, 2),
#             "fuel_requirements": {
#                 "vehicle_max_range_miles": VEHICLE_MAX_RANGE_MILES,
#                 "fuel_economy_mpg": FUEL_ECONOMY_MPG,
#                 "estimated_trip_gallons": round(
#                     estimated_gallons, 2
#                 ),
#                 "intermediate_stops_required_by_range": (
#                     distance_miles > VEHICLE_MAX_RANGE_MILES
#                 ),
#                 "status": fuel_status,
#                 "message": fuel_message,
#                 "estimated_fuel_cost": estimated_fuel_cost,
#                 "cost_currency": "USD",
#                 "cost_scope": (
#                     "Intermediate refueling only; initial tank cost "
#                     "is not included by the current optimizer."
#                 ),
#             },
#             "fuel_stops": fuel_stops,
#             "fuel_station_candidates": stations,
#             "fuel_station_count": len(stations),
#             "verified_priced_station_count": len(priced_stations),
#             "route_geometry": result["geometry"],
#         },
#         status=status.HTTP_200_OK,
#     )




from math import isfinite

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from routing.serializers import RouteRequestSerializer
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

    # 2. Discover stations along the route.
    stations = []

    try:
        stations = find_stations_along_route(
            route_coordinates=result["geometry"]["coordinates"],
            corridor_miles=10,
            sample_spacing_miles=50,
            search_radius_miles=10,
        )

        if stations is None:
            stations = []

        print(
            f"[Station Discovery] Found {len(stations)} stations "
            f"for route: {start} -> {destination}"
        )

    except (StationLocationError, TimeoutError, OSError) as exc:
        print(
            f"[Station Discovery Error] "
            f"{type(exc).__name__}: {exc}"
        )
        stations = []

    # 3. Do not trust unverified CSV prices.
    priced_stations = get_verified_priced_stations(stations)

    fuel_stops = []
    estimated_fuel_cost = None

    fuel_status = "prices_not_verified"
    fuel_message = (
        "Route calculated successfully. Station candidates are returned "
        "when discovery succeeds, but CSV prices must be verified before "
        "fuel-cost optimization."
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
                "Fuel-stop optimization used explicitly verified "
                "station prices."
            )

        except ValueError as exc:
            print(f"[Fuel Optimization Error] {exc}")

            fuel_status = "no_feasible_verified_station_route"
            fuel_message = (
                "No feasible fuel-stop route was found using the "
                "currently verified stations."
            )

    elif not stations:
        fuel_status = "station_discovery_failed_or_empty"
        fuel_message = (
            "The route was calculated, but station discovery returned "
            "no stations. Check the Django server terminal for "
            "the Station Discovery log."
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
                    "Intermediate refueling only; initial tank cost "
                    "is not included by the current optimizer."
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
