from __future__ import annotations

from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from carda_link.auctions.models import Auction, Bid, Lot
from carda_link.estates.models import HarvestBatch
from carda_link.invoicing.models import Invoice
from carda_link.users.models import Notification, User, Watchlist


def buyer_required(view_func):
    """Ensure user is an active buyer."""
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != User.Role.BUYER:
            raise PermissionDenied("Only registered buyers can access the Buyer Portal.")
        if request.user.status != User.Status.ACTIVE:
            raise PermissionDenied("Your buyer account is pending approval or inactive.")
        return view_func(request, *args, **kwargs)
    return _wrapped


def get_buyer_context(request):
    """Helper to populate common buyer badge counts and notification alerts."""
    from carda_link.auctions.services import sync_expired_auctions
    sync_expired_auctions()

    unread_notifs = Notification.objects.filter(user=request.user, is_read=False)
    recent_notifs = Notification.objects.filter(user=request.user)[:5]
    watchlist_count = Watchlist.objects.filter(buyer=request.user).count()
    return {
        "unread_notifications_count": unread_notifs.count(),
        "recent_notifications": recent_notifs,
        "watchlist_count": watchlist_count,
    }


def compute_bid_status(bid: Bid) -> dict[str, str]:
    """Compute real-time bid status: Leading, Outbid, Won, or Lost."""
    lot = bid.lot
    auction = lot.auction
    now = timezone.now()

    # Instant check: If auction has reached end_time, close and finalize immediately
    if auction.status == "ACTIVE" and auction.end_time and now >= auction.end_time:
        auction.close_auction()
        auction.refresh_from_db()
        lot.refresh_from_db()

    is_top_bid = (lot.highest_bid_per_kg is not None and bid.amount_per_kg == lot.highest_bid_per_kg)

    if auction.status == "COMPLETED" or lot.is_sold:
        if is_top_bid:
            return {
                "code": "WON",
                "label": "Won",
                "badge": "badge-won",
                "icon": "bi-trophy-fill",
                "lot_id": lot.id,
                "lot_number": lot.lot_number,
            }
        return {
            "code": "LOST",
            "label": "Lost",
            "badge": "badge-lost",
            "icon": "bi-x-circle",
            "lot_id": lot.id,
            "lot_number": lot.lot_number,
        }
    elif auction.status == "ACTIVE":
        if is_top_bid:
            return {
                "code": "LEADING",
                "label": "Leading",
                "badge": "badge-leading",
                "icon": "bi-arrow-up-circle-fill",
                "lot_id": lot.id,
                "lot_number": lot.lot_number,
            }
        return {
            "code": "OUTBID",
            "label": "Outbid",
            "badge": "badge-outbid",
            "icon": "bi-arrow-down-circle",
            "lot_id": lot.id,
            "lot_number": lot.lot_number,
        }
    elif auction.status == "CANCELLED":
        return {
            "code": "CANCELLED",
            "label": "Cancelled",
            "badge": "bg-dark text-white",
            "icon": "bi-slash-circle",
            "lot_id": lot.id,
            "lot_number": lot.lot_number,
        }
    return {
        "code": "PENDING",
        "label": "Auction Pending",
        "badge": "bg-light text-secondary border",
        "icon": "bi-clock",
        "lot_id": lot.id,
        "lot_number": lot.lot_number,
    }



# -----------------------------------------------------------------------------
# 1. Buyer Dashboard Overview
# -----------------------------------------------------------------------------
@login_required
@buyer_required
def buyer_dashboard_view(request):
    now = timezone.now()
    active_auctions_count = Auction.objects.filter(status="ACTIVE", start_time__lte=now, end_time__gte=now).count()
    upcoming_auctions_count = Auction.objects.filter(status="UPCOMING").count()

    buyer_bids = Bid.objects.filter(bidder=request.user).select_related(
        "lot__auction", "lot__harvest_batch__estate"
    ).order_by("-timestamp")
    total_bids_count = buyer_bids.count()

    # Calculate Leading and Won counts
    recent_bids = []
    leading_count = 0
    for b in buyer_bids[:8]:
        status_info = compute_bid_status(b)
        b.computed_status = status_info
        recent_bids.append(b)

    for b in buyer_bids:
        if b.lot.auction.status == "ACTIVE" and b.amount_per_kg == b.lot.highest_bid_per_kg:
            leading_count += 1

    # Won lots count
    won_lots = Lot.objects.filter(
        is_sold=True,
        bids__bidder=request.user,
    ).distinct().select_related("harvest_batch", "auction")
    won_lots_count = 0
    for l in won_lots:
        top_bid = l.bids.order_by("-amount_per_kg").first()
        if top_bid and top_bid.bidder == request.user:
            won_lots_count += 1

    # Unpaid invoices count
    pending_invoices = Invoice.objects.filter(buyer=request.user, status="PENDING")
    pending_invoices_count = pending_invoices.count()

    # Active auctions preview
    active_auctions = Auction.objects.filter(
        status__in=["ACTIVE", "UPCOMING"]
    ).prefetch_related("lots__harvest_batch").order_by("start_time")[:3]

    context = {
        **get_buyer_context(request),
        "active_auctions_count": active_auctions_count,
        "upcoming_auctions_count": upcoming_auctions_count,
        "total_bids_count": total_bids_count,
        "leading_count": leading_count,
        "won_lots_count": won_lots_count,
        "pending_invoices_count": pending_invoices_count,
        "recent_bids": recent_bids,
        "active_auctions": active_auctions,
    }
    return render(request, "users/buyer_dashboard.html", context)


# -----------------------------------------------------------------------------
# 2. Live Auctions List with Filters & Countdown
# -----------------------------------------------------------------------------
@login_required
@buyer_required
def buyer_auctions_view(request):
    for a in Auction.objects.filter(status__in=["UPCOMING", "ACTIVE"]):
        a.auto_update_status()

    grade_filter = request.GET.get("grade", "").strip()
    origin_filter = request.GET.get("origin", "").strip()
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()

    lots_qs = Lot.objects.select_related(
        "auction", "harvest_batch__estate"
    ).filter(auction__status__in=["ACTIVE", "UPCOMING"])

    if grade_filter:
        lots_qs = lots_qs.filter(harvest_batch__grade=grade_filter)
    if origin_filter:
        lots_qs = lots_qs.filter(
            Q(harvest_batch__estate__location__icontains=origin_filter)
            | Q(harvest_batch__estate__owner__seller_profile__district__icontains=origin_filter)
        )
    if min_price:
        try:
            lots_qs = lots_qs.filter(base_price_per_kg__gte=Decimal(min_price))
        except Exception:
            pass
    if max_price:
        try:
            lots_qs = lots_qs.filter(base_price_per_kg__lte=Decimal(max_price))
        except Exception:
            pass

    lots = lots_qs.order_by("auction__start_time", "lot_number")

    # Get buyer's watched lot IDs for instant starred state
    watched_lot_ids = set(
        Watchlist.objects.filter(buyer=request.user).values_list("lot_id", flat=True)
    )

    context = {
        **get_buyer_context(request),
        "lots": lots,
        "watched_lot_ids": watched_lot_ids,
        "grade_filter": grade_filter,
        "origin_filter": origin_filter,
        "min_price": min_price,
        "max_price": max_price,
        "grade_choices": HarvestBatch.GRADE_CHOICES,
    }
    return render(request, "users/buyer_auctions.html", context)


# -----------------------------------------------------------------------------
# 3. Watchlist Management
# -----------------------------------------------------------------------------
@login_required
@buyer_required
def buyer_watchlist_view(request):
    watchlist_items = Watchlist.objects.filter(
        buyer=request.user
    ).select_related(
        "lot__auction", "lot__harvest_batch__estate"
    ).order_by("-created_at")

    context = {
        **get_buyer_context(request),
        "watchlist_items": watchlist_items,
    }
    return render(request, "users/buyer_watchlist.html", context)


@require_POST
@login_required
@buyer_required
def buyer_watchlist_toggle_view(request, lot_id):
    lot = get_object_or_404(Lot, pk=lot_id)
    watchlist_item = Watchlist.objects.filter(buyer=request.user, lot=lot).first()

    if watchlist_item:
        watchlist_item.delete()
        is_watched = False
        msg = f"Lot #{lot.lot_number} removed from your watchlist."
    else:
        Watchlist.objects.create(buyer=request.user, lot=lot)
        is_watched = True
        msg = f"Lot #{lot.lot_number} added to your watchlist."

    if request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", ""):
        return JsonResponse({"status": "ok", "is_watched": is_watched, "message": msg})

    messages.info(request, msg)
    return redirect(request.META.get("HTTP_REFERER", "buyer_watchlist"))


# -----------------------------------------------------------------------------
# 4. My Bids & Computed Status
# -----------------------------------------------------------------------------
@login_required
@buyer_required
def buyer_bids_view(request):
    bids = Bid.objects.filter(
        bidder=request.user
    ).select_related(
        "lot__auction", "lot__harvest_batch__estate"
    ).order_by("-timestamp")

    for b in bids:
        b.computed_status = compute_bid_status(b)

    context = {
        **get_buyer_context(request),
        "bids": bids,
    }
    return render(request, "users/buyer_bids.html", context)


# -----------------------------------------------------------------------------
# 5. Won Lots View
# -----------------------------------------------------------------------------
@login_required
@buyer_required
def buyer_won_lots_view(request):
    # Retrieve all lots marked sold that have bids
    candidate_lots = Lot.objects.filter(
        is_sold=True
    ).select_related(
        "auction", "harvest_batch__estate", "invoice"
    ).prefetch_related("bids")

    won_lots = []
    for l in candidate_lots:
        top_bid = l.bids.order_by("-amount_per_kg").first()
        if top_bid and top_bid.bidder == request.user:
            l.winning_bid = top_bid
            total_kg = l.harvest_batch.weight_kg
            price = top_bid.amount_per_kg
            l.calculated_total = round(total_kg * price, 2)
            won_lots.append(l)

    context = {
        **get_buyer_context(request),
        "won_lots": won_lots,
    }
    return render(request, "users/buyer_won_lots.html", context)


# -----------------------------------------------------------------------------
# 6. Invoices & Payments Oversight
# -----------------------------------------------------------------------------
@login_required
@buyer_required
def buyer_invoices_view(request):
    invoices = Invoice.objects.filter(
        buyer=request.user
    ).select_related(
        "lot__auction", "lot__harvest_batch__estate"
    ).order_by("-issued_at")

    total_invoices = invoices.count()
    paid_invoices = [i for i in invoices if i.status == "PAID"]
    pending_invoices = [i for i in invoices if i.status == "PENDING"]
    total_billed = sum(i.total_amount for i in invoices)
    total_paid = sum(i.total_amount for i in paid_invoices)
    total_pending = sum(i.total_amount for i in pending_invoices)

    context = {
        **get_buyer_context(request),
        "invoices": invoices,
        "total_invoices": total_invoices,
        "paid_count": len(paid_invoices),
        "pending_count": len(pending_invoices),
        "total_billed": total_billed,
        "total_paid": total_paid,
        "total_pending": total_pending,
    }
    return render(request, "users/buyer_invoices.html", context)


@login_required
@buyer_required
def buyer_invoice_pay_view(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related(
            "lot__auction",
            "lot__harvest_batch__estate__owner",
            "buyer",
        ),
        pk=pk,
        buyer=request.user,
    )

    if invoice.status == "PAID":
        messages.info(request, f"Invoice #INV-{invoice.id:05d} has already been settled and paid.")
        return redirect("buyer_invoices")

    if request.method == "POST":
        payment_method = request.POST.get("payment_method", "UPI").strip()
        custom_ref = request.POST.get("reference_id", "").strip()

        # Method-specific handling
        timestamp_str = timezone.now().strftime("%Y%m%d%H%M")
        if payment_method == "UPI":
            upi_id = request.POST.get("upi_id", "").strip()
            ref = custom_ref or f"UPI-{timestamp_str}-{invoice.id}"
            method_label = f"UPI ({upi_id})" if upi_id else "Instant UPI"
        elif payment_method == "NETBANKING":
            bank_name = request.POST.get("bank_name", "Corporate Net Banking").strip()
            ref = custom_ref or f"NB-{timestamp_str}-{invoice.id}"
            method_label = f"Net Banking ({bank_name})"
        elif payment_method == "CARD":
            card_last4 = request.POST.get("card_number", "")[-4:] or "9876"
            ref = custom_ref or f"CARD-{timestamp_str}-{invoice.id}"
            method_label = f"Card (ending in {card_last4})"
        elif payment_method == "NEFT_RTGS":
            utr = request.POST.get("utr_number", "").strip() or custom_ref
            ref = utr or f"UTR-{timestamp_str}-{invoice.id}"
            method_label = f"NEFT / RTGS Wire (UTR: {ref})"
        else:
            ref = custom_ref or f"TXN-{timestamp_str}-{invoice.id}"
            method_label = payment_method

        invoice.status = "PAID"
        invoice.paid_at = timezone.now()
        invoice.status_note = f"Settled via {method_label} | Ref: {ref}"
        invoice.save(update_fields=["status", "paid_at", "status_note"])

        # Notify Buyer
        Notification.objects.create(
            user=request.user,
            notification_type=Notification.NotificationType.INVOICE,
            link=reverse("buyer_invoices"),
            message=f"Payment of ₹{invoice.total_amount} for Lot #{invoice.lot.lot_number} (Invoice #INV-{invoice.id:05d}) confirmed.",
        )

        # Notify Seller (Grower) if present
        seller = getattr(getattr(invoice.lot.harvest_batch, "estate", None), "owner", None)
        if seller:
            Notification.objects.create(
                user=seller,
                notification_type=Notification.NotificationType.INVOICE,
                link=reverse("seller_sales_history"),
                message=f"Payment of ₹{invoice.total_amount} for Lot #{invoice.lot.lot_number} ({invoice.lot.harvest_batch.estate.name}) settled by buyer.",
            )

        messages.success(
            request,
            f"Payment of ₹{invoice.total_amount} for Invoice #INV-{invoice.id:05d} completed successfully! Your settlement receipt is ready.",
        )
        return redirect("buyer_invoices")

    # GET request - show payment checkout
    lot = invoice.lot
    harvest_batch = lot.harvest_batch
    estate = harvest_batch.estate

    subtotal = invoice.total_amount - invoice.commission_fee
    weight_kg = harvest_batch.weight_kg
    rate_per_kg = (
        lot.highest_bid_per_kg
        if lot.highest_bid_per_kg
        else (round(subtotal / weight_kg, 2) if weight_kg else Decimal("0.00"))
    )

    context = {
        **get_buyer_context(request),
        "invoice": invoice,
        "lot": lot,
        "harvest_batch": harvest_batch,
        "estate": estate,
        "subtotal": subtotal,
        "rate_per_kg": rate_per_kg,
        "weight_kg": weight_kg,
    }
    return render(request, "users/buyer_payment.html", context)


# -----------------------------------------------------------------------------
# 7. Notifications Center
# -----------------------------------------------------------------------------
@login_required
@buyer_required
def buyer_notifications_view(request):
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by("-created_at")

    context = {
        **get_buyer_context(request),
        "notifications": notifications,
    }
    return render(request, "users/buyer_notifications.html", context)


@require_POST
@login_required
def mark_all_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect(request.META.get("HTTP_REFERER", "home"))
