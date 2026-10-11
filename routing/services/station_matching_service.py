
import re
from difflib import SequenceMatcher

from routing.models import Station


# def normalize_name(value):
#     """Normalize names for cautious station matching."""
#     if not value:
#         return ""

#     value = value.casefold()
#     value = re.sub(r"[^a-z0-9]+", " ", value)
#     return " ".join(value.split())




def normalize_name(value):
    """Normalize station names for candidate matching."""
    if not value:
        return ""

    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = " ".join(value.split())

    # Remove common store-number suffixes, e.g. "#12345".
    value = re.sub(r"\b\d{3,}\b", " ", value)

    return " ".join(value.split())



def get_csv_station_candidates(osm_station, state, city=None):
    """
    Find possible CSV matches for an OSM station.

    A brand/name similarity is only a candidate, not proof of identity.
    This function never changes the database.
    """
    if not state or len(state.strip()) != 2:
        raise ValueError("A valid two-letter state code is required.")

    osm_name = normalize_name(osm_station.get("name"))
    osm_brand = normalize_name(osm_station.get("brand"))

    if not osm_name and not osm_brand:
        return []

    queryset = Station.objects.filter(state__iexact=state.strip())

    # City is an optional narrowing filter. OSM location data may not
    # include the city, so do not guess it from coordinates here.
    if city:
        queryset = queryset.filter(city__iexact=city.strip())

    candidates = []

    for csv_station in queryset.iterator():
        csv_name = normalize_name(csv_station.name)

        name_score = (
            SequenceMatcher(None, osm_name, csv_name).ratio()
            if osm_name and csv_name
            else 0.0
        )

        brand_score = 0.0
        if osm_brand and csv_name:
            brand_score = SequenceMatcher(
                None, osm_brand, csv_name
            ).ratio()

        score = max(name_score, brand_score)

        # Return only potential candidates; do not claim an exact match.
        if score >= 0.75:
            candidates.append({
                "truckstop_id": csv_station.truckstop_id,
                "csv_name": csv_station.name,
                "city": csv_station.city,
                "state": csv_station.state,
                "address": csv_station.address,
                "retail_price": str(csv_station.retail_price),
                "name_similarity": round(score, 3),
            })

    return sorted(
        candidates,
        key=lambda item: item["name_similarity"],
        reverse=True,
    )


def get_verified_csv_price(osm_station, state, city=None):
    """
    Return a CSV price only when there is exactly one strong candidate.

    Similarity alone cannot prove two records represent the same physical
    station. Therefore this function does not automatically verify a match.
    """
    candidates = get_csv_station_candidates(osm_station, state, city)

    return {
        "verified": False,
        "price": None,
        "candidates": candidates[:5],
        "reason": (
            "Name similarity alone cannot verify the exact physical station."
        ),
    }



def find_unique_name_candidate(osm_station, state, city=None):
    """
    Return one strong name candidate for manual review.
    This does not verify physical station identity.
    """
    candidates = get_csv_station_candidates(
        osm_station=osm_station,
        state=state,
        city=city,
    )

    if len(candidates) != 1:
        return {
            "status": "ambiguous" if candidates else "unmatched",
            "candidate": None,
            "message": (
                "Multiple candidates found; manual review required."
                if candidates
                else "No matching CSV candidate found."
            ),
        }

    return {
        "status": "candidate_for_review",
        "candidate": candidates[0],
        "message": (
            "Only one name candidate found, but exact station identity "
            "still requires address or location verification."
        ),
    }



def build_matching_report(osm_stations, state, city=None):
    """
    Compare OSM stations with CSV records.

    Results are candidates for review only. Name similarity does not
    prove the records refer to the same physical fuel station.
    """
    report = []

    for osm_station in osm_stations:
        result = find_unique_name_candidate(
            osm_station=osm_station,
            state=state,
            city=city,
        )

        report.append({
            "osm_name": osm_station.get("name"),
            "osm_brand": osm_station.get("brand"),
            "osm_latitude": osm_station.get("latitude"),
            "osm_longitude": osm_station.get("longitude"),
            "match_status": result["status"],
            "csv_candidate": result["candidate"],
            "reason": result["message"],
        })

    return report
