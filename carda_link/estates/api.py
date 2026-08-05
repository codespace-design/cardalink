from ninja import Router

router = Router(tags=["Estates & Farm Management"])


@router.get("/health-check")
def estates_health_check(request):
    return {"status": "ok", "module": "Estates & Farm Intelligence"}
