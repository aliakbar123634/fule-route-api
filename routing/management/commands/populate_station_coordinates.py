from django.core.management.base import BaseCommand

from routing.models import Station
from routing.services.geocoding_service import (
    get_coordinates,
    GeocodingError,
)


class Command(BaseCommand):
    help = (
        "Geocode distinct station cities (via cached Nominatim lookups) "
        "and save coordinates on the Station rows. Run once after "
        "load_stations. Takes ~15 minutes for ~900 cities on first run; "
        "results are cached in the database."
    )

    def handle(self, *args, **options):
        targets = (
            Station.objects.filter(
                latitude__isnull=True,
                longitude__isnull=True,
            )
            .values("city", "state")
            .distinct()
        )

        pairs = [
            (item["city"].strip(), item["state"].strip().upper())
            for item in targets
            if item["city"] and item["city"].strip()
            and item["state"] and len(item["state"].strip()) == 2
        ]

        total = len(pairs)
        self.stdout.write(f"Geocoding {total} distinct city/state pairs...")

        done = 0
        failed = 0

        for city, state in pairs:
            query = f"{city}, {state}"

            try:
                latitude, longitude = get_coordinates(query)
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
            if done % 50 == 0:
                self.stdout.write(f"  ... {done}/{total}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Geocoded {done} cities, {failed} failed."
            )
        )
