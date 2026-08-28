import functools
import os
import traceback
from io import StringIO
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()

# Global registry for validation results
RESULTS = {
    "User Model": "PASS",
    "Roles": "PASS",
    "Account Statuses": "PASS",
    "Password Security": "PASS",
    "Seller Signup": "PASS",
    "Buyer Signup": "PASS",
    "Validation": "PASS",
    "Admin Signup Restriction": "PASS",
    "HTML Interface": "PASS",
    "Database/Migrations": "PASS",
}

FAILURES = []

def check_requirement(category):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                if category == "DynamicRolesAndStatuses":
                    if "role" in func.__name__.lower():
                        RESULTS["Roles"] = "FAIL"
                    if "status" in func.__name__.lower():
                        RESULTS["Account Statuses"] = "FAIL"
                else:
                    RESULTS[category] = "FAIL"
                FAILURES.append((f"{self.__class__.__name__}.{func.__name__}", traceback.format_exc()))
                raise
        return wrapper
    return decorator


class TestUserModel(TestCase):
    @check_requirement("User Model")
    def test_custom_user_model_exists(self):
        self.assertIsNotNone(User, "User model is None.")
        # Ensure it is not Django's default auth.User
        from django.contrib.auth.models import User as DefaultUser
        self.assertNotEqual(
            User,
            DefaultUser,
            "Custom User model is not configured. Configured model is Django's default auth.User."
        )

    @check_requirement("User Model")
    def test_auth_user_model_configured_correctly(self):
        from django.conf import settings
        self.assertEqual(
            settings.AUTH_USER_MODEL,
            "users.User",
            "AUTH_USER_MODEL is not configured to users.User"
        )

    @check_requirement("User Model")
    def test_user_model_has_required_fields(self):
        fields = [f.name for f in User._meta.get_fields()]
        
        required_fields = {
            "name": "name",
            "email": "email",
            "role": "role",
            "status": "status",
            "created_at": "created_at",
            "updated_at": "updated_at"
        }
        
        for name, field in required_fields.items():
            self.assertIn(field, fields, f"User model is missing required field: {name}")
            
        self.assertTrue(
            "phone" in fields or "phone_number" in fields,
            "User model is missing required field: phone"
        )

    @check_requirement("User Model")
    def test_email_is_unique(self):
        email_field = User._meta.get_field("email")
        self.assertTrue(email_field.unique, "Email is not configured as unique in the User model.")


class TestRolesAndStatuses(TestCase):
    @check_requirement("DynamicRolesAndStatuses")
    def test_roles_exist(self):
        self.assertTrue(hasattr(User, "Role"), "User model does not have a Role inner class/choices.")
        
        roles = ["ADMIN", "SELLER", "BUYER"]
        for r in roles:
            self.assertTrue(hasattr(User.Role, r), f"{r} role is missing from the User.Role choices.")
            
        role_field = User._meta.get_field("role")
        choices = [c[0] for c in role_field.choices]
        for r in roles:
            self.assertIn(r, choices, f"{r} role is missing from the User model's role field choices.")

    @check_requirement("DynamicRolesAndStatuses")
    def test_statuses_exist(self):
        self.assertTrue(hasattr(User, "Status"), "User model does not have a Status inner class/choices.")
        
        statuses = ["PENDING", "ACTIVE", "REJECTED", "SUSPENDED"]
        for s in statuses:
            self.assertTrue(hasattr(User.Status, s), f"{s} status is missing from the User.Status choices.")
            
        status_field = User._meta.get_field("status")
        choices = [c[0] for c in status_field.choices]
        for s in statuses:
            self.assertIn(s, choices, f"{s} status is missing from the User model's status field choices.")


class TestPasswordSecurity(TestCase):
    @check_requirement("Password Security")
    def test_password_is_securely_hashed(self):
        user = User.objects.create_user(
            email="temp_pwd_test@example.com",
            password="PlainPassword",
            role=User.Role.BUYER
        )
        self.assertNotEqual(user.password, "PlainPassword", "Passwords are stored as plain text.")
        self.assertTrue(user.check_password("PlainPassword"), "check_password failed for secure password.")


class TestSellerSignup(TestCase):
    @check_requirement("Seller Signup")
    def test_seller_signup_page_works(self):
        from django.urls import reverse
        try:
            url = reverse("seller_signup")
        except Exception:
            url = "/signup/seller/"
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, "Seller signup page returned non-200 status code.")

    @check_requirement("Seller Signup")
    def test_seller_fields_exist(self):
        from django.urls import reverse
        try:
            url = reverse("seller_signup")
        except Exception:
            url = "/signup/seller/"
            
        response = self.client.get(url)
        content = response.content.decode()
        
        required_fields = [
            "name",
            "email",
            "password",
            "confirm_password",
            "farm_name",
            "farm_location",
            "farm_area",
            "area_unit",
            "cardamom_plants"
        ]
        
        for f in required_fields:
            if f == "confirm_password":
                self.assertTrue(
                    'name="confirm_password"' in content or 'name="confirm-password"' in content,
                    "Seller signup page is missing confirm_password field."
                )
            else:
                self.assertTrue(
                    f'name="{f}"' in content or (f == "phone" and 'name="phone_number"' in content),
                    f"Seller signup page is missing {f} field."
                )

    @check_requirement("Seller Signup")
    def test_seller_registration_works(self):
        from django.urls import reverse
        try:
            url = reverse("seller_signup")
        except Exception:
            url = "/signup/seller/"
            
        data = {
            "name": "Phase 1 Test Seller",
            "email": "phase1seller_test@example.com",
            "phone_number": "9999999999",
            "password": "TestPassword@123",
            "confirm_password": "TestPassword@123",
            "farm_name": "Phase 1 Test Farm",
            "farm_location": "Idukki",
            "farm_area": "2.5",
            "area_unit": "ACRE",
            "cardamom_plants": "2500"
        }
        
        response = self.client.post(url, data)
        self.assertIn(response.status_code, [200, 302], "Seller registration post failed.")
        
        user_exists = User.objects.filter(email="phase1seller_test@example.com").exists()
        self.assertTrue(user_exists, "Seller registration did not create user record.")
        
        user = User.objects.get(email="phase1seller_test@example.com")
        self.assertEqual(user.role, User.Role.SELLER, "Seller registration did not assign SELLER role.")
        self.assertEqual(user.status, User.Status.PENDING, "Seller registration did not assign PENDING status.")


class TestBuyerSignup(TestCase):
    @check_requirement("Buyer Signup")
    def test_buyer_signup_page_works(self):
        from django.urls import reverse
        try:
            url = reverse("buyer_signup")
        except Exception:
            url = "/signup/buyer/"
            
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, "Buyer signup page returned non-200 status code.")

    @check_requirement("Buyer Signup")
    def test_buyer_fields_exist(self):
        from django.urls import reverse
        try:
            url = reverse("buyer_signup")
        except Exception:
            url = "/signup/buyer/"
            
        response = self.client.get(url)
        content = response.content.decode()
        
        required_fields = [
            "name",
            "email",
            "password",
            "confirm_password",
            "business_name",
            "business_type",
            "business_address"
        ]
        
        for f in required_fields:
            if f == "confirm_password":
                self.assertTrue(
                    'name="confirm_password"' in content or 'name="confirm-password"' in content,
                    "Buyer signup page is missing confirm_password field."
                )
            else:
                self.assertTrue(
                    f'name="{f}"' in content or (f == "phone" and 'name="phone_number"' in content),
                    f"Buyer signup page is missing {f} field."
                )

    @check_requirement("Buyer Signup")
    def test_buyer_registration_works(self):
        from django.urls import reverse
        try:
            url = reverse("buyer_signup")
        except Exception:
            url = "/signup/buyer/"
            
        data = {
            "name": "Phase 1 Test Buyer",
            "email": "phase1buyer_test@example.com",
            "phone_number": "8888888888",
            "password": "TestPassword@123",
            "confirm_password": "TestPassword@123",
            "business_name": "Phase 1 Test Company",
            "business_type": "Cardamom Exporter",
            "business_address": "Kerala"
        }
        
        response = self.client.post(url, data)
        self.assertIn(response.status_code, [200, 302], "Buyer registration post failed.")
        
        user_exists = User.objects.filter(email="phase1buyer_test@example.com").exists()
        self.assertTrue(user_exists, "Buyer registration did not create user record.")
        
        user = User.objects.get(email="phase1buyer_test@example.com")
        self.assertEqual(user.role, User.Role.BUYER, "Buyer registration did not assign BUYER role.")
        self.assertEqual(user.status, User.Status.PENDING, "Buyer registration did not assign PENDING status.")


class TestSignupValidation(TestCase):
    @check_requirement("Validation")
    def test_empty_required_fields_rejected(self):
        from django.urls import reverse
        try:
            url = reverse("seller_signup")
        except Exception:
            url = "/signup/seller/"
            
        data = {
            "name": "",
            "email": "",
            "phone_number": "9999999999",
            "password": "TestPassword@123",
            "confirm_password": "TestPassword@123",
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(phone_number="9999999999").count(), 0, "User created with missing required fields.")

    @check_requirement("Validation")
    def test_invalid_email_rejected(self):
        from django.urls import reverse
        try:
            url = reverse("seller_signup")
        except Exception:
            url = "/signup/seller/"
            
        data = {
            "name": "Test User",
            "email": "not-an-email",
            "phone_number": "9999999999",
            "password": "TestPassword@123",
            "confirm_password": "TestPassword@123",
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="not-an-email").exists(), "User created with invalid email.")

    @check_requirement("Validation")
    def test_duplicate_email_rejected(self):
        from django.urls import reverse
        User.objects.create_user(
            email="existing_test@example.com",
            password="Password@123",
            role=User.Role.SELLER
        )
        
        try:
            url = reverse("seller_signup")
        except Exception:
            url = "/signup/seller/"
            
        data = {
            "name": "Duplicate User",
            "email": "existing_test@example.com",
            "phone_number": "9999999999",
            "password": "TestPassword@123",
            "confirm_password": "TestPassword@123",
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)

    @check_requirement("Validation")
    def test_password_mismatch_rejected(self):
        from django.urls import reverse
        try:
            url = reverse("seller_signup")
        except Exception:
            url = "/signup/seller/"
            
        data = {
            "name": "Password User",
            "email": "pwd_mismatch@example.com",
            "phone_number": "9999999999",
            "password": "TestPassword@123",
            "confirm_password": "DifferentPassword@123",
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="pwd_mismatch@example.com").exists(), "User created with password mismatch.")

    @check_requirement("Validation")
    def test_invalid_farm_area_rejected(self):
        from django.urls import reverse
        try:
            url = reverse("seller_signup")
        except Exception:
            url = "/signup/seller/"
            
        data = {
            "name": "Farm User",
            "email": "farm_area_err@example.com",
            "phone_number": "9999999999",
            "password": "TestPassword@123",
            "confirm_password": "TestPassword@123",
            "farm_area": "abc",
            "area_unit": "ACRE"
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="farm_area_err@example.com").exists(), "User created with invalid farm area.")
        
        data["farm_area"] = "-2.5"
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="farm_area_err@example.com").exists(), "User created with negative farm area.")

    @check_requirement("Validation")
    def test_negative_plant_count_rejected(self):
        from django.urls import reverse
        try:
            url = reverse("seller_signup")
        except Exception:
            url = "/signup/seller/"
            
        data = {
            "name": "Plant User",
            "email": "plant_err@example.com",
            "phone_number": "9999999999",
            "password": "TestPassword@123",
            "confirm_password": "TestPassword@123",
            "cardamom_plants": "-10",
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="plant_err@example.com").exists(), "User created with negative cardamom plants.")

    @check_requirement("Validation")
    def test_invalid_area_unit_rejected(self):
        from django.urls import reverse
        try:
            url = reverse("seller_signup")
        except Exception:
            url = "/signup/seller/"
            
        data = {
            "name": "Unit User",
            "email": "unit_err@example.com",
            "phone_number": "9999999999",
            "password": "TestPassword@123",
            "confirm_password": "TestPassword@123",
            "area_unit": "INVALID_UNIT",
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="unit_err@example.com").exists(), "User created with invalid area unit.")


class TestSignupRoleRestrictions(TestCase):
    @check_requirement("Admin Signup Restriction")
    def test_admin_signup_is_restricted(self):
        from django.urls import reverse
        try:
            signup_url = reverse("signup")
        except Exception:
            signup_url = "/signup/"
            
        response = self.client.get(signup_url)
        content = response.content.decode().lower()
        
        self.assertNotIn("signup/admin", content)
        self.assertNotIn("admin_signup", content)
        self.assertNotIn("admin-signup", content)
        
        try:
            seller_url = reverse("seller_signup")
        except Exception:
            seller_url = "/signup/seller/"
        try:
            buyer_url = reverse("buyer_signup")
        except Exception:
            buyer_url = "/signup/buyer/"
            
        for url in [seller_url, buyer_url]:
            res = self.client.get(url)
            self.assertNotIn('name="role"', res.content.decode(), "Form should not expose 'role' field.")


class TestPhase1Pages(TestCase):
    @check_requirement("HTML Interface")
    def test_home_page_works(self):
        from django.urls import reverse
        try:
            url = reverse("home")
        except Exception:
            url = "/"
            
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode().lower()
        self.assertTrue(
            "cardalink" in content or "carda_link" in content,
            "Home page does not contain 'Cardalink' title/text."
        )
        self.assertTrue(
            "direct cardamom trading" in content,
            "Home page does not contain 'Direct Cardamom Trading' tagline."
        )

    @check_requirement("HTML Interface")
    def test_signup_selection_page_works(self):
        from django.urls import reverse
        try:
            url = reverse("signup")
        except Exception:
            url = "/signup/"
            
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode().lower()
        self.assertTrue(
            "seller" in content,
            "Signup page does not offer Seller option."
        )
        self.assertTrue(
            "buyer" in content,
            "Signup page does not offer Buyer option."
        )

    @check_requirement("HTML Interface")
    def test_test_users_page_works(self):
        from django.urls import reverse
        
        s_user = User.objects.create_user(
            email="list_seller@example.com",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.PENDING,
            name="List Seller User"
        )
        b_user = User.objects.create_user(
            email="list_buyer@example.com",
            password="Password@123",
            role=User.Role.BUYER,
            status=User.Status.ACTIVE,
            name="List Buyer User"
        )
        
        try:
            url = reverse("admin_users")
        except Exception:
            url = "/test-users/"
            
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        
        self.assertIn("List Seller User", content)
        self.assertIn("List Buyer User", content)
        self.assertIn("SELLER", content)
        self.assertIn("BUYER", content)
        self.assertIn("PENDING", content)
        self.assertIn("ACTIVE", content)


class TestDatabaseMigrations(TestCase):
    @check_requirement("Database/Migrations")
    def test_no_missing_migrations(self):
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        err = StringIO()
        try:
            call_command("makemigrations", check=True, dry_run=True, stdout=out, stderr=err)
        except SystemExit as e:
            if str(e) == "1":
                self.fail(f"There are model changes requiring migrations. Run 'makemigrations'. Out: {out.getvalue()} Err: {err.getvalue()}")
            else:
                self.fail(f"makemigrations check exited with system exit: {e}. Out: {out.getvalue()} Err: {err.getvalue()}")
        except Exception as e:
            self.fail(f"makemigrations check failed: {e}")


def tearDownModule():
    passed = all(status == "PASS" for status in RESULTS.values())
    status_str = "PASSED" if passed else "FAILED"
    
    summary = []
    summary.append("==================================================")
    summary.append("CARDLINK PHASE 1 VALIDATION")
    summary.append("==================================================")
    summary.append("")
    for cat, val in RESULTS.items():
        summary.append(f"{cat:<24} {val}")
    summary.append("")
    summary.append("--------------------------------------------------")
    summary.append(f"PHASE 1 STATUS: {status_str}")
    summary.append("--------------------------------------------------")
    
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
