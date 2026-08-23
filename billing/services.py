from calendar import monthrange

from django.db.models import Max
from django.utils import timezone

from attendance.models import Student
from bookings.models import Sport

from .models import Invoice


def rupees_to_paise(value) -> int:
    try:
        rupees = float(value)
    except (TypeError, ValueError):
        return 0
    return int(round(rupees * 100))


def paise_to_rupees_label(paise: int) -> str:
    return f"₹{paise / 100:.2f}"


def next_invoice_number(sport: Sport, period_start) -> str:
    prefix = (sport.invoice_prefix or sport.slug[:3]).upper()
    stamp = period_start.strftime("%Y-%m")
    startswith = f"INV-{prefix}-{stamp}-"
    last = (
        Invoice.objects.filter(number__startswith=startswith)
        .aggregate(Max("number"))
        .get("number__max")
    )
    seq = 1
    if last:
        try:
            seq = int(last.rsplit("-", 1)[-1]) + 1
        except ValueError:
            seq = Invoice.objects.filter(number__startswith=startswith).count() + 1
    return f"{startswith}{seq:04d}"


def tax_for(sport: Sport, subtotal_paise: int) -> int:
    if not (sport.gstin or "").strip():
        return 0
    return int(round(subtotal_paise * 0.18))


def generate_month_invoices(*, sport: Sport, user, day=None) -> int:
    day = day or timezone.localdate()
    period_start = day.replace(day=1)
    period_end = day.replace(day=monthrange(day.year, day.month)[1])
    created = 0
    students = Student.objects.filter(
        sport=sport, is_active=True, monthly_fee_paise__gt=0
    ).exclude(membership_tier=Student.TIER_WALKIN)
    for student in students:
        if Invoice.objects.filter(student=student, period_start=period_start).exists():
            continue
        subtotal = student.monthly_fee_paise
        tax = tax_for(sport, subtotal)
        Invoice.objects.create(
            student=student,
            sport=sport,
            number=next_invoice_number(sport, period_start),
            period_start=period_start,
            period_end=period_end,
            due_date=period_end,
            status=Invoice.STATUS_DRAFT,
            subtotal_paise=subtotal,
            tax_paise=tax,
            total_paise=subtotal + tax,
            issued_by=user,
        )
        created += 1
    return created
