from django.urls import path

from carda_link.users import admin_views
from carda_link.users import views as user_views

urlpatterns = [
    # 1. Main Dashboard
    path("", admin_views.admin_dashboard_view, name="admin_dashboard"),

    # 2. User Management
    path("users/", admin_views.admin_all_users_view, name="admin_all_users"),
    path("users/pending/", admin_views.admin_users_pending_view, name="admin_pending_registrations"),
    path("users/create/", admin_views.admin_user_create_view, name="admin_user_create"),
    path("users/<int:pk>/", admin_views.admin_user_detail_view, name="admin_user_detail"),
    path("users/<int:pk>/approve/", admin_views.admin_user_approve_view, name="admin_user_approve"),
    path("users/<int:pk>/reject/", admin_views.admin_user_reject_view, name="admin_user_reject"),
    path("users/<int:pk>/suspend/", admin_views.admin_user_suspend_view, name="admin_user_suspend"),
    path("users/<int:pk>/reactivate/", admin_views.admin_user_reactivate_view, name="admin_user_reactivate"),

    # 3. Auction Scheduling & Management
    path("auctions/", admin_views.admin_auctions_list_view, name="admin_auctions"),
    path("auctions/create/", admin_views.admin_auction_create_view, name="admin_auction_create"),
    path("auctions/<int:pk>/", admin_views.admin_auction_detail_view, name="admin_auction_detail"),
    path("auctions/<int:pk>/edit/", admin_views.admin_auction_edit_view, name="admin_auction_edit"),
    path("auctions/<int:pk>/cancel/", admin_views.admin_auction_cancel_view, name="admin_auction_cancel"),
    path("auctions/<int:pk>/force-close/", admin_views.admin_auction_force_close_view, name="admin_auction_force_close"),

    # 4. Lot Assignment
    path("auctions/<int:pk>/lots/add/", admin_views.admin_auction_lots_add_view, name="admin_auction_lots_add"),
    path("lots/<int:pk>/remove/", admin_views.admin_lot_remove_view, name="admin_lot_remove"),

    # 5. Grade Verification Queue
    path("batches/ungraded/", admin_views.admin_batches_ungraded_view, name="admin_batches_ungraded"),
    path("batches/<int:pk>/grade/", admin_views.admin_batch_grade_view, name="admin_batch_grade"),
    path("batches/<int:pk>/reject/", admin_views.admin_batch_reject_view, name="admin_batch_reject"),

    # 6. Settlement Oversight & Platform Settings
    path("invoices/", admin_views.admin_invoices_list_view, name="admin_invoices_list"),
    path("invoices/<int:pk>/mark-paid/", admin_views.admin_invoice_mark_paid_view, name="admin_invoice_mark_paid"),
    path("invoices/<int:pk>/mark-failed/", admin_views.admin_invoice_mark_failed_view, name="admin_invoice_mark_failed"),
    path("settings/", admin_views.admin_platform_settings_view, name="admin_platform_settings"),

    # 7. Audit Log
    path("logs/", admin_views.admin_audit_logs_view, name="admin_audit_logs"),

    # 8. Estates Overview
    path("estates/", user_views.admin_estates_view, name="admin_estates"),
    path("estates/<int:pk>/", user_views.admin_estate_detail_view, name="admin_estate_detail"),
]
