from __future__ import annotations

from factory import Faker
from factory import post_generation
from factory.django import DjangoModelFactory

from carda_link.users.models import User


class UserFactory(DjangoModelFactory[User]):
    email = Faker("email")
    name = Faker("name")
    role = "BUYER"
    status = "ACTIVE"

    @post_generation
    def password(self: User, create: bool, extracted: str | None, **kwargs):
        password = (
            extracted
            if extracted
            else Faker(
                "password",
                length=42,
                special_chars=True,
                digits=True,
                upper_case=True,
                lower_case=True,
            ).evaluate(None, None, extra={"locale": None})
        )
        self.set_password(password)
        if create:
            self.save()

    class Meta:
        model = User
        django_get_or_create = ["email"]
        skip_postgeneration_save = True
