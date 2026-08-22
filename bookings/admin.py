from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import Booking, CallSession, Customer, Slot, Sport
from .services import BookingError, create_booking, customer_has_active_booking


@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "timings")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ("sport", "date", "start_time", "end_time", "is_booked")
    list_filter = ("sport", "date", "is_booked")
    search_fields = ("sport__name",)
    date_hierarchy = "date"
    ordering = ("date", "start_time")
    readonly_fields = ("is_booked",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "user")
    search_fields = ("full_name", "phone", "user__username")


class BookingAdminForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ("customer", "slots", "status", "created_via")

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk:
            return cleaned
        slots = list(cleaned.get("slots") or [])
        customer = cleaned.get("customer")
        if not slots:
            raise ValidationError("Select 1 or 2 consecutive slots.")
        try:
            Booking.validate_slot_selection(slots)
        except ValidationError:
            raise
        if any(slot.is_booked for slot in slots):
            raise ValidationError("One of those slots is already booked.")
        if customer and customer_has_active_booking(customer):
            raise ValidationError("This customer already has an active booking.")
        return cleaned


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    form = BookingAdminForm
    list_display = ("id", "customer", "status", "created_via", "created_at", "slot_summary")
    list_filter = ("status", "created_via", "created_at")
    autocomplete_fields = ("customer",)
    filter_horizontal = ("slots",)
    readonly_fields = ("created_at",)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("created_at", "customer", "slots", "created_via")
        return ("created_at",)

    def slot_summary(self, obj):
        return obj.summary_times()

    slot_summary.short_description = "When"

    def save_model(self, request, obj, form, change):
        if change:
            previous = Booking.objects.get(pk=obj.pk)
            super().save_model(request, obj, form, change)
            if (
                previous.status != Booking.STATUS_CANCELLED
                and obj.status == Booking.STATUS_CANCELLED
            ):
                Slot.objects.filter(pk__in=obj.slots.values_list("pk", flat=True)).update(
                    is_booked=False
                )
            return
        try:
            booking = create_booking(
                customer=form.cleaned_data["customer"],
                slots=form.cleaned_data["slots"],
                created_via=form.cleaned_data.get("created_via") or Booking.VIA_ADMIN,
            )
        except BookingError as exc:
            raise ValidationError(str(exc)) from exc
        obj.pk = booking.pk
        obj.created_at = booking.created_at
        obj.status = booking.status
        messages.success(request, "Booking created. SMS confirmation queued.")

    def save_related(self, request, form, formsets, change):
        if change:
            super().save_related(request, form, formsets, change)
            return
        # Slots are attached inside create_booking.
        for formset in formsets:
            self.save_formset(request, form, formset, change=change)


@admin.register(CallSession)
class CallSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "sport_slug", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = ("messages", "last_agent_text", "plivo_call_uuid", "created_at")
