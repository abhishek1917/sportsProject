from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Booking, Customer, Slot, Sport
from .sms import send_booking_sms


class BookingError(Exception):
    """User-facing booking failure."""


def normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        return digits
    if len(digits) == 10:
        return "91" + digits
    if len(digits) < 10:
        raise BookingError("Enter a valid 10-digit mobile number.")
    return digits


def get_or_create_customer(*, full_name: str, phone: str) -> Customer:
    phone = normalize_phone(phone)
    customer = Customer.objects.filter(phone=phone).select_related("user").first()
    if customer:
        if full_name and customer.full_name != full_name:
            customer.full_name = full_name
            customer.save(update_fields=["full_name"])
        return customer

    username = f"phone_{phone}"
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"first_name": full_name[:30]},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    customer, _ = Customer.objects.get_or_create(
        user=user,
        defaults={"full_name": full_name, "phone": phone},
    )
    if customer.phone != phone:
        raise BookingError("This account is already linked to a different phone number.")
    return customer


def customer_has_active_booking(customer: Customer, exclude_booking_id=None) -> bool:
    qs = customer.bookings.active()
    if exclude_booking_id:
        qs = qs.exclude(pk=exclude_booking_id)
    return qs.exists()


def create_booking(*, customer: Customer, slots, created_via: str) -> Booking:
    slot_list = list(slots)
    try:
        ordered = Booking.validate_slot_selection(slot_list)
    except ValidationError as exc:
        raise BookingError(exc.messages[0] if getattr(exc, "messages", None) else str(exc)) from exc

    with transaction.atomic():
        locked = list(
            Slot.objects.select_for_update()
            .select_related("sport")
            .filter(pk__in=[s.pk for s in ordered])
            .order_by("start_time")
        )
        if len(locked) != len(ordered):
            raise BookingError("One or more slots could not be found. Please try again.")

        try:
            Booking.validate_slot_selection(locked)
        except ValidationError as exc:
            raise BookingError(exc.messages[0] if getattr(exc, "messages", None) else str(exc)) from exc

        if any(slot.is_booked for slot in locked):
            raise BookingError("That slot was just taken. Please pick a different time.")

        if customer_has_active_booking(customer):
            raise BookingError(
                "You already have an active booking. Cancel it or wait until it ends before booking again."
            )

        booking = Booking.objects.create(
            customer=customer,
            status=Booking.STATUS_BOOKED,
            created_via=created_via,
        )
        booking.slots.set(locked)
        Slot.objects.filter(pk__in=[s.pk for s in locked]).update(is_booked=True)

    sport = locked[0].sport
    times = booking.summary_times()
    send_booking_sms(
        customer.phone,
        f"Booking confirmed: {sport.name} on {times}. Pay at the venue. Max 4 players.",
    )
    return booking


def cancel_booking(*, booking: Booking, customer: Customer | None = None) -> Booking:
    if customer and booking.customer_id != customer.pk:
        raise BookingError("You can only cancel your own bookings.")
    if booking.status == Booking.STATUS_CANCELLED:
        raise BookingError("This booking is already cancelled.")
    if not booking.is_active():
        raise BookingError("Past bookings cannot be cancelled.")

    with transaction.atomic():
        locked_booking = Booking.objects.select_for_update().get(pk=booking.pk)
        slots = list(locked_booking.slots.select_for_update())
        locked_booking.status = Booking.STATUS_CANCELLED
        locked_booking.save(update_fields=["status"])
        Slot.objects.filter(pk__in=[s.pk for s in slots]).update(is_booked=False)

    return locked_booking
