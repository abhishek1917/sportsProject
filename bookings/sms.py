import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def mask_phone(phone: str) -> str:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    tail = digits[-10:] if len(digits) >= 10 else digits
    if len(tail) < 4:
        return "your phone"
    return f"******{tail[-4:]}"


def _ten_digit(phone: str) -> str:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    return digits


def send_booking_sms(phone: str, message: str) -> bool:
    """Send a booking SMS via MSG91. Never raises — booking must still succeed."""
    if not phone or not message:
        return False
    authkey = (getattr(settings, "MSG91_AUTHKEY", "") or "").strip()
    if not authkey:
        logger.info("SMS (MSG91_AUTHKEY missing) to %s: %s", phone, message)
        return False
    try:
        mobile = _ten_digit(phone)
        response = requests.post(
            "https://api.msg91.com/api/v2/sendsms",
            headers={"authkey": authkey, "Content-Type": "application/json"},
            json={
                "sender": getattr(settings, "MSG91_SENDER", "STADIUM") or "STADIUM",
                "route": "4",
                "country": "91",
                "sms": [{"message": message, "to": [mobile]}],
            },
            timeout=12,
        )
        if response.status_code >= 400:
            logger.warning(
                "MSG91 SMS failed (%s): %s", response.status_code, response.text[:300]
            )
            return False
        logger.info("SMS sent via MSG91 to %s", mask_phone(phone))
        return True
    except requests.RequestException:
        logger.exception("MSG91 SMS request failed for %s", phone)
        return False
