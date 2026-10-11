
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from routing.models import Station


class Command(BaseCommand):
    help = "Import fuel stations from the assessment CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            required=True,
            help="Path to the fuel prices CSV file",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv"])

        if not csv_path.is_file():
            raise CommandError(f"CSV file not found: {csv_path}")

        created_count = 0
        updated_count = 0
        skipped_count = 0

        try:
            with csv_path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as file:
                reader = csv.DictReader(file)

                required_columns = {
                    "OPIS Truckstop ID",
                    "Truckstop Name",
                    "Address",
                    "City",
                    "State",
                    "Retail Price",
                }

                actual_columns = set(reader.fieldnames or [])
                missing_columns = required_columns - actual_columns

                if missing_columns:
                    raise CommandError(
                        f"Missing CSV columns: {sorted(missing_columns)}"
                    )

                with transaction.atomic():
                    for row in reader:
                        truckstop_id = (
                            row["OPIS Truckstop ID"] or ""
                        ).strip()

                        name = (row["Truckstop Name"] or "").strip()
                        address = (row["Address"] or "").strip()
                        city = (row["City"] or "").strip()
                        state = (row["State"] or "").strip().upper()

                        try:
                            price = Decimal(
                                (row["Retail Price"] or "").strip()
                            )
                        except (InvalidOperation, ValueError):
                            skipped_count += 1
                            continue

                        if (
                            not truckstop_id
                            or not name
                            or not city
                            or len(state) != 2
                            or not price.is_finite()
                            or price <= 0
                        ):
                            skipped_count += 1
                            continue

                        station, created = Station.objects.update_or_create(
                            truckstop_id=truckstop_id,
                            defaults={
                                "name": name,
                                "address": address,
                                "city": city,
                                "state": state,
                                "retail_price": price,
                            },
                        )

                        if created:
                            created_count += 1
                        else:
                            updated_count += 1

        except UnicodeDecodeError as exc:
            raise CommandError(
                "CSV encoding could not be read."
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete. Created: {created_count}, "
                f"Updated: {updated_count}, Skipped: {skipped_count}"
            )
        )
