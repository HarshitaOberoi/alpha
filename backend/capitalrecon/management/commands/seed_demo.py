from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from capitalrecon.models import CapitalCall, LineItem, Organization

SEED_DATA = [
    {
        "org_slug": "northwind",
        "org_name": "Northwind Ventures",
        "calls": [
            {
                "number": 1,
                "call_date": date(2026, 3, 25),
                "due_date": date(2026, 4, 10),
                "line_items": [
                    ("Haller Capital LLC", "CC-1001", "27500.00"),
                    ("Rahul Shah Trust", "CC-1002", "25000.00"),
                    ("Patel Family Trust", "CC-1003", "12500.00"),
                    ("Meridian Partners LP", "CC-1004", "15000.00"),
                    ("Oakridge Holdings LLC", "CC-1005", "15000.00"),
                ],
            },
            {
                "number": 2,
                "call_date": date(2026, 4, 1),
                "due_date": date(2026, 4, 20),
                "line_items": [
                    ("Oakridge Holdings LLC", "CC-1006", "15000.00"),
                ],
            },
        ],
    },
    {
        "org_slug": "bluebird",
        "org_name": "Bluebird Capital",
        "calls": [
            {
                "number": 1,
                "call_date": date(2026, 4, 1),
                "due_date": date(2026, 4, 15),
                "line_items": [
                    ("Cedar Grove Fund LP", "CC-2001", "40000.00"),
                ],
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Seed demo data (idempotent)."

    def handle(self, *args, **options):
        for org_spec in SEED_DATA:
            org, _ = Organization.objects.get_or_create(
                slug=org_spec["org_slug"],
                defaults={"name": org_spec["org_name"]},
            )
            for call_spec in org_spec["calls"]:
                call, _ = CapitalCall.objects.get_or_create(
                    organization=org,
                    call_number=call_spec["number"],
                    defaults={
                        "call_date": call_spec["call_date"],
                        "due_date": call_spec["due_date"],
                    },
                )
                for investor, ref, amount in call_spec["line_items"]:
                    LineItem.objects.get_or_create(
                        organization=org,
                        reference=ref,
                        defaults={
                            "capital_call": call,
                            "investor_entity": investor,
                            "amount_called": Decimal(amount),
                            "amount_funded": Decimal("0.00"),
                            "status": LineItem.STATUS_OPEN,
                        },
                    )
        self.stdout.write(self.style.SUCCESS("Demo data seeded."))
