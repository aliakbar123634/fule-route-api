
from pathlib import Path
import os
import django

# Django settings initialize karo
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from routing.models import Station


def main():
    # Texas ke unique fuel-station city names
    targets = set(
        Station.objects.filter(state="TX")
        .values_list("city", flat=True)
    )

    # Case-insensitive lookup: McAllen aur Mcallen ko match kar sake
    target_lookup = {
        city.strip().casefold(): city
        for city in targets
        if city and city.strip()
    }

    found = {}

    file_path = Path("data/US.txt")

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        return

    print("Reading GeoNames file...")

    # File ko line-by-line read karo; poori file memory mein nahi aayegi
    with file_path.open(encoding="utf-8") as file:
        for line in file:
            row = line.rstrip("\n").split("\t")

            # Required columns available hain?
            if len(row) <= 10:
                continue

            # Column 6 = feature class; P means populated place
            # Column 10 = state/admin code
            if row[6] != "P" or row[10] != "TX":
                continue

            city_key = row[1].strip().casefold()
            matched_city = target_lookup.get(city_key)

            if not matched_city:
                continue

            try:
                latitude = float(row[4])
                longitude = float(row[5])
            except ValueError:
                continue

            # Invalid coordinates ignore karo
            if not (-90 <= latitude <= 90):
                continue

            if not (-180 <= longitude <= 180):
                continue

            # Agar same city ke multiple records hon, pehla match rakho
            found.setdefault(
                matched_city,
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "feature_code": row[7],
                    "geonames_name": row[1],
                },
            )

    unmatched = sorted(targets - set(found))

    print("\n--- Texas City Matching Results ---")
    print(f"Texas station cities: {len(targets)}")
    print(f"Matched city names: {len(found)}")
    print(f"Unmatched city names: {len(unmatched)}")

    print("\nSample matches:")
    for city, details in list(found.items())[:15]:
        print(f"{city}: {details}")

    print("\nUnmatched cities:")
    print(unmatched[:20])


if __name__ == "__main__":
    main()
