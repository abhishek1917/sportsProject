import json
from datetime import date, datetime, time

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Booking, Slot, Sport
from .services import BookingError, create_booking, get_or_create_customer
from .slots import ensure_slots_for_date


def _unauthorized():
    return JsonResponse({"ok": False, "error": "Unauthorized"}, status=401)


def _require_internal_key(request):
    expected = settings.INTERNAL_API_KEY
    if not expected:
        return True
    provided = request.headers.get("X-Internal-Key", "")
    return provided == expected


def _parse_json(request):
    if request.body:
        try:
            return json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise BookingError("Invalid JSON body.") from exc
    return request.GET.dict() | request.POST.dict()


@csrf_exempt
@require_http_methods(["GET", "POST"])
def availability(request):
    if not _require_internal_key(request):
        return _unauthorized()
    try:
        payload = _parse_json(request) if request.method == "POST" else request.GET
        sport_slug = (payload.get("sport") or "").strip().lower()
        date_value = payload.get("date")
        sport = Sport.objects.filter(slug=sport_slug).first()
        if not sport:
            raise BookingError("Unknown sport. Use tennis or cricket.")
        day = date.fromisoformat(date_value)
        ensure_slots_for_date(sport, day)
        slots = Slot.objects.filter(sport=sport, date=day).order_by("start_time")
        open_slots = []
        for slot in slots:
            if slot.is_booked or slot.has_started():
                continue
            open_slots.append(
                {
                    "id": slot.pk,
                    "start": slot.start_time.strftime("%H:%M"),
                    "end": slot.end_time.strftime("%H:%M"),
                }
            )
        return JsonResponse(
            {
                "ok": True,
                "sport": sport.slug,
                "date": day.isoformat(),
                "slots": open_slots,
            }
        )
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Provide sport and date as YYYY-MM-DD."}, status=400)
    except BookingError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def create_booking_api(request):
    if not _require_internal_key(request):
        return _unauthorized()
    try:
        payload = _parse_json(request)
        name = (payload.get("customer_name") or payload.get("name") or "").strip()
        phone = (payload.get("phone") or "").strip()
        sport_slug = (payload.get("sport") or "").strip().lower()
        date_value = payload.get("date")
        start_times = payload.get("start_times") or payload.get("slots") or []
        if isinstance(start_times, str):
            start_times = [part.strip() for part in start_times.split(",") if part.strip()]
        if not name or not phone:
            raise BookingError("customer_name and phone are required.")
        sport = Sport.objects.filter(slug=sport_slug).first()
        if not sport:
            raise BookingError("Unknown sport. Use tennis or cricket.")
        day = date.fromisoformat(date_value)
        ensure_slots_for_date(sport, day)
        parsed_times = []
        for value in start_times:
            parsed_times.append(datetime.strptime(value, "%H:%M").time() if isinstance(value, str) else value)
        if not parsed_times:
            raise BookingError("Provide one or two slot start times as HH:MM.")
        slots = list(
            Slot.objects.filter(sport=sport, date=day, start_time__in=parsed_times)
        )
        if len(slots) != len(set(parsed_times)):
            raise BookingError("One or more slot times are invalid for that date.")
        customer = get_or_create_customer(full_name=name, phone=phone)
        via = payload.get("created_via") or Booking.VIA_PHONE
        if via not in {Booking.VIA_PHONE, Booking.VIA_ADMIN, Booking.VIA_SELF}:
            via = Booking.VIA_PHONE
        booking = create_booking(customer=customer, slots=slots, created_via=via)
        return JsonResponse(
            {
                "ok": True,
                "booking_id": booking.pk,
                "sport": sport.slug,
                "date": day.isoformat(),
                "times": booking.summary_times(),
                "status": booking.status,
            },
            status=201,
        )
    except (ValueError, TypeError):
        return JsonResponse(
            {"ok": False, "error": "Provide sport, date (YYYY-MM-DD), and start_times (HH:MM)."},
            status=400,
        )
    except BookingError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=409)
