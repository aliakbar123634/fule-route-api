import time

import requests
from django.db import DatabaseError

from routing.models import GeocodeCache


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "FuelRouteAssessment/1.0 (Django routing application)"

# Nominatim public policy: maximum one request per second.
_MIN_REQUEST_INTERVAL = 1.1
_last_request_time = 0.0


class GeocodingError(Exception):
    """Raised when a location cannot be geocoded."""


# A "no result" answer is permanent for that query; everything else
# (HTTP errors, timeouts, connection drops, rate-limit blocks) is
# treated as transient and worth retrying.
_PERMANENT_FAILURE_MARKER = "No US location found"


def get_coordinates_with_retry(
    query,
    max_attempts=5,
    base_delay_seconds=2.0,
    max_delay_seconds=60.0,
):
    """
    Geocode a query, retrying transient failures with exponential backoff.

    Raises GeocodingError if every attempt fails. Queries that Nominatim
    answers with "no result" are not retried.
    """
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            return get_coordinates(query)
        except GeocodingError as exc:
            last_error = exc

            if _PERMANENT_FAILURE_MARKER in str(exc):
                raise

            if attempt == max_attempts:
                break

            delay = min(
                base_delay_seconds * (2 ** (attempt - 1)),
                max_delay_seconds,
            )
            time.sleep(delay)

    raise last_error


def get_coordinates(location):
    """
    Return (latitude, longitude) for a location.

    Cached results are reused. Only cache misses call Nominatim.
    """
    global _last_request_time

    if not isinstance(location, str) or not location.strip():
        raise ValueError("Location must be a non-empty string.")

    query = " ".join(location.split())

    # 1. Check the database cache first.
    try:
        cached = GeocodeCache.objects.filter(
            query__iexact=query
        ).first()
    except DatabaseError as exc:
        raise GeocodingError("Could not read geocoding cache.") from exc

    if cached:
        return cached.latitude, cached.longitude

    # 2. Call Nominatim only on a cache miss.
    wait = _MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request_time)
    if wait > 0:
        time.sleep(wait)

    headers = {"User-Agent": USER_AGENT}
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "us",
    }

    try:
        response = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=headers,
            timeout=15,
        )
        _last_request_time = time.monotonic()
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise GeocodingError(
            "Geocoding service request failed."
        ) from exc

    if not results:
        raise GeocodingError(f"No US location found for: {query}")

    try:
        latitude = float(results[0]["lat"])
        longitude = float(results[0]["lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError(
            "Geocoding service returned invalid coordinates."
        ) from exc

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise GeocodingError("Geocoding service returned out-of-range coordinates.")

    # 3. Save the result so future requests use the cache.
    try:
        cached, _ = GeocodeCache.objects.update_or_create(
            query=query,
            defaults={
                "latitude": latitude,
                "longitude": longitude,
            },
        )
    except DatabaseError as exc:
        raise GeocodingError("Could not save geocoding cache.") from exc

    return cached.latitude, cached.longitude
