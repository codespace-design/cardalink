from decimal import Decimal
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from carda_link.auctions.models import Auction, Bid, Lot
from carda_link.auctions.services import close_auction
from carda_link.estates.models import Estate, HarvestBatch
from carda_link.invoicing.models import Invoice, PlatformSettings
from carda_link.users.admin_forms import (
    AdminManualUserCreationForm,
    AuctionScheduleForm,
    PlatformSettingsForm,
)
from carda_link.users.decorators import is_admin_user
from carda_link.users.models import AdminActionLog, User, log_admin_action


# -----------------------------------------------------------------------------
# 1. Admin Dashboard Overview
# -----------------------------------------------------------------------------

@is_admin_user
def admin_dashboard_view(request):
    total_users = User.objects.count()
    pending_users = User.objects.filter(status=User.Status.PENDING).count()
    active_users = User.objects.filter(status=User.Status.ACTIVE).count()
    rejected_users = User.objects.filter(status=User.Status.REJECTED).count()
    suspended_users = User.objects.filter(status=User.Status.SUSPENDED).count()

    total_estates = Estate.objects.count()
    ungraded_batches = HarvestBatch.objects.filter(grade="UNGRADED", is_rejected=False).count()

    active_auctions = Auction.objects.filter(status="ACTIVE").count()
    upcoming_auctions = Auction.objects.filter(status="UPCOMING").count()

    pending_invoices = Invoice.objects.filter(status="PENDING").count()
    recent_logs = AdminActionLog.objects.select_related("admin_user").all()[:10]

    context = {
        "total_users": total_users,
        "pending_users": pending_users,
        "active_users": active_users,
        "rejected_users": rejected_users,
        "suspended_users": suspended_users,
        "total_estates": total_estates,
        "ungraded_batches": ungraded_batches,
        "active_auctions": active_auctions,
        "upcoming_auctions": upcoming_auctions,
        "pending_invoices": pending_invoices,
        "recent_logs": recent_logs,
    }
    return render(request, "users/admin_dashboard.html", context)


# -----------------------------------------------------------------------------
# 2. User Management Views
# -----------------------------------------------------------------------------

@is_admin_user
def admin_users_pending_view(request):
    pending_qs = (
        User.objects.filter(status=User.Status.PENDING)
        .select_related("seller_profile", "buyer_profile")
        .order_by("-date_joined")
    )
    paginator = Paginator(pending_qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "users/admin_pending_registrations.html", {
        "page_obj": page_obj,
        "users": page_obj.object_list,
    })


@is_admin_user
def admin_all_users_view(request):
    role_filter = request.GET.get("role", "").strip()
    status_filter = request.GET.get("status", "").strip()
    search_query = request.GET.get("q", "").strip()

    qs = User.objects.select_related("seller_profile", "buyer_profile").order_by("-date_joined")
    if role_filter:
        qs = qs.filter(role=role_filter)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if search_query:
        qs = qs.filter(
            Q(email__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(phone_number__icontains=search_query)
            | Q(license_number__icontains=search_query)
        )

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "users/admin_all_users.html", {
        "page_obj": page_obj,
        "users": page_obj.object_list,
        "role_filter": role_filter,
        "status_filter": status_filter,
        "search_query": search_query,
        "roles": User.Role.choices,
        "statuses": User.Status.choices,
    })


@is_admin_user
def admin_user_detail_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    profile = None
    if target_user.role == User.Role.SELLER and hasattr(target_user, "seller_profile"):
        profile = target_user.seller_profile
    elif target_user.role == User.Role.BUYER and hasattr(target_user, "buyer_profile"):
        profile = target_user.buyer_profile

    # Fetch estates and batches if seller
    estates = target_user.estates.prefetch_related("harvest_batches").all() if target_user.role == User.Role.SELLER else []
    invoices = target_user.invoices.select_related("lot").all() if target_user.role == User.Role.BUYER else []

    # Audit history for this target
    action_logs = AdminActionLog.objects.filter(target_model="User", target_id=str(target_user.pk)).select_related("admin_user")

    context = {
        "target_user": target_user,
        "profile": profile,
        "estates": estates,
        "invoices": invoices,
        "action_logs": action_logs,
    }
    return render(request, "users/admin_user_detail.html", context)


@is_admin_user
def admin_user_approve_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    target_user.status = User.Status.ACTIVE
    target_user.is_verified = True
    target_user.rejection_reason = ""
    target_user.save(update_fields=["status", "is_verified", "rejection_reason"])

    log_admin_action(
        admin_user=request.user,
        action="APPROVE_USER",
        target=target_user,
        reason="Registration approved by administrator.",
    )
    # Stub notification call
    # send_sms_notification(target_user.phone_number, "Your CardaLink account has been approved.")
    messages.success(request, f"User {target_user.email} has been approved and activated.")
    return redirect(request.META.get("HTTP_REFERER") or "admin_pending_registrations")


@is_admin_user
def admin_user_reject_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    reason = (request.POST.get("reason") or request.GET.get("reason") or "").strip()
    if request.method == "POST" and not reason:
        messages.error(request, "A reason is mandatory when rejecting a user registration.")
        return redirect(request.META.get("HTTP_REFERER") or "admin_pending_registrations")

    if not reason:
        reason = "Registration rejected by administrator."

    target_user.status = User.Status.REJECTED
    target_user.rejection_reason = reason
    target_user.save(update_fields=["status", "rejection_reason"])

    log_admin_action(
        admin_user=request.user,
        action="REJECT_USER",
        target=target_user,
        reason=reason,
    )
    messages.warning(request, f"User {target_user.email} was rejected. Reason: {reason}")
    return redirect(request.META.get("HTTP_REFERER") or "admin_pending_registrations")


@is_admin_user
def admin_user_suspend_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    reason = (request.POST.get("reason") or request.GET.get("reason") or "").strip()
    if request.method == "POST" and not reason:
        messages.error(request, "A reason is mandatory when suspending an account.")
        return redirect(request.META.get("HTTP_REFERER") or "admin_all_users")

    if not reason:
        reason = "Account suspended by administrator."

    target_user.status = User.Status.SUSPENDED
    target_user.suspension_reason = reason
    target_user.save(update_fields=["status", "suspension_reason"])

    log_admin_action(
        admin_user=request.user,
        action="SUSPEND_USER",
        target=target_user,
        reason=reason,
    )
    messages.warning(request, f"Account {target_user.email} has been suspended.")
    return redirect(request.META.get("HTTP_REFERER") or "admin_all_users")


@is_admin_user
def admin_user_reactivate_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    target_user.status = User.Status.ACTIVE
    target_user.suspension_reason = ""
    target_user.save(update_fields=["status", "suspension_reason"])

    log_admin_action(
        admin_user=request.user,
        action="REACTIVATE_USER",
        target=target_user,
        reason="Account reactivated by administrator.",
    )
    messages.success(request, f"Account {target_user.email} has been reactivated.")
    return redirect(request.META.get("HTTP_REFERER") or "admin_all_users")


@is_admin_user
def admin_user_create_view(request):
    if request.method == "POST":
        form = AdminManualUserCreationForm(request.POST)
        if form.is_valid():
            created_user = form.save()
            log_admin_action(
                admin_user=request.user,
                action="MANUAL_CREATE_USER",
                target=created_user,
                reason=f"Manually created {created_user.role} account.",
            )
            messages.success(request, f"User {created_user.email} successfully created and activated.")
            return redirect("admin_user_detail", pk=created_user.pk)
    else:
        form = AdminManualUserCreationForm()

    return render(request, "users/admin_user_create.html", {"form": form})


# -----------------------------------------------------------------------------
# 3. Auction Scheduling & Operations
# -----------------------------------------------------------------------------

@is_admin_user
def admin_auctions_list_view(request):
    status_filter = request.GET.get("status", "").strip()
    auctions = Auction.objects.prefetch_related("lots").all()

    if status_filter:
        auctions = auctions.filter(status=status_filter)

    auctions = auctions.order_by("-start_time")

    paginator = Paginator(auctions, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "users/admin_auctions.html", {
        "page_obj": page_obj,
        "auctions": page_obj.object_list,
        "status_filter": status_filter,
        "status_choices": Auction.STATUS_CHOICES,
    })


@is_admin_user
def admin_auction_create_view(request):
    if request.method == "POST":
        form = AuctionScheduleForm(request.POST)
        if form.is_valid():
            auction = form.save()
            log_admin_action(
                admin_user=request.user,
                action="CREATE_AUCTION",
                target=auction,
                reason=f"Scheduled auction '{auction.title}'",
            )
            messages.success(request, f"Auction '{auction.title}' scheduled successfully.")
            return redirect("admin_auction_detail", pk=auction.pk)
    else:
        form = AuctionScheduleForm()

    return render(request, "users/admin_auction_form.html", {
        "form": form,
        "is_create": True,
    })


@is_admin_user
def admin_auction_edit_view(request, pk):
    auction = get_object_or_404(Auction, pk=pk)
    if auction.status != "UPCOMING":
        raise PermissionDenied("Only UPCOMING auctions can be modified.")

    if request.method == "POST":
        form = AuctionScheduleForm(request.POST, instance=auction)
        if form.is_valid():
            auction = form.save()
            log_admin_action(
                admin_user=request.user,
                action="EDIT_AUCTION",
                target=auction,
                reason=f"Updated auction details for '{auction.title}'",
            )
            messages.success(request, f"Auction '{auction.title}' updated successfully.")
            return redirect("admin_auction_detail", pk=auction.pk)
    else:
        form = AuctionScheduleForm(instance=auction)

    return render(request, "users/admin_auction_form.html", {
        "form": form,
        "auction": auction,
        "is_create": False,
    })


@require_POST
@is_admin_user
def admin_auction_cancel_view(request, pk):
    auction = get_object_or_404(Auction, pk=pk)
    if auction.status != "UPCOMING":
        messages.error(request, "Only UPCOMING auctions can be cancelled.")
        return redirect("admin_auction_detail", pk=auction.pk)

    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "A cancellation reason is required.")
        return redirect("admin_auction_detail", pk=auction.pk)

    auction.status = "CANCELLED"
    auction.cancellation_reason = reason
    auction.save(update_fields=["status", "cancellation_reason"])

    log_admin_action(
        admin_user=request.user,
        action="CANCEL_AUCTION",
        target=auction,
        reason=reason,
    )
    messages.warning(request, f"Auction '{auction.title}' has been cancelled.")
    return redirect("admin_auction_detail", pk=auction.pk)


@require_POST
@is_admin_user
def admin_auction_force_close_view(request, pk):
    auction = get_object_or_404(Auction, pk=pk)
    if auction.status != "ACTIVE":
        messages.error(request, "Emergency force-close is only permitted for ACTIVE auctions.")
        return redirect("admin_auction_detail", pk=auction.pk)

    close_auction(auction)

    log_admin_action(
        admin_user=request.user,
        action="FORCE_CLOSE_AUCTION",
        target=auction,
        reason="Manual emergency auction close executed by administrator.",
    )
    messages.success(request, f"Auction '{auction.title}' was force-closed. Winning lots and invoices generated.")
    return redirect("admin_auction_detail", pk=auction.pk)


@is_admin_user
def admin_auction_detail_view(request, pk):
    auction = get_object_or_404(
        Auction.objects.prefetch_related("lots__harvest_batch__estate__owner", "lots__bids__bidder"),
        pk=pk,
    )
    lots = auction.lots.all()
    action_logs = AdminActionLog.objects.filter(target_model="Auction", target_id=str(auction.pk))

    context = {
        "auction": auction,
        "lots": lots,
        "action_logs": action_logs,
    }
    return render(request, "users/admin_auction_detail.html", context)


# -----------------------------------------------------------------------------
# 4. Lot Assignment (Batch -> Auction)
# -----------------------------------------------------------------------------

@is_admin_user
def admin_auction_lots_add_view(request, pk):
    auction = get_object_or_404(Auction, pk=pk)
    if auction.status != "UPCOMING":
        messages.error(request, "Lots can only be added to UPCOMING auctions.")
        return redirect("admin_auction_detail", pk=auction.pk)

    # Eligible batches: graded (not UNGRADED), not rejected, not already in an active or upcoming auction
    assigned_batch_ids = Lot.objects.filter(
        auction__status__in=["UPCOMING", "ACTIVE"]
    ).values_list("harvest_batch_id", flat=True)

    eligible_batches = (
        HarvestBatch.objects.exclude(grade="UNGRADED")
        .filter(is_rejected=False)
        .exclude(id__in=assigned_batch_ids)
        .select_related("estate__owner")
        .order_by("-created_at")
    )

    if request.method == "POST":
        batch_ids = request.POST.getlist("batch_ids")
        if not batch_ids:
            messages.error(request, "Please select at least one harvest batch to assign.")
            return redirect("admin_auction_lots_add", pk=auction.pk)

        # Get next lot number
        current_max = Lot.objects.filter(auction=auction).order_by("-lot_number").values_list("lot_number", flat=True).first() or 0
        next_lot_num = current_max + 1

        added_count = 0
        with transaction.atomic():
            for b_id in batch_ids:
                batch = get_object_or_404(HarvestBatch, pk=b_id)
                # Check base price and lot number per selection
                base_price_raw = request.POST.get(f"base_price_{b_id}", "").strip()
                custom_lot_num = request.POST.get(f"lot_number_{b_id}", "").strip()

                try:
                    base_price = Decimal(base_price_raw) if base_price_raw else Decimal("1000.00")
                except Exception:
                    base_price = Decimal("1000.00")

                lot_number = int(custom_lot_num) if custom_lot_num.isdigit() else next_lot_num
                next_lot_num = max(next_lot_num + 1, lot_number + 1)

                lot = Lot.objects.create(
                    auction=auction,
                    harvest_batch=batch,
                    lot_number=lot_number,
                    base_price_per_kg=base_price,
                )
                added_count += 1
                log_admin_action(
                    admin_user=request.user,
                    action="ADD_LOT",
                    target=lot,
                    reason=f"Assigned batch #{batch.id} as Lot #{lot.lot_number} to Auction #{auction.id}",
                )

        messages.success(request, f"Successfully assigned {added_count} lot(s) to '{auction.title}'.")
        return redirect("admin_auction_detail", pk=auction.pk)

    return render(request, "users/admin_auction_lots_add.html", {
        "auction": auction,
        "eligible_batches": eligible_batches,
    })


@require_POST
@is_admin_user
def admin_lot_remove_view(request, pk):
    lot = get_object_or_404(Lot.objects.select_related("auction"), pk=pk)
    auction = lot.auction

    if auction.status != "UPCOMING":
        messages.error(request, "Lots can only be removed from UPCOMING auctions.")
        return redirect("admin_auction_detail", pk=auction.pk)

    if lot.bids.exists():
        messages.error(request, "Cannot remove a lot that already has bids placed on it.")
        return redirect("admin_auction_detail", pk=auction.pk)

    lot_num = lot.lot_number
    log_admin_action(
        admin_user=request.user,
        action="REMOVE_LOT",
        target=lot,
        reason=f"Removed Lot #{lot_num} from Auction #{auction.id}",
    )
    lot.delete()
    messages.success(request, f"Lot #{lot_num} was removed from the auction.")
    return redirect("admin_auction_detail", pk=auction.pk)


# -----------------------------------------------------------------------------
# 5. Grade Verification Queue
# -----------------------------------------------------------------------------

@is_admin_user
def admin_batches_ungraded_view(request):
    batches = (
        HarvestBatch.objects.filter(grade="UNGRADED", is_rejected=False)
        .select_related("estate__owner")
        .order_by("-created_at")
    )
    paginator = Paginator(batches, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    grade_choices = [c for c in HarvestBatch.GRADE_CHOICES if c[0] != "UNGRADED"]

    return render(request, "users/admin_ungraded_batches.html", {
        "page_obj": page_obj,
        "batches": page_obj.object_list,
        "grade_choices": grade_choices,
    })


@require_POST
@is_admin_user
def admin_batch_grade_view(request, pk):
    batch = get_object_or_404(HarvestBatch, pk=pk)
    assigned_grade = request.POST.get("grade", "").strip()

    valid_grades = [c[0] for c in HarvestBatch.GRADE_CHOICES if c[0] != "UNGRADED"]
    if assigned_grade not in valid_grades:
        messages.error(request, "Invalid cardamom grade selection.")
        return redirect("admin_batches_ungraded")

    batch.grade = assigned_grade
    batch.is_rejected = False
    batch.rejection_reason = ""
    batch.save(update_fields=["grade", "is_rejected", "rejection_reason"])

    log_admin_action(
        admin_user=request.user,
        action="GRADE_BATCH",
        target=batch,
        reason=f"Assigned grade {assigned_grade} to batch #{batch.id}",
    )
    messages.success(request, f"Batch #{batch.id} from estate '{batch.estate.name}' graded as {assigned_grade}. Now eligible for auctions.")
    return redirect("admin_batches_ungraded")


@require_POST
@is_admin_user
def admin_batch_reject_view(request, pk):
    batch = get_object_or_404(HarvestBatch, pk=pk)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "A reason is mandatory when rejecting a harvest batch.")
        return redirect("admin_batches_ungraded")

    batch.is_rejected = True
    batch.rejection_reason = reason
    batch.save(update_fields=["is_rejected", "rejection_reason"])

    log_admin_action(
        admin_user=request.user,
        action="REJECT_BATCH",
        target=batch,
        reason=reason,
    )
    messages.warning(request, f"Batch #{batch.id} rejected. Reason: {reason}")
    return redirect("admin_batches_ungraded")


# -----------------------------------------------------------------------------
# 6. Settlement Oversight & Platform Settings
# -----------------------------------------------------------------------------

@is_admin_user
def admin_invoices_list_view(request):
    status_filter = request.GET.get("status", "").strip()
    invoices = Invoice.objects.select_related("lot__auction", "buyer", "updated_by").all()

    if status_filter:
        invoices = invoices.filter(status=status_filter)

    invoices = invoices.order_by("-issued_at")

    paginator = Paginator(invoices, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "users/admin_invoices.html", {
        "page_obj": page_obj,
        "invoices": page_obj.object_list,
        "status_filter": status_filter,
        "status_choices": Invoice.STATUS_CHOICES,
    })


@require_POST
@is_admin_user
def admin_invoice_mark_paid_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    note = request.POST.get("status_note", "").strip()

    invoice.status = "PAID"
    invoice.paid_at = timezone.now()
    invoice.updated_by = request.user
    if note:
        invoice.status_note = note
    invoice.save(update_fields=["status", "paid_at", "updated_by", "status_note"])

    log_admin_action(
        admin_user=request.user,
        action="MARK_INVOICE_PAID",
        target=invoice,
        reason=note or "Manual offline settlement marked as PAID.",
    )
    messages.success(request, f"Invoice #{invoice.id} marked as PAID.")
    return redirect("admin_invoices_list")


@require_POST
@is_admin_user
def admin_invoice_mark_failed_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    note = request.POST.get("status_note", "").strip()

    invoice.status = "FAILED"
    invoice.updated_by = request.user
    if note:
        invoice.status_note = note
    invoice.save(update_fields=["status", "updated_by", "status_note"])

    log_admin_action(
        admin_user=request.user,
        action="MARK_INVOICE_FAILED",
        target=invoice,
        reason=note or "Manual settlement override: marked as FAILED.",
    )
    messages.warning(request, f"Invoice #{invoice.id} marked as FAILED.")
    return redirect("admin_invoices_list")


@is_admin_user
def admin_platform_settings_view(request):
    settings_obj = PlatformSettings.load()

    if request.method == "POST":
        form = PlatformSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            saved_settings = form.save(commit=False)
            saved_settings.updated_by = request.user
            saved_settings.save()
            log_admin_action(
                admin_user=request.user,
                action="UPDATE_PLATFORM_SETTINGS",
                target=saved_settings,
                reason=f"Updated platform commission to {saved_settings.commission_percent}%",
            )
            messages.success(request, f"Platform commission updated to {saved_settings.commission_percent}%.")
            return redirect("admin_platform_settings")
    else:
        form = PlatformSettingsForm(instance=settings_obj)

    return render(request, "users/admin_settings.html", {
        "form": form,
        "settings_obj": settings_obj,
    })


# -----------------------------------------------------------------------------
# 7. Audit Log View
# -----------------------------------------------------------------------------

@is_admin_user
def admin_audit_logs_view(request):
    admin_id = request.GET.get("admin_user", "").strip()
    action_type = request.GET.get("action", "").strip()

    logs = AdminActionLog.objects.select_related("admin_user").all()

    if admin_id:
        logs = logs.filter(admin_user_id=admin_id)
    if action_type:
        logs = logs.filter(action=action_type)

    logs = logs.order_by("-timestamp")

    paginator = Paginator(logs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    admins = User.objects.filter(role=User.Role.ADMIN)
    distinct_actions = (
        AdminActionLog.objects.values_list("action", flat=True)
        .distinct()
        .order_by("action")
    )

    return render(request, "users/admin_logs.html", {
        "page_obj": page_obj,
        "logs": page_obj.object_list,
        "admins": admins,
        "distinct_actions": distinct_actions,
        "selected_admin": admin_id,
        "selected_action": action_type,
    })


# -----------------------------------------------------------------------------
# 8. Harvest Intake / Batch Logging (Operations)
# -----------------------------------------------------------------------------

@is_admin_user
def admin_batch_create_view(request):
    estates = Estate.objects.select_related("owner").all().order_by("name")
    selected_estate_id = request.GET.get("estate_id") or request.POST.get("estate_id")

    if request.method == "POST":
        estate_id = request.POST.get("estate_id")
        weight_kg = request.POST.get("weight_kg", "").strip()
        harvest_date = request.POST.get("harvest_date", "").strip()
        grade = request.POST.get("grade", "UNGRADED").strip()
        quality_certificate = request.FILES.get("quality_certificate")

        if not estate_id or not weight_kg or not harvest_date:
            messages.error(request, "Origin estate, harvest weight, and harvest date are required.")
        else:
            try:
                estate = Estate.objects.get(pk=estate_id)
                weight = Decimal(weight_kg)
                if weight <= 0:
                    raise ValueError("Harvest weight must be greater than 0 kg.")

                valid_grades = [c[0] for c in HarvestBatch.GRADE_CHOICES]
                assigned_grade = grade if grade in valid_grades else "UNGRADED"

                batch = HarvestBatch.objects.create(
                    estate=estate,
                    weight_kg=weight,
                    harvest_date=harvest_date,
                    grade=assigned_grade,
                    quality_certificate=quality_certificate,
                )
                log_admin_action(
                    admin_user=request.user,
                    action="LOG_HARVEST_BATCH",
                    target=batch,
                    reason=f"Logged harvest batch #{batch.id} ({weight} kg, {assigned_grade}) for estate '{estate.name}'",
                )
                messages.success(
                    request,
                    f"Harvest batch #{batch.id} ({batch.weight_kg} kg, {batch.get_grade_display()}) successfully logged for '{estate.name}'.",
                )
                return redirect("admin_estate_detail", pk=estate.pk)
            except Estate.DoesNotExist:
                messages.error(request, "Selected plantation estate does not exist.")
            except Exception as e:
                messages.error(request, f"Error saving harvest batch: {str(e)}")

    recent_batches = HarvestBatch.objects.select_related("estate", "estate__owner").order_by("-created_at")[:10]
    return render(
        request,
        "users/admin_batch_create.html",
        {
            "estates": estates,
            "selected_estate_id": int(selected_estate_id) if selected_estate_id and str(selected_estate_id).isdigit() else None,
            "recent_batches": recent_batches,
        },
    )
