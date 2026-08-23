from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("login/", views.FacilityLoginView.as_view(), name="login"),
    path("logout/", views.FacilityLogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("students/new/", views.student_create, name="student_create"),
    path("students/<int:student_id>/", views.student_detail, name="student_detail"),
    path("students/<int:student_id>/edit/", views.student_edit, name="student_edit"),
    path(
        "students/<int:student_id>/mark/",
        views.mark_attendance,
        name="mark_attendance",
    ),
    path("batch/<slug:session>/", views.section_roster, name="section"),
]
