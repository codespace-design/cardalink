from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Estate
from .models import EstatePhoto
from .models import HarvestBatch


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"class": "form-control", "accept": "image/*", "id": "id_photos"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class EstateRegistrationForm(forms.ModelForm):
    photos = MultipleFileField(
        required=False,
        label=_("Additional Estate Photos (Gallery)"),
        help_text=_("Select one or more photos of your plantation, drying yard, cardamom plants, etc."),
    )

    class Meta:
        model = Estate
        fields = [
            "name",
            "owner_name",
            "phone_number",
            "address",
            "location",
            "area_in_acres",
            "primary_photo",
            "description",
        ]
        labels = {
            "name": _("Estate / Plantation Name"),
            "owner_name": _("Owner / Representative Name"),
            "phone_number": _("Contact Phone Number"),
            "address": _("Estate Full Address"),
            "location": _("Location / District"),
            "area_in_acres": _("Total Area (in Acres)"),
            "primary_photo": _("Primary Cover Photo"),
            "description": _("Estate Overview & Cultivation Notes"),
        }
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": _("e.g. Greenfield Cardamom Valley"),
                    "required": True,
                }
            ),
            "owner_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("e.g. John Doe / Green Spices Pvt Ltd"),
                    "required": True,
                }
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("e.g. +91 98765 43210"),
                    "required": True,
                }
            ),
            "address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("e.g. Survey No. 128/4, Puliyanmala Road, Vandanmedu, Idukki, Kerala - 685551"),
                    "required": True,
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("e.g. Vandanmedu, Idukki"),
                    "required": True,
                }
            ),
            "area_in_acres": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0.1",
                    "placeholder": _("e.g. 12.50"),
                    "required": True,
                }
            ),
            "primary_photo": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/*",
                    "id": "id_primary_photo",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": _("Describe your plantation altitude, cardamom varieties (Njallani, Wonder Cardamom), soil type, shade trees, organic status..."),
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user and user.is_authenticated:
            if not self.initial.get("owner_name") and getattr(user, "name", None):
                self.initial["owner_name"] = user.name
            if not self.initial.get("phone_number") and getattr(user, "phone_number", None):
                self.initial["phone_number"] = user.phone_number
            if not self.initial.get("address") and getattr(user, "address", None):
                self.initial["address"] = user.address

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number", "").strip()
        if not phone:
            raise forms.ValidationError(_("Phone number is required for buyers and auctioneers to contact you."))
        return phone

    def clean_area_in_acres(self):
        area = self.cleaned_data.get("area_in_acres")
        if area is not None and area <= 0:
            raise forms.ValidationError(_("Estate area must be greater than 0 acres."))
        return area

    def save(self, commit=True, user=None):
        estate = super().save(commit=False)
        effective_user = user or self.user
        if effective_user and effective_user.is_authenticated:
            estate.owner = effective_user
        if commit:
            estate.save()
            self.save_m2m()
        return estate


class HarvestBatchForm(forms.ModelForm):
    class Meta:
        model = HarvestBatch
        fields = [
            "harvest_date",
            "weight_kg",
            "grade",
            "quality_certificate",
        ]
        labels = {
            "harvest_date": _("Harvest Date"),
            "weight_kg": _("Harvest Weight (kg)"),
            "grade": _("Cardamom Quality Grade"),
            "quality_certificate": _("Quality / Lab Certificate (Optional)"),
        }
        widgets = {
            "harvest_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control",
                    "required": True,
                }
            ),
            "weight_kg": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0.01",
                    "placeholder": _("e.g. 150.00"),
                    "required": True,
                }
            ),
            "grade": forms.Select(
                attrs={
                    "class": "form-select",
                    "required": True,
                }
            ),
            "quality_certificate": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".pdf,.jpg,.jpeg,.png",
                }
            ),
        }

    def clean_weight_kg(self):
        weight = self.cleaned_data.get("weight_kg")
        if weight is not None and weight <= 0:
            raise forms.ValidationError(_("Harvest weight must be greater than 0 kg."))
        return weight
