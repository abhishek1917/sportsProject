from django.contrib import admin

from .models import Invoice, InvoiceShare, Payment


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "student", "sport", "status", "total_paise", "period_start")
    list_filter = ("sport", "status")
    search_fields = ("number", "student__full_name")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "method", "amount_paise", "paid_at")


@admin.register(InvoiceShare)
class InvoiceShareAdmin(admin.ModelAdmin):
    list_display = ("invoice", "channel", "staff", "created_at")
