from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from carda_link.auctions.models import Auction
from carda_link.auctions.models import Lot
from carda_link.estates.models import Estate
from carda_link.estates.models import HarvestBatch

User = get_user_model()


@pytest.mark.django_db
class TestAuctionModels:
    @pytest.fixture
    def setup_auction_data(self):
        user = User.objects.create_user(
            email="seller@cardalink.com",
            password="Password123!",
            name="Test Farmer",
            role="SELLER",
        )
        bidder1 = User.objects.create_user(
            email="buyer1@cardalink.com",
            password="Password123!",
            name="Buyer One",
            role="BUYER",
        )
        bidder2 = User.objects.create_user(
            email="buyer2@cardalink.com",
            password="Password123!",
            name="Buyer Two",
            role="BUYER",
        )
        estate = Estate.objects.create(
            owner=user,
            name="Cardamom Hills",
            location="Idukki",
            area_in_acres=Decimal("12.00"),
        )
        batch = HarvestBatch.objects.create(
            estate=estate,
            harvest_date=timezone.now().date(),
            weight_kg=Decimal("500.00"),
            grade="AGEB",
        )

        now = timezone.now()
        active_auction = Auction.objects.create(
            title="Active Auction",
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            status="ACTIVE",
        )
        upcoming_auction = Auction.objects.create(
            title="Upcoming Auction",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=2),
            status="UPCOMING",
        )

        lot = Lot.objects.create(
            auction=active_auction,
            harvest_batch=batch,
            lot_number=1,
            base_price_per_kg=Decimal("1000.00"),
        )

        return {
            "seller": user,
            "bidder1": bidder1,
            "bidder2": bidder2,
            "estate": estate,
            "batch": batch,
            "active_auction": active_auction,
            "upcoming_auction": upcoming_auction,
            "lot": lot,
        }

    def test_auction_properties_and_str(self, setup_auction_data):
        auction = setup_auction_data["active_auction"]
        assert "Active Auction" in str(auction)
        assert auction.is_active_now is True

    def test_place_bid_valid(self, setup_auction_data):
        lot = setup_auction_data["lot"]
        bidder = setup_auction_data["bidder1"]

        bid = lot.place_bid(bidder=bidder, amount_per_kg=Decimal("1200.00"))

        assert bid.amount_per_kg == Decimal("1200.00")
        assert lot.highest_bid_per_kg == Decimal("1200.00")
        assert lot.current_price == Decimal("1200.00")
        assert lot.bids.count() == 1

    def test_place_bid_lower_than_base_price_raises_error(self, setup_auction_data):
        lot = setup_auction_data["lot"]
        bidder = setup_auction_data["bidder1"]

        with pytest.raises(
            ValueError,
            match="must be strictly greater than the base price",
        ):
            lot.place_bid(bidder=bidder, amount_per_kg=Decimal("900.00"))

    def test_place_bid_lower_than_highest_bid_raises_error(self, setup_auction_data):
        lot = setup_auction_data["lot"]
        bidder1 = setup_auction_data["bidder1"]
        bidder2 = setup_auction_data["bidder2"]

        lot.place_bid(bidder=bidder1, amount_per_kg=Decimal("1200.00"))

        with pytest.raises(
            ValueError,
            match="must be strictly higher than the current highest bid",
        ):
            lot.place_bid(bidder=bidder2, amount_per_kg=Decimal("1150.00"))

    def test_place_bid_inactive_auction_raises_error(self, setup_auction_data):
        auction = setup_auction_data["upcoming_auction"]
        bidder = setup_auction_data["bidder1"]

        # Create another harvest batch to avoid OneToOne duplication
        estate = setup_auction_data["estate"]
        batch2 = HarvestBatch.objects.create(
            estate=estate,
            harvest_date=timezone.now().date(),
            weight_kg=Decimal("300.00"),
            grade="AGB",
        )

        upcoming_lot = Lot.objects.create(
            auction=auction,
            harvest_batch=batch2,
            lot_number=2,
            base_price_per_kg=Decimal("1000.00"),
        )

        with pytest.raises(ValueError, match="Bidding is closed"):
            upcoming_lot.place_bid(bidder=bidder, amount_per_kg=Decimal("1500.00"))

    def test_close_auction_marks_lots_sold(self, setup_auction_data):
        auction = setup_auction_data["active_auction"]
        lot = setup_auction_data["lot"]
        bidder = setup_auction_data["bidder1"]

        lot.place_bid(bidder=bidder, amount_per_kg=Decimal("1300.00"))
        auction.close_auction()

        lot.refresh_from_db()
        auction.refresh_from_db()
        assert auction.status == "COMPLETED"
        assert lot.is_sold is True
