from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.translation import gettext_lazy as _

from .forms import UserAdminChangeForm
from .forms import UserAdminCreationForm
from .models import AdminActionLog
from .models import BuyerProfile
from .models import SellerProfile
from .models import User

if settings.DJANGO_ADMIN_FORCE_ALLAUTH:
    # Force the `admin` sign in process to go through the `django-allauth` workflow:
    # https://docs.allauth.org/en/latest/common/admin.html#admin
    admin.autodiscover()
    admin.site.login = secure_admin_login(admin.site.login)  # type: ignore[method-assign]


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal Info & Profile"),
            {
                "fields": (
                    "name",
                    "phone_number",
                    "address",
                    "license_number",
                ),
            },
        ),
        (
            _("Role & Verification Status"),
            {
                "fields": (
                    "role",
                    "status",
                    "is_verified",
                    "created_by_admin",
                    "rejection_reason",
                    "suspension_reason",
                ),
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    list_display = [
        "email",
        "name",
        "role",
        "status",
        "phone_number",
        "is_verified",
        "is_superuser",
    ]
    list_filter = ["role", "status", "is_verified", "is_staff", "is_superuser"]
    search_fields = ["name", "email", "phone_number", "license_number"]
    ordering = ["id"]
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "role",
                    "status",
                    "phone_number",
                ),
            },
        ),
    )


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "farm_name",
        "farm_location",
        "farm_area",
        "area_unit",
        "cardamom_plants",
    ]
    search_fields = ["user__email", "user__name", "farm_name", "farm_location"]
    list_filter = ["area_unit"]


@admin.register(BuyerProfile)
class BuyerProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "company_name", "business_type", "business_address"]
    search_fields = ["user__email", "user__name", "company_name", "business_type"]


@admin.register(AdminActionLog)
class AdminActionLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "admin_user", "action", "target_model", "target_id", "reason"]
    list_filter = ["action", "target_model", "timestamp"]
    search_fields = ["admin_user__email", "action", "target_model", "target_id", "reason"]
    readonly_fields = ["admin_user", "action", "target_model", "target_id", "reason", "timestamp"]
