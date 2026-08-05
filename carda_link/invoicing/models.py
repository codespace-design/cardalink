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

    lot = models.OneToOneField(Lot, on_delete=models.CASCADE, related_name="invoice")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invoices")
    total_amount = models.DecimalField(_("Total Amount (₹)"), max_digits=12, decimal_places=2)
    commission_fee = models.DecimalField(_("Commission Fee (₹)"), max_digits=10, decimal_places=2)
    status = models.CharField(_("Status"), max_length=20, choices=STATUS_CHOICES, default="PENDING")
    issued_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Invoice #{self.id} - Lot #{self.lot.lot_number} ({self.get_status_display()})"
