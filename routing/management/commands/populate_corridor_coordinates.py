from django.core.management.base import BaseCommand

from routing.models import Station
from routing.services.geocoding_service import (
    get_coordinates_with_retry,
    GeocodingError,
)


# Default corridor for the Chicago -> Dallas demo route
# (I-57 / I-55 / I-40 / I-30). Stations anywhere inside these
# states can fall within the 10-mile route corridor.
DEFAULT_CORRIDOR_STATES = ["IL", "MO", "AR", "TN", "TX"]


class Command(BaseCommand):
    help = (
        "Geocode only the station cities in the given US states "
        "(default: the Chicago->Dallas corridor states), with "
        "retries and exponential backoff for transient Nominatim "
        "failures. Run this instead of populate_station_coordinates "
        "when the full run was rate-limited: it is resume-safe, "
        "skips already-geocoded cities, and finishes much faster."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--states",
            nargs="+",
            default=DEFAULT_CORRIDOR_STATES,
            help=(
                "State codes to geocode (default: "
                + " ".join(DEFAULT_CORRIDOR_STATES)
                + ")."
            ),
        )
        parser.add_argument(
            "--retries",
            type=int,
            default=5,
            help="Attempts per city before giving up (default: 5).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help=(
                "Geocode at most this many cities, then stop. "
                "0 means no limit (default)."
            ),
        )

    def handle(self, *args, **options):
        states = {
            str(state).strip().upper()
            for state in options["states"]
            if str(state).strip()
        }
        max_attempts = max(1, options["retries"])
        limit = max(0, options["limit"])

        targets = (
            Station.objects.filter(
                latitude__isnull=True,
                longitude__isnull=True,
                state__in=states,
            )
            .values("city", "state")
            .distinct()
            .order_by("state", "city")
        )

        pairs = [
            (item["city"].strip(), item["state"].strip().upper())
            for item in targets
            if item["city"] and item["city"].strip()
            and item["state"] and len(item["state"].strip()) == 2
        ]

        if limit:
            pairs = pairs[:limit]

        total = len(pairs)
        self.stdout.write(
            f"Geocoding {total} corridor city/state pairs "
            f"in {sorted(states)} (resume-safe; already-geocoded "
            "cities are skipped)..."
        )

        done = 0
        failed = 0

        for city, state in pairs:
            query = f"{city}, {state}"

            try:
                latitude, longitude = get_coordinates_with_retry(
                    query,
                    max_attempts=max_attempts,
                )
            except (GeocodingError, ValueError) as exc:
                failed += 1
                self.stdout.write(f"  SKIP {query}: {exc}")
                continue

            Station.objects.filter(
                city__iexact=city,
                state__iexact=state,
                latitude__isnull=True,
                longitude__isnull=True,
            ).update(latitude=latitude, longitude=longitude)

            done += 1
            if done % 25 == 0:
                self.stdout.write(f"  ... {done}/{total}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Geocoded {done} cities, {failed} failed. "
                "Re-run any time to retry the failures."
            )
        )
