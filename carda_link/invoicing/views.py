from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView
from django.views.generic import ListView

from carda_link.auctions.models import Auction
from carda_link.auctions.models import Lot
from carda_link.estates.models import Estate
from carda_link.estates.models import HarvestBatch
from carda_link.invoicing.forms import ConfirmBiddingForm
from carda_link.invoicing.models import Invoice

User = get_user_model()


def ensure_demo_data():
    """Seed initial data if the database is currently empty for seamless testing."""
    if Lot.objects.exists():
        return

    with transaction.atomic():
        # 1. Users
        buyer, _ = User.objects.get_or_create(
            email="buyer@cardalink.com",
            defaults={
                "name": "Anand Kumar",
                "is_active": True,
            },
        )
        if not buyer.has_usable_password():
            buyer.set_password("password123")
            buyer.save()

        seller, _ = User.objects.get_or_create(
            email="seller@cardalink.com",
            defaults={
                "name": "Ramesh Nair",
                "is_active": True,
            },
        )
        if not seller.has_usable_password():
            seller.set_password("password123")
            seller.save()

        # 2. Estate
        estate, _ = Estate.objects.get_or_create(
            name="Highland Green Estate",
            defaults={
                "owner": seller,
                "location": "Munnar, Idukki, Kerala",
                "area_in_acres": Decimal("24.50"),
            },
        )

        # 3. Harvest Batches
        batch1, _ = HarvestBatch.objects.get_or_create(
            estate=estate,
            grade="AGEB",
            defaults={
                "harvest_date": timezone.now().date(),
                "weight_kg": Decimal("250.00"),
            },
        )

        batch2, _ = HarvestBatch.objects.get_or_create(
            estate=estate,
            grade="AGB",
            defaults={
                "harvest_date": timezone.now().date(),
                "weight_kg": Decimal("400.00"),
            },
        )

        # 4. Auction
        auction, _ = Auction.objects.get_or_create(
            title="Idukki Premium Cardamom Auction #2026-A",
            defaults={
                "start_time": timezone.now(),
                "end_time": timezone.now() + timezone.timedelta(days=1),
                "status": "COMPLETED",
            },
        )

        # 5. Lots
        lot1 = Lot.objects.create(
            auction=auction,
            harvest_batch=batch1,
            lot_number=101,
            base_price_per_kg=Decimal("2100.00"),
            highest_bid_per_kg=Decimal("2450.00"),
            is_sold=False,
        )

        lot2 = Lot.objects.create(
            auction=auction,
            harvest_batch=batch2,
            lot_number=102,
            base_price_per_kg=Decimal("1950.00"),
            highest_bid_per_kg=Decimal("2280.00"),
            is_sold=False,
        )

        # Create 1 sample invoice for lot1
        subtotal = lot1.harvest_batch.weight_kg * lot1.highest_bid_per_kg
        commission = subtotal * Decimal("0.02")
        total = subtotal + commission

        Invoice.objects.create(
            lot=lot1,
            buyer=buyer,
            total_amount=total,
            commission_fee=commission,
            status="PENDING",
        )
        lot1.is_sold = True
        lot1.save()


class InvoiceListView(ListView):
    model = Invoice
    template_name = "invoicing/invoice_list.html"
    context_object_name = "invoices"
    ordering = ["-issued_at"]

    def get_queryset(self):
        ensure_demo_data()
        return Invoice.objects.select_related(
            "lot__auction",
            "lot__harvest_batch__estate",
            "buyer",
        ).order_by("-issued_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()

        total_invoices = qs.count()
        total_billed = sum(inv.total_amount for inv in qs)
        paid_count = qs.filter(status="PAID").count()
        pending_count = qs.filter(status="PENDING").count()

        context.update(
            {
                "total_invoices": total_invoices,
                "total_billed": total_billed,
                "paid_count": paid_count,
                "pending_count": pending_count,
                "available_lots": Lot.objects.filter(is_sold=False).select_related(
                    "harvest_batch__estate", "auction"
                ),
            }
        )
        return context


class ConfirmBiddingView(View):
    template_name = "invoicing/confirm_bidding.html"

    def get(self, request, lot_id=None):
        ensure_demo_data()

        selected_lot = None
        initial_data = {}

        if lot_id:
            selected_lot = get_object_or_404(Lot, pk=lot_id)
        else:
            param_lot_id = request.GET.get("lot_id")
            if param_lot_id:
                selected_lot = Lot.objects.filter(pk=param_lot_id).first()

        if selected_lot:
            initial_data["lot"] = selected_lot
            if selected_lot.highest_bid_per_kg:
                initial_data["winning_bid_per_kg"] = selected_lot.highest_bid_per_kg
            else:
                initial_data["winning_bid_per_kg"] = selected_lot.base_price_per_kg

        if request.user.is_authenticated:
            initial_data["buyer"] = request.user
        else:
            default_buyer = User.objects.filter(email="buyer@cardalink.com").first()
            if default_buyer:
                initial_data["buyer"] = default_buyer

        form = ConfirmBiddingForm(initial=initial_data)
        lots = Lot.objects.select_related("harvest_batch__estate", "auction").order_by(
            "lot_number"
        )

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "lots": lots,
                "selected_lot": selected_lot,
            },
        )

    def post(self, request, lot_id=None):
        ensure_demo_data()
        form = ConfirmBiddingForm(request.POST)

        if form.is_valid():
            lot = form.cleaned_data["lot"]
            buyer = form.cleaned_data.get("buyer")
            winning_bid = form.cleaned_data["winning_bid_per_kg"]
            commission_pct = form.cleaned_data["commission_percentage"]

            # Fallback buyer if not specified or anonymous
            if not buyer:
                if request.user.is_authenticated:
                    buyer = request.user
                else:
                    buyer, _ = User.objects.get_or_create(
                        email="buyer@cardalink.com",
                        defaults={"name": "Anand Kumar"},
                    )

            weight = lot.harvest_batch.weight_kg
            subtotal = weight * winning_bid
            commission_fee = subtotal * (commission_pct / Decimal("100"))
            total_amount = subtotal + commission_fee

            # Update Lot
            lot.highest_bid_per_kg = winning_bid
            lot.is_sold = True
            lot.save()

            # Create or Update Invoice
            invoice, created = Invoice.objects.update_or_create(
                lot=lot,
                defaults={
                    "buyer": buyer,
                    "total_amount": total_amount,
                    "commission_fee": commission_fee,
                    "status": "PENDING",
                },
            )

            action_verb = "created" if created else "updated"
            messages.success(
                request,
                f"Bidding confirmed! Invoice #{invoice.id} has been {action_verb} for Lot #{lot.lot_number}.",
            )

            return redirect("invoicing:detail", pk=invoice.pk)

        lots = Lot.objects.select_related("harvest_batch__estate", "auction").order_by(
            "lot_number"
        )
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "lots": lots,
            },
        )


class InvoiceDetailView(DetailView):
    model = Invoice
    template_name = "invoicing/invoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return Invoice.objects.select_related(
            "lot__auction",
            "lot__harvest_batch__estate__owner",
            "buyer",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.get_object()
        lot = invoice.lot
        harvest_batch = lot.harvest_batch
        estate = harvest_batch.estate

        subtotal = invoice.total_amount - invoice.commission_fee
        weight_kg = harvest_batch.weight_kg
        rate_per_kg = (
            lot.highest_bid_per_kg
            if lot.highest_bid_per_kg
            else (subtotal / weight_kg if weight_kg else Decimal("0.00"))
        )

        context.update(
            {
                "subtotal": subtotal,
                "weight_kg": weight_kg,
                "rate_per_kg": rate_per_kg,
                "estate": estate,
                "harvest_batch": harvest_batch,
                "lot": lot,
            }
        )
        return context


class InvoicePayView(View):
    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        invoice.status = "PAID"
        invoice.paid_at = timezone.now()
        invoice.save()

        messages.success(
            request, f"Invoice #{invoice.id} marked as PAID successfully!"
        )
        return redirect("invoicing:detail", pk=invoice.pk)


class SeedDemoDataView(View):
    def get(self, request):
        ensure_demo_data()
        messages.info(request, "Demo invoice and lot data initialized.")
        return redirect("invoicing:list")
