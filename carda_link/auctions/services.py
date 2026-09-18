from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from carda_link.invoicing.models import Invoice, PlatformSettings


def sync_expired_auctions() -> int:
    """Scans for all ACTIVE auctions whose end_time has passed, and UPCOMING auctions
    whose start_time has arrived.
    Atomically closes expired auctions, marks lots sold, and generates invoices immediately.
    Returns the count of auctions closed.
    """
    from carda_link.auctions.models import Auction
    now = timezone.now()

    # 1. Activate UPCOMING auctions that have reached start_time
    Auction.objects.filter(status="UPCOMING", start_time__lte=now).update(status="ACTIVE")

    # 2. Find and close any ACTIVE auctions whose end_time has passed
    expired_auctions = list(
        Auction.objects.filter(status="ACTIVE", end_time__lte=now)
    )
    closed_count = 0
    for auction in expired_auctions:
        close_auction(auction)
        closed_count += 1
    return closed_count



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

                    # Notify planter of lot sale and buyer of lot won
                    try:
                        from django.urls import reverse
                        from carda_link.users.models import Notification

                        seller = getattr(getattr(lot.harvest_batch, "estate", None), "owner", None)
                        if seller:
                            Notification.objects.create(
                                user=seller,
                                notification_type=Notification.NotificationType.LOT_WON,
                                link=reverse("seller_sales_history"),
                                message=f"Lot #{lot.lot_number} ({lot.harvest_batch.estate.name}) sold for ₹{price}/kg! Gross value: ₹{total_amount}.",
                            )
                        Notification.objects.create(
                            user=winning_bid.bidder,
                            notification_type=Notification.NotificationType.LOT_WON,
                            link=reverse("buyer_invoices"),
                            message=f"Congratulations! You won Lot #{lot.lot_number} ({lot.harvest_batch.estate.name}) at ₹{price}/kg.",
                        )
                    except Exception:
                        pass
            else:
                # No valid bids placed: release the lot allocation so the HarvestBatch
                # is returned to seller inventory and can be cataloged in future auctions.
                seller = getattr(getattr(lot.harvest_batch, "estate", None), "owner", None)
                lot_num = lot.lot_number
                batch_id = lot.harvest_batch.id
                lot.delete()
                returned_count += 1

                try:
                    from django.urls import reverse
                    from carda_link.users.models import Notification

                    if seller:
                        Notification.objects.create(
                            user=seller,
                            notification_type=Notification.NotificationType.AUCTION,
                            link=reverse("seller_batches"),
                            message=f"Auction concluded: Lot #{lot_num} received no qualifying bids. Batch #{batch_id} returned to inventory.",
                        )
                except Exception:
                    pass

        return sold_count, returned_count
