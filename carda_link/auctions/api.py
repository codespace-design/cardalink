from ninja import Router

router = Router(tags=["Auctions & Live Bidding Engine"])


@router.get("/health-check")
def auctions_health_check(request):
    return {"status": "ok", "module": "Live Auction Engine"}
