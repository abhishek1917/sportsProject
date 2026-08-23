from django.contrib import admin
from django.urls import include, path
from django.conf import settings

from billing.views import public_pdf

urlpatterns = [
    path("admin/", admin.site.urls),
    path("manage/billing/", include("billing.urls")),
    path("manage/", include("attendance.urls")),
    path("i/<str:token>/", public_pdf, name="public_invoice"),
    path("accounts/", include("accounts.urls")),
    path("api/", include("bookings.api_urls")),
    path("", include("bookings.urls")),
]

if settings.DEBUG:
    urlpatterns.append(path("__reload__/", include("django_browser_reload.urls")))
