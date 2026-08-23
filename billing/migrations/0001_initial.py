import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("attendance", "0002_staff_roles"),
        ("bookings", "0003_sport_invoice_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Invoice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("number", models.CharField(max_length=40, unique=True)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("due_date", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("sent", "Sent"),
                            ("pending", "Pending"),
                            ("unpaid", "Unpaid"),
                            ("paid", "Paid"),
                            ("void", "Void"),
                        ],
                        default="draft",
                        max_length=12,
                    ),
                ),
                ("subtotal_paise", models.PositiveIntegerField(default=0)),
                ("tax_paise", models.PositiveIntegerField(default=0)),
                ("total_paise", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "issued_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="issued_invoices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "sport",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="invoices",
                        to="bookings.sport",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invoices",
                        to="attendance.student",
                    ),
                ),
            ],
            options={
                "ordering": ["-period_start", "student__full_name"],
            },
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "method",
                    models.CharField(
                        choices=[("cash", "Cash"), ("upi", "UPI")],
                        default="cash",
                        max_length=8,
                    ),
                ),
                ("amount_paise", models.PositiveIntegerField()),
                ("paid_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("reference", models.CharField(blank=True, max_length=80)),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="billing.invoice",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="InvoiceShare",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        choices=[("wa_me", "WhatsApp wa.me")],
                        default="wa_me",
                        max_length=12,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shares",
                        to="billing.invoice",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(
                fields=["sport", "status", "period_start"],
                name="billing_inv_sport_i_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                fields=("student", "period_start"),
                name="unique_student_invoice_period",
            ),
        ),
    ]
