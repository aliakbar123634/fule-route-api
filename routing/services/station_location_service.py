import math
import time

import requests
from django.core.cache import cache


OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

USER_AGENT = "FuelRouteAssessment/1.0 (fuel route assessment)"
CACHE_TIMEOUT_SECONDS = 3600
REQUEST_TIMEOUT = (5, 25)


class StationLocationError(Exception):
    """Raised when fuel station location lookup fails."""


def get_fuel_stations_nearby(
    latitude,
    longitude,
    radius_meters=5000,
):
    try:
        latitude = float(latitude)
        longitude = float(longitude)
        radius_meters = int(radius_meters)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid coordinates or radius.") from exc

    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("Invalid latitude.")

    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Invalid longitude.")

    if not 100 <= radius_meters <= 50000:
        raise ValueError("Radius must be between 100 and 50000 meters.")

    cache_key = (
        f"osm_fuel_stations_v2:"
        f"{latitude:.4f}:{longitude:.4f}:{radius_meters}"
    )

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    query = f"""
    [out:json][timeout:20];
    (
      nwr["amenity"="fuel"]
        (around:{radius_meters},{latitude},{longitude});
    );
    out center tags;
    """

    last_error = None
    data = None

    for endpoint in OVERPASS_URLS:
        try:
            response = requests.post(
                endpoint,
                data={"data": query},
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, dict):
                raise ValueError("Invalid Overpass response.")

            elements = payload.get("elements")
            if not isinstance(elements, list):
                raise ValueError("Missing Overpass elements list.")

            # A valid empty response is a successful lookup.
            data = payload
            break

        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            print(
                f"[Overpass] Endpoint failed: {endpoint}; "
                f"{type(exc).__name__}: {exc}"
            )

    if data is None:
        raise StationLocationError(
            "All Overpass endpoints failed."
        ) from last_error

    stations_by_id = {}

    for element in data["elements"]:
        tags = element.get("tags") or {}

        if not isinstance(tags, dict):
            continue

        lat = element.get("lat")
        lon = element.get("lon")

        if lat is None or lon is None:
            center = element.get("center") or {}
            lat = center.get("lat")
            lon = center.get("lon")

        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError, OverflowError):
            continue

        if not (
            math.isfinite(lat)
            and math.isfinite(lon)
            and -90 <= lat <= 90
            and -180 <= lon <= 180
        ):
            continue

        osm_type = element.get("type")
        osm_id = element.get("id")

        if osm_type is None or osm_id is None:
            continue

        stations_by_id[(osm_type, osm_id)] = {
            "osm_type": osm_type,
            "osm_id": osm_id,
            "name": tags.get("name", "Unnamed"),
            "brand": tags.get("brand"),
            "latitude": lat,
            "longitude": lon,
        }

    stations = list(stations_by_id.values())

    # Cache valid responses, including empty responses.
    cache.set(
        cache_key,
        stations,
        timeout=CACHE_TIMEOUT_SECONDS,
    )

    print(
        f"[Overpass] {len(stations)} stations near "
        f"({latitude}, {longitude}), radius={radius_meters}m"
    )

    return stations
