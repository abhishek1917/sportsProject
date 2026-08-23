from xml.sax.saxutils import escape

from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse


def _base() -> str:
    return settings.PUBLIC_BASE_URL.rstrip("/")


def say_and_record(session_id: int, text: str) -> HttpResponse:
    spoken = escape(text)
    action = _base() + reverse("bookings:exotel_record", args=[session_id])
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>{spoken}</Say>
  <Pause length="1"/>
  <Record action="{escape(action)}" method="POST" maxLength="30" timeout="8" playBeep="true" />
</Response>
"""
    return HttpResponse(xml, content_type="text/xml; charset=utf-8")


def say_and_hangup(text: str) -> HttpResponse:
    spoken = escape(text)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>{spoken}</Say>
  <Hangup/>
</Response>
"""
    return HttpResponse(xml, content_type="text/xml; charset=utf-8")
