from django.contrib.auth.models import User
from django.test import Client, TestCase

from bookings.models import Customer


class SignupTests(TestCase):
    def test_signup_creates_user_and_logs_in(self):
        client = Client()
        response = client.post(
            "/accounts/signup/",
            {
                "username": "newplayer",
                "full_name": "New Player",
                "phone": "9876543210",
                "password1": "StrongPass2026!",
                "password2": "StrongPass2026!",
            },
            HTTP_HOST="lotus-license-sandra-optical.trycloudflare.com",
            HTTP_X_FORWARDED_PROTO="https",
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")
        self.assertTrue(User.objects.filter(username="newplayer").exists())
        self.assertTrue(Customer.objects.filter(phone="919876543210").exists())

    def test_signup_shows_phone_error(self):
        Customer.objects.create(
            user=User.objects.create_user(username="existing", password="x"),
            full_name="Existing",
            phone="919876543210",
        )
        client = Client()
        response = client.post(
            "/accounts/signup/",
            {
                "username": "another",
                "full_name": "Another",
                "phone": "9876543210",
                "password1": "StrongPass2026!",
                "password2": "StrongPass2026!",
            },
            HTTP_HOST="lotus-license-sandra-optical.trycloudflare.com",
            HTTP_X_FORWARDED_PROTO="https",
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("phone number already exists", response.content.decode().lower())
