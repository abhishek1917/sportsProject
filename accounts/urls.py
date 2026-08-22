from django.urls import path

from .views import CustomerLoginView, CustomerLogoutView, SignupView, phone_required

app_name = "accounts"

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", CustomerLoginView.as_view(), name="login"),
    path("logout/", CustomerLogoutView.as_view(), name="logout"),
    path("phone/", phone_required, name="phone"),
]
