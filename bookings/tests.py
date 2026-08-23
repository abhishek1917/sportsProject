from datetime import timedelta

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from bookings.agent import _run_tool
from bookings.calls import customer_from_phone, queue_inbound_call, stadium_dial_number
from bookings.models import Booking, CallSession, Customer, Slot, Sport
from bookings.services import BookingError, cancel_booking, create_booking
from bookings.slots import ensure_slots_for_date


class BookingRulesTests(TestCase):
    def setUp(self):
        self.sport = Sport.objects.create(
            name="Tennis",
            slug="tennis",
            court_details="Court",
            timings="6–10",
            rules="Max 4",
        )
        self.day = timezone.localdate() + timedelta(days=1)
        ensure_slots_for_date(self.sport, self.day)
        self.slots = list(
            Slot.objects.filter(sport=self.sport, date=self.day).order_by("start_time")[:3]
        )
        self.customer = self._customer("ada", "9876543210", "Ada Lovelace")
        self.other = self._customer("al", "9876543211", "Alan Turing")

    def _customer(self, username, phone, name):
        user = User.objects.create_user(username=username, password="pass12345")
        return Customer.objects.create(user=user, phone=f"91{phone[-10:]}", full_name=name)

    def test_one_hour_booking_locks_slot(self):
        booking = create_booking(
            customer=self.customer, slots=[self.slots[0]], created_via=Booking.VIA_SELF
        )
        self.slots[0].refresh_from_db()
        self.assertTrue(self.slots[0].is_booked)
        self.assertEqual(booking.slots.count(), 1)

    def test_two_consecutive_hours(self):
        booking = create_booking(
            customer=self.customer,
            slots=[self.slots[0], self.slots[1]],
            created_via=Booking.VIA_SELF,
        )
        self.assertEqual(booking.slots.count(), 2)

    def test_non_consecutive_rejected(self):
        with self.assertRaises(BookingError):
            create_booking(
                customer=self.customer,
                slots=[self.slots[0], self.slots[2]],
                created_via=Booking.VIA_SELF,
            )

    def test_double_booking_rejected(self):
        create_booking(
            customer=self.customer, slots=[self.slots[0]], created_via=Booking.VIA_SELF
        )
        with self.assertRaises(BookingError):
            create_booking(
                customer=self.other, slots=[self.slots[0]], created_via=Booking.VIA_PHONE
            )

    def test_one_active_booking_per_customer(self):
        create_booking(
            customer=self.customer, slots=[self.slots[0]], created_via=Booking.VIA_SELF
        )
        with self.assertRaises(BookingError):
            create_booking(
                customer=self.customer, slots=[self.slots[1]], created_via=Booking.VIA_SELF
            )

    def test_cancel_releases_slot(self):
        booking = create_booking(
            customer=self.customer, slots=[self.slots[0]], created_via=Booking.VIA_SELF
        )
        cancel_booking(booking=booking, customer=self.customer)
        self.slots[0].refresh_from_db()
        self.assertFalse(self.slots[0].is_booked)
        create_booking(
            customer=self.other, slots=[self.slots[0]], created_via=Booking.VIA_ADMIN
        )

    def test_sport_pages_and_search(self):
        Sport.objects.create(
            name="Cricket",
            slug="cricket",
            court_details="Nets",
            timings="6–10",
            rules="Max 4",
        )
        client = self.client
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get("/tennis/").status_code, 200)
        self.assertEqual(client.get("/cricket/").status_code, 200)
        response = client.get("/?q=tennis court")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/tennis/")
        api = client.get(f"/api/availability/?sport=tennis&date={self.day.isoformat()}")
        self.assertEqual(api.status_code, 200)
        self.assertTrue(api.json()["ok"])
        call_page = client.get("/book-on-call/")
        self.assertEqual(call_page.status_code, 302)


class VoiceAgentTests(TestCase):
    def setUp(self):
        self.sport = Sport.objects.create(
            name="Tennis",
            slug="tennis",
            court_details="Court",
            timings="6–10",
            rules="Max 4",
        )
        self.day = timezone.localdate() + timedelta(days=1)
        ensure_slots_for_date(self.sport, self.day)
        self.slot = Slot.objects.filter(sport=self.sport, date=self.day).order_by("start_time").first()
        user = User.objects.create_user(username="phone_user", password="pass12345")
        self.customer = Customer.objects.create(
            user=user,
            phone="917393912936",
            full_name="Test User",
        )
        self.session = CallSession.objects.create(customer=self.customer, sport_slug="tennis")

    def test_customer_from_phone_matches_indian_number(self):
        self.assertEqual(customer_from_phone("+917393912936"), self.customer)
        self.assertEqual(customer_from_phone("7393912936"), self.customer)

    def test_create_booking_tool_books_slot(self):
        start = self.slot.start_time.strftime("%H:%M")
        result = _run_tool(
            self.session,
            "create_booking",
            {"sport": "tennis", "date": self.day.isoformat(), "start_times": [start]},
        )
        self.assertTrue(result.startswith("BOOKED_OK"))
        self.slot.refresh_from_db()
        self.assertTrue(self.slot.is_booked)
        self.assertEqual(self.customer.bookings.count(), 1)
        self.assertEqual(self.customer.bookings.first().created_via, Booking.VIA_PHONE)

    def test_create_booking_tool_rejects_missing_time(self):
        result = _run_tool(
            self.session,
            "create_booking",
            {"sport": "tennis", "date": self.day.isoformat(), "start_times": ["23:00"]},
        )
        self.assertIn("not available", result)
        self.assertEqual(self.customer.bookings.count(), 0)

    @override_settings(PUBLIC_BASE_URL="https://example.com")
    @patch("bookings.voice_views.next_agent_reply", return_value=("Hello there.", False))
    def test_voice_inbound_links_pending_session(self, mock_reply):
        queue_inbound_call(customer=self.customer, sport_slug="tennis")
        response = Client().post(
            "/voice/inbound/",
            {"From": "+917393912936", "CallSid": "CA123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Hello there.", response.content)
        session = CallSession.objects.filter(customer=self.customer).latest("pk")
        self.assertEqual(session.status, CallSession.STATUS_IN_PROGRESS)
        self.assertEqual(session.sport_slug, "tennis")
        mock_reply.assert_called_once()

    def test_stadium_dial_number_from_exophone(self):
        with override_settings(EXOTEL_FROM_NUMBER="08047361459", TWILIO_FROM_NUMBER=""):
            self.assertEqual(stadium_dial_number(), "+918047361459")

    @override_settings(
        EXOTEL_ACCOUNT_SID="sid",
        EXOTEL_API_KEY="key",
        EXOTEL_API_TOKEN="token",
        EXOTEL_FROM_NUMBER="08047361459",
        GEMINI_API_KEY="test-gemini",
        PUBLIC_BASE_URL="https://example.com",
    )
    def test_book_on_call_queues_and_opens_dialer(self):
        self.client.force_login(self.customer.user)
        response = self.client.get("/book-on-call/?dial=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tel:+918047361459")
        self.assertContains(response, "Open dialer")
        self.assertFalse(b"Call me now" in response.content)
        session = CallSession.objects.filter(customer=self.customer).latest("pk")
        self.assertEqual(session.status, CallSession.STATUS_QUEUED)

    @override_settings(
        EXOTEL_ACCOUNT_SID="sid",
        EXOTEL_API_KEY="key",
        EXOTEL_API_TOKEN="token",
        EXOTEL_FROM_NUMBER="08047361459",
        GEMINI_API_KEY="test-gemini",
        PUBLIC_BASE_URL="https://example.com",
    )
    def test_book_on_call_post_returns_tel_json(self):
        self.client.force_login(self.customer.user)
        response = self.client.post(
            "/book-on-call/",
            {"mode": "inbound", "sport": "tennis"},
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["tel"], "+918047361459")
        session = CallSession.objects.get(pk=payload["session_id"])
        self.assertEqual(session.sport_slug, "tennis")
        self.assertEqual(session.status, CallSession.STATUS_QUEUED)
