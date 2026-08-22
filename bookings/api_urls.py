from django.urls import path

from . import api

urlpatterns = [
    path("availability/", api.availability, name="api_availability"),
    path("bookings/", api.create_booking_api, name="api_create_booking"),
]
