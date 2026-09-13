import io
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from carda_link.users.models import User, BuyerProfile, SellerProfile


@pytest.mark.django_db
def test_buyer_registration_creates_pending_user_and_triggers_otp(client):
    cert_file = SimpleUploadedFile("license.pdf", b"%PDF-1.4 dummy content", content_type="application/pdf")
    payload = {
        "name": "Arjun Spice Traders",
        "email": "arjun@spicetraders.com",
        "phone_number": "9876543210",
        "password": "BuyerSecurePassword123!",
        "confirm_password": "BuyerSecurePassword123!",
        "business_name": "Arjun Cardamom Exports",
        "business_type": BuyerProfile.BusinessType.EXPORTER,
        "gst_number": "32AAAAA0000A1Z5",
        "business_address": "Main Bazaar, Kumily, Kerala 685509",
        "purchase_capacity": "5000 kg/month",
        "registration_certificate": cert_file,
    }

    response = client.post(reverse("register_buyer"), data=payload, follow=False)
    assert response.status_code == 302
    assert response.url == reverse("account_verify_otp")

    user = User.objects.get(email="arjun@spicetraders.com")
    assert user.role == User.Role.BUYER
    assert user.status == User.Status.PENDING
    assert user.buyer_profile.company_name == "Arjun Cardamom Exports"
    assert user.buyer_profile.gst_number == "32AAAAA0000A1Z5"
    assert user.buyer_profile.business_type == BuyerProfile.BusinessType.EXPORTER
    assert user.buyer_profile.registration_certificate.name != ""

    # Verify session variables for OTP
    session = client.session
    assert session["otp_user_id"] == user.id
    assert session["otp_purpose"] == "registration"
    assert session["otp_code"] is not None

    # Simulate entering correct OTP
    verify_resp = client.post(reverse("account_verify_otp"), data={"otp": session["otp_code"]}, follow=True)
    assert verify_resp.status_code == 200
    user.refresh_from_db()
    assert user.is_verified is True


@pytest.mark.django_db
def test_seller_registration_creates_pending_user_and_triggers_otp(client):
    proof_file = SimpleUploadedFile("patta.pdf", b"%PDF-1.4 deed content", content_type="application/pdf")
    payload = {
        "name": "Devadasan K",
        "email": "devadasan@cardamomfarms.com",
        "phone_number": "9847012345",
        "password": "SellerSecurePassword123!",
        "confirm_password": "SellerSecurePassword123!",
        "farm_name": "Devagiri Estates",
        "district": SellerProfile.District.IDUKKI,
        "taluk": "Udumbanchola",
        "village": "Vandanmedu",
        "farm_area": 8.75,
        "area_unit": SellerProfile.AreaUnit.ACRE,
        "cardamom_plants": 3200,
        "cultivation_method": SellerProfile.CultivationMethod.ORGANIC,
        "ownership_proof": proof_file,
        "bank_account_holder": "Devadasan K",
        "bank_ifsc": "SBIN0070123",
        "bank_account_number": "67012345678",
    }

    response = client.post(reverse("register_seller"), data=payload, follow=False)
    assert response.status_code == 302
    assert response.url == reverse("account_verify_otp")

    user = User.objects.get(email="devadasan@cardamomfarms.com")
    assert user.role == User.Role.SELLER
    assert user.status == User.Status.PENDING
    assert user.seller_profile.farm_name == "Devagiri Estates"
    assert user.seller_profile.district == "IDUKKI"
    assert user.seller_profile.taluk == "Udumbanchola"
    assert user.seller_profile.village == "Vandanmedu"
    assert user.seller_profile.bank_account_number == "67012345678"
    assert user.seller_profile.bank_ifsc == "SBIN0070123"
    assert user.seller_profile.ownership_proof.name != ""

    # Verify session and complete OTP
    session = client.session
    assert session["otp_user_id"] == user.id
    assert session["otp_purpose"] == "registration"

    verify_resp = client.post(reverse("account_verify_otp"), data={"otp": session["otp_code"]}, follow=True)
    assert verify_resp.status_code == 200
    user.refresh_from_db()
    assert user.is_verified is True
