from typing import ClassVar

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractUser):
    """
    Default custom user model for CardaLink.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    class Role(models.TextChoices):
        ADMIN = "ADMIN", _("Admin")
        SELLER = "SELLER", _("Seller")
        BUYER = "BUYER", _("Buyer")

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        ACTIVE = "ACTIVE", _("Active")
        REJECTED = "REJECTED", _("Rejected")
        SUSPENDED = "SUSPENDED", _("Suspended")

    class AreaUnit(models.TextChoices):
        ACRE = "ACRE", _("Acre")
        CENT = "CENT", _("Cent")

    # First and last name do not cover name patterns around the globe
    name = models.CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    email = models.EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]

    role = models.CharField(
        _("Role"),
        max_length=10,
        choices=Role.choices,
    )
    status = models.CharField(
        _("Status"),
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    phone_number = models.CharField(
        _("Phone Number"),
        max_length=20,
        blank=True,
        null=True,
        unique=True,
    )

    @property
    def farm_name(self):
        return self.seller_profile.farm_name if hasattr(self, 'seller_profile') else None

    @property
    def farm_location(self):
        return self.seller_profile.farm_location if hasattr(self, 'seller_profile') else None

    @property
    def farm_area(self):
        return self.seller_profile.farm_area if hasattr(self, 'seller_profile') else None

    @property
    def area_unit(self):
        return self.seller_profile.area_unit if hasattr(self, 'seller_profile') else None

    @property
    def get_area_unit_display(self):
        return self.seller_profile.get_area_unit_display() if hasattr(self, 'seller_profile') else None

    @property
    def cardamom_plants(self):
        return self.seller_profile.cardamom_plants if hasattr(self, 'seller_profile') else None

    @property
    def business_name(self):
        return self.buyer_profile.company_name if hasattr(self, 'buyer_profile') else None

    @property
    def business_type(self):
        return self.buyer_profile.business_type if hasattr(self, 'buyer_profile') else None

    @property
    def business_address(self):
        return self.buyer_profile.business_address if hasattr(self, 'buyer_profile') else None


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        self.is_active = (self.status == self.Status.ACTIVE)
        super().save(*args, **kwargs)


class SellerProfile(models.Model):
    class AreaUnit(models.TextChoices):
        ACRE = "ACRE", _("Acre")
        CENT = "CENT", _("Cent")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_profile"
    )
    farm_name = models.CharField(_("Farm Name"), max_length=255)
    farm_location = models.CharField(_("Farm Location"), max_length=255)
    farm_area = models.DecimalField(
        _("Farm Area"),
        max_digits=10,
        decimal_places=2
    )
    area_unit = models.CharField(
        _("Area Unit"),
        max_length=10,
        choices=AreaUnit.choices
    )
    cardamom_plants = models.PositiveIntegerField(
        _("Number of Cardamom Plants")
    )
    cultivation_details = models.TextField(
        _("Cultivation Details"),
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Seller Profile: {self.user.email} - {self.farm_name}"


class BuyerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="buyer_profile"
    )
    company_name = models.CharField(_("Company/Business Name"), max_length=255)
    business_type = models.CharField(_("Business Type"), max_length=100)
    business_address = models.TextField(_("Business Address"))
    business_details = models.TextField(
        _("Business Details"),
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Buyer Profile: {self.user.email} - {self.company_name}"


