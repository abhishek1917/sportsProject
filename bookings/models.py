from datetime import datetime, time, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .constants import MAX_SLOTS_PER_BOOKING, SLOT_DURATION_HOURS


class Sport(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    tagline = models.CharField(max_length=200, blank=True)
    court_details = models.TextField()
    timings = models.CharField(max_length=200)
    rules = models.TextField()
    legal_name = models.CharField(max_length=160, blank=True)
    address = models.TextField(blank=True)
    gstin = models.CharField(max_length=20, blank=True)
    upi_vpa = models.CharField(max_length=80, blank=True)
    invoice_prefix = models.CharField(max_length=8, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Slot(models.Model):
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE, related_name="slots")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_booked = models.BooleanField(default=False)

    class Meta:
        ordering = ["date", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["sport", "date", "start_time"],
                name="unique_sport_slot",
            )
        ]
        indexes = [
            models.Index(fields=["sport", "date", "is_booked"]),
        ]

    def __str__(self):
        return f"{self.sport.name} {self.date} {self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')}"

    @property
    def starts_at(self):
        tz = timezone.get_current_timezone()
        return timezone.make_aware(datetime.combine(self.date, self.start_time), tz)

    @property
    def ends_at(self):
        tz = timezone.get_current_timezone()
        return timezone.make_aware(datetime.combine(self.date, self.end_time), tz)

    def has_started(self):
        return timezone.now() >= self.starts_at

    def has_ended(self):
        return timezone.now() >= self.ends_at


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=15, unique=True)

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    def e164(self):
        digits = "".join(ch for ch in self.phone if ch.isdigit())
        return f"+{digits}" if digits else ""


class BookingQuerySet(models.QuerySet):
    def active(self):
        now = timezone.localtime()
        today = now.date()
        current_time = now.time()
        return (
            self.filter(status=Booking.STATUS_BOOKED)
            .filter(
                Q(slots__date__gt=today)
                | Q(slots__date=today, slots__end_time__gt=current_time)
            )
            .distinct()
        )


class Booking(models.Model):
    STATUS_BOOKED = "booked"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_BOOKED, "Booked"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    VIA_SELF = "self"
    VIA_PHONE = "phone"
    VIA_ADMIN = "admin"
    VIA_CHOICES = [
        (VIA_SELF, "Self-service"),
        (VIA_PHONE, "Phone"),
        (VIA_ADMIN, "Admin"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="bookings"
    )
    slots = models.ManyToManyField(Slot, related_name="bookings")
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_BOOKED
    )
    created_via = models.CharField(
        max_length=12, choices=VIA_CHOICES, default=VIA_SELF
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BookingQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer} · {self.status} · {self.created_via}"

    def is_active(self):
        if self.status != self.STATUS_BOOKED:
            return False
        return any(not slot.has_ended() for slot in self.slots.all())

    @staticmethod
    def validate_slot_selection(slots):
        slots = list(slots)
        if not slots:
            raise ValidationError("Choose 1 hour or 2 consecutive hours.")
        if len(slots) > MAX_SLOTS_PER_BOOKING:
            raise ValidationError("You can book at most 2 consecutive hours.")

        sports = {slot.sport_id for slot in slots}
        dates = {slot.date for slot in slots}
        if len(sports) != 1:
            raise ValidationError("All slots in a booking must be for the same sport.")
        if len(dates) != 1:
            raise ValidationError("All slots in a booking must be on the same date.")

        ordered = sorted(slots, key=lambda s: s.start_time)
        for slot in ordered:
            if slot.has_started():
                raise ValidationError("That time has already passed. Please pick a later slot.")
            duration = datetime.combine(slot.date, slot.end_time) - datetime.combine(
                slot.date, slot.start_time
            )
            if duration != timedelta(hours=SLOT_DURATION_HOURS):
                raise ValidationError("Slots must be exactly 1 hour long.")

        if len(ordered) == 2:
            first, second = ordered
            if first.end_time != second.start_time:
                raise ValidationError("A 2-hour booking must use two consecutive slots.")

        return ordered

    def summary_times(self):
        ordered = list(self.slots.order_by("start_time"))
        if not ordered:
            return ""
        start = ordered[0].start_time.strftime("%H:%M")
        end = ordered[-1].end_time.strftime("%H:%M")
        return f"{ordered[0].date} {start}–{end}"


class CallSession(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_BOOKED = "booked"
    STATUS_FAILED = "failed"
    STATUS_ENDED = "ended"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_BOOKED, "Booked"),
        (STATUS_FAILED, "Failed"),
        (STATUS_ENDED, "Ended"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="call_sessions"
    )
    sport_slug = models.SlugField(blank=True)
    plivo_call_uuid = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    messages = models.JSONField(default=list, blank=True)
    last_agent_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Call {self.pk} · {self.customer} · {self.status}"
