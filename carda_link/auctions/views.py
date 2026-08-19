from django.shortcuts import render
from carda_link.auctions.models import Auction, Lot


def simulation_view(request):
    """
    Dedicated Live Bidding & Auction Engine Simulation Dashboard.
    Isolated within the auctions app (does not alter global base templates).
    """
    auctions = Auction.objects.all().prefetch_related("lots__harvest_batch__estate")
    active_auction = Auction.objects.filter(status="ACTIVE").first() or auctions.first()
    return render(
        request,
        "auctions/live_bidding.html",
        {
            "auctions": auctions,
            "active_auction": active_auction,
        },
    )
