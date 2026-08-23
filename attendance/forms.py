from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Student


class ManagerLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Staff username"
        self.error_messages["invalid_login"] = (
            "That staff login did not match. Use the facility username and password."
        )
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit(
                "submit",
                "Enter facility panel",
                css_class="mt-2 w-full rounded-xl bg-emerald-800 px-4 py-3 font-semibold text-white hover:bg-emerald-900",
            )
        )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not hasattr(user, "facility_manager"):
            raise forms.ValidationError(
                "This account is not a facility manager. Use the customer log in page instead.",
                code="not_manager",
            )


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ("full_name", "age", "session", "phone", "notes", "is_active")
        labels = {
            "full_name": "Student name",
            "session": "Batch",
            "is_active": "Active student",
        }
        help_texts = {
            "session": "Morning, evening, or night batch for this sport.",
            "phone": "Optional contact number for parents or the student.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit(
                "submit",
                "Save profile",
                css_class="mt-2 w-full rounded-xl bg-emerald-800 px-4 py-3 font-semibold text-white hover:bg-emerald-900 sm:w-auto",
            )
        )
