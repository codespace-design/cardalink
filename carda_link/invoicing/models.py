from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from carda_link.auctions.models import Lot


class Invoice(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending Payment"),
        ("PAID", "Paid"),
        ("FAILED", "Failed"),
        ("REFUNDED", "Refunded"),
    ]

    lot = models.OneToOneField(
        Lot,
        on_delete=models.CASCADE,
        related_name="invoice",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    total_amount = models.DecimalField(
        _("Total Amount (₹)"),
        max_digits=12,
        decimal_places=2,
    )
    commission_fee = models.DecimalField(
        _("Commission Fee (₹)"),
        max_digits=10,
        decimal_places=2,
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_invoices",
        verbose_name=_("Updated By Admin"),
    )
    status_note = models.TextField(_("Status / Audit Note"), blank=True, default="")

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return (
            f"Invoice #{self.id} - Lot #{self.lot.lot_number} "
            f"({self.get_status_display()})"
        )


class PlatformSettings(models.Model):
    commission_percent = models.DecimalField(
        _("Commission Percentage (%)"),
        max_digits=5,
        decimal_places=2,
        default=2.00,
        help_text=_("Platform commission rate charged on successful lots."),
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_platform_settings",
        verbose_name=_("Last Updated By"),
    )

    class Meta:
        verbose_name = _("Platform Setting")
        verbose_name_plural = _("Platform Settings")

    def save(self, *args, **kwargs):
        self.pk = 1  # Force singleton ID
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Platform Settings (Commission: {self.commission_percent}%)"
