
from pathlib import Path

from django.core.management.base import BaseCommand
from routing.models import Station


class Command(BaseCommand):
    help = "Preview safe GeoNames city coordinate matches"

    def handle(self, *args, **options):
        file_path = Path("data/US.txt")

        if not file_path.exists():
            self.stderr.write(f"File not found: {file_path}")
            return

        stations = Station.objects.filter(
            latitude__isnull=True,
            longitude__isnull=True,
        ).values("city", "state").distinct()

        targets = {
            (item["city"].strip().casefold(), item["state"].strip().upper())
            for item in stations
            if item["city"] and item["city"].strip()
        }

        matches = {}

        self.stdout.write("Reading GeoNames dataset...")

        with file_path.open(encoding="utf-8") as file:
            for line in file:
                row = line.rstrip("\n").split("\t")

                if len(row) < 15:
                    continue

                if row[6] != "P" or row[8] != "US":
                    continue

                key = (
                    row[1].strip().casefold(),
                    row[10].strip().upper(),
                )

                if key not in targets:
                    continue

                try:
                    latitude = float(row[4])
                    longitude = float(row[5])
                except ValueError:
                    continue

                if not (-90 <= latitude <= 90):
                    continue
                if not (-180 <= longitude <= 180):
                    continue

                matches.setdefault(key, []).append({
                    "name": row[1],
                    "latitude": latitude,
                    "longitude": longitude,
                    "feature_code": row[7],
                })

        safe_matches = {}
        ambiguous = {}

        preferred_codes = {"PPLA", "PPLA2", "PPLA3", "PPLA4"}

        for key, places in matches.items():
            if len(places) == 1:
                safe_matches[key] = places[0]
                continue

            preferred = [
                place for place in places
                if place["feature_code"] in preferred_codes
            ]

            if len(preferred) == 1:
                safe_matches[key] = preferred[0]
            else:
                ambiguous[key] = places

        unmatched = targets - set(matches)

        self.stdout.write("\n--- Safe Matching Report ---")
        self.stdout.write(f"Total city/state pairs: {len(targets)}")
        self.stdout.write(f"Safe candidate matches: {len(safe_matches)}")
        self.stdout.write(f"Still ambiguous: {len(ambiguous)}")
        self.stdout.write(f"Unmatched: {len(unmatched)}")

        self.stdout.write("\nSample selected candidates:")
        for key, place in list(safe_matches.items())[:10]:
            self.stdout.write(f"{key}: {place}")

        self.stdout.write("\nSample unresolved cities:")
        for key, places in list(ambiguous.items())[:5]:
            self.stdout.write(f"{key}: {places[:3]}")

        self.stdout.write(
            "\nPreview only: database was not modified."
        )


