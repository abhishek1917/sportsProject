import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .agent import next_agent_reply
from .calls import CallError, queue_inbound_call
from .models import CallSession, Customer
from .speech import transcribe_audio_bytes
from .voice_views import _exotel_greeting

logger = logging.getLogger(__name__)


def _customer(request) -> Customer | None:
    return getattr(request.user, "customer", None)


@login_required
@require_POST
def browser_voice_start(request):
    customer = _customer(request)
    if not customer:
        return JsonResponse({"ok": False, "error": "Customer profile missing."}, status=400)

    sport_slug = (request.POST.get("sport") or "").strip()
    if sport_slug not in {"tennis", "cricket", ""}:
        sport_slug = ""

    session = CallSession.objects.create(
        customer=customer,
        sport_slug=sport_slug,
        status=CallSession.STATUS_IN_PROGRESS,
    )
    return JsonResponse(
        {
            "ok": True,
            "session_id": session.pk,
            "message": _exotel_greeting(session),
            "hangup": False,
        }
    )


@login_required
@require_POST
def browser_voice_turn(request, session_id):
    customer = _customer(request)
    if not customer:
        return JsonResponse({"ok": False, "error": "Customer profile missing."}, status=400)

    session = get_object_or_404(CallSession, pk=session_id, customer=customer)
    text = (request.POST.get("text") or "").strip()

    if not text and request.FILES.get("audio"):
        audio_file = request.FILES["audio"]
        text = transcribe_audio_bytes(
            audio_file.read(),
            filename=audio_file.name or "browser.wav",
        )

    if not text:
        return JsonResponse(
            {
                "ok": True,
                "message": "I did not catch that. Please say tennis or cricket, the date, and time.",
                "hangup": False,
            }
        )

    try:
        spoken, hangup = next_agent_reply(session, text)
    except Exception:
        logger.exception("Browser voice failed for session %s", session.pk)
        return JsonResponse(
            {
                "ok": False,
                "error": "The booking assistant is unavailable right now.",
            },
            status=500,
        )

    if hangup or session.status == CallSession.STATUS_BOOKED:
        session.status = CallSession.STATUS_BOOKED
        session.save(update_fields=["status"])

    return JsonResponse({"ok": True, "message": spoken, "hangup": hangup})


@login_required
@require_POST
def browser_voice_prepare_phone(request):
    customer = _customer(request)
    if not customer:
        return JsonResponse({"ok": False, "error": "Customer profile missing."}, status=400)

    sport_slug = (request.POST.get("sport") or "").strip()
    if sport_slug not in {"tennis", "cricket", ""}:
        sport_slug = ""

    try:
        session = queue_inbound_call(customer=customer, sport_slug=sport_slug)
    except CallError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse({"ok": True, "session_id": session.pk})
