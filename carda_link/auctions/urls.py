from django.urls import path

from carda_link.auctions import views

app_name = "auctions"

urlpatterns = [
    path("", views.simulation_view, name="index"),
    path("simulation/", views.simulation_view, name="simulation"),
]
