import pytest
from django.urls import reverse
from carda_link.users.models import User


@pytest.mark.django_db
def test_forgot_password_flow_with_phone_number(client):
    # 1. Create an active user with a phone number and old password
    user = User.objects.create_user(
        email="testfarmer@cardalink.com",
        phone_number="9447631324",
        password="OldSecurePassword123!",
        role=User.Role.SELLER,
        status=User.Status.ACTIVE,
    )
    assert user.check_password("OldSecurePassword123!")

    # 2. User clicks Forgot Password and submits registered phone number
    resp = client.post(
        reverse("account_reset_password"),
        data={"phone_number": "9447631324"},
        follow=False,
    )
    assert resp.status_code == 302
    assert resp.url == reverse("account_verify_otp")

    # Verify session variables
    session = client.session
    assert session["otp_user_id"] == user.id
    assert session["otp_purpose"] == "password_reset"
    otp_code = session["otp_code"]
    assert otp_code is not None

    # 3. User enters the 6-digit OTP
    verify_resp = client.post(
        reverse("account_verify_otp"),
        data={"otp": otp_code},
        follow=False,
    )
    # Must redirect to the set new password page (NOT signup)
    assert verify_resp.status_code == 302
    assert verify_resp.url == reverse("account_reset_password_set")

    # 4. User loads the set new password page
    set_page_resp = client.get(reverse("account_reset_password_set"))
    assert set_page_resp.status_code == 200
    assert "Set New Password" in set_page_resp.content.decode("utf-8")

    # 5. User submits new password and confirmation
    new_pass = "FreshNewPassword456!"
    save_resp = client.post(
        reverse("account_reset_password_set"),
        data={"password1": new_pass, "password2": new_pass},
        follow=False,
    )
    assert save_resp.status_code == 302
    assert save_resp.url == reverse("home")

    # 6. Verify user's password was updated in the database
    user.refresh_from_db()
    assert user.check_password(new_pass) is True
    assert user.check_password("OldSecurePassword123!") is False

    # 7. Verify session was cleaned up
    session = client.session
    assert "otp_user_id" not in session
    assert "otp_code" not in session
    assert "otp_verified" not in session
    assert "otp_purpose" not in session


@pytest.mark.django_db
def test_set_password_mismatch_shows_error(client):
    user = User.objects.create_user(
        email="buyer@cardalink.com",
        phone_number="9876543210",
        password="OriginalPassword123!",
        role=User.Role.BUYER,
        status=User.Status.ACTIVE,
    )
    # Setup session as verified
    session = client.session
    session["otp_user_id"] = user.id
    session["otp_verified"] = True
    session["otp_purpose"] = "password_reset"
    session.save()

    resp = client.post(
        reverse("account_reset_password_set"),
        data={"password1": "PasswordOne123!", "password2": "PasswordMismatch999!"},
    )
    assert resp.status_code == 200
    assert "Passwords do not match" in resp.content.decode("utf-8")
