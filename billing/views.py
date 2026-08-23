from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.core import signing
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from attendance.context import page_ctx
from attendance.decorators import manager_required
from bookings.services import BookingError, normalize_phone

from .models import Invoice, InvoiceShare, Payment
from .pdf import build_invoice_pdf
from .services import generate_month_invoices, paise_to_rupees_label

SIGN_SALT = getattr(settings, "INVOICE_SIGNING_SALT", "invoice-pdf-v1")
TOKEN_MAX_AGE = 7 * 24 * 60 * 60


def invoice_token(invoice: Invoice) -> str:
    return signing.dumps({"id": invoice.pk}, salt=SIGN_SALT)


def invoice_from_token(token: str) -> Invoice | None:
    try:
        payload = signing.loads(token, salt=SIGN_SALT, max_age=TOKEN_MAX_AGE)
    except signing.BadSignature:
        return None
    return Invoice.objects.filter(pk=payload.get("id")).select_related(
        "student", "sport"
    ).first()


def public_invoice_url(request, invoice: Invoice) -> str:
    base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").rstrip("/")
    path = reverse("public_invoice", kwargs={"token": invoice_token(invoice)})
    if base:
        return f"{base}{path}"
    return request.build_absolute_uri(path)


@manager_required
def invoice_list(request):
    sport = request.managed_sport
    status = request.GET.get("status") or "open"
    qs = Invoice.objects.filter(sport=sport).select_related("student")
    if status == "open":
        qs = qs.filter(status__in=Invoice.OPEN_STATUSES)
    elif status == "paid":
        qs = qs.filter(status=Invoice.STATUS_PAID)
    elif status != "all":
        qs = qs.filter(status=status)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(student__full_name__icontains=q)
    return render(
        request,
        "billing/invoice_list.html",
        page_ctx(
            request,
            invoices=qs[:200],
            status_filter=status,
            q=q,
            paise_to_rupees_label=paise_to_rupees_label,
        ),
    )


@manager_required
@require_POST
def generate_month(request):
    created = generate_month_invoices(
        sport=request.managed_sport, user=request.user
    )
    messages.success(
        request,
        f"Created {created} invoice{'' if created == 1 else 's'} for this month.",
    )
    return redirect("billing:invoice_list")


@manager_required
@require_POST
def set_status(request, invoice_id):
    invoice = get_object_or_404(
        Invoice, pk=invoice_id, sport=request.managed_sport
    )
    status = request.POST.get("status")
    allowed = {
        Invoice.STATUS_SENT,
        Invoice.STATUS_PENDING,
        Invoice.STATUS_UNPAID,
        Invoice.STATUS_PAID,
        Invoice.STATUS_VOID,
    }
    if status not in allowed:
        messages.error(request, "Unknown invoice status.")
        return redirect("billing:invoice_list")
    if status == Invoice.STATUS_PAID and invoice.status != Invoice.STATUS_PAID:
        Payment.objects.create(
            invoice=invoice,
            method=request.POST.get("method") or Payment.METHOD_CASH,
            amount_paise=invoice.total_paise,
            recorded_by=request.user,
        )
    invoice.status = status
    invoice.save(update_fields=["status", "updated_at"])
    messages.success(request, f"{invoice.number} marked {invoice.get_status_display()}.")
    return redirect(request.POST.get("next") or reverse("billing:invoice_list"))


@manager_required
def invoice_pdf(request, invoice_id):
    invoice = get_object_or_404(
        Invoice.objects.select_related("student", "sport"),
        pk=invoice_id,
        sport=request.managed_sport,
    )
    pdf = build_invoice_pdf(invoice)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{invoice.number}.pdf"'
    return response


def public_pdf(request, token):
    invoice = invoice_from_token(token)
    if invoice is None or invoice.status == Invoice.STATUS_VOID:
        return HttpResponseForbidden("This invoice link is invalid or expired.")
    pdf = build_invoice_pdf(invoice)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{invoice.number}.pdf"'
    return response


@manager_required
def whatsapp_share(request, invoice_id):
    invoice = get_object_or_404(
        Invoice.objects.select_related("student", "sport"),
        pk=invoice_id,
        sport=request.managed_sport,
    )
    try:
        phone = normalize_phone(invoice.student.phone)
    except BookingError:
        messages.error(
            request,
            f"{invoice.student.full_name} needs a valid 10-digit phone for WhatsApp.",
        )
        return redirect("billing:invoice_list")
    link = public_invoice_url(request, invoice)
    caption = (
        f"{invoice.sport.name} academy invoice {invoice.number} for "
        f"{invoice.student.full_name}. Period {invoice.period_start} to "
        f"{invoice.period_end}. Amount {paise_to_rupees_label(invoice.total_paise)}. "
        f"Download: {link}"
    )
    InvoiceShare.objects.create(
        invoice=invoice, channel=InvoiceShare.CHANNEL_WA, staff=request.user
    )
    if invoice.status == Invoice.STATUS_DRAFT:
        invoice.status = Invoice.STATUS_SENT
        invoice.save(update_fields=["status", "updated_at"])
    return redirect(f"https://wa.me/{phone}?text={quote(caption)}")
