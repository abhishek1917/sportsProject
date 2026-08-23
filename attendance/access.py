from calendar import monthrange
from datetime import date

from django.utils import timezone

from attendance.models import FacilityManager, StaffVenue, Student


def staff_home_url_name(staff: FacilityManager) -> str:
    if staff.is_owner():
        return "attendance:home"
    return "attendance:dashboard"


def linked_sports(staff: FacilityManager):
    sports = [link.sport for link in staff.venues.select_related("sport").all()]
    if not sports:
        sports = [staff.sport]
    return sports


def resolve_managed_sport(request, staff: FacilityManager):
    sports = linked_sports(staff)
    if staff.is_owner() and sports:
        raw = request.session.get("venue_id")
        chosen = next((sport for sport in sports if sport.pk == raw), None)
        if chosen is None:
            default_link = staff.venues.filter(is_default=True).select_related("sport").first()
            chosen = default_link.sport if default_link else sports[0]
            request.session["venue_id"] = chosen.pk
        request.managed_venues = sports
        return chosen
    request.managed_venues = sports
    return staff.sport


def month_bounds(day: date | None = None):
    day = day or timezone.localdate()
    start = day.replace(day=1)
    end = day.replace(day=monthrange(day.year, day.month)[1])
    return start, end


def coach_can_access_session(staff: FacilityManager, sport, session: str) -> bool:
    if not staff.is_coach():
        return True
    return staff.assignments.filter(sport=sport, session=session).exists()


def coach_can_mark_student(staff: FacilityManager, student: Student) -> bool:
    if not staff.is_coach():
        return True
    qs = staff.assignments.filter(sport=student.sport, session=student.session)
    if student.court_label:
        labeled = qs.filter(court_label=student.court_label)
        if labeled.exists():
            return True
        return qs.filter(court_label="").exists()
    return qs.exists()
