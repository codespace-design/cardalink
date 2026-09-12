from decimal import Decimal
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from carda_link.auctions.models import Auction, Lot
from carda_link.invoicing.models import PlatformSettings
from carda_link.users.models import BuyerProfile, SellerProfile, User


class AdminManualUserCreationForm(forms.Form):
    ROLE_CHOICES = [
        (User.Role.SELLER, _("Seller / Cardamom Farmer")),
        (User.Role.BUYER, _("Buyer / Trader")),
    ]

    role = forms.ChoiceField(
        label=_("User Role"),
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_admin_role"}),
    )
    name = forms.CharField(
        label=_("Full Name"),
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Full legal name"}),
    )
    email = forms.EmailField(
        label=_("Email Address"),
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@example.com"}),
    )
    password = forms.CharField(
        label=_("Temporary Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    confirm_password = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    phone_number = forms.CharField(
        label=_("Phone Number"),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+91 9876543210"}),
    )
    address = forms.CharField(
        label=_("Address / Location"),
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
    license_number = forms.CharField(
        label=_("Spices Board / Trading License Number"),
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    # Seller specific fields
    farm_name = forms.CharField(
        label=_("Farm / Estate Name"),
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    farm_location = forms.CharField(
        label=_("Farm Location"),
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    farm_area = forms.DecimalField(
        label=_("Farm Area"),
        required=False,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    area_unit = forms.ChoiceField(
        label=_("Area Unit"),
        required=False,
        choices=User.AreaUnit.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cardamom_plants = forms.IntegerField(
        label=_("Number of Cardamom Plants"),
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    cultivation_details = forms.CharField(
        label=_("Cultivation Details"),
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )

    # Buyer specific fields
    company_name = forms.CharField(
        label=_("Company / Firm Name"),
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    business_type = forms.CharField(
        label=_("Business Type"),
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    business_address = forms.CharField(
        label=_("Business Address"),
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
    business_details = forms.CharField(
        label=_("Business Details"),
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(_("An account with this email address already exists."))
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        role = cleaned_data.get("role")

        if password:
            try:
                validate_password(password)
            except ValidationError as error:
                self.add_error("password", error)

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", _("Passwords do not match."))

        if role == User.Role.SELLER:
            if not cleaned_data.get("farm_name"):
                self.add_error("farm_name", _("Farm Name is required for Sellers."))
            if not cleaned_data.get("farm_location"):
                self.add_error("farm_location", _("Farm Location is required for Sellers."))
            if cleaned_data.get("farm_area") is None:
                self.add_error("farm_area", _("Farm Area is required for Sellers."))
            if cleaned_data.get("cardamom_plants") is None:
                self.add_error("cardamom_plants", _("Number of plants is required for Sellers."))
        elif role == User.Role.BUYER:
            if not cleaned_data.get("company_name"):
                self.add_error("company_name", _("Company name is required for Buyers."))
            if not cleaned_data.get("business_type"):
                self.add_error("business_type", _("Business type is required for Buyers."))
            if not cleaned_data.get("business_address"):
                self.add_error("business_address", _("Business address is required for Buyers."))

        return cleaned_data

    def save(self):
        data = self.cleaned_data
        role = data["role"]
        user = User.objects.create(
            email=data["email"],
            name=data["name"],
            role=role,
            status=User.Status.ACTIVE,
            phone_number=data.get("phone_number") or None,
            address=data.get("address", ""),
            license_number=data.get("license_number", ""),
            is_verified=True,
            created_by_admin=True,
        )
        user.set_password(data["password"])
        user.save()

        if role == User.Role.SELLER:
            SellerProfile.objects.create(
                user=user,
                farm_name=data["farm_name"],
                farm_location=data["farm_location"],
                farm_area=data.get("farm_area") or Decimal("0.00"),
                area_unit=data.get("area_unit") or User.AreaUnit.ACRE,
                cardamom_plants=data.get("cardamom_plants") or 0,
                cultivation_details=data.get("cultivation_details", ""),
            )
        elif role == User.Role.BUYER:
            BuyerProfile.objects.create(
                user=user,
                company_name=data["company_name"],
                business_type=data["business_type"],
                business_address=data["business_address"],
                business_details=data.get("business_details", ""),
            )

        return user


class AuctionScheduleForm(forms.ModelForm):
    start_time = forms.DateTimeField(
        label=_("Start Date & Time"),
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"},
            format="%Y-%m-%dT%H:%M",
        ),
    )
    end_time = forms.DateTimeField(
        label=_("End Date & Time"),
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"},
            format="%Y-%m-%dT%H:%M",
        ),
    )

    class Meta:
        model = Auction
        fields = ["title", "start_time", "end_time", "description"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Weekly Premium Cardamom Auction"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Auction session details..."}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if start_time and end_time:
            if end_time <= start_time:
                self.add_error("end_time", _("End time must be strictly after the start time."))

            # Only enforce start_time in future when creating a new auction
            if not self.instance.pk and start_time < timezone.now():
                self.add_error("start_time", _("Start time must be set in the future."))

        return cleaned_data


class PlatformSettingsForm(forms.ModelForm):
    class Meta:
        model = PlatformSettings
        fields = ["commission_percent"]
        widgets = {
            "commission_percent": forms.NumberInput(
                attrs={"class": "form-control form-control-lg", "step": "0.01", "min": "0", "max": "100"}
            ),
        }
