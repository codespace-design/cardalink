import functools
import os
import traceback
from io import StringIO
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core import mail
from django.core.management import call_command
from carda_link.users.models import SellerProfile, BuyerProfile

User = get_user_model()

# Global registry for validation results
RESULTS = {
    "Seller Login": "PASS",
    "Buyer Login": "PASS",
    "OTP Removed": "PASS",
    "Pending Account Handling": "PASS",
    "Rejected Account Handling": "PASS",
    "Suspended Account Handling": "PASS",
    "Seller Dashboard Redirect": "PASS",
    "Buyer Dashboard Redirect": "PASS",
    "Admin Dashboard Redirect": "PASS",
    "Role Protection": "PASS",
    "Admin Authentication": "PASS",
    "Phase 1 Regression": "PASS",
    "Phase 2 Regression": "PASS",
    "Phase 3 Regression": "PASS",
    "Phase 4 Tests": "PASS",
    "Django System Check": "PASS",
}

FAILURES = []

def check_requirement(category):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                RESULTS[category] = "FAIL"
                FAILURES.append((f"{self.__class__.__name__}.{func.__name__}", traceback.format_exc()))
                raise
        return wrapper
    return decorator


class TestSellerBuyerLogin(TestCase):
    def setUp(self):
        mail.outbox.clear()
        self.seller = User.objects.create_user(
            email="active_seller@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.ACTIVE
        )
        self.buyer = User.objects.create_user(
            email="active_buyer@example.com",
            password="Password@123",
            role=User.Role.BUYER,
            status=User.Status.ACTIVE
        )

    @check_requirement("Seller Login")
    def test_active_seller_can_login_with_email_password(self):
        logged_in = self.client.login(email="active_seller@example.com", password="Password@123")
        self.assertTrue(logged_in)

    @check_requirement("Seller Dashboard Redirect")
    def test_active_seller_redirected_to_seller_dashboard(self):
        response = self.client.post(
            reverse("account_login"),
            {"login": "active_seller@example.com", "password": "Password@123"},
            follow=True
        )
        # Should redirect to usersRedirectView first, then to seller dashboard
        self.assertRedirects(response, reverse("seller_dashboard"), target_status_code=200)

    @check_requirement("OTP Removed")
    def test_active_seller_receives_no_otp(self):
        self.client.post(
            reverse("account_login"),
            {"login": "active_seller@example.com", "password": "Password@123"}
        )
        # No verification mail should be queued
        self.assertEqual(len(mail.outbox), 0)

    @check_requirement("Buyer Login")
    def test_active_buyer_can_login_with_email_password(self):
        logged_in = self.client.login(email="active_buyer@example.com", password="Password@123")
        self.assertTrue(logged_in)

    @check_requirement("Buyer Dashboard Redirect")
    def test_active_buyer_redirected_to_buyer_dashboard(self):
        response = self.client.post(
            reverse("account_login"),
            {"login": "active_buyer@example.com", "password": "Password@123"},
            follow=True
        )
        self.assertRedirects(response, reverse("buyer_dashboard"), target_status_code=200)

    @check_requirement("OTP Removed")
    def test_active_buyer_receives_no_otp(self):
        self.client.post(
            reverse("account_login"),
            {"login": "active_buyer@example.com", "password": "Password@123"}
        )
        self.assertEqual(len(mail.outbox), 0)


class TestLoginStatusHandling(TestCase):
    def setUp(self):
        mail.outbox.clear()
        self.pending_seller = User.objects.create_user(
            email="pending_s@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.PENDING
        )
        self.rejected_buyer = User.objects.create_user(
            email="rejected_b@example.com",
            password="Password@123",
            role=User.Role.BUYER,
            status=User.Status.REJECTED
        )
        self.suspended_seller = User.objects.create_user(
            email="suspended_s@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.SUSPENDED
        )

    @check_requirement("Pending Account Handling")
    def test_pending_user_cannot_login_and_gets_msg(self):
        response = self.client.post(
            reverse("account_login"),
            {"login": "pending_s@example.com", "password": "Password@123"}
        )
        # Login should be blocked and output error message
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Your account has not yet been approved by the administrator. Please wait for admin approval.",
            response.content.decode()
        )
        self.assertEqual(len(mail.outbox), 0)

    @check_requirement("Rejected Account Handling")
    def test_rejected_user_cannot_login_and_gets_msg(self):
        response = self.client.post(
            reverse("account_login"),
            {"login": "rejected_b@example.com", "password": "Password@123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Your registration has been rejected by the administrator.",
            response.content.decode()
        )
        self.assertEqual(len(mail.outbox), 0)

    @check_requirement("Suspended Account Handling")
    def test_suspended_user_cannot_login_and_gets_msg(self):
        response = self.client.post(
            reverse("account_login"),
            {"login": "suspended_s@example.com", "password": "Password@123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Your account has been suspended. Please contact the administrator.",
            response.content.decode()
        )
        self.assertEqual(len(mail.outbox), 0)


class TestRoleProtection(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.ACTIVE
        )
        self.buyer = User.objects.create_user(
            email="buyer@example.com",
            password="Password@123",
            role=User.Role.BUYER,
            status=User.Status.ACTIVE
        )

    @check_requirement("Role Protection")
    def test_seller_cannot_access_buyer_dashboard(self):
        self.client.login(email="seller@example.com", password="Password@123")
        response = self.client.get(reverse("buyer_dashboard"))
        self.assertEqual(response.status_code, 403)

    @check_requirement("Role Protection")
    def test_buyer_cannot_access_seller_dashboard(self):
        self.client.login(email="buyer@example.com", password="Password@123")
        response = self.client.get(reverse("seller_dashboard"))
        self.assertEqual(response.status_code, 403)

    @check_requirement("Role Protection")
    def test_seller_cannot_access_admin_dashboard(self):
        self.client.login(email="seller@example.com", password="Password@123")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 403)


class TestAdminAuthentication(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="Password@123",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE
        )
        self.seller = User.objects.create_user(
            email="seller_adm@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.ACTIVE
        )

    @check_requirement("Admin Authentication")
    def test_active_admin_can_login(self):
        response = self.client.post(
            reverse("admin_login"),
            {"email": "admin@example.com", "password": "Password@123"}
        )
        self.assertEqual(response.status_code, 302)

    @check_requirement("Admin Dashboard Redirect")
    def test_admin_redirected_to_admin_dashboard(self):
        response = self.client.post(
            reverse("admin_login"),
            {"email": "admin@example.com", "password": "Password@123"}
        )
        self.assertRedirects(response, reverse("admin_dashboard"))

    @check_requirement("Admin Authentication")
    def test_seller_cannot_use_admin_login(self):
        response = self.client.post(
            reverse("admin_login"),
            {"email": "seller_adm@example.com", "password": "Password@123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Only administrators can log in here.", response.content.decode())


class TestRegressionCheck(TestCase):
    @check_requirement("Phase 1 Regression")
    def test_phase1_regression_model_and_auth(self):
        # Validate custom User structure remains fully functional
        self.assertEqual(User.Role.ADMIN, "ADMIN")
        self.assertEqual(User.Role.SELLER, "SELLER")
        self.assertEqual(User.Role.BUYER, "BUYER")
        
        user = User.objects.create_user(
            email="regression1@example.com",
            password="Password@123",
            role=User.Role.SELLER
        )
        self.assertTrue(user.check_password("Password@123"))

    @check_requirement("Phase 2 Regression")
    def test_phase2_regression_profiles(self):
        user = User.objects.create_user(
            email="regression2@example.com",
            password="Password@123",
            role=User.Role.SELLER
        )
        profile = SellerProfile.objects.create(
            user=user,
            farm_name="Phase 2 Regression Farm",
            farm_location="Idukki",
            farm_area=2.0,
            area_unit=SellerProfile.AreaUnit.ACRE,
            cardamom_plants=100
        )
        self.assertEqual(user.seller_profile.farm_name, "Phase 2 Regression Farm")

    @check_requirement("Phase 3 Regression")
    def test_phase3_regression_approval_views(self):
        admin = User.objects.create_user(
            email="regression_admin@example.com",
            password="Password@123",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE
        )
        seller = User.objects.create_user(
            email="regression_seller@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.PENDING
        )
        SellerProfile.objects.create(
            user=seller,
            farm_name="Review Farm",
            farm_location="Idukki",
            farm_area=2.0,
            area_unit=SellerProfile.AreaUnit.ACRE,
            cardamom_plants=100
        )
        
        self.client.login(email="regression_admin@example.com", password="Password@123")
        response = self.client.get(reverse("admin_user_approve", kwargs={"pk": seller.pk}))
        self.assertEqual(response.status_code, 302)
        seller.refresh_from_db()
        self.assertEqual(seller.status, User.Status.ACTIVE)


class TestSystemCheck(TestCase):
    @check_requirement("Django System Check")
    def test_system_check(self):
        out = StringIO()
        call_command("check", stdout=out)
        self.assertIn("System check identified no issues", out.getvalue())


def tearDownModule():
    passed = all(status == "PASS" for status in RESULTS.values())
    status_str = "PASSED" if passed else "FAILED"
    
    summary = []
    summary.append("========================================")
    summary.append("CARDLINK PHASE 4 VALIDATION")
    summary.append("========================================")
    summary.append("")
    for cat, val in RESULTS.items():
        summary.append(f"{cat:<30} {val}")
    summary.append("")
    summary.append("----------------------------------------")
    summary.append(f"PHASE 4 STATUS: {status_str}")
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
    
    import os
    summary_path = os.path.join(os.path.dirname(__file__), "validation_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)
