import pytest
from django.db import connection
from carda_link.users.models import User, SellerProfile


@pytest.mark.django_db
def test_encrypted_char_field_stores_ciphertext_and_reads_plaintext():
    user = User.objects.create_user(
        email="farmer@example.com",
        password="ValidPassword123!",
        role=User.Role.SELLER,
        status=User.Status.ACTIVE,
    )
    profile = SellerProfile.objects.create(
        user=user,
        farm_name="Highland Cardamom",
        district=SellerProfile.District.IDUKKI,
        taluk="Udumbanchola",
        village="Vandanmedu",
        farm_area=5.5,
        area_unit=SellerProfile.AreaUnit.ACRE,
        cardamom_plants=1200,
        cultivation_method=SellerProfile.CultivationMethod.ORGANIC,
        bank_account_holder="John Doe",
        bank_ifsc="SBIN0001234",
        bank_account_number="987654321012",
    )

    # Reload from DB
    profile.refresh_from_db()
    assert profile.bank_account_number == "987654321012"
    assert profile.bank_ifsc == "SBIN0001234"
    assert profile.district == "IDUKKI"

    # Query raw database column to verify it's stored as an encrypted Fernet token (not plaintext)
    with connection.cursor() as cursor:
        cursor.execute("SELECT bank_account_number FROM users_sellerprofile WHERE id = %s", [profile.id])
        raw_db_val = cursor.fetchone()[0]

    assert raw_db_val != "987654321012"
    assert raw_db_val.startswith("gAAAAA")  # Fernet tokens start with gAAAAA
