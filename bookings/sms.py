import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_booking_sms(phone: str, message: str) -> None:
    """Send an SMS via MSG91. If no API key is configured, log the message instead."""
    authkey = settings.MSG91_AUTHKEY
    if not authkey:
        logger.info("SMS (MSG91 not configured) to %s: %s", phone, message)
        return

    try:
        response = requests.post(
            "https://api.msg91.com/api/v2/sendsms",
            headers={
                "authkey": authkey,
                "Content-Type": "application/json",
            },
            json={
                "sender": settings.MSG91_SENDER,
                "route": "4",
                "country": "91",
                "sms": [{"message": message, "to": [phone]}],
            },
            timeout=10,
        )
        if response.status_code >= 400:
            logger.warning(
                "MSG91 SMS failed (%s): %s", response.status_code, response.text[:300]
            )
        else:
            logger.info("SMS sent to %s", phone)
    except requests.RequestException:
        logger.exception("MSG91 SMS request failed for %s", phone)
