from django.urls import path
from . import views

app_name = "invoicing"

urlpatterns = [
    path("", views.InvoiceListView.as_view(), name="list"),
    path("<int:pk>/", views.InvoiceDetailView.as_view(), name="detail"),
    path("confirm/", views.ConfirmBiddingView.as_view(), name="confirm"),
    path("confirm/<int:lot_id>/", views.ConfirmBiddingView.as_view(), name="confirm_lot"),
    path("<int:pk>/pay/", views.InvoicePayView.as_view(), name="pay"),
    path("seed-demo/", views.SeedDemoDataView.as_view(), name="seed_demo"),
]
