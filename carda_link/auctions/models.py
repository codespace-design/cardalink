from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from carda_link.estates.models import HarvestBatch


class Auction(models.Model):
    STATUS_CHOICES = [
        ("UPCOMING", "Upcoming"),
        ("ACTIVE", "Active / Bidding Open"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    title = models.CharField(_("Auction Title"), max_length=255)
    start_time = models.DateTimeField(_("Start Time"))
    end_time = models.DateTimeField(_("End Time"))
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="UPCOMING",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class Lot(models.Model):
    auction = models.ForeignKey(
        Auction,
        on_delete=models.CASCADE,
        related_name="lots",
    )
    harvest_batch = models.OneToOneField(
        HarvestBatch,
        on_delete=models.CASCADE,
        related_name="auction_lot",
    )
    lot_number = models.PositiveIntegerField(_("Lot Number"))
    base_price_per_kg = models.DecimalField(
        _("Base Price per kg (₹)"),
        max_digits=10,
        decimal_places=2,
    )
    highest_bid_per_kg = models.DecimalField(
        _("Highest Bid per kg (₹)"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    is_sold = models.BooleanField(default=False)

    def __str__(self):
        return f"Lot #{self.lot_number} - {self.harvest_batch.grade}"


class Bid(models.Model):
    lot = models.ForeignKey(
        Lot,
        on_delete=models.CASCADE,
        related_name="bids",
    )
    bidder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bids",
    )
    amount_per_kg = models.DecimalField(
        _("Bid Amount per kg (₹)"),
        max_digits=10,
        decimal_places=2,
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"₹{self.amount_per_kg}/kg by {self.bidder} on Lot #{self.lot.lot_number}"
        )
