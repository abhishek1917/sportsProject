import re
import sys

import requests

base = "https://sportsproject.onrender.com"
s = requests.Session()
r = s.get(f"{base}/accounts/login/", timeout=120)
match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
if not match:
    print("NO_CSRF")
    sys.exit(1)
token = match.group(1)
r2 = s.post(
    f"{base}/accounts/login/",
    data={
        "username": "abhi",
        "password": "StadiumAdmin2026",
        "csrfmiddlewaretoken": token,
        "next": "/",
    },
    headers={"Referer": f"{base}/accounts/login/"},
    timeout=120,
    allow_redirects=True,
)
print("URL", r2.url)
if "correct username and password" in r2.text:
    print("LOGIN_FAILED")
    sys.exit(2)
if "Log out" in r2.text or "/accounts/login/" not in r2.url:
    print("LOGIN_OK")
else:
    print("UNKNOWN", r2.text[:300])
