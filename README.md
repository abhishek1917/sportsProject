# Stadium booking

Django site for booking **Tennis** and **Cricket** court slots. Payment is offline at the venue. Confirmations go out by SMS (MSG91).

This is a **public website**. It must run on a cloud host, not on your laptop. If Django only runs on your computer, the site (and Twilio call webhooks) die when you shut the laptop. Tunnels like ngrok are only for quick local tests.

## Run locally (your computer, for development)

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py tailwind install
python manage.py migrate
python manage.py seed_sports
python manage.py createsuperuser
```

In two terminals:

```bash
python manage.py tailwind start
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Put it online (stays up when your laptop is off)

Use **Render** (or Railway / any VPS). You get a public HTTPS URL immediately. Later you point your own domain at the same app — no rewrite of the site.

1. Push this project to GitHub (do **not** commit `.env`).
2. Create a [Render](https://render.com) account, **New → Blueprint**, and select this repo (`render.yaml` is already in the project).
3. After the first deploy, open the service URL, e.g. `https://stadium-booking.onrender.com`.
4. In Render → Environment, set at least:
   - `DJANGO_ALLOWED_HOSTS` = that hostname (add your domain later, comma-separated)
   - `PUBLIC_BASE_URL` = `https://that-hostname` (change this to `https://www.yourdomain.com` when you have a domain)
   - `TWILIO_*`, `GEMINI_API_KEY`, and SMS keys when you need calling/SMS
5. Create a staff user on the server: Render shell → `python manage.py createsuperuser`

The database is Postgres on the host, so bookings are not stored on your laptop.

Render’s free web service can sleep after idle time and wake on the next visit. Free Postgres expires after 30 days unless you upgrade. For a real public stadium site, switch the web service (and later the database) to a paid always-on plan.

### Your own domain later

1. Buy a domain (GoDaddy, Namecheap, Google Domains, etc.).
2. In Render → Custom Domain, add `www.yourdomain.com` and follow their DNS instructions.
3. Update env vars:
   - `DJANGO_ALLOWED_HOSTS=your-render-host.onrender.com,www.yourdomain.com`
   - `PUBLIC_BASE_URL=https://www.yourdomain.com`
   - `CSRF_TRUSTED_ORIGINS=https://www.yourdomain.com`
4. Redeploy. The same server keeps running; only the name in the address bar changes.

## Internal API (voice agent)

- `GET/POST /api/availability/` — `sport` (`tennis` or `cricket`) and `date` (`YYYY-MM-DD`)
- `POST /api/bookings/` — JSON: `customer_name`, `phone`, `sport`, `date`, `start_times` (`["09:00"]` or `["09:00", "10:00"]`)

If `INTERNAL_API_KEY` is set, send it as the `X-Internal-Key` header.

## Book on call

Logged-in users (phone number required at signup) can click **Book on call**. The site places an outbound Twilio call to that number. Gemini talks to them and books only after they confirm, using the same slot rules as the website.

On the **hosted** site, set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `GEMINI_API_KEY`, and `PUBLIC_BASE_URL` (the live HTTPS origin, no trailing slash). Twilio must reach `/voice/answer/<id>/` and `/voice/input/<id>/`. Trial accounts can only call numbers you verify in the Twilio console.

Staff can also create bookings in `/admin/` while the phone agent is still a human.
