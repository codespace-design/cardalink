from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include
from django.urls import path
from django.views import defaults as default_views
from django.views.generic import TemplateView

from carda_link.users import views as user_views
from .api import api

urlpatterns = [
    path("", user_views.home_view, name="home"),
    path(
        "about/",
        TemplateView.as_view(template_name="pages/about.html"),
        name="about",
    ),
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    # User management
    path("users/", include("carda_link.users.urls", namespace="users")),
    path("auctions/", include("carda_link.auctions.urls", namespace="auctions")),
    # Mobile OTP Password Recovery
    path("accounts/password/reset/", user_views.mobile_password_reset_view, name="account_reset_password"),
    path("accounts/password/reset/verify-otp/", user_views.mobile_verify_otp_view, name="account_verify_otp"),
    path("accounts/password/reset/set-password/", user_views.mobile_set_password_view, name="account_set_password"),
    path("accounts/login/", user_views.home_view, name="account_login"),
    path("accounts/", include("allauth.urls")),
    # Estates management
    path("estates/", include("carda_link.estates.urls", namespace="estates")),
    # AI Assistant
    path("assistant/", include("carda_link.assistant.urls")),
    # Role Selection & Registration
    path("signup/", user_views.signup_selection_view, name="signup"),
    path("register/", user_views.signup_selection_view, name="register"),
    path("signup-selection/", user_views.signup_selection_view, name="signup_selection"),
    path("signup/seller/", user_views.seller_signup_view, name="seller_signup"),
    path("signup/buyer/", user_views.buyer_signup_view, name="buyer_signup"),
    path("register/seller/", user_views.seller_signup_view),
    path("register/buyer/", user_views.buyer_signup_view),
    # Dashboard Routes (supports both /seller-dashboard/ and /seller/dashboard/)
    path("seller-dashboard/", user_views.seller_dashboard_view, name="seller_dashboard"),
    path("seller/dashboard/", user_views.seller_dashboard_view),
    path("seller/profile/", user_views.seller_profile_view, name="seller_profile"),
    path("seller/profile/edit/", user_views.seller_profile_edit_view, name="seller_profile_edit"),
    path("buyer-dashboard/", user_views.buyer_dashboard_view, name="buyer_dashboard"),
    path("buyer/dashboard/", user_views.buyer_dashboard_view),
    path("buyer/profile/", user_views.buyer_profile_view, name="buyer_profile"),
    path("buyer/profile/edit/", user_views.buyer_profile_edit_view, name="buyer_profile_edit"),
    # Admin Portal (all admin routes live under /admin-dashboard/)
    path("admin-dashboard/", include("carda_link.users.admin_urls")),
    path("admin-dashboard/logout/", user_views.admin_logout_view, name="admin_logout"),
    path("portal/admin/logout/", user_views.admin_logout_view),
    path("portal/admin/login/", user_views.admin_login_view, name="admin_login"),
    path("admin-users/", user_views.admin_users_view, name="admin_users"),
    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]


# API URLS
urlpatterns += [
    # API base url
    path("api/", api.urls),
]

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
            *urlpatterns,
        ]
