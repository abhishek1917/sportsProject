import os
from datetime import timedelta
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.utils import timezone

from .models import CallSession, Customer


class CallError(Exception):
    pass


def _llm_is_configured() -> bool:
    return bool(settings.GEMINI_API_KEY or settings.ANTHROPIC_API_KEY)


def exotel_is_configured() -> bool:
    return bool(
        settings.EXOTEL_ACCOUNT_SID
        and settings.EXOTEL_API_KEY
        and settings.EXOTEL_API_TOKEN
    )


def twilio_is_configured() -> bool:
    return bool(
        settings.TWILIO_ACCOUNT_SID
        and settings.TWILIO_AUTH_TOKEN
        and settings.TWILIO_FROM_NUMBER
    )


def voice_provider() -> str:
    if exotel_is_configured() and settings.EXOTEL_FROM_NUMBER:
        return "exotel"
    if twilio_is_configured():
        return "twilio"
    if exotel_is_configured():
        return "exotel"
    return ""


def stadium_phone_number() -> str:
    if settings.EXOTEL_FROM_NUMBER:
        return settings.EXOTEL_FROM_NUMBER
    return settings.TWILIO_FROM_NUMBER


def stadium_dial_number() -> str:
    """E.164-style number for tel: links (no tel: prefix)."""
    raw = (stadium_phone_number() or "").strip()
    if not raw:
        return ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return ""
    if raw.startswith("+"):
        return f"+{digits}"
    if digits.startswith("0") and len(digits) >= 10:
        return f"+91{digits[1:]}"
    if len(digits) == 10:
        return f"+91{digits}"
    if digits.startswith("91"):
        return f"+{digits}"
    return f"+{digits}"


def stadium_tel_href() -> str:
    number = stadium_dial_number()
    return f"tel:{number}" if number else ""


def voice_is_configured() -> bool:
    provider = voice_provider()
    if provider == "exotel":
        return bool(exotel_is_configured() and stadium_phone_number() and _llm_is_configured() and settings.PUBLIC_BASE_URL)
    if provider == "twilio":
        return bool(twilio_is_configured() and _llm_is_configured() and settings.PUBLIC_BASE_URL)
    return False


def missing_voice_settings() -> list[str]:
    missing = []
    if exotel_is_configured():
        if not settings.EXOTEL_FROM_NUMBER:
            missing.append("EXOTEL_FROM_NUMBER")
    elif not twilio_is_configured():
        missing.append("EXOTEL_* or TWILIO_* credentials")
    if not _llm_is_configured():
        missing.append("GEMINI_API_KEY")
    if not settings.PUBLIC_BASE_URL:
        missing.append("PUBLIC_BASE_URL")
    return missing


def exotel_api_base() -> str:
    subdomain = settings.EXOTEL_SUBDOMAIN.rstrip("/")
    if not subdomain.startswith("http"):
        subdomain = f"https://{subdomain}"
    return subdomain


def exotel_outbound_enabled() -> bool:
    if not exotel_is_configured():
        return False
    return os.getenv("EXOTEL_OUTBOUND_ENABLED", "false").lower() in {"1", "true", "yes"}


def exotel_inbound_webhook_url() -> str:
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/voice/exotel/inbound/"


def exotel_outbound_answer_url(session_id: int) -> str:
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/voice/exotel/outbound/{session_id}/"


def warm_public_server(*, timeout: int = 15) -> bool:
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    if not base:
        return False
    for path in ("/health/", "/"):
        try:
            response = requests.get(f"{base}{path}", timeout=timeout)
            if response.status_code < 500:
                return True
        except requests.RequestException:
            continue
    return False


def schedule_public_warmup() -> None:
    import threading

    def _warm() -> None:
        try:
            warm_public_server(timeout=10)
        except Exception:
            pass

    threading.Thread(target=_warm, daemon=True).start()


def exotel_voice_flow_url() -> str:
    app_id = (settings.EXOTEL_VOICE_APP_ID or "").strip()
    if not app_id:
        return ""
    return (
        f"https://my.exotel.com/{settings.EXOTEL_ACCOUNT_SID}"
        f"/exoml/start_voice/{app_id}"
    )


def exotel_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) >= 10:
        return "0" + digits[-10:]
    return digits


def fetch_exotel_exophone() -> str:
    if not exotel_is_configured():
        raise CallError("Exotel credentials are missing.")
    url = urljoin(
        exotel_api_base() + "/",
        f"v1/Accounts/{settings.EXOTEL_ACCOUNT_SID}/IncomingPhoneNumbers.json",
    )
    response = requests.get(
        url,
        auth=(settings.EXOTEL_API_KEY, settings.EXOTEL_API_TOKEN),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    numbers = payload.get("IncomingPhoneNumbers") or []
    if not numbers and payload.get("IncomingPhoneNumber"):
        numbers = [payload["IncomingPhoneNumber"]]
    if not numbers:
        return ""
    first = numbers[0]
    if isinstance(first, dict):
        return first.get("PhoneNumber") or first.get("FriendlyName") or ""
    return str(first)


def _exotel_error_detail(exc: requests.RequestException) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        try:
            payload = exc.response.json()
            rest = payload.get("RestException") or {}
            if rest.get("Message"):
                return str(rest["Message"])
        except ValueError:
            pass
        text = (exc.response.text or "").strip()
        if text:
            return text
    return str(exc)


def _friendly_call_error(exc: Exception, *, customer: Customer) -> str:
    message = str(exc).lower()
    if "kyc" in message and "outbound" in message:
        stadium = settings.EXOTEL_FROM_NUMBER or "the stadium line"
        return (
            "Exotel cannot call you yet — your Exotel account must complete KYC first. "
            f"Use “Call stadium line” below and dial {stadium} from your registered phone, "
            "or use the browser agent on this page."
        )
    if "trial accounts have limited parameter access" in message:
        return (
            "Twilio trial cannot place outbound calls to your server. "
            "Use dial-in to the stadium line instead, or upgrade Twilio."
        )
    if "verified" in message and ("caller" in message or "recipient" in message):
        return (
            f"Twilio trial can only call verified numbers. "
            f"Verify {customer.phone} in Twilio Console."
        )
    if "unauthorized" in message or "34010" in message:
        return "Exotel rejected the call request. Check your API key and token."
    if "dnd" in message or "ndnc" in message:
        return (
            f"{customer.phone} is on Do Not Disturb. "
            "Use a number that can receive promotional/transactional calls."
        )
    return f"Could not place the call: {exc}"


def _start_exotel_outbound_call(*, customer: Customer, sport_slug: str = "") -> CallSession:
    if not exotel_is_configured() or not settings.EXOTEL_FROM_NUMBER:
        raise CallError("Exotel is not fully configured.")
    if not settings.PUBLIC_BASE_URL:
        raise CallError("PUBLIC_BASE_URL is missing.")

    schedule_public_warmup()

    session = CallSession.objects.create(
        customer=customer,
        sport_slug=sport_slug,
        status=CallSession.STATUS_QUEUED,
    )
    payload = {
        "From": exotel_phone(customer.phone),
        "CallerId": settings.EXOTEL_FROM_NUMBER,
        "Url": exotel_outbound_answer_url(session.pk),
        "CallType": "trans",
        "TimeOut": "45",
        "StatusCallback": f"{settings.PUBLIC_BASE_URL.rstrip('/')}/voice/exotel/status/",
    }

    api_url = urljoin(
        exotel_api_base() + "/",
        f"v1/Accounts/{settings.EXOTEL_ACCOUNT_SID}/Calls/connect.json",
    )
    try:
        response = requests.post(
            api_url,
            auth=(settings.EXOTEL_API_KEY, settings.EXOTEL_API_TOKEN),
            data=payload,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        session.status = CallSession.STATUS_FAILED
        session.save(update_fields=["status"])
        detail = _exotel_error_detail(exc) if isinstance(exc, requests.HTTPError) else exc
        raise CallError(_friendly_call_error(Exception(detail), customer=customer)) from exc

    body = response.json()
    call = body.get("Call") or {}
    session.plivo_call_uuid = call.get("Sid") or ""
    session.status = CallSession.STATUS_IN_PROGRESS
    session.save(update_fields=["plivo_call_uuid", "status"])
    return session


def customer_from_phone(raw: str) -> Customer | None:
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 10:
        return None
    tail = digits[-10:]
    normalized = f"91{tail}"
    customer = Customer.objects.filter(phone=normalized).first()
    if customer:
        return customer
    return Customer.objects.filter(phone__endswith=tail).first()


def queue_inbound_call(*, customer: Customer, sport_slug: str = "") -> CallSession:
    if not voice_is_configured():
        raise CallError(
            "Call agent is not connected yet. Add Exotel or Twilio, Gemini, and PUBLIC_BASE_URL."
        )
    CallSession.objects.filter(
        customer=customer,
        status=CallSession.STATUS_QUEUED,
    ).update(status=CallSession.STATUS_ENDED)
    return CallSession.objects.create(
        customer=customer,
        sport_slug=sport_slug,
        status=CallSession.STATUS_QUEUED,
    )


def latest_pending_session(customer: Customer) -> CallSession | None:
    cutoff = timezone.now() - timedelta(minutes=15)
    return (
        CallSession.objects.filter(
            customer=customer,
            status=CallSession.STATUS_QUEUED,
            created_at__gte=cutoff,
        )
        .order_by("-created_at")
        .first()
    )


def configure_twilio_inbound_webhook() -> str:
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise CallError("Twilio credentials are missing.")
    if not settings.PUBLIC_BASE_URL:
        raise CallError("PUBLIC_BASE_URL is missing.")

    from twilio.rest import Client

    inbound_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/voice/inbound/"
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    numbers = client.incoming_phone_numbers.list(limit=20)
    if not numbers:
        raise CallError("No Twilio phone numbers were found on your account.")
    target = settings.TWILIO_FROM_NUMBER
    chosen = None
    for number in numbers:
        if number.phone_number == target:
            chosen = number
            break
    if chosen is None:
        chosen = numbers[0]
    chosen.update(voice_url=inbound_url, voice_method="POST")
    return inbound_url


def start_outbound_call(*, customer: Customer, sport_slug: str = "") -> CallSession:
    if voice_provider() == "exotel":
        if not exotel_outbound_enabled():
            raise CallError(
                "Outbound calls are off until Exotel KYC is complete. "
                f"Use “Call stadium line” and dial {settings.EXOTEL_FROM_NUMBER} "
                "from your registered phone, or use the browser agent."
            )
        return _start_exotel_outbound_call(customer=customer, sport_slug=sport_slug)
    if not voice_is_configured():
        raise CallError(
            "Call agent is not connected yet. Add Twilio, Gemini, and PUBLIC_BASE_URL on the server."
        )

    from twilio.rest import Client

    session = CallSession.objects.create(
        customer=customer,
        sport_slug=sport_slug,
        status=CallSession.STATUS_QUEUED,
    )
    answer_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/voice/answer/{session.pk}/"
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    try:
        call = client.calls.create(
            to=customer.e164(),
            from_=settings.TWILIO_FROM_NUMBER,
            url=answer_url,
            method="POST",
        )
    except Exception as exc:
        session.status = CallSession.STATUS_FAILED
        session.save(update_fields=["status"])
        raise CallError(_friendly_call_error(exc, customer=customer)) from exc

    session.plivo_call_uuid = call.sid or ""
    session.save(update_fields=["plivo_call_uuid"])
    return session
