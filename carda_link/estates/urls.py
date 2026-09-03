from django.urls import path

from .views import estate_create_view
from .views import estate_delete_view
from .views import estate_detail_view
from .views import estate_list_view
from .views import estate_photo_delete_view
from .views import estate_update_view
from .views import harvest_batch_create_view
from .views import harvest_batch_delete_view
from .views import harvest_batch_update_view

app_name = "estates"

urlpatterns = [
    path("", view=estate_list_view, name="list"),
    path("register/", view=estate_create_view, name="register"),
    path("<int:pk>/", view=estate_detail_view, name="detail"),
    path("<int:pk>/edit/", view=estate_update_view, name="update"),
    path("<int:pk>/delete/", view=estate_delete_view, name="delete"),
    path("<int:estate_pk>/photos/<int:photo_pk>/delete/", view=estate_photo_delete_view, name="photo-delete"),
    path("<int:estate_pk>/harvest/add/", view=harvest_batch_create_view, name="harvest-create"),
    path("harvest/<int:pk>/edit/", view=harvest_batch_update_view, name="harvest-update"),
    path("harvest/<int:pk>/delete/", view=harvest_batch_delete_view, name="harvest-delete"),
]
