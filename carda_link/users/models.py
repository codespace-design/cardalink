from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import CharField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .fields import EncryptedCharField
from .managers import UserManager


class User(AbstractUser):
    """Default custom user model for CardaLink.

    Supports role-based user management for Farmers (Sellers),
    Buyers, Auctioneers, and Admins.
    """

    class Role(models.TextChoices):
        SELLER = "SELLER", _("Seller / Cardamom Farmer")
        BUYER = "BUYER", _("Buyer / Trader")
        AUCTIONEER = "AUCTIONEER", _("Auctioneer / Spices Board Rep")
        ADMIN = "ADMIN", _("System Administrator")

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        ACTIVE = "ACTIVE", _("Active")
        REJECTED = "REJECTED", _("Rejected")
        SUSPENDED = "SUSPENDED", _("Suspended")

    class AreaUnit(models.TextChoices):
        ACRE = "ACRE", _("Acre")
        CENT = "CENT", _("Cent")

    # First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
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
    address = models.TextField(_("Address / Location"), blank=True, default="")
    license_number = models.CharField(
        _("Spices Board / Trading License Number"),
        max_length=100,
        blank=True,
        default="",
    )
    is_verified = models.BooleanField(_("Is Verified User"), default=False)
    rejection_reason = models.TextField(_("Rejection Reason"), blank=True, default="")
    suspension_reason = models.TextField(_("Suspension Reason"), blank=True, default="")
    created_by_admin = models.BooleanField(_("Created by Admin"), default=False)

    @property
    def farm_name(self):
        return (
            self.seller_profile.farm_name if hasattr(self, "seller_profile") else None
        )

    @property
    def farm_location(self):
        return (
            self.seller_profile.farm_location
            if hasattr(self, "seller_profile")
            else None
        )

    @property
    def farm_area(self):
        return (
            self.seller_profile.farm_area if hasattr(self, "seller_profile") else None
        )

    @property
    def area_unit(self):
        return (
            self.seller_profile.area_unit if hasattr(self, "seller_profile") else None
        )

    @property
    def get_area_unit_display(self):
        return (
            self.seller_profile.get_area_unit_display()
            if hasattr(self, "seller_profile")
            else None
        )

    @property
    def cardamom_plants(self):
        return (
            self.seller_profile.cardamom_plants
            if hasattr(self, "seller_profile")
            else None
        )

    @property
    def business_name(self):
        return (
            self.buyer_profile.company_name if hasattr(self, "buyer_profile") else None
        )

    @property
    def business_type(self):
        return (
            self.buyer_profile.business_type if hasattr(self, "buyer_profile") else None
        )

    @property
    def business_address(self):
        return (
            self.buyer_profile.business_address
            if hasattr(self, "buyer_profile")
            else None
        )

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
        return reverse("users:detail", kwargs={"pk": self.id})

    def save(self, *args, **kwargs):
        self.is_active = self.status == self.Status.ACTIVE
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("is_active")
            kwargs["update_fields"] = update_fields
        super().save(*args, **kwargs)


class SellerProfile(models.Model):
    class AreaUnit(models.TextChoices):
        ACRE = "ACRE", _("Acre")
        CENT = "CENT", _("Cent")

    class District(models.TextChoices):
        ALAPPUZHA = "ALAPPUZHA", _("Alappuzha")
        ERNAKULAM = "ERNAKULAM", _("Ernakulam")
        IDUKKI = "IDUKKI", _("Idukki")
        KANNUR = "KANNUR", _("Kannur")
        KASARAGOD = "KASARAGOD", _("Kasaragod")
        KOLLAM = "KOLLAM", _("Kollam")
        KOTTAYAM = "KOTTAYAM", _("Kottayam")
        KOZHIKODE = "KOZHIKODE", _("Kozhikode")
        MALAPPURAM = "MALAPPURAM", _("Malappuram")
        PALAKKAD = "PALAKKAD", _("Palakkad")
        PATHANAMTHITTA = "PATHANAMTHITTA", _("Pathanamthitta")
        THIRUVANANTHAPURAM = "THIRUVANANTHAPURAM", _("Thiruvananthapuram")
        THRISSUR = "THRISSUR", _("Thrissur")
        WAYANAD = "WAYANAD", _("Wayanad")

    class CultivationMethod(models.TextChoices):
        ORGANIC = "ORGANIC", _("Organic")
        CONVENTIONAL = "CONVENTIONAL", _("Conventional")
        MIXED = "MIXED", _("Mixed")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_profile",
    )
    farm_name = models.CharField(_("Farm Name"), max_length=255)
    farm_location = models.CharField(_("Farm Location"), max_length=255, blank=True, default="")
    district = models.CharField(
        _("District"),
        max_length=30,
        choices=District.choices,
        default=District.IDUKKI,
    )
    taluk = models.CharField(_("Taluk"), max_length=100, blank=True, default="")
    village = models.CharField(_("Village"), max_length=100, blank=True, default="")

    farm_area = models.DecimalField(
        _("Farm Area"),
        max_digits=10,
        decimal_places=2,
    )
    area_unit = models.CharField(
        _("Area Unit"),
        max_length=10,
        choices=AreaUnit.choices,
        default=AreaUnit.ACRE,
    )
    cardamom_plants = models.PositiveIntegerField(
        _("Number of Cardamom Plants"),
    )
    cultivation_method = models.CharField(
        _("Cultivation Method"),
        max_length=20,
        choices=CultivationMethod.choices,
        default=CultivationMethod.CONVENTIONAL,
    )
    cultivation_details = models.TextField(
        _("Cultivation Details"),
        blank=True,
        default="",
    )
    ownership_proof = models.FileField(
        _("Land Ownership / Cultivation Proof"),
        upload_to="seller_documents/",
        blank=True,
        null=True,
    )

    # Banking details (account number encrypted at rest with independent key)
    bank_account_holder = models.CharField(
        _("Bank Account Holder Name"),
        max_length=255,
        blank=True,
        default="",
    )
    bank_ifsc = models.CharField(
        _("Bank IFSC Code"),
        max_length=20,
        blank=True,
        default="",
    )
    bank_account_number = EncryptedCharField(
        _("Bank Account Number"),
        max_length=255,
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Seller Profile: {self.user.email} - {self.farm_name}"


class BuyerProfile(models.Model):
    class BusinessType(models.TextChoices):
        EXPORTER = "EXPORTER", _("Exporter")
        WHOLESALER = "WHOLESALER", _("Wholesaler")
        TRADER = "TRADER", _("Trader")
        PROCESSOR = "PROCESSOR", _("Processor")
        RETAILER = "RETAILER", _("Retailer")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="buyer_profile",
    )
    company_name = models.CharField(_("Company/Business Name"), max_length=255)
    business_type = models.CharField(
        _("Business Type"),
        max_length=50,
        choices=BusinessType.choices,
        default=BusinessType.TRADER,
    )
    gst_number = models.CharField(
        _("GST / Business Registration Number"),
        max_length=50,
        blank=True,
        default="",
    )
    business_address = models.TextField(_("Business Address"))
    registration_certificate = models.FileField(
        _("Business License / Registration Certificate"),
        upload_to="buyer_certificates/",
        blank=True,
        null=True,
    )
    purchase_capacity = models.CharField(
        _("Expected Purchase Capacity"),
        max_length=100,
        blank=True,
        default="",
    )
    business_details = models.TextField(
        _("Business Details"),
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Buyer Profile: {self.user.email} - {self.company_name}"


class Watchlist(models.Model):
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlist_items",
    )
    lot = models.ForeignKey(
        "auctions.Lot",
        on_delete=models.CASCADE,
        related_name="watched_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("buyer", "lot")

    def __str__(self):
        return f"{self.buyer.email} -> Lot #{self.lot.lot_number}"


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        OUTBID = "OUTBID", _("Outbid Alert")
        AUCTION = "AUCTION", _("Auction Event")
        LOT_WON = "LOT_WON", _("Lot Won")
        INVOICE = "INVOICE", _("Invoice & Settlement")
        BATCH = "BATCH", _("Harvest Batch Quality")
        SYSTEM = "SYSTEM", _("System Notification")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    message = models.CharField(_("Message"), max_length=255)
    link = models.CharField(_("Target Link"), max_length=255, blank=True, default="")
    notification_type = models.CharField(
        _("Notification Type"),
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM,
    )
    is_read = models.BooleanField(_("Is Read"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification for {self.user.email}: {self.message[:30]}"


class AdminActionLog(models.Model):
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_actions",
        verbose_name=_("Admin User"),
    )
    action = models.CharField(_("Action"), max_length=50)
    target_model = models.CharField(_("Target Model"), max_length=50)
    target_id = models.CharField(_("Target ID"), max_length=50)
    reason = models.TextField(_("Reason / Remarks"), blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = _("Admin Action Log")
        verbose_name_plural = _("Admin Action Logs")

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} | {self.admin_user.email} -> {self.action} on {self.target_model}#{self.target_id}"


def log_admin_action(admin_user, action: str, target, reason: str | None = None) -> AdminActionLog:
    """Helper to record audit trail of admin decisions and operations."""
    target_model = target.__class__.__name__ if target is not None else "System"
    target_id = str(getattr(target, "pk", target or ""))
    return AdminActionLog.objects.create(
        admin_user=admin_user,
        action=action,
        target_model=target_model,
        target_id=target_id,
        reason=reason or None,
    )
