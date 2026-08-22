from xml.sax.saxutils import escape

from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse


def _base() -> str:
    return settings.PUBLIC_BASE_URL.rstrip("/")


def speak_and_listen(session_id: int, text: str) -> HttpResponse:
    spoken = escape(text)
    action = _base() + reverse("bookings:voice_input", args=[session_id])
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" action="{escape(action)}" method="POST" speechTimeout="auto" language="en-IN">
    <Say language="en-IN">{spoken}</Say>
  </Gather>
  <Say language="en-IN">I did not hear anything. Goodbye.</Say>
</Response>
"""
    return HttpResponse(xml, content_type="text/xml")


def speak_and_hangup(text: str) -> HttpResponse:
    spoken = escape(text)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="en-IN">{spoken}</Say>
  <Hangup/>
</Response>
"""
    return HttpResponse(xml, content_type="text/xml")
