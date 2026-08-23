import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .agent import next_agent_reply
from .exoml import say_and_hangup as exoml_hangup
from .exoml import say_and_record as exoml_listen
from .models import CallSession
from .speech import transcribe_recording_url
from .twiml import speak_and_hangup, speak_and_listen

logger = logging.getLogger(__name__)


def _start_session(*, customer, call_sid: str):
    from .calls import latest_pending_session

    session = latest_pending_session(customer)
    if session is None:
        session = CallSession.objects.create(
            customer=customer,
            status=CallSession.STATUS_IN_PROGRESS,
            plivo_call_uuid=call_sid,
        )
    else:
        session.status = CallSession.STATUS_IN_PROGRESS
        session.plivo_call_uuid = call_sid or session.plivo_call_uuid
        session.save(update_fields=["status", "plivo_call_uuid"])
    return session


@csrf_exempt
@require_POST
def voice_inbound(request):
    from .calls import customer_from_phone

    caller = request.POST.get("From", "")
    call_sid = request.POST.get("CallSid", "") or ""
    customer = customer_from_phone(caller)
    if customer is None:
        logger.warning("Inbound call from unknown caller: %s", caller)
        return speak_and_hangup(
            "Sorry, we could not find your account. "
            "Please sign up on the website with this phone number first."
        )

    session = _start_session(customer=customer, call_sid=call_sid)
    try:
        spoken, hangup = next_agent_reply(session, None)
    except Exception:
        logger.exception("Inbound agent failed for session %s", session.pk)
        session.status = CallSession.STATUS_FAILED
        session.save(update_fields=["status"])
        return speak_and_hangup(
            "Sorry, the booking assistant is unavailable right now. Please book on the website."
        )
    if hangup:
        session.status = CallSession.STATUS_BOOKED
        session.save(update_fields=["status"])
        return speak_and_hangup(spoken)
    return speak_and_listen(session.pk, spoken)


@csrf_exempt
@require_POST
def voice_answer(request, session_id):
    session = get_object_or_404(
        CallSession.objects.select_related("customer"),
        pk=session_id,
    )
    session.plivo_call_uuid = (
        request.POST.get("CallSid")
        or request.POST.get("CallUUID")
        or session.plivo_call_uuid
    )
    session.status = CallSession.STATUS_IN_PROGRESS
    session.save(update_fields=["plivo_call_uuid", "status"])
    try:
        spoken, hangup = next_agent_reply(session, None)
    except Exception:
        logger.exception("Outbound agent failed for session %s", session.pk)
        return speak_and_hangup(
            "Sorry, the booking assistant is unavailable right now. Please book on the website."
        )
    if hangup:
        return speak_and_hangup(spoken)
    return speak_and_listen(session.pk, spoken)


@csrf_exempt
@require_POST
def voice_input(request, session_id):
    session = get_object_or_404(
        CallSession.objects.select_related("customer"),
        pk=session_id,
    )
    speech = (
        request.POST.get("SpeechResult")
        or request.POST.get("Speech")
        or request.POST.get("Digits")
        or ""
    ).strip()
    if not speech:
        return speak_and_listen(
            session.pk,
            "I did not catch that. Please say tennis or cricket, the date, and the time.",
        )
    try:
        spoken, hangup = next_agent_reply(session, speech)
    except Exception:
        logger.exception("Voice input failed for session %s", session.pk)
        return speak_and_hangup(
            "Sorry, something went wrong. Please try booking on the website."
        )
    if hangup or session.status == CallSession.STATUS_BOOKED:
        return speak_and_hangup(spoken)
    return speak_and_listen(session.pk, spoken)


def _exotel_caller(request) -> str:
    return (
        request.GET.get("CallFrom")
        or request.GET.get("From")
        or request.POST.get("CallFrom")
        or request.POST.get("From")
        or ""
    )


def _exotel_call_sid(request) -> str:
    return (
        request.GET.get("CallSid")
        or request.POST.get("CallSid")
        or ""
    )


def _exotel_custom_field(request) -> str:
    return (
        request.GET.get("CustomField")
        or request.POST.get("CustomField")
        or ""
    ).strip()


def _exotel_greeting(session: CallSession) -> str:
    name = session.customer.full_name.split()[0] if session.customer.full_name else "there"
    if session.sport_slug:
        return (
            f"Hello {name}. I am the stadium booking assistant. "
            f"You selected {session.sport_slug}. Tell me the date and time you want."
        )
    return (
        f"Hello {name}. I am the stadium booking assistant. "
        "Tell me tennis or cricket, the date, and the time you want."
    )


def _begin_exotel_session(*, session: CallSession, call_sid: str):
    session.status = CallSession.STATUS_IN_PROGRESS
    session.plivo_call_uuid = call_sid or session.plivo_call_uuid
    session.save(update_fields=["status", "plivo_call_uuid"])
    if not session.messages:
        return exoml_listen(session.pk, _exotel_greeting(session))
    try:
        spoken, hangup = next_agent_reply(session, None)
    except Exception:
        logger.exception("Exotel agent failed for session %s", session.pk)
        session.status = CallSession.STATUS_FAILED
        session.save(update_fields=["status"])
        return exoml_hangup(
            "Sorry, the booking assistant is unavailable right now. Please book on the website."
        )
    if hangup:
        session.status = CallSession.STATUS_BOOKED
        session.save(update_fields=["status"])
        return exoml_hangup(spoken)
    return exoml_listen(session.pk, spoken)


@csrf_exempt
def exotel_record(request, session_id):
    if request.method not in {"GET", "POST"}:
        return exoml_hangup("Sorry, this line is not available.")

    session = get_object_or_404(
        CallSession.objects.select_related("customer"),
        pk=session_id,
    )
    recording_url = (
        request.GET.get("RecordingUrl")
        or request.POST.get("RecordingUrl")
        or ""
    ).strip()
    speech = transcribe_recording_url(recording_url)
    if not speech:
        return exoml_listen(
            session.pk,
            "I did not catch that. Please say tennis or cricket, the date, and the time.",
        )
    try:
        spoken, hangup = next_agent_reply(session, speech)
    except Exception:
        logger.exception("Exotel record failed for session %s", session.pk)
        return exoml_hangup("Sorry, something went wrong. Please book on the website.")
    if hangup or session.status == CallSession.STATUS_BOOKED:
        session.status = CallSession.STATUS_BOOKED
        session.save(update_fields=["status"])
        return exoml_hangup(spoken)
    return exoml_listen(session.pk, spoken)


@csrf_exempt
def exotel_status(request):
    if request.method not in {"GET", "POST"}:
        return HttpResponse(status=405)
    call_sid = (
        request.GET.get("CallSid")
        or request.POST.get("CallSid")
        or ""
    )
    status = (
        request.GET.get("Status")
        or request.POST.get("Status")
        or ""
    )
    custom_field = (
        request.GET.get("CustomField")
        or request.POST.get("CustomField")
        or ""
    )
    logger.info(
        "Exotel status callback sid=%s status=%s session=%s",
        call_sid,
        status,
        custom_field,
    )
    return HttpResponse(status=200)


@csrf_exempt
def exotel_outbound(request, session_id):
    if request.method not in {"GET", "POST"}:
        return exoml_hangup("Sorry, this line is not available.")

    session = get_object_or_404(
        CallSession.objects.select_related("customer"),
        pk=session_id,
    )
    call_sid = _exotel_call_sid(request)
    logger.info("Exotel outbound answer session=%s sid=%s", session_id, call_sid)
    return _begin_exotel_session(session=session, call_sid=call_sid)


@csrf_exempt
def exotel_inbound(request):
    from .calls import customer_from_phone

    if request.method not in {"GET", "POST"}:
        return exoml_hangup("Sorry, this line is not available.")

    custom_field = _exotel_custom_field(request)
    if custom_field.isdigit():
        session = get_object_or_404(CallSession, pk=int(custom_field))
        return _begin_exotel_session(session=session, call_sid=_exotel_call_sid(request))

    caller = _exotel_caller(request)
    call_sid = _exotel_call_sid(request)
    customer = customer_from_phone(caller)
    if customer is None:
        logger.warning("Exotel inbound from unknown caller: %s", caller)
        return exoml_hangup(
            "Sorry, we could not find your account. "
            "Please sign up on the website with this phone number first."
        )

    session = _start_session(customer=customer, call_sid=call_sid)
    return _begin_exotel_session(session=session, call_sid=call_sid)
