from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import get_object_or_404
from ninja import Router

from carda_link.users.api.schema import UpdateUserSchema
from carda_link.users.api.schema import UserSchema
from carda_link.users.models import User

if TYPE_CHECKING:
    from django.db.models import QuerySet

router = Router(tags=["users"])


def _get_users_queryset(request) -> QuerySet[User]:
    return User.objects.filter(pk=request.user.pk)


@router.get("/", response=list[UserSchema])
def list_users(request, role: str | None = None):
    qs = User.objects.all()
    if role:
        qs = qs.filter(role=role.upper())
    return qs


@router.get("/me/", response=UserSchema)
def retrieve_current_user(request):
    return request.user


@router.get("/{pk}/", response=UserSchema)
def retrieve_user(request, pk: int):
    return get_object_or_404(User, pk=pk)


@router.patch("/me/", response=UserSchema)
def update_current_user(request, data: UpdateUserSchema):
    user = request.user
    for attr, value in data.dict(exclude_unset=True).items():
        setattr(user, attr, value)
    user.save()
    return user


@router.patch("/{pk}/", response=UserSchema)
def update_user(request, pk: int, data: UpdateUserSchema):
    user = get_object_or_404(User, pk=pk)
    for attr, value in data.dict(exclude_unset=True).items():
        setattr(user, attr, value)
    user.save()
    return user

