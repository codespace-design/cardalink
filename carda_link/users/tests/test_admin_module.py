from datetime import timedelta
from decimal import Decimal
import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from carda_link.auctions.models import Auction, Bid, Lot
from carda_link.estates.models import Estate, HarvestBatch
from carda_link.invoicing.models import Invoice, PlatformSettings
from carda_link.users.models import AdminActionLog, BuyerProfile, SellerProfile, User


@pytest.fixture
def admin_user(db):
    user, created = User.objects.get_or_create(
        email="testadmin@example.com",
        defaults={
            "name": "Admin User",
            "role": User.Role.ADMIN,
            "status": User.Status.ACTIVE,
            "is_verified": True,
        },
    )
    user.set_password("AdminSecure#2026")
    user.save()
    return user


@pytest.fixture
def seller_user(db):
    user, created = User.objects.get_or_create(
        email="testseller@example.com",
        defaults={
            "name": "Seller Farmer",
            "role": User.Role.SELLER,
            "status": User.Status.ACTIVE,
            "is_verified": True,
        },
    )
    user.set_password("SellerSecure#2026")
    user.save()
    SellerProfile.objects.get_or_create(
        user=user,
        defaults={
            "farm_name": "Green Spices Farm",
            "farm_location": "Idukki",
            "farm_area": Decimal("12.50"),
            "area_unit": User.AreaUnit.ACRE,
            "cardamom_plants": 3500,
        },
    )
    return user


@pytest.fixture
def buyer_user(db):
    user, created = User.objects.get_or_create(
        email="testbuyer@example.com",
        defaults={
            "name": "Buyer Trader",
            "role": User.Role.BUYER,
            "status": User.Status.ACTIVE,
            "is_verified": True,
        },
    )
    user.set_password("BuyerSecure#2026")
    user.save()
    BuyerProfile.objects.get_or_create(
        user=user,
        defaults={
            "company_name": "Spice Global Exports",
            "business_type": "Spices Trader",
            "business_address": "Cochin Harbour",
        },
    )
    return user


@pytest.fixture
def estate_with_batches(db, seller_user):
    estate = Estate.objects.create(
        owner=seller_user,
        name="Highland Estate",
        location="Vandanmedu, Idukki",
        area_in_acres=Decimal("25.00"),
    )
    batch_ungraded = HarvestBatch.objects.create(
        estate=estate,
        harvest_date=timezone.now().date(),
        weight_kg=Decimal("250.00"),
        grade="UNGRADED",
    )
    batch_graded = HarvestBatch.objects.create(
        estate=estate,
        harvest_date=timezone.now().date(),
        weight_kg=Decimal("180.00"),
        grade="AGEB",
    )
    return estate, batch_ungraded, batch_graded


@pytest.mark.django_db
class TestAdminAccessControl:
    def test_anonymous_access_denied(self, client):
        response = client.get(reverse("admin_dashboard"))
        # PermissionDenied triggers 403
        assert response.status_code in [403, 302]

    def test_seller_access_denied(self, client, seller_user):
        client.force_login(seller_user)
        response = client.get(reverse("admin_dashboard"))
        assert response.status_code == 403

    def test_buyer_access_denied(self, client, buyer_user):
        client.force_login(buyer_user)
        response = client.get(reverse("admin_dashboard"))
        assert response.status_code == 403

    def test_admin_access_allowed(self, client, admin_user):
        client.force_login(admin_user)
        response = client.get(reverse("admin_dashboard"))
        assert response.status_code == 200
        assert "Executive Control Center" in response.content.decode()


@pytest.mark.django_db
class TestUserManagement:
    def test_pending_users_list_and_approve(self, client, admin_user):
        client.force_login(admin_user)
        pending_u = User.objects.create(
            email="pending@cardalink.com",
            name="Pending Farmer",
            role=User.Role.SELLER,
            status=User.Status.PENDING,
        )
        SellerProfile.objects.create(
            user=pending_u,
            farm_name="Periyar Estate",
            farm_location="Kumily",
            farm_area=Decimal("5.00"),
            area_unit=User.AreaUnit.ACRE,
            cardamom_plants=1200,
        )

        response = client.get(reverse("admin_pending_registrations"))
        assert response.status_code == 200
        assert pending_u.email in response.content.decode()
        assert "Periyar Estate" in response.content.decode()

        # Approve user (POST only)
        resp_approve = client.post(reverse("admin_user_approve", kwargs={"pk": pending_u.pk}))
        assert resp_approve.status_code == 302

        pending_u.refresh_from_db()
        assert pending_u.status == User.Status.ACTIVE
        assert pending_u.is_verified is True

        # Check Audit Log
        assert AdminActionLog.objects.filter(action="APPROVE_USER", target_id=str(pending_u.pk)).exists()

    def test_reject_user_requires_reason(self, client, admin_user):
        client.force_login(admin_user)
        pending_u = User.objects.create(
            email="rejectme@cardalink.com",
            role=User.Role.BUYER,
            status=User.Status.PENDING,
        )

        # POST without reason fails to reject
        client.post(reverse("admin_user_reject", kwargs={"pk": pending_u.pk}), {"reason": ""})
        pending_u.refresh_from_db()
        assert pending_u.status == User.Status.PENDING

        # POST with reason succeeds
        resp = client.post(
            reverse("admin_user_reject", kwargs={"pk": pending_u.pk}),
            {"reason": "Invalid business license provided."},
        )
        assert resp.status_code == 302
        pending_u.refresh_from_db()
        assert pending_u.status == User.Status.REJECTED
        assert pending_u.rejection_reason == "Invalid business license provided."

        assert AdminActionLog.objects.filter(
            action="REJECT_USER",
            target_id=str(pending_u.pk),
            reason="Invalid business license provided.",
        ).exists()

    def test_suspend_and_reactivate_user(self, client, admin_user, seller_user):
        client.force_login(admin_user)

        # Suspend
        resp_suspend = client.post(
            reverse("admin_user_suspend", kwargs={"pk": seller_user.pk}),
            {"reason": "Multiple contract defaults."},
        )
        assert resp_suspend.status_code == 302
        seller_user.refresh_from_db()
        assert seller_user.status == User.Status.SUSPENDED
        assert seller_user.suspension_reason == "Multiple contract defaults."

        # Reactivate
        resp_reactivate = client.post(reverse("admin_user_reactivate", kwargs={"pk": seller_user.pk}))
        assert resp_reactivate.status_code == 302
        seller_user.refresh_from_db()
        assert seller_user.status == User.Status.ACTIVE
        assert seller_user.suspension_reason == ""

    def test_manual_user_creation_by_admin(self, client, admin_user):
        client.force_login(admin_user)

        payload = {
            "role": User.Role.SELLER,
            "name": "Direct Seller",
            "email": "direct.seller@example.com",
            "password": "Password#2026",
            "confirm_password": "Password#2026",
            "phone_number": "+919988776655",
            "address": "Cardamom Hills, Munnar",
            "license_number": "SB-IND-9991",
            "farm_name": "Munnar Green Plantation",
            "farm_location": "Munnar",
            "farm_area": "20.00",
            "area_unit": User.AreaUnit.ACRE,
            "cardamom_plants": 5000,
        }

        resp = client.post(reverse("admin_user_create"), payload)
        assert resp.status_code == 302

        created_user = User.objects.get(email="direct.seller@example.com")
        assert created_user.status == User.Status.ACTIVE
        assert created_user.created_by_admin is True
        assert created_user.seller_profile.farm_name == "Munnar Green Plantation"

        assert AdminActionLog.objects.filter(action="MANUAL_CREATE_USER", target_id=str(created_user.pk)).exists()


@pytest.mark.django_db
class TestAuctionSchedulingAndClosing:
    def test_create_and_edit_auction(self, client, admin_user):
        client.force_login(admin_user)

        now = timezone.now()
        start = now + timedelta(days=2)
        end = now + timedelta(days=2, hours=4)

        # Validation: start in future and end > start
        payload = {
            "title": "Bodi Premium Cardamom Auction",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": end.strftime("%Y-%m-%dT%H:%M"),
            "description": "Exclusive extra bold cardamom lots.",
        }

        resp = client.post(reverse("admin_auction_create"), payload)
        assert resp.status_code == 302

        auction = Auction.objects.get(title="Bodi Premium Cardamom Auction")
        assert auction.status == "UPCOMING"
        assert auction.description == "Exclusive extra bold cardamom lots."

        # Edit while UPCOMING
        edit_payload = {
            "title": "Bodi Premium Cardamom Auction - Rescheduled",
            "start_time": (start + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "end_time": (end + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "description": "Updated terms.",
        }
        resp_edit = client.post(reverse("admin_auction_edit", kwargs={"pk": auction.pk}), edit_payload)
        assert resp_edit.status_code == 302
        auction.refresh_from_db()
        assert auction.title == "Bodi Premium Cardamom Auction - Rescheduled"

        # Edit when ACTIVE must raise 403 PermissionDenied
        auction.status = "ACTIVE"
        auction.save()
        resp_blocked = client.get(reverse("admin_auction_edit", kwargs={"pk": auction.pk}))
        assert resp_blocked.status_code == 403

    def test_cancel_auction(self, client, admin_user):
        client.force_login(admin_user)
        now = timezone.now()
        auction = Auction.objects.create(
            title="Cancelled Auction",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=2),
            status="UPCOMING",
        )

        resp = client.post(
            reverse("admin_auction_cancel", kwargs={"pk": auction.pk}),
            {"reason": "Severe weather alert in plantation zone."},
        )
        assert resp.status_code == 302
        auction.refresh_from_db()
        assert auction.status == "CANCELLED"
        assert auction.cancellation_reason == "Severe weather alert in plantation zone."

    def test_force_close_active_auction_with_invoicing(self, client, admin_user, buyer_user, estate_with_batches):
        client.force_login(admin_user)
        estate, _, batch_graded = estate_with_batches

        now = timezone.now()
        auction = Auction.objects.create(
            title="Live Force Close Auction",
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            status="ACTIVE",
        )
        lot = Lot.objects.create(
            auction=auction,
            harvest_batch=batch_graded,
            lot_number=1,
            base_price_per_kg=Decimal("1200.00"),
            highest_bid_per_kg=Decimal("1500.00"),
        )
        # Winning bid
        Bid.objects.create(
            lot=lot,
            bidder=buyer_user,
            amount_per_kg=Decimal("1500.00"),
        )

        # Ensure platform commission is 2.5%
        settings_obj = PlatformSettings.load()
        settings_obj.commission_percent = Decimal("2.50")
        settings_obj.save()

        # Trigger emergency force close
        resp = client.post(reverse("admin_auction_force_close", kwargs={"pk": auction.pk}))
        assert resp.status_code == 302

        auction.refresh_from_db()
        lot.refresh_from_db()

        assert auction.status == "COMPLETED"
        assert lot.is_sold is True

        # Verify Invoice generated
        invoice = Invoice.objects.get(lot=lot)
        assert invoice.buyer == buyer_user
        expected_total = Decimal("180.00") * Decimal("1500.00")  # 270,000.00
        expected_commission = round(expected_total * Decimal("0.025"), 2)  # 6,750.00
        assert invoice.total_amount == expected_total
        assert invoice.commission_fee == expected_commission
        assert invoice.status == "PENDING"

        assert AdminActionLog.objects.filter(action="FORCE_CLOSE_AUCTION", target_id=str(auction.pk)).exists()


@pytest.mark.django_db
class TestLotAssignment:
    def test_add_and_remove_lot(self, client, admin_user, estate_with_batches):
        client.force_login(admin_user)
        _, _, batch_graded = estate_with_batches

        now = timezone.now()
        auction = Auction.objects.create(
            title="Upcoming Lot Assign Session",
            start_time=now + timedelta(days=2),
            end_time=now + timedelta(days=2, hours=3),
            status="UPCOMING",
        )

        # Add lot via POST
        payload = {
            "batch_ids": [batch_graded.id],
            f"base_price_{batch_graded.id}": "1350.00",
            f"lot_number_{batch_graded.id}": "10",
        }
        resp = client.post(reverse("admin_auction_lots_add", kwargs={"pk": auction.pk}), payload)
        assert resp.status_code == 302

        lot = Lot.objects.get(auction=auction, harvest_batch=batch_graded)
        assert lot.lot_number == 10
        assert lot.base_price_per_kg == Decimal("1350.00")

        # Remove lot (zero bids)
        resp_remove = client.post(reverse("admin_lot_remove", kwargs={"pk": lot.pk}))
        assert resp_remove.status_code == 302
        assert not Lot.objects.filter(pk=lot.pk).exists()


@pytest.mark.django_db
class TestGradeVerificationQueue:
    def test_grade_and_reject_batch(self, client, admin_user, estate_with_batches):
        client.force_login(admin_user)
        _, batch_ungraded, _ = estate_with_batches

        assert batch_ungraded.grade == "UNGRADED"

        # Grade batch
        resp_grade = client.post(
            reverse("admin_batch_grade", kwargs={"pk": batch_ungraded.pk}),
            {"grade": "AGS1"},
        )
        assert resp_grade.status_code == 302
        batch_ungraded.refresh_from_db()
        assert batch_ungraded.grade == "AGS1"
        assert batch_ungraded.is_rejected is False

        # Reject batch
        resp_reject = client.post(
            reverse("admin_batch_reject", kwargs={"pk": batch_ungraded.pk}),
            {"reason": "High moisture content above Spices Board standards."},
        )
        assert resp_reject.status_code == 302
        batch_ungraded.refresh_from_db()
        assert batch_ungraded.is_rejected is True
        assert batch_ungraded.rejection_reason == "High moisture content above Spices Board standards."


@pytest.mark.django_db
class TestSettlementOversightAndSettings:
    def test_mark_invoice_paid_and_failed(self, client, admin_user, buyer_user, estate_with_batches):
        client.force_login(admin_user)
        _, _, batch_graded = estate_with_batches

        auction = Auction.objects.create(
            title="Completed Auction",
            start_time=timezone.now() - timedelta(days=1),
            end_time=timezone.now() - timedelta(hours=10),
            status="COMPLETED",
        )
        lot = Lot.objects.create(
            auction=auction,
            harvest_batch=batch_graded,
            lot_number=1,
            base_price_per_kg=Decimal("1000.00"),
            is_sold=True,
        )
        invoice = Invoice.objects.create(
            lot=lot,
            buyer=buyer_user,
            total_amount=Decimal("180000.00"),
            commission_fee=Decimal("3600.00"),
            status="PENDING",
        )

        # Mark Paid
        resp_paid = client.post(
            reverse("admin_invoice_mark_paid", kwargs={"pk": invoice.pk}),
            {"status_note": "RTGS ref #UTR998822 received."},
        )
        assert resp_paid.status_code == 302
        invoice.refresh_from_db()
        assert invoice.status == "PAID"
        assert invoice.paid_at is not None
        assert invoice.updated_by == admin_user
        assert invoice.status_note == "RTGS ref #UTR998822 received."

        # Mark Failed
        resp_fail = client.post(
            reverse("admin_invoice_mark_failed", kwargs={"pk": invoice.pk}),
            {"status_note": "Transaction reversed."},
        )
        assert resp_fail.status_code == 302
        invoice.refresh_from_db()
        assert invoice.status == "FAILED"

    def test_platform_settings_update(self, client, admin_user):
        client.force_login(admin_user)

        resp = client.post(reverse("admin_platform_settings"), {"commission_percent": "3.25"})
        assert resp.status_code == 302

        settings_obj = PlatformSettings.load()
        assert settings_obj.commission_percent == Decimal("3.25")
        assert settings_obj.updated_by == admin_user
        assert AdminActionLog.objects.filter(action="UPDATE_PLATFORM_SETTINGS").exists()


@pytest.mark.django_db
class TestAuditLogsView:
    def test_audit_logs_list_and_filter(self, client, admin_user):
        client.force_login(admin_user)

        AdminActionLog.objects.create(
            admin_user=admin_user,
            action="CUSTOM_TEST_ACTION",
            target_model="Auction",
            target_id="99",
            reason="Audit verification test.",
        )

        resp = client.get(reverse("admin_audit_logs"))
        assert resp.status_code == 200
        assert "CUSTOM_TEST_ACTION" in resp.content.decode()

        # Filter by action
        resp_filter = client.get(reverse("admin_audit_logs") + "?action=CUSTOM_TEST_ACTION")
        assert resp_filter.status_code == 200
        assert "CUSTOM_TEST_ACTION" in resp_filter.content.decode()
