from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .services import paise_to_rupees_label


def build_invoice_pdf(invoice) -> bytes:
    student = invoice.student
    sport = invoice.sport
    buffer = BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 20 * mm

    page.setFont("Helvetica-Bold", 16)
    page.drawString(20 * mm, y, sport.legal_name or f"{sport.name} academy")
    y -= 8 * mm
    page.setFont("Helvetica", 10)
    if sport.address:
        page.drawString(20 * mm, y, sport.address[:90])
        y -= 6 * mm
    if sport.gstin:
        page.drawString(20 * mm, y, f"GSTIN: {sport.gstin}")
        y -= 6 * mm
    page.drawString(20 * mm, y, f"Invoice {invoice.number}")
    y -= 6 * mm
    page.drawString(
        20 * mm,
        y,
        f"Period: {invoice.period_start.isoformat()} to {invoice.period_end.isoformat()}",
    )
    y -= 12 * mm
    page.setFont("Helvetica-Bold", 12)
    page.drawString(20 * mm, y, "Bill to")
    y -= 7 * mm
    page.setFont("Helvetica", 10)
    page.drawString(20 * mm, y, student.full_name)
    y -= 5 * mm
    page.drawString(
        20 * mm,
        y,
        f"Age {student.age} · {student.get_session_display()} · {sport.name}",
    )
    if student.guardian_name:
        y -= 5 * mm
        page.drawString(20 * mm, y, f"Guardian: {student.guardian_name}")
    y -= 14 * mm
    page.setFont("Helvetica-Bold", 10)
    page.drawString(20 * mm, y, "Description")
    page.drawRightString(190 * mm, y, "Amount")
    y -= 6 * mm
    page.setFont("Helvetica", 10)
    page.drawString(20 * mm, y, f"{student.get_membership_tier_display()} academy fee")
    page.drawRightString(190 * mm, y, paise_to_rupees_label(invoice.subtotal_paise))
    y -= 6 * mm
    page.drawString(20 * mm, y, "GST")
    page.drawRightString(190 * mm, y, paise_to_rupees_label(invoice.tax_paise))
    y -= 8 * mm
    page.setFont("Helvetica-Bold", 12)
    page.drawString(20 * mm, y, "Total")
    page.drawRightString(190 * mm, y, paise_to_rupees_label(invoice.total_paise))
    y -= 12 * mm
    page.setFont("Helvetica", 10)
    page.drawString(20 * mm, y, f"Status: {invoice.get_status_display()}")
    if invoice.status == invoice.STATUS_PAID:
        y -= 6 * mm
        page.setFillColorRGB(0.05, 0.45, 0.28)
        page.drawString(20 * mm, y, "PAID")
        page.setFillColorRGB(0, 0, 0)
    y -= 12 * mm
    if sport.upi_vpa:
        page.drawString(20 * mm, y, f"UPI: {sport.upi_vpa}")
        y -= 6 * mm
    page.drawString(20 * mm, y, "Pay at the venue desk or via UPI. This is a computer-generated invoice.")
    page.showPage()
    page.save()
    return buffer.getvalue()
