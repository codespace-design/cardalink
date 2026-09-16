from django.db import models
from django.shortcuts import render

from carda_link.auctions.models import Auction, Bid, Lot


def simulation_view(request):
    """
    Dedicated Live Bidding & Auction Engine Simulation Dashboard.
    Isolated within the auctions app (does not alter global base templates).
    """
    for a in Auction.objects.filter(status__in=["UPCOMING", "ACTIVE"]):
        a.auto_update_status()

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

    return render(
        request,
        "auctions/live_bidding.html",
        {
            "auctions": auctions,
            "active_auction": active_auction,
            "first_lot": first_lot,
            "recent_bids": recent_bids,
            "all_closed_lots": all_closed_lots,
        },
    )
