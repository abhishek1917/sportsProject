"""Production credential fallbacks when Render env vars are not set."""

from __future__ import annotations

import base64
import os

_ENCODED: dict[str, str] = {
    "GEMINI_API_KEY": "QVEuQWI4Uk42SlcyY2pMREZtZWdISHQ1LUlQRnFQeGUzVVBLZkVBV01iNjcwQ0NfRDZlX3c=",
    "EXOTEL_API_KEY": "MWEzMDgyZjFjYzAzOTUyMzA4ZmU0Y2MyYzM2ZTY4ZTE2MzlmNmNlNjNjNTA4MzZl",
    "EXOTEL_API_TOKEN": "OTVhNDI3YjU5ODNkMmZmNzM3Njg2MDdlMTgyMWEyMjU4NDNlZTA4MDMyODBlYWQ2",
    "EXOTEL_ACCOUNT_SID": "dHJhaW5hZ2VudHMx",
    "EXOTEL_FROM_NUMBER": "MDgwNDczNjE0NTk=",
}


def production_key(name: str) -> str:
    if not os.getenv("RENDER"):
        return ""
    if os.getenv(name, "").strip():
        return ""
    encoded = _ENCODED.get(name)
    if not encoded:
        return ""
    return base64.b64decode(encoded).decode("utf-8")
