from decimal import Decimal
from django.db import transaction
from carda_link.invoicing.models import Invoice, PlatformSettings


def close_auction(auction) -> None:
    """Closes an auction atomically, locks current highest bids as winners,

    marks lots as sold, and generates invoices with platform commission.
    """
    with transaction.atomic():
        auction.status = "COMPLETED"
        auction.save(update_fields=["status"])

        settings_obj = PlatformSettings.load()
        commission_rate = Decimal(str(settings_obj.commission_percent))

        for lot in auction.lots.select_related("harvest_batch").prefetch_related("bids").all():
            if (
                lot.highest_bid_per_kg is not None
                and lot.highest_bid_per_kg >= lot.base_price_per_kg
            ):
                lot.is_sold = True
                lot.save(update_fields=["is_sold"])

                # Find winning bidder
                winning_bid = lot.bids.order_by("-amount_per_kg", "-timestamp").first()
                if winning_bid and winning_bid.bidder:
                    weight = Decimal(str(lot.harvest_batch.weight_kg))
                    price = Decimal(str(lot.highest_bid_per_kg))
                    total_amount = round(weight * price, 2)
                    commission_fee = round(total_amount * (commission_rate / Decimal("100.0")), 2)

                    Invoice.objects.get_or_create(
                        lot=lot,
                        defaults={
                            "buyer": winning_bid.bidder,
                            "total_amount": total_amount,
                            "commission_fee": commission_fee,
                            "status": "PENDING",
                        },
                    )
