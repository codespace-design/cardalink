import logging
from typing import Any

from .auction_service import AuctionService
from .farm_service import FarmService
from .intent_service import IntentClassifier
from .website_service import WebsiteService

logger = logging.getLogger(__name__)


class ChatbotService:
    """
    Main Chatbot Service for CardaLink AI Assistant.
    Uses IntentClassifier for automated NLP routing to WebsiteService,
    AuctionService, or FarmService, while providing dynamic suggested questions.
    """

    def __init__(self) -> None:
        self.intent_classifier = IntentClassifier()
        self.website = WebsiteService()
        self.auction = AuctionService()
        self.farm = FarmService()

    def get_response(self, question: str) -> dict[str, Any]:
        """
        Processes incoming user message, detects intent, routes to specialized service,
        and returns response dict containing category, answer, and suggestions.
        """
        if not question or not question.strip():
            unknown_res = self.website.get_dynamic_unknown_response()
            return {
                "category": "Unknown",
                "answer": unknown_res["answer"],
                "suggestions": unknown_res["suggestions"],
            }

        clean_question = question.strip()
        intent = self.intent_classifier.classify(clean_question)
        logger.debug("Detected intent '%s' for question: '%s'", intent, clean_question)

        # -------------------------
        # 1. FARM ASSISTANT
        # -------------------------
        if intent == "Farm Assistant":
            farm_answer = self.farm.answer(clean_question)
            return {
                "category": "Farm Assistant",
                "answer": farm_answer,
                "suggestions": self.website.suggested_questions,
            }

        # -------------------------
        # 2. AUCTION
        # -------------------------
        if intent == "Auction":
            auction_answer = self.auction.answer(clean_question)
            if auction_answer:
                return {
                    "category": "Auction",
                    "answer": auction_answer,
                    "suggestions": self.website.suggested_questions,
                }

        # -------------------------
        # 3. WEBSITE GUIDE
        # -------------------------
        if intent == "Website Guide":
            website_res = self.website.answer(clean_question)
            category = "Website Guide" if website_res.get("matched") else "Unknown"
            return {
                "category": category,
                "answer": website_res["answer"],
                "suggestions": website_res["suggestions"],
            }

        # -------------------------
        # 4. UNKNOWN / FALLBACK ROUTING
        # -------------------------
        # Attempt website guide matching before final fallback
        website_res = self.website.answer(clean_question)
        if website_res.get("matched"):
            return {
                "category": "Website Guide",
                "answer": website_res["answer"],
                "suggestions": website_res["suggestions"],
            }

        # Try auction answering in case keyword missed classification
        auction_answer = self.auction.answer(clean_question)
        if auction_answer and "Overview" not in auction_answer:
            return {
                "category": "Auction",
                "answer": auction_answer,
                "suggestions": self.website.suggested_questions,
            }

        # Final Unknown Fallback with dynamic headings suggestions
        return {
            "category": "Unknown",
            "answer": website_res["answer"],
            "suggestions": website_res["suggestions"],
        }