from django.urls import path
from carda_link.auctions import views

app_name = "auctions"

urlpatterns = [
    path("simulation/", views.simulation_view, name="simulation"),
]
