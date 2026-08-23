from django.conf import settings
from django.db import models
from django.utils import timezone


class FacilityManager(models.Model):
    ROLE_OWNER = "owner"
    ROLE_MANAGER = "manager"
    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_MANAGER, "Manager"),
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


class Student(models.Model):
    SESSION_MORNING = "morning"
    SESSION_EVENING = "evening"
    SESSION_NIGHT = "night"
    SESSION_CHOICES = [
        (SESSION_MORNING, "Morning"),
        (SESSION_EVENING, "Evening"),
        (SESSION_NIGHT, "Night"),
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


class AttendanceRecord(models.Model):
    STATUS_PRESENT = "present"
    STATUS_ABSENT = "absent"
    STATUS_CHOICES = [
        (STATUS_PRESENT, "Present"),
        (STATUS_ABSENT, "Absent"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="attendance"
    )
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
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
