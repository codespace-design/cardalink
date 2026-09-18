from django.contrib import messages
from django.db import models
from django.shortcuts import redirect, render

from carda_link.auctions.models import Auction, Bid, Lot


def simulation_view(request):
    """
    Dedicated Live Bidding & Auction Engine Simulation Dashboard.
    Isolated within the auctions app (does not alter global base templates).
    """
    if request.user.is_authenticated and getattr(request.user, "role", None) == "SELLER":
        messages.info(
            request,
            "Live auction bidding is reserved for verified buyers. As a planter, you receive real-time notifications for all bid activity and sales on your lots.",
        )
        return redirect("seller_dashboard")

    from carda_link.auctions.services import sync_expired_auctions
    sync_expired_auctions()

    auctions = Auction.objects.all().prefetch_related("lots__harvest_batch__estate")
    auction_id = request.GET.get("auction_id")
    if auction_id:
        active_auction = (
            Auction.objects.filter(pk=auction_id).first()
            or Auction.objects.filter(status="ACTIVE").first()
            or auctions.first()
        )
    else:
        active_auction = Auction.objects.filter(status="ACTIVE").first() or auctions.first()

    recent_bids = []
    if active_auction:
        recent_bids = (
            Bid.objects.filter(lot__auction=active_auction)
            .select_related("lot", "bidder")
            .order_by("-timestamp")[:20]
        )

    # Fetch closed/sold lots across all sessions for rich audit and demo
    all_closed_lots = (
        Lot.objects.filter(models.Q(is_sold=True) | models.Q(auction__status="COMPLETED"))
        .select_related("auction", "harvest_batch__estate")
        .order_by("-auction__start_time", "lot_number")[:15]
    )

    first_lot = active_auction.lots.first() if active_auction else None

    user_won_lots = []
    if request.user.is_authenticated and active_auction and active_auction.status == "COMPLETED":
        for lot in active_auction.lots.filter(is_sold=True).prefetch_related("bids"):
            top_bid = lot.bids.order_by("-amount_per_kg").first()
            if top_bid and top_bid.bidder == request.user:
                user_won_lots.append(lot)

    can_manage_auction = bool(
        request.user.is_authenticated
        and (getattr(request.user, "role", None) == "ADMIN" or request.user.is_staff or request.user.is_superuser)
    )

    return render(
        request,
        "auctions/live_bidding.html",
        {
            "auctions": auctions,
            "active_auction": active_auction,
            "first_lot": first_lot,
            "recent_bids": recent_bids,
            "all_closed_lots": all_closed_lots,
            "user_won_lots": user_won_lots,
            "can_manage_auction": can_manage_auction,
        },
    )

