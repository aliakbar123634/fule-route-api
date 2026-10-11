
import requests


OSRM_BASE_URL = "https://router.project-osrm.org"
from routing.services.geocoding_service import get_coordinates

class RouteServiceError(Exception):
    """Raised when route calculation fails."""


def get_route(start_lon, start_lat, end_lon, end_lat):
    """
    Get a driving route from OSRM.

    Coordinates are supplied as latitude/longitude, but OSRM
    expects longitude,latitude in its URL.

    Returns:
        dict: Distance in meters and miles, duration in seconds,
              and GeoJSON route geometry.
    """
    coordinates = (
        start_lon,
        start_lat,
        end_lon,
        end_lat,
    )

    if not all(-180 <= value <= 180 for value in coordinates):
        raise ValueError("Coordinates must be valid longitude/latitude values.")

    if not (-90 <= start_lat <= 90 and -90 <= end_lat <= 90):
        raise ValueError("Latitude must be between -90 and 90.")

    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
    )

    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise RouteServiceError(
            "Unable to connect to the routing service."
        ) from exc
    except ValueError as exc:
        raise RouteServiceError(
            "Routing service returned invalid JSON."
        ) from exc

    if data.get("code") != "Ok" or not data.get("routes"):
        raise RouteServiceError(
            f"No route found. OSRM response: {data.get('code', 'Unknown error')}"
        )

    route = data["routes"][0]
    distance_meters = route["distance"]

    return {
        "distance_meters": distance_meters,
        "distance_miles": distance_meters / 1609.344,
        "duration_seconds": route["duration"],
        "geometry": route["geometry"],
    }






def get_route_by_location(start, destination):
    """
    Geocode two US locations and calculate the driving route.
    """
    start_lat, start_lon = get_coordinates(start)
    end_lat, end_lon = get_coordinates(destination)

    route = get_route(
        start_lon=start_lon,
        start_lat=start_lat,
        end_lon=end_lon,
        end_lat=end_lat,
    )

    return {
        "start": start,
        "destination": destination,
        **route,
    }
