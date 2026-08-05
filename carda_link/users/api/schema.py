from django.urls import reverse
from ninja import ModelSchema

from carda_link.users.models import User


class UpdateUserSchema(ModelSchema):
    class Meta:
        model = User
        fields = ["name", "phone_number", "address", "license_number"]


class UserSchema(ModelSchema):
    url: str

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "role",
            "phone_number",
            "address",
            "license_number",
            "is_verified",
        ]

    @staticmethod
    def resolve_url(obj: User):
        return reverse("api:retrieve_user", kwargs={"pk": obj.pk})
