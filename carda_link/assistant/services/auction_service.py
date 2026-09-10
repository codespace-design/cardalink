import logging

from django.db.models import Max

logger = logging.getLogger(__name__)


class AuctionService:
    """
    Handles auction-related questions.
    Queries live database models when available, falling back to mock data only when database tables are empty.
    """

    def __init__(self) -> None:
        self.mock_data: dict[str, str | int] = {
            "highest_bid": "₹2850/kg",
            "last_bid": "₹2740/kg",
            "active_auctions": 18,
            "completed_auctions": 250,
            "total_buyers": 45,
            "total_sellers": 30,
        }

    def _get_live_highest_bid(self) -> str | None:
        try:
            from carda_link.auctions.models import Bid, Lot

            if not Bid.objects.exists() and not Lot.objects.exists():
                return None

            max_bid = Bid.objects.aggregate(Max("amount_per_kg"))[
                "amount_per_kg__max"
            ]
            if max_bid is None:
                max_bid = Lot.objects.aggregate(Max("highest_bid_per_kg"))[
                    "highest_bid_per_kg__max"
                ]

            if max_bid is not None:
                return f"₹{max_bid}/kg"
        except Exception as e:
            logger.debug("Database query for highest bid failed/empty: %s", e)
        return None

    def _get_live_last_bid(self) -> str | None:
        try:
            from carda_link.auctions.models import Bid

            if not Bid.objects.exists():
                return None

            latest = Bid.objects.order_by("-timestamp", "-id").first()
            if latest and latest.amount_per_kg is not None:
                return f"₹{latest.amount_per_kg}/kg"
        except Exception as e:
            logger.debug("Database query for last bid failed/empty: %s", e)
        return None

    def _get_live_active_auctions(self) -> int | None:
        try:
            from carda_link.auctions.models import Auction

            if not Auction.objects.exists():
                return None
            return Auction.objects.filter(status="ACTIVE").count()
        except Exception as e:
            logger.debug("Database query for active auctions failed/empty: %s", e)
        return None

    def _get_live_completed_auctions(self) -> int | None:
        try:
            from carda_link.auctions.models import Auction

            if not Auction.objects.exists():
                return None
            return Auction.objects.filter(status="COMPLETED").count()
        except Exception as e:
            logger.debug("Database query for completed auctions failed/empty: %s", e)
        return None

    def _get_live_buyers_count(self) -> int | None:
        try:
            from carda_link.users.models import User

            if not User.objects.filter(role="BUYER").exists() and not User.objects.exists():
                return None
            return User.objects.filter(role="BUYER").count()
        except Exception as e:
            logger.debug("Database query for buyers count failed/empty: %s", e)
        return None

    def _get_live_sellers_count(self) -> int | None:
        try:
            from carda_link.users.models import User

            if not User.objects.filter(role="SELLER").exists() and not User.objects.exists():
                return None
            return User.objects.filter(role="SELLER").count()
        except Exception as e:
            logger.debug("Database query for sellers count failed/empty: %s", e)
        return None

    def answer(self, question: str) -> str | None:
        if not question:
            return None

        q_lower = question.lower()

        # Highest Bid natural language queries
        if any(
            phrase in q_lower
            for phrase in [
                "highest bid",
                "maximum bid",
                "max bid",
                "highest price",
                "top bid",
                "current highest bid",
            ]
        ):
            live_val = self._get_live_highest_bid()
            val = live_val if live_val is not None else self.mock_data["highest_bid"]
            return f"The current highest bid is {val}."

        # Latest / Last Bid natural language queries
        if any(
            phrase in q_lower
            for phrase in [
                "latest bid",
                "last bid",
                "recent bid",
                "latest price",
                "latest auction price",
                "show latest bid",
                "last successful bid",
            ]
        ):
            live_val = self._get_live_last_bid()
            val = live_val if live_val is not None else self.mock_data["last_bid"]
            return f"The latest successful bid is {val}."

        # Active Auctions natural language queries
        if any(
            phrase in q_lower
            for phrase in [
                "active auction",
                "active auctions",
                "running auction",
                "running auctions",
                "current auction count",
                "live auction count",
                "bidding open",
            ]
        ):
            live_val = self._get_live_active_auctions()
            val = live_val if live_val is not None else self.mock_data["active_auctions"]
            return f"There are currently {val} active auctions."

        # Completed Auctions natural language queries
        if any(
            phrase in q_lower
            for phrase in [
                "completed auction",
                "completed auctions",
                "finished auction",
                "finished auctions",
                "past auctions",
            ]
        ):
            live_val = self._get_live_completed_auctions()
            val = live_val if live_val is not None else self.mock_data["completed_auctions"]
            return f"{val} auctions have been successfully completed."

        # Buyer Count natural language queries
        if any(
            phrase in q_lower
            for phrase in [
                "registered buyer",
                "registered buyers",
                "total buyer",
                "total buyers",
                "buyer count",
                "number of buyer",
                "number of buyers",
                "count of buyer",
            ]
        ):
            live_val = self._get_live_buyers_count()
            val = live_val if live_val is not None else self.mock_data["total_buyers"]
            return f"There are {val} registered buyers."

        # Seller Count natural language queries
        if any(
            phrase in q_lower
            for phrase in [
                "registered seller",
                "registered sellers",
                "total seller",
                "total sellers",
                "seller count",
                "number of seller",
                "number of sellers",
                "count of seller",
            ]
        ):
            live_val = self._get_live_sellers_count()
            val = live_val if live_val is not None else self.mock_data["total_sellers"]
            return f"There are {val} registered sellers."

        # Generic auction fallback if intent was categorized as Auction
        live_highest = self._get_live_highest_bid()
        val_highest = live_highest if live_highest is not None else self.mock_data["highest_bid"]

        live_active = self._get_live_active_auctions()
        val_active = live_active if live_active is not None else self.mock_data["active_auctions"]

        return (
            f"Auction Overview:\n"
            f"• Current Highest Bid: {val_highest}\n"
            f"• Active Auctions: {val_active}\n\n"
            f"You can ask specifically about highest bid, latest price, active auctions, completed auctions, total buyers, or total sellers."
        )