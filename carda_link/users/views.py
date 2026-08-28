from __future__ import annotations

from typing import TYPE_CHECKING

import functools
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
from django.views.generic import RedirectView
from django.views.generic import UpdateView

from carda_link.users.forms import (
    BuyerSignupForm,
    SellerSignupForm,
    SellerProfileForm,
    BuyerProfileForm,
)
from carda_link.users.models import User, SellerProfile, BuyerProfile

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
        if user.role == "ADMIN":
            return reverse("admin_dashboard")
        elif user.role == "SELLER":
            return reverse("seller_dashboard")
        elif user.role == "BUYER":
            return reverse("buyer_dashboard")
        return reverse("users:detail", kwargs={"pk": user.pk})


user_redirect_view = UserRedirectView.as_view()


# Phase 1 Testing Views

def home_view(request):
    return render(request, "users/home.html")


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
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != "ADMIN" or request.user.status != "ACTIVE":
            raise PermissionDenied("Only active administrators can access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_login_view(request):
    if request.user.is_authenticated and request.user.role == "ADMIN":
        return redirect("admin_dashboard")
        
    error = None
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        user = authenticate(request, username=email, password=password)
        if user is not None:
            if user.role == "ADMIN":
                if user.status == "ACTIVE":
                    login(request, user)
                    return redirect("admin_dashboard")
                elif user.status == "PENDING":
                    error = "Your account has not yet been approved by the administrator. Please wait for admin approval."
                elif user.status == "REJECTED":
                    error = "Your registration has been rejected by the administrator."
                elif user.status == "SUSPENDED":
                    error = "Your account has been suspended. Please contact the administrator."
            else:
                error = "Access Denied: Only administrators can log in here."
        else:
            error = "Invalid email or password."
            
    return render(request, "users/admin_login.html", {"error": error})


def admin_logout_view(request):
    logout(request)
    return redirect("home")


@admin_required
def admin_dashboard_view(request):
    total_users = User.objects.all().count()
    pending_users = User.objects.filter(status="PENDING").count()
    active_users = User.objects.filter(status="ACTIVE").count()
    rejected_users = User.objects.filter(status="REJECTED").count()
    suspended_users = User.objects.filter(status="SUSPENDED").count()
    
    context = {
        "total_users": total_users,
        "pending_users": pending_users,
        "active_users": active_users,
        "rejected_users": rejected_users,
        "suspended_users": suspended_users,
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
        messages.success(request, f"Registration approved successfully. The account is now ACTIVE.")
    return redirect("admin_pending_registrations")


@admin_required
def admin_user_reject_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.status == "PENDING":
        user.status = "REJECTED"
        user.save()
        messages.success(request, f"Registration rejected.")
    return redirect("admin_pending_registrations")


@admin_required
def admin_user_suspend_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.status == "ACTIVE":
        user.status = "SUSPENDED"
        user.save()
        messages.success(request, f"Account has been suspended.")
    return redirect("admin_active_users")


@admin_required
def admin_user_reactivate_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.status == "SUSPENDED":
        user.status = "ACTIVE"
        user.save()
        messages.success(request, f"Account reactivated successfully. The account is now ACTIVE.")
    return redirect("admin_suspended_users")


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
            "cultivation_details": ""
        }
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
            "cultivation_details": ""
        }
    )
    
    if request.method == "POST":
        form = SellerProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("seller_profile")
    else:
        form = SellerProfileForm(instance=profile)
    return render(request, "users/seller_profile_edit.html", {"form": form, "profile": profile})


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
            "business_details": ""
        }
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
            "business_details": ""
        }
    )
    
    if request.method == "POST":
        form = BuyerProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("buyer_profile")
    else:
        form = BuyerProfileForm(instance=profile)
    return render(request, "users/buyer_profile_edit.html", {"form": form, "profile": profile})


# Phase 4 Dashboard Views

def seller_required(view_func):
    @functools.wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != "SELLER" or request.user.status != "ACTIVE":
            raise PermissionDenied("Only active sellers can access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def buyer_required(view_func):
    @functools.wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != "BUYER" or request.user.status != "ACTIVE":
            raise PermissionDenied("Only active buyers can access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@seller_required
def seller_dashboard_view(request):
    return render(request, "users/seller_dashboard.html")


@buyer_required
def buyer_dashboard_view(request):
    return render(request, "users/buyer_dashboard.html")



