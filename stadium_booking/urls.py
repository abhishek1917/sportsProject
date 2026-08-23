from django.contrib import admin
from django.urls import include, path
from django.conf import settings

urlpatterns = [
    path("admin/", admin.site.urls),
    path("manage/", include("attendance.urls")),
    path("accounts/", include("accounts.urls")),
    path("api/", include("bookings.api_urls")),
    path("", include("bookings.urls")),
]

if settings.DEBUG:
    urlpatterns.append(path("__reload__/", include("django_browser_reload.urls")))
