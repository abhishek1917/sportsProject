from django.contrib import admin

from .models import AttendanceRecord, FacilityManager, Student


@admin.register(FacilityManager)
class FacilityManagerAdmin(admin.ModelAdmin):
    list_display = ("user", "sport", "role", "display_name")
    list_filter = ("sport", "role")
    search_fields = ("user__username", "display_name")
    autocomplete_fields = ("user", "sport")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "age", "sport", "session", "is_active", "created_at")
    list_filter = ("sport", "session", "is_active")
    search_fields = ("full_name", "phone")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "status", "marked_by", "marked_at")
    list_filter = ("status", "date", "student__sport")
    date_hierarchy = "date"
    autocomplete_fields = ("student",)
