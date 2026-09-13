from decimal import Decimal
import json
import pytest
from django.urls import reverse
from django.utils import timezone

from carda_link.assistant.models import ChatQueryLog
from carda_link.auctions.models import Auction, Bid, Lot
from carda_link.estates.models import Estate, HarvestBatch
from carda_link.invoicing.models import Invoice
from carda_link.users.models import BuyerProfile, SellerProfile, User, Watchlist


@pytest.fixture
def seller_user(db):
    user = User.objects.create_user(
        email="seller_assistant@test.com",
        phone_number="+919876543301",
        password="ValidPassword123!",
        name="Assistant Seller",
        role=User.Role.SELLER,
        status=User.Status.ACTIVE,
        is_verified=True,
    )
    SellerProfile.objects.create(
        user=user,
        farm_name="Carda Valley Farm",
        farm_location="Vandanmedu, Idukki",
        farm_area=Decimal("15.0"),
        area_unit=SellerProfile.AreaUnit.ACRE,
        cardamom_plants=600,
        district=SellerProfile.District.IDUKKI,
        taluk="Udumbanchola",
        village="Vandanmedu",
        cultivation_method=SellerProfile.CultivationMethod.ORGANIC,
        bank_account_holder="Assistant Seller",
        bank_ifsc="SBIN0001234",
        bank_account_number="123456789012",
    )
    estate = Estate.objects.create(
        owner=user,
        name="Carda Valley Estate",
        location="Vandanmedu, Idukki",
        area_in_acres=Decimal("15.0"),
        owner_name=user.name,
        phone_number=user.phone_number,
    )
    HarvestBatch.objects.create(
        estate=estate,
        harvest_date="2026-09-02",
        weight_kg=Decimal("200.0"),
        grade="AGEB",
    )
    HarvestBatch.objects.create(
        estate=estate,
        harvest_date="2026-09-05",
        weight_kg=Decimal("100.0"),
        grade="UNGRADED",
        is_rejected=True,
        rejection_reason="High moisture level exceeding 14%",
    )
    return user


@pytest.fixture
def buyer_user(db, seller_user):
    user = User.objects.create_user(
        email="buyer_assistant@test.com",
        phone_number="+919876543302",
        password="ValidPassword123!",
        name="Assistant Buyer",
        role=User.Role.BUYER,
        status=User.Status.ACTIVE,
        is_verified=True,
    )
    BuyerProfile.objects.create(
        user=user,
        company_name="Spice Global Trade",
        business_address="Kochi, Kerala",
        business_type=BuyerProfile.BusinessType.WHOLESALER,
        gst_number="32ABCDE5678F1Z2",
        purchase_capacity="8000 kg",
    )
    estate = Estate.objects.get(owner=seller_user)
    batch = HarvestBatch.objects.filter(estate=estate, is_rejected=False).first()

    now = timezone.now()
    auction = Auction.objects.create(
        title="Weekly Spice Exchange",
        status="ACTIVE",
        start_time=now - timezone.timedelta(hours=1),
        end_time=now + timezone.timedelta(hours=5),
    )
    lot = Lot.objects.create(
        auction=auction,
        harvest_batch=batch,
        lot_number=202,
        base_price_per_kg=Decimal("2100.00"),
        highest_bid_per_kg=Decimal("2400.00"),
    )
    Bid.objects.create(
        lot=lot,
        bidder=user,
        amount_per_kg=Decimal("2400.00"),
    )
    Watchlist.objects.create(
        buyer=user,
        lot=lot,
    )
    Invoice.objects.create(
        buyer=user,
        lot=lot,
        total_amount=Decimal("480000.00"),
        commission_fee=Decimal("9600.00"),
        status="PENDING",
    )
    return user


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin_assistant@test.com",
        phone_number="+919876543303",
        password="ValidAdminPassword123!",
        name="Super Admin",
        role=User.Role.ADMIN,
    )


@pytest.mark.django_db
class TestRoleAwareAssistant:
    def test_assistant_query_requires_login(self, client):
        res = client.post(reverse("assistant_query"), json.dumps({"message": "Hello"}), content_type="application/json")
        assert res.status_code == 302  # redirected to login

    def test_seller_queries_batches_and_rejection_reason(self, client, seller_user):
        client.force_login(seller_user)
        res = client.post(
            reverse("assistant_query"),
            json.dumps({"message": "What is the status of my harvest batches?"}),
            content_type="application/json",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "AGEB" in data["answer"]
        assert "High moisture level exceeding 14%" in data["answer"]
        assert "Carda Valley Estate" in data["answer"]

        # Check ChatQueryLog created
        log = ChatQueryLog.objects.filter(user=seller_user).latest("created_at")
        assert "harvest batches" in log.query_text
        assert "High moisture level" in log.response_text

    def test_seller_queries_estates(self, client, seller_user):
        client.force_login(seller_user)
        res = client.post(
            reverse("assistant_query"),
            json.dumps({"message": "Show my cardamom estates"}),
            content_type="application/json",
        )
        assert res.status_code == 200
        data = res.json()
        assert "Carda Valley Estate" in data["answer"]
        assert "Acres" in data["answer"]
        assert "15" in data["answer"]

    def test_buyer_queries_bids_and_watchlist(self, client, buyer_user):
        client.force_login(buyer_user)

        # 1. Bids query
        res_bids = client.post(
            reverse("assistant_query"),
            json.dumps({"message": "What is my current bid status?"}),
            content_type="application/json",
        )
        assert res_bids.status_code == 200
        data_bids = res_bids.json()
        assert "Lot #202" in data_bids["answer"]
        assert "LEADING" in data_bids["answer"]

        # 2. Watchlist query
        res_watch = client.post(
            reverse("assistant_query"),
            json.dumps({"message": "Show my starred lots"}),
            content_type="application/json",
        )
        assert res_watch.status_code == 200
        assert "Lot #202" in res_watch.json()["answer"]

    def test_buyer_data_isolation(self, client, buyer_user, seller_user):
        """Verify that buyer queries never leak seller internal batch / farm rejection notes."""
        client.force_login(buyer_user)
        res = client.post(
            reverse("assistant_query"),
            json.dumps({"message": "Show my harvest batches"}),
            content_type="application/json",
        )
        assert res.status_code == 200
        data = res.json()
        # Buyer has no batches; should not return the seller's batches
        assert "High moisture level" not in data["answer"]
        assert "Carda Valley Estate" not in data["answer"]

    def test_admin_query_platform_status(self, client, admin_user):
        client.force_login(admin_user)
        res = client.post(
            reverse("assistant_query"),
            json.dumps({"message": "What are the platform stats and pending approvals?"}),
            content_type="application/json",
        )
        assert res.status_code == 200
        data = res.json()
        assert "Pending User Registrations" in data["answer"]
        assert "Ungraded Harvest Batches" in data["answer"]

    def test_domain_farming_query_fallback(self, client, seller_user):
        client.force_login(seller_user)
        res = client.post(
            reverse("assistant_query"),
            json.dumps({"message": "How do I control cardamom thrips and capsule rot?"}),
            content_type="application/json",
        )
        assert res.status_code == 200
        data = res.json()
        # Should return domain assistant answer
        assert len(data["answer"]) > 10
