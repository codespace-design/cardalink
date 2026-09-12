from __future__ import annotations

from datetime import datetime, timedelta
import functools
from typing import TYPE_CHECKING

from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.password_validation import validate_password
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from carda_link.users.sms import generate_otp
from carda_link.users.sms import normalize_phone_number
from carda_link.users.sms import send_sms_otp

from django.urls import reverse
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView
from django.views.generic import RedirectView
from django.views.generic import UpdateView

from carda_link.users.forms import BuyerProfileForm
from carda_link.users.forms import BuyerSignupForm
from carda_link.users.forms import SellerProfileForm
from carda_link.users.forms import SellerSignupForm
from carda_link.auctions.models import Auction
from carda_link.auctions.models import Bid
from carda_link.auctions.models import Lot
from carda_link.estates.models import Estate
from carda_link.estates.models import HarvestBatch
from carda_link.users.models import BuyerProfile
from carda_link.users.models import SellerProfile
from carda_link.users.models import User
from carda_link.users.models import AdminActionLog
from carda_link.users.models import log_admin_action

if TYPE_CHECKING:
    from django.db.models import QuerySet


class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    slug_field = "id"
    slug_url_kwarg = "id"


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    fields = ["name"]
    success_message = _("Information successfully updated")

    def get_success_url(self) -> str:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user.get_absolute_url()

    def get_object(self, queryset: QuerySet | None = None) -> User:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user


user_update_view = UserUpdateView.as_view()


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self) -> str:
        user = self.request.user
        if user.role == "ADMIN" or user.is_staff or user.is_superuser:
            return reverse("admin_dashboard")
        if user.role == "SELLER":
            return reverse("seller_dashboard")
        if user.role == "BUYER":
            return reverse("buyer_dashboard")
        return reverse("admin_dashboard" if user.is_staff else "home")


user_redirect_view = UserRedirectView.as_view()


# Phase 1 Testing Views


def home_view(request):
    login_error = None
    login_email = ""

    if request.method == "POST":
        login_email = request.POST.get("login", "").strip()
        password = request.POST.get("password", "")
        remember = request.POST.get("remember")

        user = authenticate(request, username=login_email, password=password)
        if user is not None:
            if user.status == User.Status.PENDING:
                login_error = "Your account has not yet been approved by the administrator. Please wait for admin approval."
            elif user.status == User.Status.REJECTED:
                login_error = "Your registration has been rejected by the administrator."
            elif user.status == User.Status.SUSPENDED:
                login_error = "Your account has been suspended. Please contact the administrator."
            else:
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                if not remember:
                    request.session.set_expiry(0)

                next_url = request.POST.get("next") or request.GET.get("next")
                if next_url:
                    return redirect(next_url)

                if user.role == User.Role.ADMIN or user.is_staff or user.is_superuser:
                    return redirect("admin_dashboard")
                elif user.role == User.Role.SELLER:
                    return redirect("seller_dashboard")
                elif user.role == User.Role.BUYER:
                    return redirect("buyer_dashboard")
                return redirect("home")
        else:
            # When status is PENDING/REJECTED/SUSPENDED, is_active is False so ModelBackend.authenticate returns None.
            # Check if user exists and password is correct to display the accurate, professional status message.
            existing_user = User.objects.filter(email__iexact=login_email).first()
            if existing_user and existing_user.check_password(password):
                if existing_user.status == User.Status.PENDING:
                    login_error = "Your account has not yet been approved by the administrator. Please wait for admin approval."
                elif existing_user.status == User.Status.REJECTED:
                    login_error = "Your registration has been rejected by the administrator."
                elif existing_user.status == User.Status.SUSPENDED:
                    login_error = "Your account has been suspended. Please contact the administrator."
                else:
                    login_error = "Your account is currently inactive. Please contact the administrator."
            else:
                login_error = "The email address and/or password you specified are not correct."

    return render(
        request,
        "pages/home.html",
        {
            "login_error": login_error,
            "login_email": login_email,
        },
    )


def signup_selection_view(request):
    return render(request, "users/signup.html")


def seller_signup_view(request):
    if request.method == "POST":
        form = SellerSignupForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, "users/seller_signup.html", {"success": True})
    else:
        form = SellerSignupForm()
    return render(request, "users/seller_signup.html", {"form": form})


def buyer_signup_view(request):
    if request.method == "POST":
        form = BuyerSignupForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, "users/buyer_signup.html", {"success": True})
    else:
        form = BuyerSignupForm()
    return render(request, "users/buyer_signup.html", {"form": form})


def admin_users_view(request):
    users = User.objects.all().order_by("-created_at")
    return render(request, "users/admin_users.html", {"users": users})


# Phase 3 Admin & Registration Views


def admin_required(view_func):
    @functools.wraps(view_func)
    @never_cache
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")
        is_admin = (
            request.user.role == "ADMIN"
            or request.user.is_staff
            or request.user.is_superuser
        )
        is_active = (
            request.user.status == "ACTIVE"
            or request.user.is_superuser
            or request.user.is_staff
        )
        if not is_admin or not is_active:
            raise PermissionDenied("Only active administrators can access this page.")
        response = view_func(request, *args, **kwargs)
        if hasattr(response, "__getitem__"):
            response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response

    return _wrapped_view


def admin_login_view(request):
    """Admin login is unified on the primary landing page; GET redirects to home, POST supports auth."""
    if request.method == "POST":
        email = request.POST.get("email") or request.POST.get("login")
        password = request.POST.get("password")
        user = authenticate(request, username=email, password=password)
        if user is not None:
            if user.role == User.Role.ADMIN or user.is_staff or user.is_superuser:
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                return redirect("admin_dashboard")
            from django.http import HttpResponse
            return HttpResponse("Only administrators can log in here.", status=200)
        from django.http import HttpResponse
        return HttpResponse("Invalid email or password.", status=200)
    return redirect("home")


@never_cache
def admin_logout_view(request):
    """Securely terminates administrator session, invalidates cookies, records audit log, and clears cache."""
    if request.user.is_authenticated:
        user = request.user
        if getattr(user, "role", None) == "ADMIN" or user.is_staff or user.is_superuser:
            try:
                log_admin_action(user, "ADMIN_LOGOUT", user, f"Administrator {user.email} securely signed out.")
            except Exception:
                pass
        logout(request)
        request.session.flush()
        messages.info(request, "You have been securely signed out.")

    response = redirect("home")
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


@admin_required
def admin_dashboard_view(request):
    total_users = User.objects.all().count()
    pending_users = User.objects.filter(status="PENDING").count()
    active_users = User.objects.filter(status="ACTIVE").count()
    rejected_users = User.objects.filter(status="REJECTED").count()
    suspended_users = User.objects.filter(status="SUSPENDED").count()

    total_estates = Estate.objects.count()
    total_harvests = HarvestBatch.objects.count()
    active_auctions = Auction.objects.filter(status="ACTIVE").count()
    upcoming_auctions = Auction.objects.filter(status="UPCOMING").count()

    context = {
        "total_users": total_users,
        "pending_users": pending_users,
        "active_users": active_users,
        "rejected_users": rejected_users,
        "suspended_users": suspended_users,
        "total_estates": total_estates,
        "total_harvests": total_harvests,
        "active_auctions": active_auctions,
        "upcoming_auctions": upcoming_auctions,
    }
    return render(request, "users/admin_dashboard.html", context)


@admin_required
def admin_pending_registrations_view(request):
    users = User.objects.filter(status="PENDING").order_by("-created_at")
    return render(request, "users/admin_pending_registrations.html", {"users": users})


@admin_required
def admin_all_users_view(request):
    users = User.objects.all().order_by("-created_at")
    return render(request, "users/admin_all_users.html", {"users": users})


@admin_required
def admin_active_users_view(request):
    users = User.objects.filter(status="ACTIVE").order_by("-created_at")
    return render(request, "users/admin_active_users.html", {"users": users})


@admin_required
def admin_rejected_users_view(request):
    users = User.objects.filter(status="REJECTED").order_by("-created_at")
    return render(request, "users/admin_rejected_users.html", {"users": users})


@admin_required
def admin_suspended_users_view(request):
    users = User.objects.filter(status="SUSPENDED").order_by("-created_at")
    return render(request, "users/admin_suspended_users.html", {"users": users})


@admin_required
def admin_user_detail_view(request, pk):
    user = get_object_or_404(User, pk=pk)

    profile = None
    if user.role == "SELLER" and hasattr(user, "seller_profile"):
        profile = user.seller_profile
    elif user.role == "BUYER" and hasattr(user, "buyer_profile"):
        profile = user.buyer_profile

    context = {
        "target_user": user,
        "profile": profile,
    }
    return render(request, "users/admin_user_detail.html", context)


@admin_required
def admin_user_approve_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.status == "PENDING":
        user.status = "ACTIVE"
        user.save()
        messages.success(
            request,
            "Registration approved successfully. The account is now ACTIVE.",
        )
    return redirect("admin_pending_registrations")


@admin_required
def admin_user_reject_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.status == "PENDING":
        user.status = "REJECTED"
        user.save()
        messages.success(request, "Registration rejected.")
    return redirect("admin_pending_registrations")


@admin_required
def admin_user_suspend_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.status == "ACTIVE":
        user.status = "SUSPENDED"
        user.save()
        messages.success(request, "Account has been suspended.")
    return redirect("admin_active_users")


@admin_required
def admin_user_reactivate_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.status == "SUSPENDED":
        user.status = "ACTIVE"
        user.save()
        messages.success(
            request,
            "Account reactivated successfully. The account is now ACTIVE.",
        )
    return redirect("admin_suspended_users")


@admin_required
def admin_estates_view(request):
    estates = Estate.objects.all().select_related("owner").prefetch_related("harvest_batches")
    return render(request, "users/admin_estates.html", {"estates": estates})


@admin_required
def admin_estate_detail_view(request, pk):
    estate = get_object_or_404(
        Estate.objects.select_related("owner").prefetch_related("harvest_batches__auction_lot", "photos"),
        pk=pk,
    )
    harvest_batches = estate.harvest_batches.all().order_by("-harvest_date")
    context = {
        "estate": estate,
        "harvest_batches": harvest_batches,
    }
    return render(request, "users/admin_estate_detail.html", context)


@admin_required
def admin_harvest_grade_update_view(request, pk):
    batch = get_object_or_404(HarvestBatch, pk=pk)
    if request.method == "POST":
        grade = request.POST.get("grade")
        valid_grades = [choice[0] for choice in HarvestBatch.GRADE_CHOICES]
        if grade in valid_grades:
            batch.grade = grade
            batch.save(update_fields=["grade"])
            messages.success(
                request,
                f"Quality grade updated to {batch.get_grade_display()} for Harvest Batch #{batch.pk}.",
            )
        else:
            messages.error(request, "Invalid grade selected.")
    return redirect("admin_estate_detail", pk=batch.estate.pk)


@admin_required
def admin_auctions_view(request):
    auctions = Auction.objects.all().prefetch_related("lots")
    for a in auctions:
        a.sold_lots_count = sum(1 for lot in a.lots.all() if lot.is_sold)
    return render(request, "users/admin_auctions.html", {"auctions": auctions})


@admin_required
def admin_auction_detail_view(request, pk):
    auction = get_object_or_404(
        Auction.objects.prefetch_related("lots__harvest_batch__estate", "lots__bids"),
        pk=pk,
    )
    lots = auction.lots.all()
    total_lots_cataloged = lots.count()
    sold_lots_count = sum(1 for lot in lots if lot.is_sold)
    context = {
        "auction": auction,
        "lots": lots,
        "total_lots_cataloged": total_lots_cataloged,
        "sold_lots_count": sold_lots_count,
    }
    return render(request, "users/admin_auction_detail.html", context)


# Phase 2 Profile Views

from django.contrib.auth.decorators import login_required


@login_required
def seller_profile_view(request):
    if request.user.role != User.Role.SELLER:
        raise PermissionDenied("Only sellers can access this page.")

    profile, created = SellerProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "farm_name": "",
            "farm_location": "",
            "farm_area": 0,
            "area_unit": SellerProfile.AreaUnit.ACRE,
            "cardamom_plants": 0,
            "cultivation_details": "",
        },
    )
    return render(request, "users/seller_profile.html", {"profile": profile})


@login_required
def seller_profile_edit_view(request):
    if request.user.role != User.Role.SELLER:
        raise PermissionDenied("Only sellers can edit this page.")

    profile, created = SellerProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "farm_name": "",
            "farm_location": "",
            "farm_area": 0,
            "area_unit": SellerProfile.AreaUnit.ACRE,
            "cardamom_plants": 0,
            "cultivation_details": "",
        },
    )

    if request.method == "POST":
        form = SellerProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("seller_profile")
    else:
        form = SellerProfileForm(instance=profile)
    return render(
        request,
        "users/seller_profile_edit.html",
        {"form": form, "profile": profile},
    )


@login_required
def buyer_profile_view(request):
    if request.user.role != User.Role.BUYER:
        raise PermissionDenied("Only buyers can access this page.")

    profile, created = BuyerProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "company_name": "",
            "business_type": "",
            "business_address": "",
            "business_details": "",
        },
    )
    return render(request, "users/buyer_profile.html", {"profile": profile})


@login_required
def buyer_profile_edit_view(request):
    if request.user.role != User.Role.BUYER:
        raise PermissionDenied("Only buyers can edit this page.")

    profile, created = BuyerProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "company_name": "",
            "business_type": "",
            "business_address": "",
            "business_details": "",
        },
    )

    if request.method == "POST":
        form = BuyerProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("buyer_profile")
    else:
        form = BuyerProfileForm(instance=profile)
    return render(
        request,
        "users/buyer_profile_edit.html",
        {"form": form, "profile": profile},
    )


# Phase 4 Dashboard Views


def seller_required(view_func):
    @functools.wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if (
            not request.user.is_authenticated
            or request.user.role != "SELLER"
            or request.user.status != "ACTIVE"
        ):
            raise PermissionDenied("Only active sellers can access this page.")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def buyer_required(view_func):
    @functools.wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if (
            not request.user.is_authenticated
            or request.user.role != "BUYER"
            or request.user.status != "ACTIVE"
        ):
            raise PermissionDenied("Only active buyers can access this page.")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


@seller_required
def seller_dashboard_view(request):
    estates = Estate.objects.filter(owner=request.user).prefetch_related("harvest_batches__auction_lot")
    estates_count = estates.count()
    total_acres = sum(e.area_in_acres for e in estates)
    harvest_batches = (
        HarvestBatch.objects.filter(estate__owner=request.user)
        .select_related("estate", "auction_lot__auction")
        .order_by("-harvest_date")
    )
    harvests_count = harvest_batches.count()
    total_harvest_kg = sum(b.weight_kg for b in harvest_batches)
    recent_harvests = harvest_batches[:10]

    context = {
        "estates": estates,
        "estates_count": estates_count,
        "total_acres": total_acres,
        "harvests_count": harvests_count,
        "total_harvest_kg": total_harvest_kg,
        "recent_harvests": recent_harvests,
    }
    return render(request, "users/seller_dashboard.html", context)


@buyer_required
def buyer_dashboard_view(request):
    auctions = (
        Auction.objects.filter(status__in=["ACTIVE", "UPCOMING"])
        .prefetch_related("lots")
        .order_by("start_time")
    )
    active_auctions_count = Auction.objects.filter(status="ACTIVE").count()
    upcoming_auctions_count = Auction.objects.filter(status="UPCOMING").count()

    user_bids = Bid.objects.filter(bidder=request.user).order_by("-timestamp")
    user_bids_count = user_bids.count()
    recent_bids = user_bids.select_related("lot__auction", "lot__harvest_batch")[:10]

    won_lots = (
        Lot.objects.filter(is_sold=True, bids__bidder=request.user)
        .distinct()
        .prefetch_related("bids")
    )
    won_lots_count = sum(
        1
        for lot in won_lots
        if lot.highest_bid_per_kg
        and user_bids.filter(lot=lot, amount_per_kg=lot.highest_bid_per_kg).exists()
    )

    context = {
        "auctions": auctions,
        "active_auctions_count": active_auctions_count,
        "upcoming_auctions_count": upcoming_auctions_count,
        "user_bids_count": user_bids_count,
        "recent_bids": recent_bids,
        "won_lots_count": won_lots_count,
    }
    return render(request, "users/buyer_dashboard.html", context)


# ==============================================================================
# Mobile SMS OTP Password Recovery Workflow
# ==============================================================================


def mobile_password_reset_view(request):
    """Step 1: Request OTP by entering registered Mobile Number or Email."""
    error = None

    if request.method == "POST":
        query = request.POST.get("email_or_phone", "").strip() or request.POST.get("email", "").strip()
        if not query:
            error = "Please enter your registered mobile number or email address."
        else:
            user = None
            clean_phone = normalize_phone_number(query)
            if clean_phone and len(clean_phone) >= 10:
                user = User.objects.filter(phone_number__endswith=clean_phone).first()

            if not user:
                user = User.objects.filter(email__iexact=query).first()

            if not user:
                error = "No CardaLink account is registered with this mobile number or email. Please verify your details or sign up."
            else:
                phone_to_use = user.phone_number
                if not phone_to_use:
                    if clean_phone and len(clean_phone) >= 10:
                        phone_to_use = clean_phone
                        user.phone_number = clean_phone
                        user.save(update_fields=["phone_number"])
                    else:
                        phone_to_use = "9876543210"

                otp = generate_otp()
                dispatch_result = send_sms_otp(phone_to_use, otp)

                request.session["otp_user_id"] = user.id
                request.session["otp_phone"] = phone_to_use
                request.session["otp_code"] = otp
                request.session["otp_expiry"] = (datetime.now() + timedelta(minutes=10)).timestamp()
                request.session["otp_attempts"] = 0
                if dispatch_result.get("demo_otp"):
                    request.session["otp_demo"] = dispatch_result["demo_otp"]
                else:
                    request.session.pop("otp_demo", None)

                return redirect("account_verify_otp")

    return render(request, "account/password_reset.html", {"error": error})


def mobile_verify_otp_view(request):
    """Step 2: Enter and verify 6-digit OTP code received via SMS."""
    user_id = request.session.get("otp_user_id")
    expected_otp = request.session.get("otp_code")
    expiry = request.session.get("otp_expiry", 0)
    phone = request.session.get("otp_phone", "")
    demo_otp = request.session.get("otp_demo", "")

    if not user_id or not expected_otp:
        messages.error(request, "Session expired. Please request a new verification code.")
        return redirect("account_reset_password")

    if datetime.now().timestamp() > expiry:
        messages.error(request, "Your verification code has expired. Please request a new code.")
        return redirect("account_reset_password")

    error = None
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "resend":
            new_otp = generate_otp()
            dispatch_result = send_sms_otp(phone, new_otp)
            request.session["otp_code"] = new_otp
            request.session["otp_expiry"] = (datetime.now() + timedelta(minutes=10)).timestamp()
            request.session["otp_attempts"] = 0
            if dispatch_result.get("demo_otp"):
                request.session["otp_demo"] = dispatch_result["demo_otp"]
                demo_otp = dispatch_result["demo_otp"]
            messages.success(request, "A new 6-digit verification code has been dispatched to your mobile number.")
            return redirect("account_verify_otp")

        entered_otp = request.POST.get("otp", "").strip()
        if not entered_otp:
            error = "Please enter the 6-digit verification code."
        elif entered_otp == expected_otp:
            request.session["otp_verified"] = True
            return redirect("account_set_password")
        else:
            attempts = request.session.get("otp_attempts", 0) + 1
            request.session["otp_attempts"] = attempts
            if attempts >= 5:
                request.session.flush()
                messages.error(request, "Too many failed attempts. Please restart password recovery.")
                return redirect("account_reset_password")
            error = f"Invalid verification code. {5 - attempts} attempts remaining."

    clean_p = normalize_phone_number(phone)
    masked_phone = f"+91 ******{clean_p[-4:]}" if len(clean_p) >= 4 else phone

    context = {
        "phone": phone,
        "masked_phone": masked_phone,
        "error": error,
        "demo_otp": demo_otp,
    }
    return render(request, "account/verify_otp.html", context)


def mobile_set_password_view(request):
    """Step 3: Set and confirm new password after successful OTP verification."""
    if not request.session.get("otp_verified") or not request.session.get("otp_user_id"):
        messages.error(request, "Please verify your mobile number first.")
        return redirect("account_reset_password")

    user_id = request.session["otp_user_id"]
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "User account not found.")
        return redirect("account_reset_password")

    error = None
    if request.method == "POST":
        p1 = request.POST.get("password1", "").strip()
        p2 = request.POST.get("password2", "").strip()

        if not p1 or not p2:
            error = "Please enter and confirm your new password."
        elif p1 != p2:
            error = "Passwords do not match. Please re-enter."
        else:
            try:
                validate_password(p1, user=user)
                user.set_password(p1)
                user.save()
                for key in [
                    "otp_user_id",
                    "otp_phone",
                    "otp_code",
                    "otp_expiry",
                    "otp_attempts",
                    "otp_verified",
                    "otp_demo",
                ]:
                    request.session.pop(key, None)
                messages.success(request, "Your password has been successfully updated! You can now sign in.")
                return redirect("home")
            except ValidationError as e:
                error = " ".join(e.messages)

    return render(request, "account/password_reset_from_key.html", {"error": error})

