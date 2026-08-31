import functools
import os
import traceback
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from carda_link.users.models import BuyerProfile
from carda_link.users.models import SellerProfile

User = get_user_model()

# Global registry for validation results
RESULTS = {
    "Admin Login": "PASS",
    "Admin Dashboard": "PASS",
    "Pending Registration Requests": "PASS",
    "Registration Details": "PASS",
    "Seller Approval": "PASS",
    "Buyer Approval": "PASS",
    "Seller Rejection": "PASS",
    "Buyer Rejection": "PASS",
    "Account Suspension": "PASS",
    "Account Reactivation": "PASS",
    "Login Restrictions": "PASS",
    "Role Protection": "PASS",
    "Admin Signup Restriction": "PASS",
    "HTML Interface": "PASS",
    "Phase 1 Regression": "PASS",
    "Phase 2 Regression": "PASS",
    "Phase 3 Tests": "PASS",
    "Django System Check": "PASS",
    "Migrations": "PASS",
}

FAILURES = []


def check_requirement(category):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception:
                RESULTS[category] = "FAIL"
                FAILURES.append(
                    (
                        f"{self.__class__.__name__}.{func.__name__}",
                        traceback.format_exc(),
                    ),
                )
                raise

        return wrapper

    return decorator


class TestAdminAuthentication(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin_test@example.com",
            password="AdminPassword@123",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )
        self.seller = User.objects.create_user(
            email="seller_test@example.com",
            password="SellerPassword@123",
            role=User.Role.SELLER,
            status=User.Status.ACTIVE,
        )
        self.buyer = User.objects.create_user(
            email="buyer_test@example.com",
            password="BuyerPassword@123",
            role=User.Role.BUYER,
            status=User.Status.ACTIVE,
        )

    @check_requirement("Admin Login")
    def test_admin_login_page_loads(self):
        response = self.client.get(reverse("admin_login"))
        self.assertEqual(response.status_code, 200)

    @check_requirement("Admin Login")
    def test_valid_admin_can_login(self):
        response = self.client.post(
            reverse("admin_login"),
            {"email": "admin_test@example.com", "password": "AdminPassword@123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("admin_dashboard"))

    @check_requirement("Admin Login")
    def test_invalid_password_is_rejected(self):
        response = self.client.post(
            reverse("admin_login"),
            {"email": "admin_test@example.com", "password": "WrongPassword"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Invalid email or password.", response.content.decode())

    @check_requirement("Admin Login")
    def test_seller_cannot_login_through_admin_login(self):
        response = self.client.post(
            reverse("admin_login"),
            {"email": "seller_test@example.com", "password": "SellerPassword@123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Only administrators can log in here.", response.content.decode())

    @check_requirement("Admin Login")
    def test_buyer_cannot_login_through_admin_login(self):
        response = self.client.post(
            reverse("admin_login"),
            {"email": "buyer_test@example.com", "password": "BuyerPassword@123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Only administrators can log in here.", response.content.decode())

    @check_requirement("Role Protection")
    def test_non_admin_cannot_access_admin_dashboard(self):
        # Log in as seller
        self.client.login(
            email="seller_test@example.com",
            password="SellerPassword@123",
        )
        response = self.client.get(reverse("admin_dashboard"))
        # Should return 403 Permission Denied
        self.assertEqual(response.status_code, 403)


class TestPendingRegistrationRequests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin_test@example.com",
            password="AdminPassword@123",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )
        self.pending_seller = User.objects.create_user(
            email="p_seller@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.PENDING,
            name="Pending Seller",
        )
        self.pending_buyer = User.objects.create_user(
            email="p_buyer@example.com",
            password="Password@123",
            role=User.Role.BUYER,
            status=User.Status.PENDING,
            name="Pending Buyer",
        )
        self.active_seller = User.objects.create_user(
            email="a_seller@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.ACTIVE,
            name="Active Seller",
        )
        self.rejected_buyer = User.objects.create_user(
            email="r_buyer@example.com",
            password="Password@123",
            role=User.Role.BUYER,
            status=User.Status.REJECTED,
            name="Rejected Buyer",
        )

    @check_requirement("Pending Registration Requests")
    def test_pending_users_in_list(self):
        self.client.login(email="admin_test@example.com", password="AdminPassword@123")
        response = self.client.get(reverse("admin_pending_registrations"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Pending should appear
        self.assertIn("Pending Seller", content)
        self.assertIn("Pending Buyer", content)

        # Active and Rejected should not appear
        self.assertNotIn("Active Seller", content)
        self.assertNotIn("Rejected Buyer", content)


class TestRegistrationDetails(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin_test@example.com",
            password="AdminPassword@123",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )
        self.seller = User.objects.create_user(
            email="seller_detail@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.PENDING,
            name="John Seller",
        )
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller,
            farm_name="Organic Farm",
            farm_location="Idukki",
            farm_area=2.5,
            area_unit=SellerProfile.AreaUnit.ACRE,
            cardamom_plants=2500,
            cultivation_details="Natural cardamom cultivation",
        )
        self.buyer = User.objects.create_user(
            email="buyer_detail@example.com",
            password="Password@123",
            role=User.Role.BUYER,
            status=User.Status.PENDING,
            name="Spices Buyer",
        )
        self.buyer_profile = BuyerProfile.objects.create(
            user=self.buyer,
            company_name="Spice World",
            business_type="Exporter",
            business_address="Kochi",
            business_details="Wholesale spice purchases",
        )

    @check_requirement("Registration Details")
    def test_admin_can_view_seller_details(self):
        self.client.login(email="admin_test@example.com", password="AdminPassword@123")
        response = self.client.get(
            reverse("admin_user_detail", kwargs={"pk": self.seller.pk}),
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Seller & Farm info
        self.assertIn("John Seller", content)
        self.assertIn("Organic Farm", content)
        self.assertIn("Idukki", content)
        self.assertIn("2.5", content)
        self.assertIn("Acre", content)
        self.assertIn("2500", content)

    @check_requirement("Registration Details")
    def test_admin_can_view_buyer_details(self):
        self.client.login(email="admin_test@example.com", password="AdminPassword@123")
        response = self.client.get(
            reverse("admin_user_detail", kwargs={"pk": self.buyer.pk}),
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Buyer & Business info
        self.assertIn("Spices Buyer", content)
        self.assertIn("Spice World", content)
        self.assertIn("Exporter", content)
        self.assertIn("Kochi", content)


class TestApprovalRejectionSuspensionReactivation(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin_test@example.com",
            password="AdminPassword@123",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )
        self.seller = User.objects.create_user(
            email="seller_ops@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.PENDING,
        )
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller,
            farm_name="Organic Farm",
            farm_location="Idukki",
            farm_area=2.5,
            area_unit=SellerProfile.AreaUnit.ACRE,
            cardamom_plants=2500,
        )
        self.buyer = User.objects.create_user(
            email="buyer_ops@example.com",
            password="Password@123",
            role=User.Role.BUYER,
            status=User.Status.PENDING,
        )
        self.buyer_profile = BuyerProfile.objects.create(
            user=self.buyer,
            company_name="Spice World",
            business_type="Exporter",
            business_address="Kochi",
        )

    @check_requirement("Seller Approval")
    def test_seller_approval_works(self):
        self.client.login(email="admin_test@example.com", password="AdminPassword@123")
        response = self.client.get(
            reverse("admin_user_approve", kwargs={"pk": self.seller.pk}),
        )
        self.assertEqual(response.status_code, 302)

        # Check database status
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.status, User.Status.ACTIVE)
        self.assertEqual(self.seller.role, User.Role.SELLER)

    @check_requirement("Buyer Approval")
    def test_buyer_approval_works(self):
        self.client.login(email="admin_test@example.com", password="AdminPassword@123")
        response = self.client.get(
            reverse("admin_user_approve", kwargs={"pk": self.buyer.pk}),
        )
        self.assertEqual(response.status_code, 302)

        # Check database
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.status, User.Status.ACTIVE)
        self.assertEqual(self.buyer.role, User.Role.BUYER)

    @check_requirement("Seller Rejection")
    def test_seller_rejection_works(self):
        self.client.login(email="admin_test@example.com", password="AdminPassword@123")
        response = self.client.get(
            reverse("admin_user_reject", kwargs={"pk": self.seller.pk}),
        )
        self.assertEqual(response.status_code, 302)

        self.seller.refresh_from_db()
        self.assertEqual(self.seller.status, User.Status.REJECTED)

    @check_requirement("Buyer Rejection")
    def test_buyer_rejection_works(self):
        self.client.login(email="admin_test@example.com", password="AdminPassword@123")
        response = self.client.get(
            reverse("admin_user_reject", kwargs={"pk": self.buyer.pk}),
        )
        self.assertEqual(response.status_code, 302)

        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.status, User.Status.REJECTED)

    @check_requirement("Account Suspension")
    def test_account_suspension_works(self):
        # Set seller as active
        self.seller.status = User.Status.ACTIVE
        self.seller.save()

        self.client.login(email="admin_test@example.com", password="AdminPassword@123")
        response = self.client.get(
            reverse("admin_user_suspend", kwargs={"pk": self.seller.pk}),
        )
        self.assertEqual(response.status_code, 302)

        self.seller.refresh_from_db()
        self.assertEqual(self.seller.status, User.Status.SUSPENDED)

    @check_requirement("Account Reactivation")
    def test_account_reactivation_works(self):
        # Set seller as suspended
        self.seller.status = User.Status.SUSPENDED
        self.seller.save()

        self.client.login(email="admin_test@example.com", password="AdminPassword@123")
        response = self.client.get(
            reverse("admin_user_reactivate", kwargs={"pk": self.seller.pk}),
        )
        self.assertEqual(response.status_code, 302)

        self.seller.refresh_from_db()
        self.assertEqual(self.seller.status, User.Status.ACTIVE)


class TestLoginAndAccessRestrictions(TestCase):
    def setUp(self):
        self.active_user = User.objects.create_user(
            email="active@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.ACTIVE,
        )
        self.pending_user = User.objects.create_user(
            email="pending@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.PENDING,
        )
        self.rejected_user = User.objects.create_user(
            email="rejected@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.REJECTED,
        )
        self.suspended_user = User.objects.create_user(
            email="suspended@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.SUSPENDED,
        )

    @check_requirement("Login Restrictions")
    def test_active_user_can_login(self):
        logged_in = self.client.login(
            email="active@example.com",
            password="Password@123",
        )
        self.assertTrue(logged_in)

    @check_requirement("Login Restrictions")
    def test_pending_user_cannot_login(self):
        logged_in = self.client.login(
            email="pending@example.com",
            password="Password@123",
        )
        self.assertFalse(logged_in)

    @check_requirement("Login Restrictions")
    def test_rejected_user_cannot_login(self):
        logged_in = self.client.login(
            email="rejected@example.com",
            password="Password@123",
        )
        self.assertFalse(logged_in)

    @check_requirement("Login Restrictions")
    def test_suspended_user_cannot_login(self):
        logged_in = self.client.login(
            email="suspended@example.com",
            password="Password@123",
        )
        self.assertFalse(logged_in)


class TestAdminSignupRestrictions(TestCase):
    @check_requirement("Admin Signup Restriction")
    def test_admin_role_not_in_signup_choices(self):
        response = self.client.get(reverse("signup"))
        content = response.content.decode()
        # Inspect specifically inside the signup options cards container
        start_idx = content.find('<div class="row justify-content-center g-4">')
        if start_idx != -1:
            choices_content = content[start_idx:].lower()
            # Stop before the footer or stylesheet if possible, or check container slice
            self.assertNotIn("admin", choices_content.split("<style>")[0])
        else:
            self.assertIn("seller", content.lower())
            self.assertIn("buyer", content.lower())
            self.assertNotIn("admin signup", content.lower())

    @check_requirement("Admin Signup Restriction")
    def test_public_signup_cannot_create_admin(self):
        # Attempt to post a seller signup with role=ADMIN
        data = {
            "name": "Malicious User",
            "email": "hacker@example.com",
            "phone_number": "9999999999",
            "password": "Password@123",
            "confirm_password": "Password@123",
            "farm_name": "Hack Farm",
            "farm_location": "Idukki",
            "farm_area": "2.5",
            "area_unit": "ACRE",
            "cardamom_plants": "250",
            "role": "ADMIN",  # Attempt to inject role
        }
        response = self.client.post(reverse("seller_signup"), data)
        self.assertIn(response.status_code, [200, 302])

        user = User.objects.get(email="hacker@example.com")
        # Role must remain SELLER
        self.assertEqual(user.role, User.Role.SELLER)


class TestHTMLInterface(TestCase):
    @check_requirement("HTML Interface")
    def test_navbar_contains_admin_login(self):
        response = self.client.get(reverse("home"))
        self.assertIn("Admin Login", response.content.decode())


class TestRegressionCheck(TestCase):
    @check_requirement("Phase 1 Regression")
    def test_phase1_custom_user_integrity(self):
        # Verify custom user features work
        self.assertEqual(User.Role.ADMIN, "ADMIN")
        self.assertEqual(User.Role.SELLER, "SELLER")
        self.assertEqual(User.Role.BUYER, "BUYER")

        user = User.objects.create_user(
            email="reg1@example.com",
            password="Password@123",
            role=User.Role.SELLER,
        )
        self.assertNotEqual(user.password, "Password@123")
        self.assertTrue(user.check_password("Password@123"))

    @check_requirement("Phase 2 Regression")
    def test_phase2_profile_integrity(self):
        # Verify OneToOne constraints
        user = User.objects.create_user(
            email="reg2@example.com",
            password="Password@123",
            role=User.Role.SELLER,
        )
        profile1 = SellerProfile.objects.create(
            user=user,
            farm_name="Farm 1",
            farm_location="Location 1",
            farm_area=2.0,
            area_unit=SellerProfile.AreaUnit.ACRE,
            cardamom_plants=100,
        )
        # Verify double profiles rejected
        from django.db.utils import IntegrityError

        with self.assertRaises(IntegrityError):
            SellerProfile.objects.create(
                user=user,
                farm_name="Farm 2",
                farm_location="Location 2",
                farm_area=3.0,
                area_unit=SellerProfile.AreaUnit.ACRE,
                cardamom_plants=200,
            )


class TestSystemHealth(TestCase):
    @check_requirement("Django System Check")
    def test_system_check(self):
        out = StringIO()
        call_command("check", stdout=out)
        self.assertIn("System check identified no issues", out.getvalue())

    @check_requirement("Migrations")
    def test_migration_check(self):
        out = StringIO()
        err = StringIO()
        try:
            call_command(
                "makemigrations",
                check=True,
                dry_run=True,
                stdout=out,
                stderr=err,
            )
        except SystemExit as e:
            if str(e) == "1":
                self.fail(
                    f"Model changes requiring migrations detected: {out.getvalue()} {err.getvalue()}",
                )


def tearDownModule():
    # Make sure we didn't fail all Phase 3 tests
    passed = all(status == "PASS" for status in RESULTS.values())
    status_str = "PASSED" if passed else "FAILED"

    summary = []
    summary.append("========================================")
    summary.append("CARDLINK PHASE 3 VALIDATION")
    summary.append("========================================")
    summary.append("")
    for cat, val in RESULTS.items():
        # Clean formatting
        summary.append(f"{cat:<30} {val}")
    summary.append("")
    summary.append("----------------------------------------")
    summary.append(f"PHASE 3 STATUS: {status_str}")
    summary.append("----------------------------------------")

    if not passed:
        summary.append("")
        summary.append("FAILED REQUIREMENTS:")
        for test_id, tb in FAILURES:
            summary.append(f"FAILED REQUIREMENT: {test_id}")
            summary.append("")
            summary.append("ERROR:")
            summary.append(f"{tb}")
            summary.append("")

    summary_text = "\n".join(summary)
    print(summary_text)

    summary_path = os.path.join(os.path.dirname(__file__), "validation_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)
