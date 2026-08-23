from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from billing.models import Invoice
from bookings.models import Slot

from .access import (
    coach_can_access_session,
    coach_can_mark_student,
    staff_home_url_name,
)
from .context import page_ctx
from .decorators import manager_required, staff_required
from .forms import ManagerLoginForm, StudentForm
from .models import (
    AttendanceRecord,
    CoachAssignment,
    CoachAttendance,
    FacilityManager,
    Student,
)


class FacilityLoginView(LoginView):
    template_name = "attendance/login.html"
    authentication_form = ManagerLoginForm
    redirect_authenticated_user = False

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and hasattr(request.user, "facility_manager"):
            name = staff_home_url_name(request.user.facility_manager)
            return redirect(name)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        messages.success(
            self.request,
            f"Welcome to the {user.facility_manager.sport.name} facility panel.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(staff_home_url_name(self.request.user.facility_manager))


class FacilityLogoutView(LogoutView):
    next_page = reverse_lazy("attendance:login")


def _attendance_date(request) -> date:
    raw = request.GET.get("date") or request.POST.get("date")
    parsed = parse_date(raw) if raw else None
    return parsed or timezone.localdate()


def _section_rows(sport, day, sessions=None):
    allowed = sessions or [key for key, _label in Student.SESSION_CHOICES]
    students = Student.objects.filter(sport=sport, is_active=True)
    rows = []
    for key, label in Student.SESSION_CHOICES:
        if key not in allowed:
            continue
        in_batch = students.filter(session=key)
        marked = AttendanceRecord.objects.filter(
            student__sport=sport,
            student__session=key,
            student__is_active=True,
            date=day,
        )
        present = marked.filter(status=AttendanceRecord.STATUS_PRESENT).count()
        absent = marked.filter(status=AttendanceRecord.STATUS_ABSENT).count()
        total = in_batch.count()
        rows.append(
            {
                "key": key,
                "label": label,
                "total": total,
                "present": present,
                "absent": absent,
                "pending": max(total - present - absent, 0),
            }
        )
    return rows, students.filter(session__in=allowed).count()


@staff_required
def home(request):
    staff = request.facility_manager
    if not staff.is_owner():
        return redirect("attendance:dashboard")
    sport = request.managed_sport
    today = timezone.localdate()
    students = Student.objects.filter(sport=sport, is_active=True)
    student_total = students.count()
    marked_today = AttendanceRecord.objects.filter(
        student__in=students, date=today
    ).count()
    roll_pct = int(round(100 * marked_today / student_total)) if student_total else 0
    unpaid = (
        Invoice.objects.filter(sport=sport, status__in=Invoice.OPEN_STATUSES).aggregate(
            s=Sum("total_paise")
        )["s"]
        or 0
    )
    window_start = today - timedelta(days=13)
    slots = Slot.objects.filter(sport=sport, date__gte=window_start, date__lte=today)
    slot_total = slots.count()
    slot_booked = slots.filter(is_booked=True).count()
    util_pct = int(round(100 * slot_booked / slot_total)) if slot_total else 0
    open_invoices = (
        Invoice.objects.filter(sport=sport, status__in=Invoice.OPEN_STATUSES)
        .select_related("student")[:8]
    )
    coach_rows = []
    coaches = FacilityManager.objects.filter(
        role=FacilityManager.ROLE_COACH, venues__sport=sport
    ).distinct()
    if not coaches.exists():
        coaches = FacilityManager.objects.filter(
            role=FacilityManager.ROLE_COACH, sport=sport
        )
    for coach in coaches:
        checkins = CoachAttendance.objects.filter(
            staff=coach, sport=sport, date=today, status=CoachAttendance.STATUS_PRESENT
        ).count()
        assigned = CoachAssignment.objects.filter(staff=coach, sport=sport).count()
        coach_rows.append(
            {"coach": coach, "checkins": checkins, "assigned": assigned}
        )
    return render(
        request,
        "attendance/home.html",
        page_ctx(
            request,
            today=today,
            student_total=student_total,
            marked_today=marked_today,
            roll_pct=roll_pct,
            unpaid_paise=unpaid,
            unpaid_rupees=unpaid / 100,
            util_pct=util_pct,
            slot_booked=slot_booked,
            slot_total=slot_total,
            open_invoices=open_invoices,
            coach_rows=coach_rows,
            sections=_section_rows(sport, today)[0],
        ),
    )


@staff_required
def dashboard(request):
    sport = request.managed_sport
    staff = request.facility_manager
    today = _attendance_date(request)
    sessions = staff.assigned_sessions(sport)
    if staff.is_coach() and not sessions:
        messages.warning(
            request,
            "No batch is assigned to you yet. Ask the owner to add a coach assignment.",
        )
    section_rows, student_total = _section_rows(sport, today, sessions)
    checkins = {}
    if staff.is_coach():
        checkins = {
            row.session: row
            for row in CoachAttendance.objects.filter(
                staff=staff, sport=sport, date=today
            )
        }
    return render(
        request,
        "attendance/dashboard.html",
        page_ctx(
            request,
            attendance_date=today,
            sections=section_rows,
            student_total=student_total,
            coach_checkins=checkins,
        ),
    )


@staff_required
@require_POST
def switch_venue(request):
    staff = request.facility_manager
    if not staff.is_owner():
        messages.error(request, "Only owners can switch venues.")
        return redirect("attendance:dashboard")
    try:
        venue_id = int(request.POST.get("venue_id") or 0)
    except (TypeError, ValueError):
        venue_id = 0
    allowed = {sport.pk for sport in getattr(request, "managed_venues", [])}
    if venue_id not in allowed:
        messages.error(request, "That venue is not linked to your login.")
        return redirect("attendance:home")
    request.session["venue_id"] = venue_id
    next_url = request.POST.get("next") or reverse("attendance:home")
    return redirect(next_url)


@staff_required
@require_POST
def coach_checkin(request):
    staff = request.facility_manager
    sport = request.managed_sport
    session = request.POST.get("session")
    if not coach_can_access_session(staff, sport, session or ""):
        messages.error(request, "You are not assigned to that batch.")
        return redirect("attendance:dashboard")
    CoachAttendance.objects.update_or_create(
        staff=staff,
        date=timezone.localdate(),
        session=session,
        defaults={"sport": sport, "status": CoachAttendance.STATUS_PRESENT},
    )
    messages.success(request, f"Checked in for {session} today.")
    return redirect("attendance:dashboard")


@staff_required
def section_roster(request, session):
    sport = request.managed_sport
    staff = request.facility_manager
    valid = {key for key, _label in Student.SESSION_CHOICES}
    if session not in valid:
        messages.error(request, "Unknown batch.")
        return redirect("attendance:dashboard")
    if not coach_can_access_session(staff, sport, session):
        messages.error(request, "That batch is not assigned to you.")
        return redirect("attendance:dashboard")
    attendance_date = _attendance_date(request)
    students = list(
        Student.objects.filter(sport=sport, session=session, is_active=True)
    )
    if staff.is_coach():
        students = [student for student in students if coach_can_mark_student(staff, student)]
    records = {
        record.student_id: record
        for record in AttendanceRecord.objects.filter(
            student__in=students, date=attendance_date
        )
    }
    roster = [{"student": student, "record": records.get(student.pk)} for student in students]
    return render(
        request,
        "attendance/section.html",
        page_ctx(
            request,
            session=session,
            session_label=dict(Student.SESSION_CHOICES)[session],
            attendance_date=attendance_date,
            roster=roster,
        ),
    )


@staff_required
@require_POST
def mark_attendance(request, student_id):
    sport = request.managed_sport
    staff = request.facility_manager
    student = get_object_or_404(Student, pk=student_id, sport=sport, is_active=True)
    if not coach_can_mark_student(staff, student):
        messages.error(request, "You cannot mark that student.")
        return redirect("attendance:dashboard")
    attendance_date = _attendance_date(request)
    status = request.POST.get("status")
    if status not in {AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_ABSENT}:
        messages.error(request, "Choose Present or Absent.")
    else:
        source = (
            AttendanceRecord.SOURCE_COACH
            if staff.is_coach()
            else AttendanceRecord.SOURCE_STAFF
        )
        AttendanceRecord.objects.update_or_create(
            student=student,
            date=attendance_date,
            defaults={
                "status": status,
                "marked_by": request.user,
                "source": source,
            },
        )
        messages.success(
            request,
            f"Marked {student.full_name} {status} for {attendance_date}.",
        )
    next_url = request.POST.get("next") or reverse(
        "attendance:section", kwargs={"session": student.session}
    )
    query = urlencode({"date": attendance_date.isoformat()})
    joiner = "&" if "?" in next_url else "?"
    return redirect(f"{next_url}{joiner}{query}")


@manager_required
def student_create(request):
    return _student_form(request, instance=None)


@manager_required
def student_edit(request, student_id):
    student = get_object_or_404(Student, pk=student_id, sport=request.managed_sport)
    return _student_form(request, instance=student)


def _student_form(request, instance):
    sport = request.managed_sport
    if request.method == "POST":
        form = StudentForm(request.POST, instance=instance)
        if form.is_valid():
            student = form.save(commit=False)
            student.sport = sport
            if instance is None:
                student.created_by = request.user
            student.save()
            verb = "updated" if instance else "created"
            messages.success(request, f"Profile {verb} for {student.full_name}.")
            return redirect("attendance:student_detail", student_id=student.pk)
    else:
        form = StudentForm(instance=instance)
        if instance is None and request.GET.get("session") in {
            Student.SESSION_MORNING,
            Student.SESSION_EVENING,
            Student.SESSION_NIGHT,
        }:
            form.initial["session"] = request.GET["session"]
    return render(
        request,
        "attendance/student_form.html",
        page_ctx(request, form=form, student=instance),
    )


@staff_required
def student_detail(request, student_id):
    staff = request.facility_manager
    student = get_object_or_404(Student, pk=student_id, sport=request.managed_sport)
    if staff.is_coach() and not coach_can_mark_student(staff, student):
        messages.error(request, "You cannot open that profile.")
        return redirect("attendance:dashboard")
    history = student.attendance.order_by("-date")[:40]
    stats = student.attendance.aggregate(
        present=Count("id", filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
        absent=Count("id", filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
        total=Count("id"),
    )
    invoices = []
    if staff.can_bill():
        invoices = student.invoices.order_by("-period_start")[:12]
    return render(
        request,
        "attendance/student_detail.html",
        page_ctx(request, student=student, history=history, stats=stats, invoices=invoices),
    )


@manager_required
def staff_board(request):
    sport = request.managed_sport
    today = timezone.localdate()
    coaches = FacilityManager.objects.filter(role=FacilityManager.ROLE_COACH).filter(
        Q(sport=sport) | Q(venues__sport=sport)
    ).distinct()
    rows = []
    for coach in coaches:
        assignments = list(coach.assignments.filter(sport=sport))
        checkins = {
            item.session: item
            for item in CoachAttendance.objects.filter(
                staff=coach, sport=sport, date=today
            )
        }
        rows.append(
            {"coach": coach, "assignments": assignments, "checkins": checkins}
        )
    return render(
        request,
        "attendance/staff.html",
        page_ctx(request, today=today, coach_rows=rows),
    )
