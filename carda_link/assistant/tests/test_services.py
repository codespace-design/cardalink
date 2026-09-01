import pytest
from django.test import override_settings

from carda_link.assistant.services.auction_service import AuctionService
from carda_link.assistant.services.chatbot_service import ChatbotService
from carda_link.assistant.services.farm_service import FarmService
from carda_link.assistant.services.intent_service import IntentClassifier
from carda_link.assistant.services.website_service import WebsiteService
from carda_link.auctions.models import Auction, Bid, Lot
from carda_link.estates.models import HarvestBatch
from carda_link.users.models import User


@pytest.mark.django_db
class TestAssistantServices:

    def test_intent_classifier(self) -> None:
        classifier = IntentClassifier()

        assert classifier.classify("What is the highest bid?") == "Auction"
        assert classifier.classify("How many active auctions?") == "Auction"
        assert classifier.classify("Total buyers count") == "Auction"

        assert classifier.classify("Why are my cardamom leaves turning yellow?") == "Farm Assistant"
        assert classifier.classify("why leaves are turning yellow in my cradamom") == "Farm Assistant"
        assert classifier.classify("Best fertilizer for cardamom crop") == "Farm Assistant"

        assert classifier.classify("I want to register as a buyer") == "Website Guide"
        assert classifier.classify("How do I download my invoice?") == "Website Guide"

        assert classifier.classify("Quantum physics equation") == "Unknown"

    def test_website_service_natural_language_matching(self) -> None:
        service = WebsiteService()

        # Dynamic suggested questions should be loaded from guide headings
        assert len(service.suggested_questions) > 0
        assert "Buyer Registration" in service.suggested_questions
        assert "Seller Registration" in service.suggested_questions

        # Test natural language queries matching guide content
        queries = [
            "how to sign up",
            "I want to register as a buyer",
            "How can I become a buyer?",
            "Where do I register?",
            "Can you explain buyer registration?",
            "I forgot how to login.",
            "How do I place a bid?",
            "I want to download my invoice.",
            "How can I view live auctions?",
            "Where can I see my purchase history?",
            "I need help changing my password.",
        ]

        for query in queries:
            res = service.answer(query)
            assert res["matched"] is True, f"Failed to match natural query: {query}"
            assert res["answer"] is not None
            assert len(res["suggestions"]) > 0

    def test_website_service_unknown_question(self) -> None:
        service = WebsiteService()

        res = service.answer("How do I fly a rocket?")
        assert res["matched"] is False
        assert "I couldn't find that information in the CardaLink guides." in res["answer"]
        assert "Seller Registration" in res["answer"]
        assert "Buyer Registration" in res["answer"]
        assert len(res["suggestions"]) > 0

    def test_auction_service_mock_fallback_when_db_empty(self) -> None:
        service = AuctionService()

        # DB is empty, should return fallback values
        res_highest = service.answer("What is the highest bid?")
        assert "2850" in res_highest

        res_active = service.answer("How many active auctions?")
        assert "18" in res_active

        res_buyers = service.answer("Total registered buyers?")
        assert "45" in res_buyers

    def test_auction_service_live_db_queries(self) -> None:
        # Create live database records
        seller = User.objects.create_user(
            email="seller@test.com", password="password", role=User.Role.SELLER
        )
        buyer = User.objects.create_user(
            email="buyer@test.com", password="password", role=User.Role.BUYER
        )

        batch = HarvestBatch.objects.create(
            farmer=seller,
            grade="AGE",
            weight_kg=100.0,
        )

        auction = Auction.objects.create(
            title="Test Auction",
            start_time="2026-08-01T00:00:00Z",
            end_time="2026-08-30T00:00:00Z",
            status="ACTIVE",
        )

        lot = Lot.objects.create(
            auction=auction,
            harvest_batch=batch,
            lot_number=101,
            base_price_per_kg=1500.00,
            highest_bid_per_kg=3200.00,
        )

        Bid.objects.create(
            lot=lot,
            bidder=buyer,
            amount_per_kg=3200.00,
        )

        service = AuctionService()

        # Query highest bid (live DB value is 3200.00)
        res_highest = service.answer("What is the highest bid?")
        assert "3200" in res_highest

        # Query active auctions (live DB value is 1)
        res_active = service.answer("How many active auctions are running?")
        assert "1" in res_active

        # Query buyers count (live DB value is 1)
        res_buyers = service.answer("Number of buyers")
        assert "1" in res_buyers

    @override_settings(GEMINI_API_KEY="")
    def test_farm_service_without_api_key(self) -> None:
        service = FarmService()
        res = service.answer("Why are my cardamom leaves turning yellow?")
        assert "Gemini API key is not configured" in res

    def test_chatbot_service(self) -> None:
        chatbot = ChatbotService()

        # Website Guide query
        res_guide = chatbot.get_response("How can I become a buyer?")
        assert res_guide["category"] == "Website Guide"
        assert "suggestions" in res_guide

        # Auction query
        res_auc = chatbot.get_response("Show me the latest bid")
        assert res_auc["category"] == "Auction"
        assert "answer" in res_auc

        # Unknown query
        res_unk = chatbot.get_response("Tell me quantum physics theory")
        assert res_unk["category"] == "Unknown"
        assert "I couldn't find that information in the CardaLink guides" in res_unk["answer"]
        assert len(res_unk["suggestions"]) > 0
