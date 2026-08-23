from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .calls import (
    CallError,
    latest_pending_session,
    missing_voice_settings,
    queue_inbound_call,
    stadium_phone_number,
    start_outbound_call,
    voice_is_configured,
    voice_provider,
)
from .constants import MAX_PLAYERS_PER_COURT
from .models import Booking, Customer, Slot, Sport
from .services import BookingError, create_booking, cancel_booking
from .slots import ensure_slots_for_date


def _customer_or_none(user):
    if not user.is_authenticated:
        return None
    return getattr(user, "customer", None)


def health(request):
    return HttpResponse("ok", content_type="text/plain")


def home(request):
    query = (request.GET.get("q") or "").strip()
    if query:
        slug = resolve_sport_query(query)
        if slug:
            return redirect("bookings:sport", slug=slug)
        messages.error(
            request,
            "We only book tennis and cricket here. Try searching for one of those.",
        )
    return render(request, "bookings/home.html")


def resolve_sport_query(query: str) -> str | None:
    text = query.lower().strip()
    if not text:
        return None
    matches = []
    for slug in ("tennis", "cricket"):
        if slug in text or (len(text) >= 3 and (slug.startswith(text) or text in slug)):
            matches.append(slug)
    if "tennis" in matches and "cricket" not in text:
        return "tennis"
    if len(matches) == 1:
        return matches[0]
    if "cricket" in text:
        return "cricket"
    if "tennis" in text:
        return "tennis"
    return matches[0] if matches else None


def sport_page(request, slug):
    sport = get_object_or_404(Sport, slug=slug)
    today = timezone.localdate()
    selected = _parse_date(request.GET.get("date"), today)
    if selected < today:
        selected = today
    if selected > today + timedelta(days=14):
        selected = today + timedelta(days=14)

    ensure_slots_for_date(sport, selected)
    slots = (
        Slot.objects.filter(sport=sport, date=selected)
        .order_by("start_time")
    )

    customer = _customer_or_none(request.user)
    has_active = False
    if customer:
        has_active = customer.bookings.active().exists()

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect_to_login(f"{request.path}?date={selected.isoformat()}")
        if not customer:
            messages.error(request, "Your account is missing a customer profile. Please contact the venue.")
            return redirect("bookings:sport", slug=slug)
        slot_ids = request.POST.getlist("slot_ids")
        chosen = list(slots.filter(pk__in=slot_ids))
        try:
            create_booking(customer=customer, slots=chosen, created_via=Booking.VIA_SELF)
        except BookingError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                "You're booked. Pay at the venue. A confirmation SMS is on its way.",
            )
            return redirect("bookings:my_bookings")
        return redirect(f"{request.path}?date={selected.isoformat()}")

    return render(
        request,
        "bookings/sport.html",
        {
            "sport": sport,
            "selected_date": selected,
            "min_date": today,
            "max_date": today + timedelta(days=14),
            "slots": slots,
            "has_active": has_active,
            "max_players": MAX_PLAYERS_PER_COURT,
        },
    )


def _parse_date(value, fallback: date) -> date:
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except ValueError:
        return fallback


@login_required
def my_bookings(request):
    customer = _customer_or_none(request.user)
    if not customer:
        messages.error(request, "No customer profile is linked to this account.")
        return redirect("bookings:home")
    bookings = (
        customer.bookings.select_related("customer")
        .prefetch_related("slots__sport")
        .all()
    )
    return render(
        request,
        "bookings/my_bookings.html",
        {"bookings": bookings},
    )


@login_required
@require_POST
def cancel_booking_view(request, booking_id):
    customer = _customer_or_none(request.user)
    booking = get_object_or_404(Booking, pk=booking_id, customer=customer)
    try:
        cancel_booking(booking=booking, customer=customer)
    except BookingError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Booking cancelled. Those slots are open again.")
    return redirect("bookings:my_bookings")


def _require_customer_phone(request):
    customer = _customer_or_none(request.user)
    if not customer or not customer.phone:
        messages.info(request, "Add your phone number first. The agent will call that number.")
        return None
    return customer


@login_required
@require_http_methods(["GET", "POST"])
def book_on_call(request):
    customer = _require_customer_phone(request)
    if customer is None:
        return redirect("accounts:phone")

    sport_slug = (request.POST.get("sport") or request.GET.get("sport") or "").strip()
    if sport_slug not in {"tennis", "cricket", ""}:
        sport_slug = ""

    auto_call = request.method == "GET" and request.GET.get("auto") == "1" and not request.GET.get("calling")
    if auto_call:
        if not voice_is_configured():
            messages.error(
                request,
                "Call agent is not connected yet. Missing: "
                + ", ".join(missing_voice_settings() or ["voice settings"]),
            )
        else:
            try:
                session = start_outbound_call(customer=customer, sport_slug=sport_slug)
            except CallError as exc:
                messages.error(request, str(exc))
                if missing_voice_settings():
                    messages.error(
                        request,
                        "Missing settings: " + ", ".join(missing_voice_settings()),
                    )
            else:
                messages.success(
                    request,
                    f"Calling {customer.phone} now. Pick up and confirm your slot with the agent.",
                )
                suffix = f"?calling={session.pk}"
                if sport_slug:
                    suffix += f"&sport={sport_slug}"
                return redirect(f"{request.path}{suffix}")

    if request.method == "POST":
        mode = (request.POST.get("mode") or "outbound").strip()
        try:
            if mode == "inbound":
                session = queue_inbound_call(customer=customer, sport_slug=sport_slug)
            else:
                session = start_outbound_call(customer=customer, sport_slug=sport_slug)
                mode = "outbound"
        except CallError as exc:
            if request.headers.get("X-Requested-With") == "fetch":
                return JsonResponse({"ok": False, "error": str(exc)}, status=400)
            messages.error(request, str(exc))
            if missing_voice_settings():
                messages.error(
                    request,
                    "Missing settings: " + ", ".join(missing_voice_settings()),
                )
        else:
            if mode == "inbound":
                if request.headers.get("X-Requested-With") == "fetch":
                    return JsonResponse(
                        {
                            "ok": True,
                            "tel": stadium_phone_number(),
                            "session_id": session.pk,
                        }
                    )
                messages.success(
                    request,
                    f"Dial {stadium_phone_number()} and say yes to confirm your booking.",
                )
                return redirect(f"{request.path}?ready={session.pk}")
            if request.headers.get("X-Requested-With") == "fetch":
                return JsonResponse(
                    {
                        "ok": True,
                        "calling": True,
                        "phone": customer.phone,
                        "session_id": session.pk,
                    }
                )
            messages.success(
                request,
                f"Calling {customer.phone} now. Pick up and confirm your slot with the agent.",
            )
            return redirect(f"{request.path}?calling={session.pk}")

    stadium = stadium_phone_number()
    pending_session = latest_pending_session(customer) if voice_is_configured() else None
    calling_now = bool(request.GET.get("calling"))
    use_outbound = voice_is_configured()

    return render(
        request,
        "bookings/book_on_call.html",
        {
            "customer": customer,
            "sport_slug": sport_slug,
            "missing": missing_voice_settings(),
            "twilio_number": stadium,
            "stadium_number": stadium,
            "voice_provider": voice_provider(),
            "public_base_url": settings.PUBLIC_BASE_URL.rstrip("/"),
            "exotel_webhook_url": f"{settings.PUBLIC_BASE_URL.rstrip('/')}/voice/exotel/inbound/"
            if settings.PUBLIC_BASE_URL
            else "",
            "pending_session": pending_session,
            "voice_ready": voice_is_configured(),
            "use_outbound": use_outbound,
            "use_inbound": False,
            "calling_now": calling_now,
            "customer_phone": customer.phone,
            "browser_voice_ready": voice_is_configured(),
            "sarvam_ready": bool(getattr(settings, "SARVAM_API_KEY", "")),
        },
    )
