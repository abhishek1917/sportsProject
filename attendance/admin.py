from django.contrib import admin

from .models import (
    AttendanceRecord,
    CoachAssignment,
    CoachAttendance,
    FacilityManager,
    StaffVenue,
    Student,
)


class StaffVenueInline(admin.TabularInline):
    model = StaffVenue
    extra = 1
    autocomplete_fields = ("sport",)


class CoachAssignmentInline(admin.TabularInline):
    model = CoachAssignment
    extra = 1
    autocomplete_fields = ("sport",)


@admin.register(FacilityManager)
class FacilityManagerAdmin(admin.ModelAdmin):
    list_display = ("user", "sport", "role", "display_name")
    list_filter = ("sport", "role")
    search_fields = ("user__username", "display_name")
    autocomplete_fields = ("user", "sport")
    inlines = (StaffVenueInline, CoachAssignmentInline)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "age",
        "sport",
        "session",
        "membership_tier",
        "is_active",
    )
    list_filter = ("sport", "session", "is_active")
    search_fields = ("full_name", "phone")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "status", "source", "marked_by")
    list_filter = ("status", "source", "date", "student__sport")
    date_hierarchy = "date"
    autocomplete_fields = ("student",)


@admin.register(CoachAttendance)
class CoachAttendanceAdmin(admin.ModelAdmin):
    list_display = ("staff", "sport", "date", "session", "status")
    list_filter = ("sport", "session", "status")
