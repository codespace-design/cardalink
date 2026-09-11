from django import forms
from django.contrib.auth import get_user_model
from carda_link.auctions.models import Lot
from carda_link.invoicing.models import Invoice

User = get_user_model()


class ConfirmBiddingForm(forms.Form):
    lot = forms.ModelChoiceField(
        queryset=Lot.objects.all(),
        label="Select Auction Lot",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    buyer = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label="Winning Bidder / Buyer",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Select buyer. If left empty, a default buyer account will be assigned.",
    )
    winning_bid_per_kg = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label="Winning Bid Rate (₹ per kg)",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.01", "placeholder": "e.g. 2450.00"}
        ),
    )
    commission_percentage = forms.DecimalField(
        max_digits=4,
        decimal_places=2,
        initial=2.0,
        label="Platform Commission (%)",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.1", "placeholder": "2.0"}
        ),
    )
