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
class TestAuctionAPI:
    @pytest.fixture
    def setup_api_data(self, client):
        user = User.objects.create_user(
            email="buyer_api@cardalink.com",
            password="Password123!",
            name="API Buyer",
            role="BUYER",
            status=User.Status.ACTIVE,
            is_verified=True,
        )
        seller = User.objects.create_user(
            email="seller_api@cardalink.com",
            password="Password123!",
            name="API Seller",
            role="SELLER",
            status=User.Status.ACTIVE,
            is_verified=True,
        )
        estate = Estate.objects.create(
            owner=seller,
            name="API Estate",
            location="Idukki",
            area_in_acres=Decimal("15.00"),
        )
        batch = HarvestBatch.objects.create(
            estate=estate,
            harvest_date=timezone.now().date(),
            weight_kg=Decimal("400.00"),
            grade="AGEB",
        )

        now = timezone.now()
        auction = Auction.objects.create(
            title="API Test Auction",
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=3),
            status="ACTIVE",
        )
        lot = Lot.objects.create(
            auction=auction,
            harvest_batch=batch,
            lot_number=10,
            base_price_per_kg=Decimal("1500.00"),
        )

        return {
            "user": user,
            "seller": seller,
            "estate": estate,
            "batch": batch,
            "auction": auction,
            "lot": lot,
            "client": client,
        }

    def test_health_check_endpoint(self, client):
        response = client.get("/api/auctions/health-check")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_list_auctions_endpoint(self, setup_api_data):
        client = setup_api_data["client"]
        response = client.get("/api/auctions/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["title"] == "API Test Auction"

    def test_create_auction_endpoint(self, setup_api_data):
        client = setup_api_data["client"]
        user = setup_api_data["user"]
        client.force_login(user)
        now = timezone.now()
        payload = {
            "title": "Newly Created API Auction",
            "start_time": (now + timedelta(hours=1)).isoformat(),
            "end_time": (now + timedelta(hours=5)).isoformat(),
            "status": "UPCOMING",
        }
        response = client.post(
            "/api/auctions/",
            data=payload,
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Newly Created API Auction"

    def test_place_bid_api_authenticated(self, setup_api_data):
        client = setup_api_data["client"]
        user = setup_api_data["user"]
        lot = setup_api_data["lot"]

        client.force_login(user)
        payload = {"amount_per_kg": 1650.00}
        response = client.post(
            f"/api/auctions/lots/{lot.id}/bids/",
            data=payload,
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert Decimal(str(data["amount_per_kg"])) == Decimal("1650.00")
        assert data["bidder_email"] == "buyer_api@cardalink.com"

    def test_place_bid_api_too_low(self, setup_api_data):
        client = setup_api_data["client"]
        user = setup_api_data["user"]
        lot = setup_api_data["lot"]

        client.force_login(user)
        payload = {"amount_per_kg": 1400.00}  # Below base price 1500.00
        response = client.post(
            f"/api/auctions/lots/{lot.id}/bids/",
            data=payload,
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_close_auction_api(self, setup_api_data):
        client = setup_api_data["client"]
        user = setup_api_data["user"]
        client.force_login(user)
        auction = setup_api_data["auction"]

        response = client.post(f"/api/auctions/{auction.id}/close/")
        assert response.status_code == 200
        auction.refresh_from_db()
        assert auction.status == "COMPLETED"

    def test_live_bidding_view_buyer_has_no_go_live_or_force_close(self, setup_api_data):
        client = setup_api_data["client"]
        user = setup_api_data["user"]
        auction = setup_api_data["auction"]
        # Ensure auction is active
        auction.status = "ACTIVE"
        auction.end_time = timezone.now() + timedelta(hours=2)
        auction.save(update_fields=["status", "end_time"])

        client.force_login(user)
        response = client.get(f"/auctions/simulation/?auction_id={auction.id}")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Go Live Now" not in content
        assert "Force Close" not in content
        assert "forceStartAuction" not in content
        assert "forceCloseAuction" not in content

    def test_live_bidding_view_admin_has_controls(self, setup_api_data):
        client = setup_api_data["client"]
        auction = setup_api_data["auction"]
        auction.status = "ACTIVE"
        auction.end_time = timezone.now() + timedelta(hours=2)
        auction.save(update_fields=["status", "end_time"])

        admin = User.objects.create_user(
            email="admin_auction_test@cardalink.com",
            password="Password123!",
            name="Admin Tester",
            role="ADMIN",
            status=User.Status.ACTIVE,
            is_verified=True,
            is_staff=True,
        )
        client.force_login(admin)
        response = client.get(f"/auctions/simulation/?auction_id={auction.id}")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Force Close" in content
        assert "forceCloseAuction" in content

