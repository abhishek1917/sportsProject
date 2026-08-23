from django.conf import settings
from django.db import models
from django.utils import timezone


class FacilityManager(models.Model):
    ROLE_OWNER = "owner"
    ROLE_MANAGER = "manager"
    ROLE_COACH = "coach"
    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_COACH, "Coach"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="facility_manager",
    )
    sport = models.ForeignKey(
        "bookings.Sport",
        on_delete=models.PROTECT,
        related_name="facility_managers",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_MANAGER)
    display_name = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["sport__name", "user__username"]

    def __str__(self):
        return f"{self.label} · {self.sport.name} ({self.get_role_display()})"

    @property
    def label(self):
        return self.display_name or self.user.get_full_name() or self.user.username

    def can_manage_students(self):
        return self.role in {self.ROLE_OWNER, self.ROLE_MANAGER}

    def can_bill(self):
        return self.role in {self.ROLE_OWNER, self.ROLE_MANAGER}

    def is_owner(self):
        return self.role == self.ROLE_OWNER

    def is_coach(self):
        return self.role == self.ROLE_COACH

    def assigned_sessions(self, sport):
        if not self.is_coach():
            return [key for key, _label in Student.SESSION_CHOICES]
        return list(
            self.assignments.filter(sport=sport).values_list("session", flat=True).distinct()
        )


class StaffVenue(models.Model):
    staff = models.ForeignKey(
        FacilityManager, on_delete=models.CASCADE, related_name="venues"
    )
    sport = models.ForeignKey(
        "bookings.Sport", on_delete=models.CASCADE, related_name="staff_links"
    )
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["staff", "sport"], name="unique_staff_venue"),
        ]

    def __str__(self):
        return f"{self.staff.label} · {self.sport.name}"


class CoachAssignment(models.Model):
    staff = models.ForeignKey(
        FacilityManager, on_delete=models.CASCADE, related_name="assignments"
    )
    sport = models.ForeignKey("bookings.Sport", on_delete=models.CASCADE)
    session = models.CharField(max_length=12)
    court_label = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["staff", "sport", "session", "court_label"],
                name="unique_coach_assignment",
            )
        ]

    def __str__(self):
        court = f" · {self.court_label}" if self.court_label else ""
        return f"{self.staff.label} · {self.sport.name} · {self.session}{court}"


class CoachAttendance(models.Model):
    STATUS_PRESENT = "present"
    STATUS_ABSENT = "absent"
    STATUS_CHOICES = [
        (STATUS_PRESENT, "Present"),
        (STATUS_ABSENT, "Absent"),
    ]

    staff = models.ForeignKey(
        FacilityManager, on_delete=models.CASCADE, related_name="checkins"
    )
    sport = models.ForeignKey("bookings.Sport", on_delete=models.CASCADE)
    date = models.DateField(default=timezone.localdate)
    session = models.CharField(max_length=12)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["staff", "date", "session"],
                name="unique_coach_checkin",
            )
        ]

    def __str__(self):
        return f"{self.staff.label} · {self.date} · {self.session} · {self.status}"


class Student(models.Model):
    SESSION_MORNING = "morning"
    SESSION_EVENING = "evening"
    SESSION_NIGHT = "night"
    SESSION_CHOICES = [
        (SESSION_MORNING, "Morning"),
        (SESSION_EVENING, "Evening"),
        (SESSION_NIGHT, "Night"),
    ]
    TIER_TRIAL = "trial"
    TIER_MONTHLY = "monthly"
    TIER_QUARTERLY = "quarterly"
    TIER_WALKIN = "walkin"
    TIER_CHOICES = [
        (TIER_TRIAL, "Trial"),
        (TIER_MONTHLY, "Monthly"),
        (TIER_QUARTERLY, "Quarterly"),
        (TIER_WALKIN, "Walk-in"),
    ]

    sport = models.ForeignKey(
        "bookings.Sport",
        on_delete=models.CASCADE,
        related_name="academy_students",
    )
    full_name = models.CharField(max_length=120)
    age = models.PositiveSmallIntegerField()
    session = models.CharField(max_length=12, choices=SESSION_CHOICES)
    phone = models.CharField(max_length=15, blank=True)
    guardian_name = models.CharField(max_length=120, blank=True)
    court_label = models.CharField(max_length=40, blank=True)
    membership_tier = models.CharField(
        max_length=16, choices=TIER_CHOICES, default=TIER_MONTHLY
    )
    monthly_fee_paise = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_students",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["session", "full_name"]
        indexes = [
            models.Index(
                fields=["sport", "session", "is_active"],
                name="attendance__sport_id_sess_idx",
            ),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.sport.name} · {self.get_session_display()})"

    @property
    def monthly_fee_rupees(self):
        return self.monthly_fee_paise / 100


class AttendanceRecord(models.Model):
    STATUS_PRESENT = "present"
    STATUS_ABSENT = "absent"
    STATUS_CHOICES = [
        (STATUS_PRESENT, "Present"),
        (STATUS_ABSENT, "Absent"),
    ]
    SOURCE_STAFF = "staff"
    SOURCE_COACH = "coach"
    SOURCE_CHOICES = [
        (SOURCE_STAFF, "Staff"),
        (SOURCE_COACH, "Coach"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="attendance"
    )
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    source = models.CharField(
        max_length=10, choices=SOURCE_CHOICES, default=SOURCE_STAFF
    )
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_attendance",
    )
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "student__full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "date"],
                name="unique_student_attendance_date",
            )
        ]

    def __str__(self):
        return f"{self.student.full_name} · {self.date} · {self.status}"
