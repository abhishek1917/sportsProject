from django.urls import path

from . import browser_voice_views
from . import views
from . import voice_views

app_name = "bookings"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("", views.home, name="home"),
    path("my-bookings/", views.my_bookings, name="my_bookings"),
    path("my-bookings/<int:booking_id>/cancel/", views.cancel_booking_view, name="cancel_booking"),
    path("book-on-call/", views.book_on_call, name="book_on_call"),
    path("voice/browser/start/", browser_voice_views.browser_voice_start, name="browser_voice_start"),
    path("voice/browser/turn/<int:session_id>/", browser_voice_views.browser_voice_turn, name="browser_voice_turn"),
    path("voice/browser/prepare-phone/", browser_voice_views.browser_voice_prepare_phone, name="browser_voice_prepare_phone"),
    path("voice/inbound/", voice_views.voice_inbound, name="voice_inbound"),
    path("voice/exotel/inbound/", voice_views.exotel_inbound, name="exotel_inbound"),
    path("voice/exotel/status/", voice_views.exotel_status, name="exotel_status"),
    path("voice/exotel/outbound/<int:session_id>/", voice_views.exotel_outbound, name="exotel_outbound"),
    path("voice/exotel/record/<int:session_id>/", voice_views.exotel_record, name="exotel_record"),
    path("voice/answer/<int:session_id>/", voice_views.voice_answer, name="voice_answer"),
    path("voice/input/<int:session_id>/", voice_views.voice_input, name="voice_input"),
    path("<slug:slug>/", views.sport_page, name="sport"),
]
