import re
import sys
import time
import uuid

import requests

base = "https://sportsproject.onrender.com"
s = requests.Session()


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    if not match:
        raise RuntimeError("CSRF token not found")
    return match.group(1)


def main() -> None:
    suffix = uuid.uuid4().hex[:8]
    username = f"test_{suffix}"
    password = "TestPass123!"
    phone = "98765" + f"{int(uuid.uuid4().int % 100000):05d}"

    r = s.get(f"{base}/accounts/signup/", timeout=120)
    token = csrf_from(r.text)
    r2 = s.post(
        f"{base}/accounts/signup/",
        data={
            "username": username,
            "full_name": "Test User",
            "phone": phone,
            "password1": password,
            "password2": password,
            "csrfmiddlewaretoken": token,
        },
        headers={"Referer": f"{base}/accounts/signup/"},
        timeout=120,
        allow_redirects=True,
    )
    print("Signup", r2.status_code, r2.url)
    if "/accounts/signup/" in r2.url:
        print("SIGNUP_FAILED")
        print(r2.text[:600])
        sys.exit(1)

    r3 = s.get(f"{base}/book-on-call/", timeout=120)
    print("Book on call", r3.status_code)
    if "Not connected yet" in r3.text:
        print("STILL_MISSING_SETTINGS")
        start = r3.text.find("Not connected yet")
        print(r3.text[start : start + 200])
        sys.exit(2)
    if "Open dialer" in r3.text or "Call me now" in r3.text:
        print("BOOK_ON_CALL_READY")
    if "Dial" in r3.text and "registered phone" in r3.text:
        print("EXOTEL_CONFIGURED")
    if phone_required := ("phone" in r3.url):
        print("NEEDS_PHONE")
        token = csrf_from(r3.text)
        r4 = s.post(
            f"{base}/accounts/phone/",
            data={
                "full_name": "Test User",
                "phone": phone,
                "csrfmiddlewaretoken": token,
                "next": "/book-on-call/",
            },
            headers={"Referer": f"{base}/accounts/phone/"},
            timeout=120,
            allow_redirects=True,
        )
        r5 = s.get(f"{base}/book-on-call/", timeout=120)
        if "Not connected yet" in r5.text:
            print("STILL_MISSING_AFTER_PHONE")
            sys.exit(2)
        if "Open dialer" in r5.text or "Call me now" in r5.text:
            print("BOOK_ON_CALL_READY_AFTER_PHONE")


if __name__ == "__main__":
    main()
