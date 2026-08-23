from django.conf import settings
from django.db import models
from django.utils import timezone


class Invoice(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_PENDING = "pending"
    STATUS_UNPAID = "unpaid"
    STATUS_PAID = "paid"
    STATUS_VOID = "void"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SENT, "Sent"),
        (STATUS_PENDING, "Pending"),
        (STATUS_UNPAID, "Unpaid"),
        (STATUS_PAID, "Paid"),
        (STATUS_VOID, "Void"),
    ]
    OPEN_STATUSES = (STATUS_DRAFT, STATUS_SENT, STATUS_PENDING, STATUS_UNPAID)

    student = models.ForeignKey(
        "attendance.Student", on_delete=models.CASCADE, related_name="invoices"
    )
    sport = models.ForeignKey(
        "bookings.Sport", on_delete=models.PROTECT, related_name="invoices"
    )
    number = models.CharField(max_length=40, unique=True)
    period_start = models.DateField()
    period_end = models.DateField()
    due_date = models.DateField()
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )
    subtotal_paise = models.PositiveIntegerField(default=0)
    tax_paise = models.PositiveIntegerField(default=0)
    total_paise = models.PositiveIntegerField(default=0)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_start", "student__full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "period_start"],
                name="unique_student_invoice_period",
            )
        ]
        indexes = [
            models.Index(
                fields=["sport", "status", "period_start"],
                name="billing_inv_sport_i_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} · {self.student.full_name}"

    @property
    def total_rupees(self):
        return self.total_paise / 100

    def is_open(self):
        return self.status in self.OPEN_STATUSES


class Payment(models.Model):
    METHOD_CASH = "cash"
    METHOD_UPI = "upi"
    METHOD_CHOICES = [
        (METHOD_CASH, "Cash"),
        (METHOD_UPI, "UPI"),
    ]

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="payments"
    )
    method = models.CharField(max_length=8, choices=METHOD_CHOICES, default=METHOD_CASH)
    amount_paise = models.PositiveIntegerField()
    paid_at = models.DateTimeField(default=timezone.now)
    reference = models.CharField(max_length=80, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.invoice.number} · {self.amount_paise} paise"


class InvoiceShare(models.Model):
    CHANNEL_WA = "wa_me"
    CHANNEL_CHOICES = [(CHANNEL_WA, "WhatsApp wa.me")]

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="shares"
    )
    channel = models.CharField(max_length=12, choices=CHANNEL_CHOICES, default=CHANNEL_WA)
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.invoice.number} · {self.channel}"
