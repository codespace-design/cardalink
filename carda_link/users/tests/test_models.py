from __future__ import annotations

import pytest
from django.db.utils import IntegrityError

from carda_link.users.models import User
from carda_link.users.tests.factories import UserFactory


def test_user_get_absolute_url(user: User):
    assert user.get_absolute_url() == f"/users/{user.pk}/"


@pytest.mark.django_db
def test_user_roles_and_statuses():
    # Test choices exist
    assert User.Role.ADMIN == "ADMIN"
    assert User.Role.SELLER == "SELLER"
    assert User.Role.BUYER == "BUYER"

    assert User.Status.PENDING == "PENDING"
    assert User.Status.ACTIVE == "ACTIVE"
    assert User.Status.REJECTED == "REJECTED"
    assert User.Status.SUSPENDED == "SUSPENDED"


@pytest.mark.django_db
def test_user_is_active_sync():
    # Test that is_active is synced with status == ACTIVE
    user = UserFactory.build(status=User.Status.PENDING)
    user.save()
    assert not user.is_active

    user.status = User.Status.ACTIVE
    user.save()
    assert user.is_active

    user.status = User.Status.SUSPENDED
    user.save()
    assert not user.is_active


@pytest.mark.django_db
def test_unique_phone_number():
    # Create user with a phone number
    UserFactory.create(email="user1@example.com", phone_number="1234567890")

    # Try creating another user with the same phone number
    with pytest.raises(IntegrityError):
        UserFactory.create(email="user2@example.com", phone_number="1234567890")
