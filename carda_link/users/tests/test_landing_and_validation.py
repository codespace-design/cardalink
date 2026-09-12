from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from carda_link.users.forms import BuyerSignupForm
from carda_link.users.forms import SellerSignupForm
from carda_link.users.models import User
from carda_link.users.validators import ComplexPasswordValidator


class ComplexPasswordValidatorTest(TestCase):
    def setUp(self):
        self.validator = ComplexPasswordValidator(min_length=8)

    def test_short_password(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate("Ab1!")
        self.assertTrue(any("at least 8 characters" in msg for msg in ctx.exception.messages))

    def test_no_letter(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate("12345678!@#")
        self.assertTrue(any("at least one letter" in msg for msg in ctx.exception.messages))

    def test_no_number(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate("Abcdefgh!@#")
        self.assertTrue(any("at least one numeric digit" in msg for msg in ctx.exception.messages))

    def test_no_symbol(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate("Abcdefgh123")
        self.assertTrue(any("at least one special symbol" in msg for msg in ctx.exception.messages))

    def test_valid_password(self):
        try:
            self.validator.validate("CardaLink@2026")
        except ValidationError:
            self.fail("validate() unexpectedly raised ValidationError for valid password!")

    def test_django_validate_password_integration(self):
        # Base settings register the validator
        try:
            validate_password("SecurePass#999")
        except ValidationError:
            self.fail("validate_password() unexpectedly raised ValidationError for valid password!")


class LandingPageAndRegistrationFlowTest(TestCase):
    def setUp(self):
        self.pending_user = User.objects.create_user(
            email="farmer_pending@cardalink.test",
            password="Password@123",
            role=User.Role.SELLER,
            status=User.Status.PENDING,
        )

    def test_landing_page_ordering(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check that username/email input is present
        self.assertIn('name="login"', content)
        # Check that password input is present
        self.assertIn('name="password"', content)
        # Check that Sign In submit button is present
        self.assertIn("Sign In", content)
        # Check that Register button links to role selection
        self.assertIn(reverse("register"), content)
        # Check Google auth button is NOT present per requirements
        self.assertNotIn("Continue with Google", content)

        # Verify relative sequence in HTML: login form before Register
        pos_login = content.find('name="login"')
        pos_signin_btn = content.find('type="submit"')
        pos_register = content.find(reverse("register"))

        self.assertTrue(pos_login < pos_signin_btn < pos_register,
                        f"Elements not in requested order: login={pos_login}, submit={pos_signin_btn}, register={pos_register}")

    def test_register_redirects_to_role_selection(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Must offer Seller and Buyer
        self.assertIn("Seller", content)
        self.assertIn("Buyer", content)
        self.assertIn(reverse("seller_signup"), content)
        self.assertIn(reverse("buyer_signup"), content)

    def test_password_field_has_anti_autofill_attributes(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('autocomplete="new-password"', content)
        self.assertIn('resetPassword', content)

    def test_pending_user_professional_warning(self):
        response = self.client.post(
            reverse("home"),
            {"login": "farmer_pending@cardalink.test", "password": "Password@123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Your account has not yet been approved by the administrator. Please wait for admin approval.",
            response.content.decode(),
        )

    def test_seller_signup_form_rejects_weak_password(self):
        form = SellerSignupForm(
            data={
                "name": "Test Farmer",
                "email": "farmer1@example.com",
                "phone_number": "+919876543210",
                "password": "simplepassword",
                "confirm_password": "simplepassword",
                "farm_name": "Highland Cardamom",
                "farm_location": "Idukki",
                "farm_area": "5.5",
                "area_unit": "ACRE",
                "cardamom_plants": 1200,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)

    def test_seller_signup_form_accepts_compliant_password(self):
        form = SellerSignupForm(
            data={
                "name": "Test Farmer",
                "email": "farmer2@example.com",
                "phone_number": "+919876543211",
                "password": "CardaLink@2026",
                "confirm_password": "CardaLink@2026",
                "farm_name": "Highland Cardamom",
                "farm_location": "Idukki",
                "farm_area": "5.5",
                "area_unit": "ACRE",
                "cardamom_plants": 1200,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
