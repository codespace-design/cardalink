from decimal import Decimal
from django.db import transaction
from carda_link.invoicing.models import Invoice, PlatformSettings


def close_auction(auction) -> tuple[int, int]:
    """Closes an auction atomically, locks current highest bids as winners,
    marks lots as sold, generates invoices with platform commission,
    and returns unbid/unsold lots to seller inventory so harvest batches can be reused.
    Returns (sold_count, returned_count).
    """
    with transaction.atomic():
        auction.status = "COMPLETED"
        auction.save(update_fields=["status"])

        settings_obj = PlatformSettings.load()
        commission_rate = Decimal(str(settings_obj.commission_percent))

        sold_count = 0
        returned_count = 0

        for lot in list(auction.lots.select_related("harvest_batch").prefetch_related("bids").all()):
            if (
                lot.highest_bid_per_kg is not None
                and lot.highest_bid_per_kg >= lot.base_price_per_kg
                and lot.bids.exists()
            ):
                lot.is_sold = True
                lot.save(update_fields=["is_sold"])
                sold_count += 1

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
            else:
                # No valid bids placed: release the lot allocation so the HarvestBatch
                # is returned to seller inventory and can be cataloged in future auctions.
                lot.delete()
                returned_count += 1

        return sold_count, returned_count
