from allauth.account.forms import LoginForm
from allauth.account.forms import ResetPasswordForm
from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django import forms
from django.contrib.auth import forms as admin_forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import BuyerProfile
from .models import SellerProfile
from .models import User


class CustomLoginForm(LoginForm):
    """Custom login form supporting admin, seller, and buyer authentication."""
    pass


class CustomResetPasswordForm(ResetPasswordForm):
    """Password reset form verifying user existence with professional feedback."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "email" in self.fields:
            self.fields["email"].widget.attrs.update(
                {
                    "class": "form-control form-control-lg form-input-clean",
                    "placeholder": "name@example.com",
                    "autocomplete": "email",
                    "autofocus": "autofocus",
                }
            )

    def clean_email(self) -> str:
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError(_("Please enter your registered email address."))

        if not User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                _("No CardaLink account is registered with this email address. Please verify your email or create a new account.")
            )

        return super().clean_email()




class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):
        model = User
        field_classes = {"email": forms.EmailField}


class UserAdminCreationForm(admin_forms.AdminUserCreationForm):
    """
    Form for User Creation in the Admin Area.
    To change user signup, see UserSignupForm and UserSocialSignupForm.
    """

    role = forms.ChoiceField(
        choices=User.Role.choices,
        initial=User.Role.BUYER,
        required=False,
    )
    status = forms.ChoiceField(
        choices=User.Status.choices,
        initial=User.Status.PENDING,
        required=False,
    )

    class Meta(admin_forms.UserCreationForm.Meta):
        model = User
        fields = ("email", "role", "status", "phone_number")
        field_classes = {"email": forms.EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("role"):
            cleaned_data["role"] = User.Role.BUYER
        if not cleaned_data.get("status"):
            cleaned_data["status"] = User.Status.PENDING
        return cleaned_data


class UserSignupForm(SignupForm):
    """
    Form that will be rendered on a user sign up section/screen.
    Default fields will be added automatically.
    Check UserSocialSignupForm for accounts created from social.
    """


class UserSocialSignupForm(SocialSignupForm):
    """
    Renders the form when user has signed up using social accounts.
    Default fields will be added automatically.
    See UserSignupForm otherwise.
    """


class SellerSignupForm(forms.ModelForm):
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=True,
    )
    confirm_password = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=True,
    )

    # Seller Profile fields
    farm_name = forms.CharField(
        label=_("Farm / Estate Name"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Cardamom Valley Estate"}),
        required=True,
    )
    farm_location = forms.CharField(
        label=_("Farm Location"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Vandanmedu, Idukki"}),
        required=False,
    )
    district = forms.ChoiceField(
        label=_("District"),
        choices=SellerProfile.District.choices,
        initial=SellerProfile.District.IDUKKI,
        widget=forms.Select(attrs={"class": "form-select"}),
        required=False,
    )
    taluk = forms.CharField(
        label=_("Taluk"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Udumbanchola"}),
        required=False,
    )
    village = forms.CharField(
        label=_("Village"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Vandanmedu"}),
        required=False,
    )
    farm_area = forms.DecimalField(
        label=_("Cultivated Area"),
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g. 10.5"}),
        required=True,
    )
    area_unit = forms.ChoiceField(
        label=_("Area Unit"),
        choices=SellerProfile.AreaUnit.choices,
        initial=SellerProfile.AreaUnit.ACRE,
        widget=forms.Select(attrs={"class": "form-select"}),
        required=True,
    )
    cardamom_plants = forms.IntegerField(
        label=_("Approx. Cardamom Plant Count"),
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g. 2500"}),
        required=True,
    )
    cultivation_method = forms.ChoiceField(
        label=_("Cultivation Method"),
        choices=SellerProfile.CultivationMethod.choices,
        initial=SellerProfile.CultivationMethod.CONVENTIONAL,
        widget=forms.Select(attrs={"class": "form-select"}),
        required=False,
    )
    ownership_proof = forms.FileField(
        label=_("Land Ownership / Cultivation Proof Document"),
        widget=forms.FileInput(attrs={"class": "form-control"}),
        required=False,
        help_text=_("Upload tax receipt, title deed, or cultivation certificate (PDF or Image)."),
    )

    # Bank Account Details
    bank_account_holder = forms.CharField(
        label=_("Bank Account Holder Name"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "As shown in bank passbook"}),
        required=False,
    )
    bank_ifsc = forms.CharField(
        label=_("Bank IFSC Code"),
        max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. SBIN0001234"}),
        required=False,
    )
    bank_account_number = forms.CharField(
        label=_("Bank Account Number"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Account number for payouts"}),
        required=False,
    )
    cultivation_details = forms.CharField(
        label=_("Additional Farm Notes"),
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Optional details..."}),
        required=False,
    )

    class Meta:
        model = User
        fields = (
            "name",
            "email",
            "phone_number",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Full legal name"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@example.com"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "10-digit mobile number"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise ValidationError(_("This email is already registered."))
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number", "").strip()
        if not phone:
            raise ValidationError(_("Phone number is required for OTP verification."))
        return phone

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password:
            try:
                validate_password(password)
            except ValidationError as error:
                self.add_error("password", error)

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", _("Passwords do not match. Please verify and try again."))

        farm_area = cleaned_data.get("farm_area")
        if farm_area is not None and farm_area <= 0:
            self.add_error("farm_area", _("Farm area must be a positive number."))

        cardamom_plants = cleaned_data.get("cardamom_plants")
        if cardamom_plants is not None and cardamom_plants < 0:
            self.add_error(
                "cardamom_plants",
                _("Number of cardamom plants cannot be negative."),
            )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.role = User.Role.SELLER
        user.status = User.Status.PENDING
        if commit:
            user.save()
            district = self.cleaned_data.get("district") or SellerProfile.District.IDUKKI
            taluk = self.cleaned_data.get("taluk", "")
            village = self.cleaned_data.get("village", "")
            parts = [p for p in [village, taluk, district] if p]
            loc_from_parts = ", ".join(parts)
            farm_location = self.cleaned_data.get("farm_location") or (loc_from_parts or district)

            SellerProfile.objects.create(
                user=user,
                farm_name=self.cleaned_data["farm_name"],
                farm_location=farm_location,
                district=district,
                taluk=taluk,
                village=village,
                farm_area=self.cleaned_data["farm_area"],
                area_unit=self.cleaned_data["area_unit"],
                cardamom_plants=self.cleaned_data["cardamom_plants"],
                cultivation_method=self.cleaned_data.get("cultivation_method") or SellerProfile.CultivationMethod.CONVENTIONAL,
                cultivation_details=self.cleaned_data.get("cultivation_details", ""),
                ownership_proof=self.cleaned_data.get("ownership_proof"),
                bank_account_holder=self.cleaned_data.get("bank_account_holder", ""),
                bank_ifsc=self.cleaned_data.get("bank_ifsc", "").upper(),
                bank_account_number=self.cleaned_data.get("bank_account_number", ""),
            )
            from carda_link.estates.models import Estate
            area_val = self.cleaned_data.get("farm_area") or Decimal("1.00")
            if area_val <= 0:
                area_val = Decimal("1.00")
            Estate.objects.create(
                owner=user,
                name=self.cleaned_data["farm_name"],
                owner_name=user.name or user.email,
                phone_number=user.phone_number or "",
                address=user.address or farm_location,
                location=farm_location,
                area_in_acres=area_val,
                description=self.cleaned_data.get("cultivation_details", ""),
            )
        return user


class BuyerSignupForm(forms.ModelForm):
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=True,
    )
    confirm_password = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=True,
    )

    # Buyer Profile fields
    business_name = forms.CharField(
        label=_("Company / Business Name"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Spice Route Exports Pvt Ltd"}),
        required=True,
    )
    business_type = forms.CharField(
        label=_("Business Type"),
        widget=forms.Select(choices=BuyerProfile.BusinessType.choices, attrs={"class": "form-select"}),
        required=False,
        initial=BuyerProfile.BusinessType.TRADER,
    )
    gst_number = forms.CharField(
        label=_("GST / Business Registration Number"),
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 32AAAAA0000A1Z5"}),
        required=False,
    )
    business_address = forms.CharField(
        label=_("Registered Business Address"),
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Street, City, State, PIN"}),
        required=True,
    )
    registration_certificate = forms.FileField(
        label=_("Business License / Registration Certificate"),
        widget=forms.FileInput(attrs={"class": "form-control"}),
        required=False,
        help_text=_("Upload GST certificate, trade license, or Spices Board registration."),
    )
    purchase_capacity = forms.CharField(
        label=_("Expected Purchase Capacity (Optional)"),
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 500 - 1000 kg / month"}),
        required=False,
    )
    business_details = forms.CharField(
        label=_("Additional Business Details"),
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Optional info..."}),
        required=False,
    )

    class Meta:
        model = User
        fields = (
            "name",
            "email",
            "phone_number",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Contact person name"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "buyer@company.com"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "10-digit mobile number"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise ValidationError(_("This email is already registered."))
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number", "").strip()
        if not phone:
            raise ValidationError(_("Phone number is required for OTP verification."))
        return phone

    def clean_business_type(self):
        bt = str(self.cleaned_data.get("business_type", "")).strip().upper()
        if "EXPORTER" in bt:
            return BuyerProfile.BusinessType.EXPORTER
        elif "WHOLESALER" in bt:
            return BuyerProfile.BusinessType.WHOLESALER
        elif "PROCESSOR" in bt:
            return BuyerProfile.BusinessType.PROCESSOR
        elif "RETAILER" in bt:
            return BuyerProfile.BusinessType.RETAILER
        elif "TRADER" in bt:
            return BuyerProfile.BusinessType.TRADER
        return BuyerProfile.BusinessType.TRADER

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password:
            try:
                validate_password(password)
            except ValidationError as error:
                self.add_error("password", error)

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", _("Passwords do not match. Please verify and try again."))

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.role = User.Role.BUYER
        user.status = User.Status.PENDING
        if commit:
            user.save()
            BuyerProfile.objects.create(
                user=user,
                company_name=self.cleaned_data["business_name"],
                business_type=self.cleaned_data["business_type"],
                gst_number=self.cleaned_data.get("gst_number", ""),
                business_address=self.cleaned_data["business_address"],
                registration_certificate=self.cleaned_data.get("registration_certificate"),
                purchase_capacity=self.cleaned_data.get("purchase_capacity", ""),
                business_details=self.cleaned_data.get("business_details", ""),
            )
        return user


class SellerProfileForm(forms.ModelForm):
    class Meta:
        model = SellerProfile
        fields = (
            "farm_name",
            "farm_location",
            "farm_area",
            "area_unit",
            "cardamom_plants",
            "cultivation_details",
        )
        widgets = {
            "farm_name": forms.TextInput(attrs={"class": "form-control"}),
            "farm_location": forms.TextInput(attrs={"class": "form-control"}),
            "farm_area": forms.NumberInput(attrs={"class": "form-control"}),
            "area_unit": forms.Select(attrs={"class": "form-select"}),
            "cardamom_plants": forms.NumberInput(attrs={"class": "form-control"}),
            "cultivation_details": forms.Textarea(
                attrs={"class": "form-control", "rows": 3},
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        farm_area = cleaned_data.get("farm_area")
        if farm_area is not None and farm_area <= 0:
            self.add_error("farm_area", _("Farm area must be a positive number."))

        cardamom_plants = cleaned_data.get("cardamom_plants")
        if cardamom_plants is not None and cardamom_plants < 0:
            self.add_error(
                "cardamom_plants",
                _("Number of cardamom plants cannot be negative."),
            )

        return cleaned_data


class BuyerProfileForm(forms.ModelForm):
    company_name = forms.CharField(
        label=_("Company / Business Name"),
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
    )

    class Meta:
        model = BuyerProfile
        fields = (
            "company_name",
            "business_type",
            "business_address",
            "business_details",
        )
        widgets = {
            "business_type": forms.TextInput(attrs={"class": "form-control"}),
            "business_address": forms.Textarea(
                attrs={"class": "form-control", "rows": 3},
            ),
            "business_details": forms.Textarea(
                attrs={"class": "form-control", "rows": 3},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["company_name"].initial = self.instance.company_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.company_name = self.cleaned_data["company_name"]
        if commit:
            profile.save()
        return profile


from allauth.account.forms import LoginForm


class CustomLoginForm(LoginForm):
    def clean(self):
        cleaned_data = super().clean()
        if hasattr(self, "user") and self.user:
            user = self.user
            if user.status == "PENDING":
                raise forms.ValidationError(
                    "Your account has not yet been approved by the administrator. Please wait for admin approval.",
                )
            if user.status == "REJECTED":
                raise forms.ValidationError(
                    "Your registration has been rejected by the administrator.",
                )
            if user.status == "SUSPENDED":
                raise forms.ValidationError(
                    "Your account has been suspended. Please contact the administrator.",
                )
        return cleaned_data
