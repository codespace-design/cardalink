from ninja import Router

router = Router(tags=["Invoicing & Billing"])


@router.get("/health-check")
def invoicing_health_check(request):
    return {"status": "ok", "module": "Invoicing & Commerce"}
