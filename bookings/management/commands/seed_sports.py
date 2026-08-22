from django.core.management.base import BaseCommand

from bookings.models import Sport
from bookings.slots import ensure_upcoming_slots

SPORTS = [
    {
        "name": "Tennis",
        "slug": "tennis",
        "tagline": "Hard courts, floodlights, book by the hour.",
        "court_details": (
            "Two outdoor hard courts with floodlights. "
            "Nets, scoring, and seating around the court are provided. "
            "Bring your own racquets and balls, or rent them at the front desk."
        ),
        "timings": "Open daily 6:00 AM – 10:00 PM. Slots are 1 hour.",
        "rules": (
            "Maximum 4 players per booking. Wear non-marking shoes. "
            "Pay at the venue before play. Cancel from My Bookings if your plans change. "
            "One active booking per customer at a time."
        ),
    },
    {
        "name": "Cricket",
        "slug": "cricket",
        "tagline": "Net practice on a turf pitch, hour by hour.",
        "court_details": (
            "Covered practice nets on a turf pitch with bowling machine available on request "
            "at the venue. Stumps and a practice kit can be borrowed from staff."
        ),
        "timings": "Open daily 6:00 AM – 10:00 PM. Slots are 1 hour.",
        "rules": (
            "Maximum 4 players per booking. Wear sports shoes (no spikes). "
            "Pay at the venue before play. Cancel from My Bookings if your plans change. "
            "One active booking per customer at a time."
        ),
    },
]


class Command(BaseCommand):
    help = "Create Tennis and Cricket sports and generate upcoming slots."

    def handle(self, *args, **options):
        for data in SPORTS:
            sport, created = Sport.objects.update_or_create(
                slug=data["slug"], defaults=data
            )
            verb = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{verb} {sport.name}"))
        ensure_upcoming_slots()
        self.stdout.write(self.style.SUCCESS("Upcoming slots are ready."))
