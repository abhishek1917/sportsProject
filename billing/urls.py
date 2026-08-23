from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("", views.invoice_list, name="invoice_list"),
    path("generate-month/", views.generate_month, name="generate_month"),
    path("<int:invoice_id>/status/", views.set_status, name="set_status"),
    path("<int:invoice_id>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path("<int:invoice_id>/whatsapp/", views.whatsapp_share, name="whatsapp"),
]
