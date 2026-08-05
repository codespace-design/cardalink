from ninja import Router

router = Router(tags=["AI Agricultural Assistant"])


@router.get("/health-check")
def assistant_health_check(request):
    return {"status": "ok", "module": "AI Agricultural Assistant & NLP Service"}
