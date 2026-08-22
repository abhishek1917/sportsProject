from datetime import datetime, time, timedelta

from django.utils import timezone

SLOT_START_HOUR = 6
SLOT_END_HOUR = 22  # last slot starts at 21:00
SLOT_DURATION_HOURS = 1
MAX_SLOTS_PER_BOOKING = 2
MAX_PLAYERS_PER_COURT = 4
SLOT_HORIZON_DAYS = 14
