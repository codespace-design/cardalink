from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse

from carda_link.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client

    from carda_link.users.models import User

pytestmark = pytest.mark.django_db


def _user_dict(user: User, name: str | None = None) -> dict:
    return {
        "id": user.pk,
        "email": user.email,
        "name": name if name is not None else user.name,
        "role": user.role,
        "phone_number": user.phone_number,
        "address": user.address,
        "license_number": user.license_number,
        "is_verified": user.is_verified,
        "url": f"/api/users/{user.pk}/",
    }


def test_list_users_as_anonymous_user(client: Client):
    response = client.get(reverse("api:list_users"))

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_list_users_as_authenticated_user(client: Client, user: User):
    client.force_login(user)
    # Another user, excluded from the response
    UserFactory.create()

    response = client.get(reverse("api:list_users"))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == [_user_dict(user)]


def test_retrieve_current_user(client: Client, user: User):
    client.force_login(user)

    response = client.get(
        reverse("api:retrieve_current_user"),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == _user_dict(user)


def test_retrieve_user(client: Client, user: User):
    client.force_login(user)

    response = client.get(
        reverse("api:retrieve_user", kwargs={"pk": user.pk}),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == _user_dict(user)


def test_retrieve_another_user(client: Client, user: User):
    client.force_login(user)
    user_2 = UserFactory.create()

    response = client.get(
        reverse("api:retrieve_user", kwargs={"pk": user_2.pk}),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Not Found"}


def test_update_current_user(client: Client):
    user = UserFactory.create(name="Old")
    client.force_login(user)

    response = client.patch(
        reverse("api:update_current_user"),
        data='{"name": "New Name"}',
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.OK, response.json()
    assert response.json() == _user_dict(user, name="New Name")


def test_update_user(client: Client):
    user = UserFactory.create(name="Old")
    client.force_login(user)

    response = client.patch(
        reverse("api:update_user", kwargs={"pk": user.pk}),
        data='{"name": "New Name"}',
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.OK, response.json()
    assert response.json() == _user_dict(user, name="New Name")
