from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import AttendanceRecord, FacilityManager, Student
from bookings.models import Customer, Sport


class AttendancePanelTests(TestCase):
    def setUp(self):
        self.tennis = Sport.objects.create(
            name="Tennis",
            slug="tennis",
            court_details="Courts",
            timings="6–22",
            rules="Rules",
        )
        self.cricket = Sport.objects.create(
            name="Cricket",
            slug="cricket",
            court_details="Nets",
            timings="6–22",
            rules="Rules",
        )
        self.owner = User.objects.create_user(
            username="tennis_owner", password="StaffPass2026!"
        )
        FacilityManager.objects.create(
            user=self.owner,
            sport=self.tennis,
            role=FacilityManager.ROLE_OWNER,
            display_name="Tennis Owner",
        )
        self.customer_user = User.objects.create_user(
            username="player", password="StrongPass2026!"
        )
        Customer.objects.create(
            user=self.customer_user, full_name="Player One", phone="919876543210"
        )
        self.client = Client()

    def test_customer_cannot_open_facility_panel(self):
        self.client.login(username="player", password="StrongPass2026!")
        response = self.client.get(reverse("attendance:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_customer_rejected_on_facility_login(self):
        response = self.client.post(
            reverse("attendance:login"),
            {"username": "player", "password": "StrongPass2026!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not a facility manager")

    def test_manager_login_opens_sport_dashboard(self):
        response = self.client.post(
            reverse("attendance:login"),
            {"username": "tennis_owner", "password": "StaffPass2026!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("attendance:dashboard"))
        dashboard = self.client.get(reverse("attendance:dashboard"))
        self.assertContains(dashboard, "Tennis academy")
        self.assertNotContains(dashboard, "Cricket academy")

    def test_owner_creates_student_in_own_sport_only(self):
        self.client.login(username="tennis_owner", password="StaffPass2026!")
        response = self.client.post(
            reverse("attendance:student_create"),
            {
                "full_name": "Asha Rao",
                "age": "14",
                "session": Student.SESSION_MORNING,
                "phone": "",
                "notes": "",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        student = Student.objects.get(full_name="Asha Rao")
        self.assertEqual(student.sport, self.tennis)
        self.assertEqual(student.session, Student.SESSION_MORNING)

        cricket_kid = Student.objects.create(
            sport=self.cricket,
            full_name="Cricket Kid",
            age=12,
            session=Student.SESSION_EVENING,
        )
        hidden = self.client.get(
            reverse("attendance:student_detail", args=[cricket_kid.pk])
        )
        self.assertEqual(hidden.status_code, 404)

    def test_mark_attendance(self):
        self.client.login(username="tennis_owner", password="StaffPass2026!")
        student = Student.objects.create(
            sport=self.tennis,
            full_name="Dev",
            age=11,
            session=Student.SESSION_NIGHT,
            created_by=self.owner,
        )
        today = timezone.localdate()
        response = self.client.post(
            reverse("attendance:mark_attendance", args=[student.pk]),
            {"status": "present", "date": today.isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        record = AttendanceRecord.objects.get(student=student, date=today)
        self.assertEqual(record.status, AttendanceRecord.STATUS_PRESENT)
        section = self.client.get(
            reverse("attendance:section", args=["night"]),
            {"date": today.isoformat()},
        )
        self.assertContains(section, "Dev")
        self.assertContains(section, "Present")
