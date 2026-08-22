from datetime import date, datetime, time, timedelta

from django.utils import timezone

from .constants import SLOT_END_HOUR, SLOT_HORIZON_DAYS, SLOT_START_HOUR
from .models import Slot, Sport


def iter_slot_times():
    for hour in range(SLOT_START_HOUR, SLOT_END_HOUR):
        yield time(hour, 0), time(hour + 1, 0)


def ensure_slots_for_date(sport: Sport, day: date) -> None:
    existing = set(
        Slot.objects.filter(sport=sport, date=day).values_list("start_time", flat=True)
    )
    to_create = [
        Slot(sport=sport, date=day, start_time=start, end_time=end, is_booked=False)
        for start, end in iter_slot_times()
        if start not in existing
    ]
    if to_create:
        Slot.objects.bulk_create(to_create)


def ensure_upcoming_slots(sport: Sport | None = None, days: int = SLOT_HORIZON_DAYS) -> None:
    today = timezone.localdate()
    sports = [sport] if sport else list(Sport.objects.all())
    for item in sports:
        for offset in range(days + 1):
            ensure_slots_for_date(item, today + timedelta(days=offset))
