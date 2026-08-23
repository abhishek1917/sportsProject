from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import (
    AttendanceRecord,
    CoachAssignment,
    CoachAttendance,
    FacilityManager,
    StaffVenue,
    Student,
)
from billing.models import Invoice, InvoiceShare
from bookings.models import Customer, Sport


def _sport(name, slug):
    return Sport.objects.create(
        name=name,
        slug=slug,
        court_details="Courts",
        timings="6–22",
        rules="Rules",
        invoice_prefix=slug[:3].upper(),
        legal_name=f"{name} Academy",
    )


class AttendancePanelTests(TestCase):
    def setUp(self):
        self.tennis = _sport("Tennis", "tennis")
        self.cricket = _sport("Cricket", "cricket")
        self.owner = User.objects.create_user(
            username="tennis_owner", password="StaffPass2026!"
        )
        self.owner_staff = FacilityManager.objects.create(
            user=self.owner,
            sport=self.tennis,
            role=FacilityManager.ROLE_OWNER,
            display_name="Tennis Owner",
        )
        StaffVenue.objects.create(
            staff=self.owner_staff, sport=self.tennis, is_default=True
        )
        StaffVenue.objects.create(staff=self.owner_staff, sport=self.cricket)
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
        self.assertContains(response, "not facility staff")

    def test_owner_login_opens_home(self):
        response = self.client.post(
            reverse("attendance:login"),
            {"username": "tennis_owner", "password": "StaffPass2026!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("attendance:home"))
        home = self.client.get(reverse("attendance:home"))
        self.assertContains(home, "Owner dashboard")
        self.assertContains(home, "Tennis")

    def test_owner_creates_student_in_own_sport_only(self):
        self.client.login(username="tennis_owner", password="StaffPass2026!")
        response = self.client.post(
            reverse("attendance:student_create"),
            {
                "full_name": "Asha Rao",
                "age": "14",
                "session": Student.SESSION_MORNING,
                "phone": "9876543211",
                "guardian_name": "",
                "court_label": "",
                "membership_tier": Student.TIER_MONTHLY,
                "monthly_fee_rupees": "4500",
                "notes": "",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        student = Student.objects.get(full_name="Asha Rao")
        self.assertEqual(student.sport, self.tennis)
        self.assertEqual(student.monthly_fee_paise, 450000)

        cricket_kid = Student.objects.create(
            sport=self.cricket,
            full_name="Cricket Kid",
            age=12,
            session=Student.SESSION_EVENING,
        )
        self.client.post(
            reverse("attendance:switch_venue"),
            {"venue_id": self.tennis.pk, "next": reverse("attendance:home")},
        )
        hidden = self.client.get(
            reverse("attendance:student_detail", args=[cricket_kid.pk])
        )
        self.assertEqual(hidden.status_code, 404)

    def test_owner_switches_venue(self):
        self.client.login(username="tennis_owner", password="StaffPass2026!")
        response = self.client.post(
            reverse("attendance:switch_venue"),
            {"venue_id": self.cricket.pk, "next": reverse("attendance:home")},
        )
        self.assertEqual(response.status_code, 302)
        home = self.client.get(reverse("attendance:home"))
        self.assertContains(home, "Cricket")

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


class CoachAttendanceTests(TestCase):
    def setUp(self):
        self.tennis = _sport("Tennis", "tennis")
        self.cricket = _sport("Cricket", "cricket")
        self.coach_user = User.objects.create_user(
            username="tennis_coach", password="StaffPass2026!"
        )
        self.coach = FacilityManager.objects.create(
            user=self.coach_user,
            sport=self.tennis,
            role=FacilityManager.ROLE_COACH,
            display_name="Eve Coach",
        )
        CoachAssignment.objects.create(
            staff=self.coach,
            sport=self.tennis,
            session=Student.SESSION_EVENING,
            court_label="",
        )
        self.eve = Student.objects.create(
            sport=self.tennis,
            full_name="Eve Student",
            age=13,
            session=Student.SESSION_EVENING,
        )
        self.morn = Student.objects.create(
            sport=self.tennis,
            full_name="Morning Student",
            age=13,
            session=Student.SESSION_MORNING,
        )
        self.cricket_kid = Student.objects.create(
            sport=self.cricket,
            full_name="Other Sport",
            age=13,
            session=Student.SESSION_EVENING,
        )
        self.client = Client()
        self.client.login(username="tennis_coach", password="StaffPass2026!")

    def test_coach_login_lands_on_attendance(self):
        self.client.logout()
        response = self.client.post(
            reverse("attendance:login"),
            {"username": "tennis_coach", "password": "StaffPass2026!"},
        )
        self.assertEqual(response.url, reverse("attendance:dashboard"))

    def test_coach_cannot_open_unassigned_batch(self):
        response = self.client.get(reverse("attendance:section", args=["morning"]))
        self.assertEqual(response.status_code, 302)

    def test_coach_marks_assigned_student(self):
        today = timezone.localdate()
        response = self.client.post(
            reverse("attendance:mark_attendance", args=[self.eve.pk]),
            {"status": "present", "date": today.isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        record = AttendanceRecord.objects.get(student=self.eve)
        self.assertEqual(record.source, AttendanceRecord.SOURCE_COACH)

    def test_coach_cannot_mark_other_batch_or_sport(self):
        self.client.post(
            reverse("attendance:mark_attendance", args=[self.morn.pk]),
            {"status": "present"},
        )
        self.assertFalse(AttendanceRecord.objects.filter(student=self.morn).exists())
        hidden = self.client.get(
            reverse("attendance:student_detail", args=[self.cricket_kid.pk])
        )
        self.assertEqual(hidden.status_code, 404)

    def test_coach_forbidden_from_billing_and_create(self):
        self.assertEqual(self.client.get(reverse("billing:invoice_list")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("attendance:student_create")).status_code, 403
        )

    def test_coach_checkin(self):
        response = self.client.post(
            reverse("attendance:coach_checkin"),
            {"session": Student.SESSION_EVENING},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CoachAttendance.objects.filter(
                staff=self.coach, session=Student.SESSION_EVENING
            ).exists()
        )


class BillingTests(TestCase):
    def setUp(self):
        self.tennis = _sport("Tennis", "tennis")
        self.owner = User.objects.create_user(
            username="bill_owner", password="StaffPass2026!"
        )
        FacilityManager.objects.create(
            user=self.owner,
            sport=self.tennis,
            role=FacilityManager.ROLE_OWNER,
            display_name="Owner",
        )
        self.student = Student.objects.create(
            sport=self.tennis,
            full_name="Fee Student",
            age=12,
            session=Student.SESSION_MORNING,
            phone="9876543210",
            monthly_fee_paise=450000,
        )
        self.client = Client()
        self.client.login(username="bill_owner", password="StaffPass2026!")

    def test_generate_pdf_and_whatsapp(self):
        gen = self.client.post(reverse("billing:generate_month"))
        self.assertEqual(gen.status_code, 302)
        invoice = Invoice.objects.get(student=self.student)
        pdf = self.client.get(reverse("billing:invoice_pdf", args=[invoice.pk]))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        wa = self.client.get(reverse("billing:whatsapp", args=[invoice.pk]))
        self.assertEqual(wa.status_code, 302)
        self.assertTrue(wa.url.startswith("https://wa.me/919876543210"))
        self.assertTrue(InvoiceShare.objects.filter(invoice=invoice).exists())
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.STATUS_SENT)
        paid = self.client.post(
            reverse("billing:set_status", args=[invoice.pk]),
            {"status": Invoice.STATUS_PAID},
        )
        self.assertEqual(paid.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.STATUS_PAID)
