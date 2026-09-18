from __future__ import annotations

from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from carda_link.auctions.models import Auction, Lot
from carda_link.estates.models import Estate, HarvestBatch
from carda_link.invoicing.models import Invoice
from carda_link.users.models import Notification, User


def seller_required(view_func):
    """Ensure user is an active seller."""
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != User.Role.SELLER:
            raise PermissionDenied("Only registered cardamom sellers can access the Seller Portal.")
        if request.user.status != User.Status.ACTIVE:
            raise PermissionDenied("Your seller account is pending approval or inactive.")
        return view_func(request, *args, **kwargs)
    return _wrapped


def get_seller_context(request):
    """Helper for seller common notification counters."""
    from carda_link.auctions.services import sync_expired_auctions
    sync_expired_auctions()

    unread_notifs = Notification.objects.filter(user=request.user, is_read=False)
    recent_notifs = Notification.objects.filter(user=request.user)[:5]
    estates_count = Estate.objects.filter(owner=request.user).count()
    return {
        "unread_notifications_count": unread_notifs.count(),
        "recent_notifications": recent_notifs,
        "estates_count": estates_count,
    }



# -----------------------------------------------------------------------------
# 1. Seller Dashboard Overview
# -----------------------------------------------------------------------------
@login_required
@seller_required
def seller_dashboard_view(request):
    estates = Estate.objects.filter(owner=request.user).order_by("-created_at")
    estates_count = estates.count()

    batches = HarvestBatch.objects.filter(estate__owner=request.user).select_related(
        "estate", "auction_lot__auction"
    ).order_by("-harvest_date")
    total_batches_count = batches.count()
    ungraded_count = batches.filter(grade="UNGRADED", is_rejected=False).count()
    rejected_count = batches.filter(is_rejected=True).count()
    graded_count = batches.filter(~Q(grade="UNGRADED"), is_rejected=False).count()

    # Active Lots in current auctions
    active_lots = Lot.objects.filter(
        harvest_batch__estate__owner=request.user,
        auction__status="ACTIVE"
    ).select_related("auction", "harvest_batch")
    active_lots_count = active_lots.count()

    # Earnings & Sales calculation
    sold_lots = Lot.objects.filter(
        harvest_batch__estate__owner=request.user,
        is_sold=True,
    ).select_related("harvest_batch", "invoice")

    total_sold_kg = sum(l.harvest_batch.weight_kg for l in sold_lots)
    total_sold_value = sum(
        (l.harvest_batch.weight_kg * (l.highest_bid_per_kg or l.base_price_per_kg))
        for l in sold_lots
    )

    completed_payout = Decimal("0.00")
    pending_payout = Decimal("0.00")
    for l in sold_lots:
        val = l.harvest_batch.weight_kg * (l.highest_bid_per_kg or l.base_price_per_kg)
        # Deduct 2% commission approximation
        net_val = round(val * Decimal("0.98"), 2)
        if hasattr(l, "invoice") and l.invoice and l.invoice.status == "PAID":
            completed_payout += net_val
        else:
            pending_payout += net_val

    recent_batches = batches[:8]

    context = {
        **get_seller_context(request),
        "estates_count": estates_count,
        "total_batches_count": total_batches_count,
        "ungraded_count": ungraded_count,
        "graded_count": graded_count,
        "rejected_count": rejected_count,
        "active_lots_count": active_lots_count,
        "total_sold_kg": total_sold_kg,
        "total_sold_value": total_sold_value,
        "completed_payout": completed_payout,
        "pending_payout": pending_payout,
        "recent_batches": recent_batches,
        "active_lots": active_lots[:4],
    }
    return render(request, "users/seller_dashboard.html", context)


# -----------------------------------------------------------------------------
# 2. My Estates (CRUD)
# -----------------------------------------------------------------------------
@login_required
@seller_required
def seller_estates_view(request):
    estates = Estate.objects.filter(owner=request.user).prefetch_related("harvest_batches").order_by("-created_at")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        location = request.POST.get("location", "").strip()
        area_in_acres = request.POST.get("area_in_acres", "1.0")
        description = request.POST.get("description", "").strip()
        primary_photo = request.FILES.get("primary_photo")

        if not name or not location:
            messages.error(request, "Estate name and location are required.")
        else:
            try:
                acres = Decimal(area_in_acres)
            except Exception:
                acres = Decimal("1.0")

            Estate.objects.create(
                owner=request.user,
                name=name,
                owner_name=request.user.name or request.user.email,
                phone_number=request.user.phone_number or "",
                location=location,
                area_in_acres=acres,
                description=description,
                primary_photo=primary_photo,
            )
            messages.success(request, f"Estate '{name}' registered successfully.")
            return redirect("seller_estates")

    context = {
        **get_seller_context(request),
        "estates": estates,
    }
    return render(request, "users/seller_estates.html", context)


@login_required
@seller_required
def seller_estate_edit_view(request, pk):
    estate = get_object_or_404(Estate, pk=pk, owner=request.user)

    if request.method == "POST":
        estate.name = request.POST.get("name", estate.name).strip()
        estate.location = request.POST.get("location", estate.location).strip()
        area = request.POST.get("area_in_acres")
        if area:
            try:
                estate.area_in_acres = Decimal(area)
            except Exception:
                pass
        estate.description = request.POST.get("description", estate.description).strip()
        if "primary_photo" in request.FILES:
            estate.primary_photo = request.FILES["primary_photo"]
        estate.save()
        messages.success(request, f"Estate '{estate.name}' updated successfully.")
        return redirect("seller_estates")

    context = {
        **get_seller_context(request),
        "estate": estate,
    }
    return render(request, "users/seller_estate_edit.html", context)


@require_POST
@login_required
@seller_required
def seller_estate_delete_view(request, pk):
    estate = get_object_or_404(Estate, pk=pk, owner=request.user)
    name = estate.name
    estate.delete()
    messages.success(request, f"Estate '{name}' has been deleted.")
    return redirect("seller_estates")


# -----------------------------------------------------------------------------
# 3. Harvest Batches (Log & Quality Status)
# -----------------------------------------------------------------------------
@login_required
@seller_required
def seller_batches_view(request):
    seller_estates = Estate.objects.filter(owner=request.user)
    batches = HarvestBatch.objects.filter(estate__owner=request.user).select_related(
        "estate", "auction_lot__auction"
    ).order_by("-harvest_date")

    if request.method == "POST":
        estate_id = request.POST.get("estate_id")
        weight_kg = request.POST.get("weight_kg")
        harvest_date = request.POST.get("harvest_date")
        quality_cert = request.FILES.get("quality_certificate")

        estate = get_object_or_404(Estate, pk=estate_id, owner=request.user)

        if not weight_kg or not harvest_date:
            messages.error(request, "Weight and harvest date are required.")
        else:
            try:
                weight = Decimal(weight_kg)
                if weight <= 0:
                    raise ValueError
            except Exception:
                messages.error(request, "Invalid weight value specified.")
                return redirect("seller_batches")

            HarvestBatch.objects.create(
                estate=estate,
                weight_kg=weight,
                harvest_date=harvest_date,
                grade="UNGRADED",
                quality_certificate=quality_cert,
            )
            messages.success(request, f"New harvest batch ({weight} kg) logged for {estate.name}. Sent to administrator verification queue.")
            return redirect("seller_batches")

    context = {
        **get_seller_context(request),
        "batches": batches,
        "seller_estates": seller_estates,
    }
    return render(request, "users/seller_batches.html", context)


# -----------------------------------------------------------------------------
# 4. My Lots (Read-Only Live Highest Bid View)
# -----------------------------------------------------------------------------
@login_required
@seller_required
def seller_lots_view(request):
    lots = Lot.objects.filter(
        harvest_batch__estate__owner=request.user
    ).select_related(
        "auction", "harvest_batch__estate"
    ).order_by("-auction__start_time", "lot_number")

    context = {
        **get_seller_context(request),
        "lots": lots,
    }
    return render(request, "users/seller_lots.html", context)


# -----------------------------------------------------------------------------
# 5. Sales History View
# -----------------------------------------------------------------------------
@login_required
@seller_required
def seller_sales_history_view(request):
    completed_lots = Lot.objects.filter(
        harvest_batch__estate__owner=request.user,
        is_sold=True,
    ).select_related(
        "auction", "harvest_batch__estate", "invoice__buyer"
    ).order_by("-auction__end_time")

    for l in completed_lots:
        price = l.highest_bid_per_kg or l.base_price_per_kg
        l.final_sale_value = round(l.harvest_batch.weight_kg * price, 2)
        l.net_payout = round(l.final_sale_value * Decimal("0.98"), 2)

    context = {
        **get_seller_context(request),
        "completed_lots": completed_lots,
    }
    return render(request, "users/seller_sales.html", context)


# -----------------------------------------------------------------------------
# 6. Earnings Summary View
# -----------------------------------------------------------------------------
@login_required
@seller_required
def seller_earnings_view(request):
    sold_lots = Lot.objects.filter(
        harvest_batch__estate__owner=request.user,
        is_sold=True,
    ).select_related("harvest_batch", "invoice")

    total_kg_sold = sum(l.harvest_batch.weight_kg for l in sold_lots)
    gross_earnings = sum(
        (l.harvest_batch.weight_kg * (l.highest_bid_per_kg or l.base_price_per_kg))
        for l in sold_lots
    )

    completed_payout = Decimal("0.00")
    pending_payout = Decimal("0.00")
    for l in sold_lots:
        net = round((l.harvest_batch.weight_kg * (l.highest_bid_per_kg or l.base_price_per_kg)) * Decimal("0.98"), 2)
        if hasattr(l, "invoice") and l.invoice and l.invoice.status == "PAID":
            completed_payout += net
        else:
            pending_payout += net

    profile = getattr(request.user, "seller_profile", None)
    masked_acc = ""
    if profile and profile.bank_account_number:
        acc = profile.bank_account_number
        masked_acc = f"•••• •••• {acc[-4:]}" if len(acc) >= 4 else acc

    context = {
        **get_seller_context(request),
        "total_kg_sold": total_kg_sold,
        "gross_earnings": gross_earnings,
        "completed_payout": completed_payout,
        "pending_payout": pending_payout,
        "sold_lots": sold_lots,
        "profile": profile,
        "masked_acc": masked_acc,
    }
    return render(request, "users/seller_earnings.html", context)


# -----------------------------------------------------------------------------
# 7. Notifications Center
# -----------------------------------------------------------------------------
@login_required
@seller_required
def seller_notifications_view(request):
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by("-created_at")

    context = {
        **get_seller_context(request),
        "notifications": notifications,
    }
    return render(request, "users/seller_notifications.html", context)
