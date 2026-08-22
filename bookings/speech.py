import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def transcribe_audio_bytes(audio: bytes, *, filename: str = "recording.wav") -> str:
    if not audio:
        return ""
    if settings.SARVAM_API_KEY:
        text = _transcribe_with_sarvam(audio, filename=filename)
        if text:
            return text
    return _transcribe_with_gemini(audio, filename=filename)


def transcribe_recording_url(url: str) -> str:
    if not url:
        return ""
    try:
        response = requests.get(url, timeout=45)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Could not download Exotel recording")
        return ""

    audio = response.content
    if not audio:
        return ""
    filename = url.rsplit("/", 1)[-1] or "recording.wav"
    return transcribe_audio_bytes(audio, filename=filename)


def _transcribe_with_sarvam(audio: bytes, *, filename: str) -> str:
    try:
        response = requests.post(
            "https://api.sarvam.ai/speech-to-text",
            headers={"api-subscription-key": settings.SARVAM_API_KEY},
            files={"file": (filename, audio, "audio/wav")},
            data={
                "model": settings.SARVAM_STT_MODEL,
                "language_code": settings.SARVAM_LANGUAGE_CODE,
                "mode": "codemix",
            },
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Sarvam transcription failed")
        return ""
    payload = response.json()
    return (payload.get("transcript") or "").strip()


def _transcribe_with_gemini(audio: bytes, *, filename: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    mime_type = "audio/wav"
    if filename.lower().endswith(".mp3"):
        mime_type = "audio/mpeg"

    try:
        result = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=audio, mime_type=mime_type),
                "Transcribe what the caller said. Return plain text only, no labels.",
            ],
        )
    except Exception:
        logger.exception("Gemini transcription failed")
        return ""

    return (result.text or "").strip()
