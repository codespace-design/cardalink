from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from carda_link.auctions.models import Auction, Bid, Lot
from carda_link.estates.models import Estate, HarvestBatch
from carda_link.invoicing.models import Invoice
from carda_link.users.models import BuyerProfile, Notification, SellerProfile, User, Watchlist


@pytest.fixture
def active_buyer(db):
    user = User.objects.create_user(
        email="buyer_dash@test.com",
        phone_number="+919876543201",
        password="ValidPassword123!",
        name="Test Buyer Dash",
        role=User.Role.BUYER,
        status=User.Status.ACTIVE,
        is_verified=True,
    )
    BuyerProfile.objects.create(
        user=user,
        company_name="Cardamom Traders Ltd",
        business_address="Kochi, Kerala",
        business_type=BuyerProfile.BusinessType.EXPORTER,
        gst_number="32ABCDE1234F1Z5",
        purchase_capacity="5000 kg",
    )
    return user


@pytest.fixture
def active_seller(db):
    user = User.objects.create_user(
        email="seller_dash@test.com",
        phone_number="+919876543202",
        password="ValidPassword123!",
        name="Test Seller Dash",
        role=User.Role.SELLER,
        status=User.Status.ACTIVE,
        is_verified=True,
    )
    SellerProfile.objects.create(
        user=user,
        farm_name="Green Highs Farm",
        farm_location="Vandanmedu, Idukki",
        district=SellerProfile.District.IDUKKI,
        taluk="Udumbanchola",
        village="Vandanmedu",
        farm_area=Decimal("12.5"),
        area_unit=SellerProfile.AreaUnit.ACRE,
        cardamom_plants=500,
        cultivation_method=SellerProfile.CultivationMethod.ORGANIC,
        bank_account_holder="Test Seller Dash",
        bank_ifsc="SBIN0001234",
        bank_account_number="987654321098",
    )
    return user


@pytest.fixture
def pending_seller(db):
    user = User.objects.create_user(
        email="pending_seller@test.com",
        phone_number="+919876543203",
        password="ValidPassword123!",
        name="Pending Seller",
        role=User.Role.SELLER,
        status=User.Status.PENDING,
        is_verified=True,
    )
    SellerProfile.objects.create(
        user=user,
        farm_name="Pending Farm",
        farm_location="Idukki",
        district=SellerProfile.District.IDUKKI,
        farm_area=Decimal("5.0"),
        area_unit=SellerProfile.AreaUnit.ACRE,
        cardamom_plants=200,
    )
    return user


@pytest.fixture
def sample_estate(db, active_seller):
    return Estate.objects.create(
        owner=active_seller,
        name="Green Highs Estate",
        location="Vandanmedu, Idukki",
        area_in_acres=Decimal("12.5"),
        owner_name=active_seller.name,
        phone_number=active_seller.phone_number,
    )


@pytest.fixture
def sample_batch(db, sample_estate):
    return HarvestBatch.objects.create(
        estate=sample_estate,
        harvest_date="2026-09-01",
        weight_kg=Decimal("150.0"),
        grade="AGB",
    )


@pytest.fixture
def sample_auction_and_lot(db, sample_batch):
    now = timezone.now()
    auction = Auction.objects.create(
        title="Idukki Premium Spices Auction",
        status="ACTIVE",
        start_time=now - timezone.timedelta(hours=1),
        end_time=now + timezone.timedelta(hours=5),
    )
    lot = Lot.objects.create(
        auction=auction,
        harvest_batch=sample_batch,
        lot_number=101,
        base_price_per_kg=Decimal("2200.00"),
        highest_bid_per_kg=Decimal("2350.00"),
    )
    return auction, lot


# -----------------------------------------------------------------------------
# BUYER DASHBOARD TESTS
# -----------------------------------------------------------------------------
@pytest.mark.django_db
class TestBuyerDashboard:
    def test_buyer_dashboard_access_active(self, client, active_buyer):
        client.force_login(active_buyer)
        response = client.get(reverse("buyer_dashboard"))
        assert response.status_code == 200
        assert "BUYER PORTAL" in response.content.decode("utf-8")
        assert "Dashboard" in response.content.decode("utf-8")

    def test_buyer_dashboard_permission_denied_for_seller(self, client, active_seller):
        client.force_login(active_seller)
        response = client.get(reverse("buyer_dashboard"))
        assert response.status_code == 403

    def test_buyer_auctions_view(self, client, active_buyer, sample_auction_and_lot):
        client.force_login(active_buyer)
        response = client.get(reverse("buyer_auctions"))
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Lot #101" in content
        assert "Green Highs Estate" in content

    def test_buyer_watchlist_toggle(self, client, active_buyer, sample_auction_and_lot):
        _, lot = sample_auction_and_lot
        client.force_login(active_buyer)

        # Toggle on
        res1 = client.post(reverse("buyer_watchlist_toggle", kwargs={"lot_id": lot.id}))
        assert Watchlist.objects.filter(buyer=active_buyer, lot=lot).exists()

        # View watchlist
        res_view = client.get(reverse("buyer_watchlist"))
        assert res_view.status_code == 200
        assert "Lot #101" in res_view.content.decode("utf-8")

        # Toggle off
        res2 = client.post(reverse("buyer_watchlist_toggle", kwargs={"lot_id": lot.id}))
        assert not Watchlist.objects.filter(buyer=active_buyer, lot=lot).exists()

    def test_buyer_bids_view_computed_status(self, client, active_buyer, sample_auction_and_lot):
        _, lot = sample_auction_and_lot
        # Place bid
        Bid.objects.create(
            lot=lot,
            bidder=active_buyer,
            amount_per_kg=Decimal("2350.00"),
        )
        client.force_login(active_buyer)
        response = client.get(reverse("buyer_bids"))
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Lot #101" in content
        assert "Leading" in content

    def test_buyer_invoices_view(self, client, active_buyer, sample_auction_and_lot):
        _, lot = sample_auction_and_lot
        inv = Invoice.objects.create(
            buyer=active_buyer,
            lot=lot,
            total_amount=Decimal("352500.00"),
            commission_fee=Decimal("7050.00"),
            status="PENDING",
        )
        client.force_login(active_buyer)
        response = client.get(reverse("buyer_invoices"))
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert f"INV-{inv.id:05d}" in content
        assert "Pay Now" in content
        assert reverse("buyer_invoice_pay", kwargs={"pk": inv.pk}) in content

    def test_buyer_invoice_pay_get_and_post_upi(self, client, active_buyer, sample_auction_and_lot):
        _, lot = sample_auction_and_lot
        inv = Invoice.objects.create(
            buyer=active_buyer,
            lot=lot,
            total_amount=Decimal("250000.00"),
            commission_fee=Decimal("5000.00"),
            status="PENDING",
        )
        client.force_login(active_buyer)

        # 1. GET Checkout
        get_resp = client.get(reverse("buyer_invoice_pay", kwargs={"pk": inv.pk}))
        assert get_resp.status_code == 200
        content = get_resp.content.decode("utf-8")
        assert f"INV-{inv.id:05d}" in content
        assert "250000.00" in content
        assert "Instant UPI" in content or "UPI / QR" in content
        assert "Net Banking" in content
        assert "NEFT / RTGS" in content

        # 2. POST Payment
        post_data = {
            "payment_method": "UPI",
            "upi_id": "buyer@okhdfcbank",
            "reference_id": "UPI-REF-998811",
        }
        post_resp = client.post(reverse("buyer_invoice_pay", kwargs={"pk": inv.pk}), post_data)
        assert post_resp.status_code == 302
        assert post_resp.url == reverse("buyer_invoices")

        inv.refresh_from_db()
        assert inv.status == "PAID"
        assert inv.paid_at is not None
        assert "UPI-REF-998811" in inv.status_note

        buyer_notif = Notification.objects.filter(
            user=active_buyer,
            notification_type=Notification.NotificationType.INVOICE,
        ).first()
        assert buyer_notif is not None
        assert "250000.00" in buyer_notif.message

    def test_buyer_invoice_pay_post_neft(self, client, active_buyer, sample_auction_and_lot):
        _, lot = sample_auction_and_lot
        inv = Invoice.objects.create(
            buyer=active_buyer,
            lot=lot,
            total_amount=Decimal("120000.00"),
            commission_fee=Decimal("2400.00"),
            status="PENDING",
        )
        client.force_login(active_buyer)

        post_data = {
            "payment_method": "NEFT_RTGS",
            "utr_number": "UTR20260913982012",
        }
        post_resp = client.post(reverse("buyer_invoice_pay", kwargs={"pk": inv.pk}), post_data)
        assert post_resp.status_code == 302

        inv.refresh_from_db()
        assert inv.status == "PAID"
        assert "UTR20260913982012" in inv.status_note

    def test_buyer_cannot_pay_another_buyers_invoice(self, client, active_buyer, sample_auction_and_lot):
        _, lot = sample_auction_and_lot
        other_buyer = User.objects.create_user(
            email="otherbuyer@cardalink.com",
            name="Other Buyer",
            role=User.Role.BUYER,
            status=User.Status.ACTIVE,
            password="password123",
        )
        inv = Invoice.objects.create(
            buyer=other_buyer,
            lot=lot,
            total_amount=Decimal("75000.00"),
            commission_fee=Decimal("1500.00"),
            status="PENDING",
        )

        client.force_login(active_buyer)
        # Attempt to access another buyer's invoice
        resp = client.get(reverse("buyer_invoice_pay", kwargs={"pk": inv.pk}))
        assert resp.status_code == 404

    def test_buyer_invoice_already_paid_redirect(self, client, active_buyer, sample_auction_and_lot):
        _, lot = sample_auction_and_lot
        inv = Invoice.objects.create(
            buyer=active_buyer,
            lot=lot,
            total_amount=Decimal("80000.00"),
            commission_fee=Decimal("1600.00"),
            status="PAID",
        )
        client.force_login(active_buyer)
        resp = client.get(reverse("buyer_invoice_pay", kwargs={"pk": inv.pk}))
        assert resp.status_code == 302
        assert resp.url == reverse("buyer_invoices")


# -----------------------------------------------------------------------------
# SELLER DASHBOARD TESTS
# -----------------------------------------------------------------------------
@pytest.mark.django_db
class TestSellerDashboard:
    def test_seller_dashboard_access_active(self, client, active_seller):
        client.force_login(active_seller)
        response = client.get(reverse("seller_dashboard"))
        assert response.status_code == 200
        assert "SELLER PORTAL" in response.content.decode("utf-8")

    def test_seller_dashboard_permission_denied_pending(self, client, pending_seller):
        client.force_login(pending_seller)
        response = client.get(reverse("seller_dashboard"))
        # Inactive/pending users are rejected from accessing seller dashboard
        assert response.status_code in [302, 403]

    def test_seller_dashboard_permission_denied_for_buyer(self, client, active_buyer):
        client.force_login(active_buyer)
        response = client.get(reverse("seller_dashboard"))
        assert response.status_code == 403

    def test_seller_estates_crud(self, client, active_seller):
        client.force_login(active_seller)
        # 1. Create Estate via POST
        res_create = client.post(reverse("seller_estates"), {
            "name": "Misty Hills Plantation",
            "location": "Kumily, Kerala",
            "area_in_acres": "8.5",
            "description": "High altitude premium cardamom estate",
        })
        assert res_create.status_code == 302
        estate = Estate.objects.get(name="Misty Hills Plantation")
        assert estate.owner == active_seller

        # 2. Edit Estate
        res_edit = client.post(reverse("seller_estate_edit", kwargs={"pk": estate.pk}), {
            "name": "Misty Hills Organic Plantation",
            "location": "Kumily, Kerala",
            "area_in_acres": "9.0",
            "description": "Certified organic high altitude cardamom",
        })
        assert res_edit.status_code == 302
        estate.refresh_from_db()
        assert estate.name == "Misty Hills Organic Plantation"
        assert estate.area_in_acres == Decimal("9.0")

        # 3. Delete Estate
        res_del = client.post(reverse("seller_estate_delete", kwargs={"pk": estate.pk}))
        assert res_del.status_code == 302
        assert not Estate.objects.filter(pk=estate.pk).exists()

    def test_seller_batches_logging_and_rejection_reason(self, client, active_seller, sample_estate):
        client.force_login(active_seller)
        # Create batch via POST
        res = client.post(reverse("seller_batches"), {
            "estate_id": sample_estate.id,
            "harvest_date": "2026-09-10",
            "weight_kg": "220.0",
        })
        assert res.status_code == 302
        batch = HarvestBatch.objects.get(weight_kg=Decimal("220.0"))
        assert batch.grade == "UNGRADED"

        # Simulate admin rejection with reason
        batch.is_rejected = True
        batch.rejection_reason = "Excessive moisture content (>14%) and discolored capsules"
        batch.save()

        # View batches page and verify rejection reason is displayed
        res_view = client.get(reverse("seller_batches"))
        assert res_view.status_code == 200
        content = res_view.content.decode("utf-8")
        assert "Excessive moisture content" in content

    def test_seller_earnings_masked_bank_account(self, client, active_seller):
        client.force_login(active_seller)
        response = client.get(reverse("seller_earnings"))
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        # Bank account number is 987654321098 -> should display masked: •••• •••• 1098
        assert "•••• •••• 1098" in content
        # Must NOT display full unmasked account number
        assert "987654321098" not in content

    def test_mark_all_notifications_read(self, client, active_seller):
        Notification.objects.create(
            user=active_seller,
            message="Your batch was approved!",
            is_read=False,
        )
        assert Notification.objects.filter(user=active_seller, is_read=False).count() == 1

        client.force_login(active_seller)
        client.post(reverse("mark_all_notifications_read"))
        assert Notification.objects.filter(user=active_seller, is_read=False).count() == 0
