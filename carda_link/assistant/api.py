from ninja import Router

from .services.chatbot_service import ChatbotService

router = Router(tags=["AI Agricultural Assistant"])

# Single shared instance created once for optimal performance
chatbot_service = ChatbotService()


@router.get("/health-check")
def assistant_health_check(request):
    return {
        "status": "ok",
        "module": "AI Agricultural Assistant & NLP Service",
    }


@router.get("/chat")
def chat(request, message: str):
    """
    Main chatbot endpoint.
    Returns category, answer markdown, and dynamic suggestions.
    """
    return chatbot_service.get_response(message)