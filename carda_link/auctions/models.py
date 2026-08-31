from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
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

    class Meta:
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def is_active_now(self) -> bool:
        now = timezone.now()
        return self.status == "ACTIVE" and self.start_time <= now <= self.end_time

    def auto_update_status(self):
        now = timezone.now()
        if self.status == "UPCOMING" and now >= self.start_time:
            self.status = "ACTIVE"
            self.save(update_fields=["status"])
        elif self.status == "ACTIVE" and now >= self.end_time:
            self.close_auction()

    def close_auction(self):
        self.status = "COMPLETED"
        self.save(update_fields=["status"])
        for lot in self.lots.all():
            if lot.highest_bid_per_kg is not None and lot.highest_bid_per_kg >= lot.base_price_per_kg:
                lot.is_sold = True
                lot.save(update_fields=["is_sold"])


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

    class Meta:
        ordering = ["lot_number"]

    def __str__(self):
        return f"Lot #{self.lot_number} - {self.harvest_batch.grade}"

    @property
    def current_price(self) -> Decimal:
        return self.highest_bid_per_kg if self.highest_bid_per_kg is not None else self.base_price_per_kg

    def place_bid(self, bidder, amount_per_kg: Decimal) -> "Bid":
        amount_decimal = Decimal(str(amount_per_kg))
        now = timezone.now()

        # Check auction status
        if self.auction.status != "ACTIVE":
            raise ValueError(f"Bidding is closed. Current auction status is '{self.auction.get_status_display()}'.")

        if not (self.auction.start_time <= now <= self.auction.end_time):
            raise ValueError("Bidding is only permitted between the auction start time and end time.")

        # Check bid amount vs base price
        if amount_decimal <= self.base_price_per_kg:
            raise ValueError(
                f"Bid amount (₹{amount_decimal}/kg) must be strictly greater than the base price (₹{self.base_price_per_kg}/kg)."
            )

        # Check bid amount vs highest bid
        if self.highest_bid_per_kg is not None and amount_decimal <= self.highest_bid_per_kg:
            raise ValueError(
                f"Bid amount (₹{amount_decimal}/kg) must be strictly higher than the current highest bid (₹{self.highest_bid_per_kg}/kg)."
            )

        # Record bid
        bid = Bid.objects.create(
            lot=self,
            bidder=bidder,
            amount_per_kg=amount_decimal,
        )

        self.highest_bid_per_kg = amount_decimal
        self.save(update_fields=["highest_bid_per_kg"])
        return bid


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

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return (
            f"₹{self.amount_per_kg}/kg by {self.bidder} on Lot #{self.lot.lot_number}"
        )

