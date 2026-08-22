from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from bookings.models import Customer

from .forms import LoginForm, PhoneRequiredForm, SignupForm


class SignupView(View):
    template_name = "accounts/signup.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("bookings:home")
        return render(request, self.template_name, {"form": SignupForm()})

    def post(self, request):
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created. You are now logged in.")
            return redirect("bookings:home")
        messages.error(
            request,
            "Could not create your account. Please fix the errors below.",
        )
        return render(request, self.template_name, {"form": form})


class CustomerLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class CustomerLogoutView(LogoutView):
    next_page = reverse_lazy("bookings:home")


@login_required
def phone_required(request):
    customer = getattr(request.user, "customer", None)
    if customer and customer.phone:
        return redirect(request.GET.get("next") or "bookings:book_on_call")

    initial = {}
    if customer:
        initial["full_name"] = customer.full_name
        initial["phone"] = customer.phone
    elif request.user.get_full_name():
        initial["full_name"] = request.user.get_full_name()

    if request.method == "POST":
        form = PhoneRequiredForm(request.POST, user=request.user)
        if form.is_valid():
            Customer.objects.update_or_create(
                user=request.user,
                defaults={
                    "full_name": form.cleaned_data["full_name"],
                    "phone": form.cleaned_data["phone"],
                },
            )
            return redirect(request.POST.get("next") or "bookings:book_on_call")
    else:
        form = PhoneRequiredForm(user=request.user, initial=initial)
    return render(request, "accounts/phone.html", {"form": form})
