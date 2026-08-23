from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from bookings.services import BookingError, normalize_phone
from bookings.models import Customer


class PhoneMixin:
    def clean_phone(self):
        try:
            phone = normalize_phone(self.cleaned_data["phone"])
        except BookingError as exc:
            raise forms.ValidationError(str(exc)) from exc
        qs = Customer.objects.filter(phone=phone)
        if getattr(self, "instance_user", None):
            qs = qs.exclude(user=self.instance_user)
        if qs.exists():
            raise forms.ValidationError("An account with this phone number already exists.")
        return phone


class SignupForm(PhoneMixin, UserCreationForm):
    full_name = forms.CharField(max_length=120, label="Full name")
    phone = forms.CharField(
        max_length=15,
        label="Phone number",
        help_text="Required. Call the stadium line from this number for Book on call. We also send SMS confirmations here.",
    )

    class Meta:
        model = User
        fields = ("username", "full_name", "phone", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit(
                "submit",
                "Create account",
                css_class="mt-2 w-full rounded-xl bg-emerald-800 px-4 py-3 font-semibold text-white hover:bg-emerald-900",
            )
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["full_name"][:30]
        if commit:
            user.save()
            Customer.objects.create(
                user=user,
                full_name=self.cleaned_data["full_name"],
                phone=self.cleaned_data["phone"],
            )
        return user


class PhoneRequiredForm(PhoneMixin, forms.Form):
    full_name = forms.CharField(max_length=120, label="Full name")
    phone = forms.CharField(
        max_length=15,
        label="Phone number",
        help_text="Required. Call the stadium line from this number so the agent can find your account.",
    )

    def __init__(self, *args, user=None, **kwargs):
        self.instance_user = user
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit(
                "submit",
                "Save phone number",
                css_class="mt-2 w-full rounded-xl bg-emerald-800 px-4 py-3 font-semibold text-white hover:bg-emerald-900",
            )
        )


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit(
                "submit",
                "Log in",
                css_class="mt-2 w-full rounded-xl bg-emerald-800 px-4 py-3 font-semibold text-white hover:bg-emerald-900",
            )
        )
