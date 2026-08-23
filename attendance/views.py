from datetime import date
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .decorators import manager_required
from .forms import ManagerLoginForm, StudentForm
from .models import AttendanceRecord, Student


class FacilityLoginView(LoginView):
    template_name = "attendance/login.html"
    authentication_form = ManagerLoginForm
    redirect_authenticated_user = False

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and hasattr(request.user, "facility_manager"):
            return redirect("attendance:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        messages.success(
            self.request,
            f"Welcome to the {user.facility_manager.sport.name} facility panel.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("attendance:dashboard")


class FacilityLogoutView(LogoutView):
    next_page = reverse_lazy("attendance:login")


def _attendance_date(request) -> date:
    raw = request.GET.get("date") or request.POST.get("date")
    parsed = parse_date(raw) if raw else None
    return parsed or timezone.localdate()


def _theme(sport) -> dict:
    palettes = {
        "tennis": {
            "accent": "emerald",
            "hero": "from-emerald-900 via-emerald-700 to-lime-700",
            "chip": "bg-lime-100 text-lime-900",
        },
        "cricket": {
            "accent": "teal",
            "hero": "from-teal-950 via-teal-800 to-amber-700",
            "chip": "bg-amber-100 text-amber-950",
        },
    }
    return palettes.get(sport.slug, palettes["tennis"])


@manager_required
def dashboard(request):
    sport = request.managed_sport
    today = _attendance_date(request)
    students = Student.objects.filter(sport=sport, is_active=True)
    section_rows = []
    for key, label in Student.SESSION_CHOICES:
        in_batch = students.filter(session=key)
        marked = AttendanceRecord.objects.filter(
            student__sport=sport,
            student__session=key,
            student__is_active=True,
            date=today,
        )
        present = marked.filter(status=AttendanceRecord.STATUS_PRESENT).count()
        absent = marked.filter(status=AttendanceRecord.STATUS_ABSENT).count()
        total = in_batch.count()
        section_rows.append(
            {
                "key": key,
                "label": label,
                "total": total,
                "present": present,
                "absent": absent,
                "pending": max(total - present - absent, 0),
            }
        )
    return render(
        request,
        "attendance/dashboard.html",
        {
            "sport": sport,
            "manager": request.facility_manager,
            "theme": _theme(sport),
            "attendance_date": today,
            "sections": section_rows,
            "student_total": students.count(),
        },
    )


@manager_required
def section_roster(request, session):
    sport = request.managed_sport
    valid = {key for key, _label in Student.SESSION_CHOICES}
    if session not in valid:
        messages.error(request, "Unknown batch.")
        return redirect("attendance:dashboard")
    attendance_date = _attendance_date(request)
    students = list(
        Student.objects.filter(sport=sport, session=session, is_active=True)
    )
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
        {
            "sport": sport,
            "manager": request.facility_manager,
            "theme": _theme(sport),
            "session": session,
            "session_label": dict(Student.SESSION_CHOICES)[session],
            "attendance_date": attendance_date,
            "roster": roster,
        },
    )


@manager_required
@require_POST
def mark_attendance(request, student_id):
    sport = request.managed_sport
    student = get_object_or_404(Student, pk=student_id, sport=sport, is_active=True)
    attendance_date = _attendance_date(request)
    status = request.POST.get("status")
    if status not in {AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_ABSENT}:
        messages.error(request, "Choose Present or Absent.")
    else:
        AttendanceRecord.objects.update_or_create(
            student=student,
            date=attendance_date,
            defaults={"status": status, "marked_by": request.user},
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
        {
            "sport": sport,
            "manager": request.facility_manager,
            "theme": _theme(sport),
            "form": form,
            "student": instance,
        },
    )


@manager_required
def student_detail(request, student_id):
    sport = request.managed_sport
    student = get_object_or_404(Student, pk=student_id, sport=sport)
    history = student.attendance.order_by("-date")[:40]
    stats = student.attendance.aggregate(
        present=Count("id", filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
        absent=Count("id", filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
        total=Count("id"),
    )
    return render(
        request,
        "attendance/student_detail.html",
        {
            "sport": sport,
            "manager": request.facility_manager,
            "theme": _theme(sport),
            "student": student,
            "history": history,
            "stats": stats,
        },
    )
