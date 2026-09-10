from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django import forms
from django.contrib.auth import forms as admin_forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import BuyerProfile
from .models import SellerProfile
from .models import User


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

    # Seller Profile fields (explicily defined form fields)
    farm_name = forms.CharField(
        label=_("Farm Name"),
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
    )
    farm_location = forms.CharField(
        label=_("Farm Location"),
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
    )
    farm_area = forms.DecimalField(
        label=_("Farm Area"),
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        required=True,
    )
    area_unit = forms.ChoiceField(
        label=_("Area Unit"),
        choices=SellerProfile.AreaUnit.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
        required=True,
    )
    cardamom_plants = forms.IntegerField(
        label=_("Number of Cardamom Plants"),
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        required=True,
    )
    cultivation_details = forms.CharField(
        label=_("Cultivation Details"),
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
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
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise ValidationError(_("This email is already registered."))
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", _("Passwords do not match."))

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
            SellerProfile.objects.create(
                user=user,
                farm_name=self.cleaned_data["farm_name"],
                farm_location=self.cleaned_data["farm_location"],
                farm_area=self.cleaned_data["farm_area"],
                area_unit=self.cleaned_data["area_unit"],
                cardamom_plants=self.cleaned_data["cardamom_plants"],
                cultivation_details=self.cleaned_data.get("cultivation_details", ""),
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

    # Buyer Profile fields (defined as explicit form fields, maps to BuyerProfile company_name/business_type/business_address/business_details)
    business_name = forms.CharField(
        label=_("Company/Business Name"),
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
    )
    business_type = forms.CharField(
        label=_("Business Type"),
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
    )
    business_address = forms.CharField(
        label=_("Business Address"),
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        required=True,
    )
    business_details = forms.CharField(
        label=_("Business Details"),
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
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
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise ValidationError(_("This email is already registered."))
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", _("Passwords do not match."))

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
                business_address=self.cleaned_data["business_address"],
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
