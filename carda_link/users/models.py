from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import CharField, EmailField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractUser):
    """Default custom user model for CardaLink.

    Supports role-based user management for Farmers (Sellers), Buyers, Auctioneers, and Admins.
    """

    class Role(models.TextChoices):
        SELLER = "SELLER", _("Seller / Cardamom Farmer")
        BUYER = "BUYER", _("Buyer / Trader")
        AUCTIONEER = "AUCTIONEER", _("Auctioneer / Spices Board Rep")
        ADMIN = "ADMIN", _("System Administrator")

    name = CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    email = EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]

    role = CharField(
        _("User Role"),
        max_length=20,
        choices=Role.choices,
        default=Role.SELLER,
    )
    phone_number = CharField(_("Phone Number"), max_length=20, blank=True, default="")
    address = models.TextField(_("Address / Location"), blank=True, default="")
    license_number = CharField(
        _("Spices Board / Trading License Number"),
        max_length=100,
        blank=True,
        default="",
    )
    is_verified = models.BooleanField(_("Is Verified User"), default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"pk": self.id})
